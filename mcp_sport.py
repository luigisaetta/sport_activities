"""
File name: mcp_sport.py
Author: Luigi Saetta
Date last modified: 2026-01-05
Python Version: 3.11

Description:
    MCP (Model Context Protocol) server for sport data analysis using Garmin Connect data.
    It exposes tools that allow an LLM assistant to:
      - Fetch activity summaries in a date range (optionally filtered by type)
      - Fetch best-effort activity details
      - Aggregate metrics by day and by activity type
      - Produce a basic data-quality report

Security:
    Uses shared MCP utilities in mcp_utils.py.
    If ENABLE_JWT_TOKEN=True in config.py, requests must include a valid JWT token
    verifiable via OCI IAM JWKS.

Transport:
    Uses TRANSPORT from config.py, recommended "streamable-http" for HTTP streaming.

Dependencies:
    - fastmcp (your existing dependency)
    - python-garminconnect (cyberjunky/python-garminconnect)
    - requests
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Union
from datetime import datetime
import logging

from mcp_utils import create_server, run_server

from garmin_client import (
    ActivitySummaryBase,
    get_activities_in_range,
    get_activity_details,
)

logger = logging.getLogger("mcp_sport")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

mcp = create_server("Sport MCP")


# -----------------------
# Helper utilities
# -----------------------


def _safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _sum_opt(values: Iterable[Optional[float]]) -> float:
    return float(sum(v for v in values if isinstance(v, (int, float))))


def _iso_day_from_begin_ts(begin_timestamp_ms: Optional[int]) -> Optional[str]:
    if not begin_timestamp_ms:
        return None
    try:
        dt = datetime.utcfromtimestamp(begin_timestamp_ms / 1000.0)
        return dt.date().isoformat()
    except (OSError, ValueError, OverflowError):
        return None


def _normalize_types(
    activity_type: Optional[Union[str, List[str]]],
) -> Optional[List[str]]:
    if activity_type is None:
        return None
    if isinstance(activity_type, str):
        return [activity_type]
    return list(activity_type)


# -----------------------
# MCP tools
# -----------------------


@mcp.tool()
def sport_get_activities(
    start_date: str,
    end_date: str,
    activity_type: Optional[Union[str, List[str]]] = None,
    include_raw: bool = False,
    page_size: int = 50,
    max_pages: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Fetch Garmin activity summaries between start_date and end_date (inclusive).

    Args:
        start_date: "YYYY-MM-DD"
        end_date: "YYYY-MM-DD"
        activity_type:
            Optional activity type(s) to filter, by Garmin typeKey
            Examples: "running" or ["running", "virtual_ride"]
        include_raw:
            If True, include the original Garmin raw payload per activity.
        page_size:
            Garmin paging size used by garmin_client.get_activities_in_range()
        max_pages:
            Optional safety cap to limit calls for very large histories.

    Returns:
        {
          "count": int,
          "activities": [ { ... } ]
        }
    """
    types = _normalize_types(activity_type)
    logger.info(
        "sport_get_activities called start=%r end=%r types=%r include_raw=%r page_size=%r max_pages=%r",
        start_date,
        end_date,
        types,
        include_raw,
        page_size,
        max_pages,
    )

    try:
        acts: List[ActivitySummaryBase] = get_activities_in_range(
            start_date,
            end_date,
            activity_type=types,
            page_size=page_size,
            max_pages=max_pages,
        )
        payload = [a.to_public_dict(include_raw=include_raw) for a in acts]
        return {"count": len(payload), "activities": payload}
    except Exception as e:  # noqa: BLE001
        logger.error("Error in sport_get_activities: %r", e)
        raise RuntimeError(f"Error fetching activities: {e}") from e


@mcp.tool()
def sport_get_activity_details(activity_id: Union[int, str]) -> Dict[str, Any]:
    """
    Best-effort fetch full details for a single activity.

    Note:
        Garmin details may be incomplete/partial; treat as optional enrichment.

    Returns:
        {"activity_id": <id>, "details": <dict>}
    """
    logger.info("sport_get_activity_details called activity_id=%r", activity_id)
    try:
        details = get_activity_details(activity_id)
        return {"activity_id": int(activity_id), "details": details}
    except Exception as e:  # noqa: BLE001
        logger.error("Error in sport_get_activity_details: %r", e)
        raise RuntimeError(f"Error fetching activity details: {e}") from e


