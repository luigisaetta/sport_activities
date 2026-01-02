"""
garmin_client.py

Wrapper around https://github.com/cyberjunky/python-garminconnect

Features
- Auth reads GARMIN_USER / GARMIN_PWD from config_private.py
- Optional session caching via session.json
- Retrieves activities in a date range (summary list), with pagination
- Optional filtering by activity type
- Structured data model (dataclasses) for activity summaries
- get_activity_details(activity_id) kept as "best effort" enrichment

Design choice
- Summaries are the canonical source for name/type/distance/duration.
- Details are not reliable for those basic fields; treat as optional enrichment.

Rounding
- Numeric fields (distance, duration, etc.) are rounded to 2 decimals.

Important
- Some library versions do not support pagination parameters on get_activities_by_date().
  This module paginates using get_activities(start, limit) and filters locally.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import date, datetime, timezone
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Type,
    TypeVar,
    Union,
    cast,
)
import json

import requests
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from config_private import GARMIN_PWD, GARMIN_USER

DateLike = Union[str, date, datetime]
T = TypeVar("T")


# -----------------------
# Helpers: dates & rounding
# -----------------------


def _to_iso(d: DateLike) -> str:
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    if isinstance(d, str):
        try:
            parsed = datetime.strptime(d, "%Y-%m-%d").date()
            return parsed.isoformat()
        except ValueError as exc:
            raise ValueError(
                f"Invalid date string '{d}'. Expected format YYYY-MM-DD."
            ) from exc
    raise TypeError(f"Unsupported date type: {type(d)}")


def _validate_range(start_date: DateLike, end_date: DateLike) -> tuple[str, str]:
    s = _to_iso(start_date)
    e = _to_iso(end_date)
    if s > e:
        raise ValueError(f"Invalid range: start_date ({s}) is after end_date ({e}).")
    return s, e


def _round2(value: Any) -> Any:
    """Round numeric values to 2 decimals; return as-is otherwise."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    return value


def _get_type_key(activity: Mapping[str, Any]) -> Optional[str]:
    at = activity.get("activityType")
    if isinstance(at, dict):
        v = at.get("typeKey") or at.get("typeName") or at.get("typeId")
        return str(v) if v is not None else None
    if isinstance(at, str):
        return at
    return None


def _normalize_numeric_fields(
    dct: Dict[str, Any], keys: Iterable[str]
) -> Dict[str, Any]:
    """Return a copy of dct with selected numeric keys rounded to 2 decimals."""
    out = dict(dct)
    for k in keys:
        if k in out:
            out[k] = _round2(out.get(k))
    return out


def _parse_activity_date_local(activity: Mapping[str, Any]) -> Optional[date]:
    """
    Extract a local date from a Garmin activity summary.

    Prefer startTimeLocal (string), else try beginTimestamp (ms).
    Returns a date() or None if not available/parsable.
    """
    stl = activity.get("startTimeLocal")
    if isinstance(stl, str):
        # Garmin often: "2025-06-01 07:12:34" (space) or ISO-like.
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(stl[:19], fmt).date()
            except ValueError:
                continue
        # Last resort: try fromisoformat (may include timezone)
        try:
            return datetime.fromisoformat(stl).date()
        except ValueError:
            return None

    ts = activity.get("beginTimestamp")
    if isinstance(ts, (int, float)):
        # Garmin beginTimestamp is usually epoch milliseconds
        try:
            return datetime.fromtimestamp(float(ts) / 1000.0, tz=timezone.utc).date()
        except (OverflowError, OSError, ValueError):
            return None

    return None


# -----------------------
# Auth
# -----------------------


@dataclass(frozen=True)
class GarminAuthConfig:
    """Configuration for authenticating to Garmin Connect and caching a session locally."""

    user: str = GARMIN_USER
    password: str = GARMIN_PWD
    session_file: Optional[Path] = Path("session.json")  # set None to disable


