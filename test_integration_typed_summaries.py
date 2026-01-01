#!/usr/bin/env python3
from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime, timezone

from garmin_client import get_activities_in_range


def main() -> int:
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
            dt = str(datetime.fromtimestamp(a.begin_timestamp / 1000, tz=timezone.utc))

        except Exception as e:
            dt = "NA"
            print(f"[ERROR] Could not print correctly activity {a.activity_id}: {e}")

        print(a.type_key, a.activity_id, a.activity_name, dt, a.distance, a.duration)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