@mcp.tool()
def sport_aggregate_by_day(
    start_date: str,
    end_date: str,
    activity_type: Optional[Union[str, List[str]]] = None,
) -> Dict[str, Any]:
    """
    Aggregate activities by day with totals for distance, duration, calories, training load.

    Returns:
        {
          "days": [
            {
              "date": "YYYY-MM-DD" | "unknown",
              "count": int,
              "distance": float,
              "duration": float,
              "calories": float,
              "activity_training_load": float
            }, ...
          ],
          "totals": { ... }
        }
    """
    types = _normalize_types(activity_type)
    logger.info(
        "sport_aggregate_by_day called start=%r end=%r types=%r",
        start_date,
        end_date,
        types,
    )

    try:
        acts = get_activities_in_range(start_date, end_date, activity_type=types)

        by_day: Dict[str, List[ActivitySummaryBase]] = {}
        for a in acts:
            day = _iso_day_from_begin_ts(a.begin_timestamp) or "unknown"
            by_day.setdefault(day, []).append(a)

        days_out: List[Dict[str, Any]] = []
        for day in sorted(by_day.keys()):
            items = by_day[day]
            days_out.append(
                {
                    "date": day,
                    "count": len(items),
                    "distance": _sum_opt(_safe_float(x.distance) for x in items),
                    "duration": _sum_opt(_safe_float(x.duration) for x in items),
                    "calories": _sum_opt(_safe_float(x.calories) for x in items),
                    "activity_training_load": _sum_opt(
                        _safe_float(x.activity_training_load) for x in items
                    ),
                }
            )

        totals = {
            "count": sum(d["count"] for d in days_out),
            "distance": sum(d["distance"] for d in days_out),
            "duration": sum(d["duration"] for d in days_out),
            "calories": sum(d["calories"] for d in days_out),
            "activity_training_load": sum(
                d["activity_training_load"] for d in days_out
            ),
        }

        return {"days": days_out, "totals": totals}
    except Exception as e:  # noqa: BLE001
        logger.error("Error in sport_aggregate_by_day: %r", e)
        raise RuntimeError(f"Error aggregating activities by day: {e}") from e


@mcp.tool()
def sport_aggregate_by_type(start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Aggregate activities by type_key.

    Returns:
        {
          "types": [
            {"type_key": str, "count": int, "distance": float, "duration": float, "training_load": float},
            ...
          ]
        }
    """
    logger.info("sport_aggregate_by_type called start=%r end=%r", start_date, end_date)

    try:
        acts = get_activities_in_range(start_date, end_date)

        by_type: Dict[str, List[ActivitySummaryBase]] = {}
        for a in acts:
            key = (a.type_key or "unknown").strip().lower()
            by_type.setdefault(key, []).append(a)

        out: List[Dict[str, Any]] = []
        for key in sorted(by_type.keys()):
            items = by_type[key]
            out.append(
                {
                    "type_key": key,
                    "count": len(items),
                    "distance": _sum_opt(_safe_float(x.distance) for x in items),
                    "duration": _sum_opt(_safe_float(x.duration) for x in items),
                    "training_load": _sum_opt(
                        _safe_float(x.activity_training_load) for x in items
                    ),
                }
            )
        return {"types": out}
    except Exception as e:  # noqa: BLE001
        logger.error("Error in sport_aggregate_by_type: %r", e)
        raise RuntimeError(f"Error aggregating activities by type: {e}") from e


@mcp.tool()
def sport_data_quality_report(
    start_date: str,
    end_date: str,
    activity_type: Optional[Union[str, List[str]]] = None,
) -> Dict[str, Any]:
    """
    Quick data-quality scan:
      - missing distance/duration
      - unknown day (missing begin_timestamp)
      - zero distance with non-zero duration (suspicious)

    Returns:
        {"summary": {...}, "issues": [...]}
    """
    types = _normalize_types(activity_type)
    logger.info(
        "sport_data_quality_report called start=%r end=%r types=%r",
        start_date,
        end_date,
        types,
    )

    try:
        acts = get_activities_in_range(start_date, end_date, activity_type=types)

        issues: List[Dict[str, Any]] = []
        missing_distance = 0
        missing_duration = 0
        unknown_day = 0

        for a in acts:
            if _iso_day_from_begin_ts(a.begin_timestamp) is None:
                unknown_day += 1

            if a.distance is None:
                missing_distance += 1
                issues.append(
                    {"activity_id": a.activity_id, "issue": "missing_distance"}
                )
            if a.duration is None:
                missing_duration += 1
                issues.append(
                    {"activity_id": a.activity_id, "issue": "missing_duration"}
                )

            dist = _safe_float(a.distance)
            dur = _safe_float(a.duration)
            if dist is not None and dur is not None and dist == 0.0 and dur > 0.0:
                issues.append(
                    {
                        "activity_id": a.activity_id,
                        "issue": "zero_distance_nonzero_duration",
                    }
                )

        summary = {
            "count": len(acts),
            "missing_distance": missing_distance,
            "missing_duration": missing_duration,
            "unknown_day": unknown_day,
            "issues_count": len(issues),
        }
        return {"summary": summary, "issues": issues}
    except Exception as e:  # noqa: BLE001
        logger.error("Error in sport_data_quality_report: %r", e)
        raise RuntimeError(f"Error producing data-quality report: {e}") from e


# -----------------------
# Main
# -----------------------

if __name__ == "__main__":
    # Normal MCP start (respects config.TRANSPORT and supports streamable-http)
    run_server(mcp)
