"""
Show month activities as JSON payload.
"""

import json
from garmin_client import get_activities_in_range

activities = get_activities_in_range(
    "2025-06-01", "2025-06-30", activity_type="road_biking"
)

# eventually limit to certain activity types
payload = [a.to_public_dict() for a in activities]

print(json.dumps(payload, indent=2, ensure_ascii=False))
