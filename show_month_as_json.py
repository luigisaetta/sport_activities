import json
from garmin_client import get_activities_in_range

activities = get_activities_in_range("2025-06-01", "2025-06-30")

# limit to 3 actsivities for brevity
payload = [a.to_dict() for a in activities[:3]]

print(json.dumps(payload, indent=2, ensure_ascii=False))
