"""
Show month activities as JSON payload.
"""

import json
from garmin_client import get_activities_in_range

activities = get_activities_in_range("2026-01-01", "2026-01-02")

for a in activities:
    payload = a.to_public_dict()
    print(json.dumps(payload, indent=2, ensure_ascii=False))
