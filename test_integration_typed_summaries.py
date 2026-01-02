"""
Test integration: fetch activities in a date range and print typed summaries.
"""

from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime, timezone

from garmin_client import get_activities_in_range


def main() -> int:
    """
    Test integration: fetch activities in a date range and print typed summaries.
    1) Usage: python test_integration_typed_summaries.py <start YYYY-MM-DD> <end YYYY-MM-DD>
    2) Fetch activities in the given range
    3) Print the number of activities and their type distribution
    4) Print a summary line for each activity with type, id, name, date, distance, duration
    5) Return 0 on success
    """

    if len(sys.argv) != 3:
        print(
            "Usage: python test_integration_typed_summaries.py <start YYYY-MM-DD> <end YYYY-MM-DD>"
        )
        return 2

    start, end = sys.argv[1], sys.argv[2]
    acts = get_activities_in_range(start, end)

    print("Activities returned:", len(acts))
    c = Counter(a.type_key for a in acts)
    print("Type distribution:", dict(c))
    print("")

    # Print
    for a in acts:
        try:
            # to handle problems with invalid timestamps
            dt = str(datetime.fromtimestamp(a.begin_timestamp / 1000, tz=timezone.utc))

        except Exception:
            dt = "NA"

        print(a.type_key, a.activity_id, a.activity_name, dt, a.distance, a.duration)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
