import csv

from garmin_client import get_activities_in_range

RUNNING_FEATURES = [
    "activity_id",
    "end_time_gmt",
    "duration",
    "elapsed_duration",
    "distance",
    "average_hr",
    "max_hr",
    "average_speed",
    "max_speed",
    "avg_power",
    "average_running_cadence_spm",
    "avg_stride_length",
    "aerobic_training_effect",
    "anaerobic_training_effect",
]


def export_running_activities_to_csv(
    activities: list[dict], output_csv: str = "running_activities.csv"
):
    """
    Filter running activities and export selected features to CSV.
    One row per activity.
    """

    running_activities = [a for a in activities if a.get("type_key") == "running"]

    if not running_activities:
        raise ValueError("No running activities found")

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RUNNING_FEATURES, extrasaction="ignore")
        writer.writeheader()

        for a in running_activities:
            row = {k: a.get(k) for k in RUNNING_FEATURES}
            writer.writerow(row)

    print(f"Exported {len(running_activities)} running activities to {output_csv}")


if __name__ == "__main__":
    # here we specify the range of activities to fetch
    # for now only 2025 activities
    activities = get_activities_in_range("2025-01-01", "2026-01-01")

    activities = [a.to_public_dict() for a in activities]

    export_running_activities_to_csv(activities)