def init_api(auth: Optional[GarminAuthConfig] = None) -> Garmin:
    """
    Initialize and authenticate Garmin API client.

    Tries to reuse session file (if configured) else logs in with user/password.
    """
    auth = auth or GarminAuthConfig()
    api = Garmin(auth.user, auth.password)

    if auth.session_file is not None:
        session_path = Path(auth.session_file)
        if session_path.exists():
            try:
                saved_session = json.loads(session_path.read_text(encoding="utf-8"))
                api.login(saved_session)
                return api
            except (OSError, ValueError, GarminConnectAuthenticationError):
                pass

    try:
        api.login()
    except (
        GarminConnectConnectionError,
        GarminConnectAuthenticationError,
        GarminConnectTooManyRequestsError,
        requests.exceptions.HTTPError,
    ) as err:
        raise RuntimeError(f"Garmin login failed: {err}") from err

    if auth.session_file is not None:
        try:
            session_data = cast(Dict[str, Any], getattr(api, "session_data"))
            Path(auth.session_file).write_text(
                json.dumps(session_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except (OSError, AttributeError, TypeError):
            pass

    return api


# -----------------------
# Pagination (robust across library versions)
# -----------------------


def _fetch_activities_in_range_via_paging(
    api: Garmin,
    start_date_iso: str,
    end_date_iso: str,
    *,
    page_size: int = 50,
    max_pages: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch all activities in the given date range by paging through api.get_activities(start, limit)
    and filtering locally.

    This avoids relying on get_activities_by_date pagination parameters, which differ by
    library version.

    Assumptions (holds for Garmin Connect):
    - get_activities returns activities in reverse chronological order (newest first)
    - once we page into activities older than start_date, we can stop

    Returns:
        List of raw activity dicts, all within [start_date, end_date] (inclusive).
    """
    if page_size <= 0 or page_size > 200:
        raise ValueError("page_size must be between 1 and 200")

    start_d = datetime.strptime(start_date_iso, "%Y-%m-%d").date()
    end_d = datetime.strptime(end_date_iso, "%Y-%m-%d").date()

    collected: List[Dict[str, Any]] = []
    offset = 0
    pages = 0

    while True:
        batch = api.get_activities(offset, page_size)
        batch_list = list(batch) if batch else []

        if not batch_list:
            break

        for act in batch_list:
            act_date = _parse_activity_date_local(act)
            if act_date is None:
                # If date cannot be parsed, keep it (better than losing data),
                # but it won't affect stopping conditions.
                collected.append(act)
                continue

            if act_date > end_d:
                # Too new (e.g. timezone edge), skip
                continue

            if act_date < start_d:
                # We've reached older than the range; we can stop after finishing this loop
                # because batches are ordered newest->oldest.
                return collected

            # In range
            collected.append(act)

        offset += len(batch_list)
        pages += 1
        if max_pages is not None and pages >= max_pages:
            break

        # Defensive stop if the API returns fewer items than requested
        if len(batch_list) < page_size:
            break

    return collected


# -----------------------
# Data model (summaries)
# -----------------------

_NUMERIC_COMMON_KEYS = (
    "distance",
    "duration",
    "elapsedDuration",
    "averageSpeed",
    "maxSpeed",
    "averageHR",
    "maxHR",
    "calories",
    "bmrCalories",
    "elevationGain",
    "elevationLoss",
    "avgPower",
    "activityTrainingLoad",
    "aerobicTrainingEffect",
    "anaerobicTrainingEffect",
)


@dataclass(frozen=True)
class ActivitySummaryBase:  # pylint: disable=too-many-instance-attributes
    """
    Common activity summary fields found across most Garmin activity types.

    Unknown/extra fields are retained in `raw` for troubleshooting and future extension.
    """

    activity_id: int
    type_key: str
    activity_name: Optional[str] = None

    begin_timestamp: Optional[int] = None
    end_time_gmt: Optional[str] = None

    distance: Optional[float] = None
    duration: Optional[float] = None
    elapsed_duration: Optional[float] = None

    average_speed: Optional[float] = None
    max_speed: Optional[float] = None
    average_hr: Optional[float] = None
    max_hr: Optional[float] = None

    calories: Optional[float] = None
    bmr_calories: Optional[float] = None

    elevation_gain: Optional[float] = None
    elevation_loss: Optional[float] = None

    avg_power: Optional[float] = None
    activity_training_load: Optional[float] = None
    aerobic_training_effect: Optional[float] = None
    anaerobic_training_effect: Optional[float] = None

    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        """Stable dict representation (good for MCP)."""
        return asdict(self)

    def to_public_dict(self, *, include_raw: bool = False) -> Dict[str, Any]:
        """
        Return a public, JSON-ready representation of the activity.

        By default, the raw Garmin payload is excluded to keep the output clean
        and suitable for UI, logging, or MCP responses.

        Args:
            include_raw: include the original Garmin payload if True

        Returns:
            dict suitable for JSON serialization
        """
        data = self.to_dict()
        if not include_raw:
            data.pop("raw", None)
        return data

    @classmethod
    def from_summary(cls: Type[T], summary: Mapping[str, Any]) -> T:
        """Parse from a Garmin activity summary dict (defensive)."""
        s = _normalize_numeric_fields(dict(summary), _NUMERIC_COMMON_KEYS)

        activity_id = int(s.get("activityId"))
        type_key = str(_get_type_key(s) or "unknown")

        def g(key: str) -> Any:
            return s.get(key)

        obj = cls(  # type: ignore[misc]
            activity_id=activity_id,
            type_key=type_key,
            activity_name=g("activityName"),
            begin_timestamp=g("beginTimestamp"),
            end_time_gmt=g("endTimeGMT"),
            distance=g("distance"),
            duration=g("duration"),
            elapsed_duration=g("elapsedDuration"),
            average_speed=g("averageSpeed"),
            max_speed=g("maxSpeed"),
            average_hr=g("averageHR"),
            max_hr=g("maxHR"),
            calories=g("calories"),
            bmr_calories=g("bmrCalories"),
            elevation_gain=g("elevationGain"),
            elevation_loss=g("elevationLoss"),
            avg_power=g("avgPower"),
            activity_training_load=g("activityTrainingLoad"),
            aerobic_training_effect=g("aerobicTrainingEffect"),
            anaerobic_training_effect=g("anaerobicTrainingEffect"),
            raw=dict(s),
        )
        return obj


def _base_kwargs_without_raw(base: ActivitySummaryBase) -> Dict[str, Any]:
    """Return kwargs for constructing a subclass from base, excluding the 'raw' field."""
    out: Dict[str, Any] = {}
    for f in fields(ActivitySummaryBase):
        if f.name == "raw":
            continue
        out[f.name] = getattr(base, f.name)
    return out


@dataclass(frozen=True)
class CyclingActivitySummary(ActivitySummaryBase):
    """Typed summary for cycling-like activities (road biking, virtual ride, etc.)."""

    average_biking_cadence_rpm: Optional[float] = None
    end_latitude: Optional[float] = None
    end_longitude: Optional[float] = None
    exclude_from_power_curve_reports: Optional[bool] = None

    @classmethod
    def from_summary(cls, summary: Mapping[str, Any]) -> "CyclingActivitySummary":
        s = _normalize_numeric_fields(
            dict(summary),
            (
                *_NUMERIC_COMMON_KEYS,
                "averageBikingCadenceInRevPerMinute",
                "endLatitude",
                "endLongitude",
            ),
        )
        base = ActivitySummaryBase.from_summary(s)
        return cls(
            **_base_kwargs_without_raw(base),
            average_biking_cadence_rpm=s.get("averageBikingCadenceInRevPerMinute"),
            end_latitude=s.get("endLatitude"),
            end_longitude=s.get("endLongitude"),
            exclude_from_power_curve_reports=s.get("excludeFromPowerCurveReports"),
            raw=dict(s),
        )


@dataclass(frozen=True)
class RunningActivitySummary(ActivitySummaryBase):
    """Typed summary for running activities."""

    average_running_cadence_spm: Optional[float] = None
    avg_grade_adjusted_speed: Optional[float] = None
    avg_ground_contact_time: Optional[float] = None
    avg_stride_length: Optional[float] = None
    avg_vertical_oscillation: Optional[float] = None
    avg_vertical_ratio: Optional[float] = None

    @classmethod
    def from_summary(cls, summary: Mapping[str, Any]) -> "RunningActivitySummary":
        s = _normalize_numeric_fields(
            dict(summary),
            (
                *_NUMERIC_COMMON_KEYS,
                "averageRunningCadenceInStepsPerMinute",
                "avgGradeAdjustedSpeed",
                "avgGroundContactTime",
                "avgStrideLength",
                "avgVerticalOscillation",
                "avgVerticalRatio",
            ),
        )
        base = ActivitySummaryBase.from_summary(s)
        return cls(
            **_base_kwargs_without_raw(base),
            average_running_cadence_spm=s.get("averageRunningCadenceInStepsPerMinute"),
            avg_grade_adjusted_speed=s.get("avgGradeAdjustedSpeed"),
            avg_ground_contact_time=s.get("avgGroundContactTime"),
            avg_stride_length=s.get("avgStrideLength"),
            avg_vertical_oscillation=s.get("avgVerticalOscillation"),
            avg_vertical_ratio=s.get("avgVerticalRatio"),
            raw=dict(s),
        )


@dataclass(frozen=True)
class SwimmingActivitySummary(ActivitySummaryBase):
    """Typed summary for swimming activities (pool and, when supported, open water)."""

    active_lengths: Optional[float] = None
    average_swim_cadence_spm: Optional[float] = None
    average_swolf: Optional[float] = None
    avg_stroke_distance: Optional[float] = None
    avg_strokes: Optional[float] = None
    fastest_split_100: Optional[float] = None

    @classmethod
    def from_summary(cls, summary: Mapping[str, Any]) -> "SwimmingActivitySummary":
        s = _normalize_numeric_fields(
            dict(summary),
            (
                *_NUMERIC_COMMON_KEYS,
                "activeLengths",
                "averageSwimCadenceInStrokesPerMinute",
                "averageSwolf",
                "avgStrokeDistance",
                "avgStrokes",
                "fastestSplit_100",
            ),
        )
        base = ActivitySummaryBase.from_summary(s)
        return cls(
            **_base_kwargs_without_raw(base),
            active_lengths=s.get("activeLengths"),
            average_swim_cadence_spm=s.get("averageSwimCadenceInStrokesPerMinute"),
            average_swolf=s.get("averageSwolf"),
            avg_stroke_distance=s.get("avgStrokeDistance"),
            avg_strokes=s.get("avgStrokes"),
            fastest_split_100=s.get("fastestSplit_100"),
            raw=dict(s),
        )


@dataclass(frozen=True)
class GenericActivitySummary(ActivitySummaryBase):
    """Fallback model for any activity type we haven't specialized yet."""

    @classmethod
    def from_summary(cls, summary: Mapping[str, Any]) -> "GenericActivitySummary":
        return cast(GenericActivitySummary, super().from_summary(summary))


_TYPE_MAP: Dict[str, Type[ActivitySummaryBase]] = {
    "road_biking": CyclingActivitySummary,
    "virtual_ride": CyclingActivitySummary,
    "cycling": CyclingActivitySummary,
    "biking": CyclingActivitySummary,
    "running": RunningActivitySummary,
    "lap_swimming": SwimmingActivitySummary,
    "swimming": SwimmingActivitySummary,
    "open_water_swimming": SwimmingActivitySummary,
}


def parse_activity_summary(summary: Mapping[str, Any]) -> ActivitySummaryBase:
    """Convert a raw Garmin summary dict into a typed ActivitySummary dataclass."""
    type_key = (_get_type_key(summary) or "unknown").strip().lower()
    cls = _TYPE_MAP.get(type_key, GenericActivitySummary)
    return cls.from_summary(summary)


# -----------------------
# Public functions
# -----------------------


def get_activities_in_range(
    start_date: DateLike,
    end_date: DateLike,
    activity_type: Optional[Union[str, Iterable[str]]] = None,
    *,
    auth: Optional[GarminAuthConfig] = None,
    page_size: int = 50,
    max_pages: Optional[int] = None,
) -> List[ActivitySummaryBase]:
    """
    Fetch activity summaries between start_date and end_date (inclusive) and return typed models.

    This uses robust pagination via api.get_activities(offset, limit) and filters locally.
    """
    s, e = _validate_range(start_date, end_date)
    api = init_api(auth)

    raw = _fetch_activities_in_range_via_paging(
        api,
        s,
        e,
        page_size=page_size,
        max_pages=max_pages,
    )

    if activity_type is not None:
        allowed = (
            {t.strip().lower() for t in set(activity_type)}
            if not isinstance(activity_type, str)
            else {activity_type.strip().lower()}
        )
        raw = _filter_activities_by_type(raw, allowed)

    return [parse_activity_summary(a) for a in raw]


def get_activity_details(
    activity_id: Union[int, str],
    *,
    auth: Optional[GarminAuthConfig] = None,
) -> Dict[str, Any]:
    """
    Best-effort fetch full details for a single activity.

    WARNING: Garmin often returns stub/partial payloads for details.
    """
    api = init_api(auth)
    try:
        details = api.get_activity_details(str(activity_id))
    except (
        GarminConnectConnectionError,
        GarminConnectAuthenticationError,
        GarminConnectTooManyRequestsError,
        requests.exceptions.HTTPError,
    ) as err:
        raise RuntimeError(
            f"Failed to fetch activity details for {activity_id}: {err}"
        ) from err

    if not isinstance(details, dict):
        return {"activityId": activity_id, "raw": details}

    details2 = _normalize_numeric_fields(
        details, ("distance", "duration", "elapsedDuration", "movingDuration")
    )
    for key in ("summaryDTO", "summary", "summaryDto"):
        if isinstance(details2.get(key), dict):
            details2[key] = _normalize_numeric_fields(
                cast(Dict[str, Any], details2[key]),
                ("distance", "duration", "elapsedDuration", "movingDuration"),
            )
    return details2


def _filter_activities_by_type(
    activities: Iterable[Dict[str, Any]],
    allowed_types: Union[set[str], Iterable[str]],
) -> List[Dict[str, Any]]:
    """Filter raw Garmin activities by activityType.typeKey (case-insensitive)."""
    allowed = {t.strip().lower() for t in set(allowed_types)}
    out: List[Dict[str, Any]] = []
    for a in activities:
        key = (_get_type_key(a) or "").strip().lower()
        if key in allowed:
            out.append(a)
    return out
