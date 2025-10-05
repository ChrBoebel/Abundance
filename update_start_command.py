#!/usr/bin/env python3
"""
Update Railway start command using GraphQL API
"""
import requests
import json

# IDs
SERVICE_ID = "53500724-09c2-411e-b0d1-e451fdfb3fe4"
API_TOKEN = "75b41108-dfc5-4f12-ae69-67a917511e23"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# Update start command to use python -m gunicorn
new_start_command = "python -m gunicorn -k gevent -w 1 --timeout 0 -b 0.0.0.0:$PORT --chdir flask_frontend app:app"

mutation = f"""
mutation {{
  serviceUpdate(
    id: "{SERVICE_ID}"
    input: {{
      startCommand: "{new_start_command}"
    }}
  ) {{
    id
    startCommand
  }}
}}
"""

print(f"Updating start command to: {new_start_command}")
response = requests.post(
    "https://backboard.railway.app/graphql/v2",
    json={"query": mutation},
    headers=headers
)

if response.status_code == 200:
    data = response.json()
    if "errors" in data:
        print(f"❌ GraphQL Error: {data['errors']}")
    else:
        print("✅ Start command updated successfully!")
        print(f"New command: {data['data']['serviceUpdate']['startCommand']}")
else:
    print(f"❌ HTTP Error {response.status_code}: {response.text}")
