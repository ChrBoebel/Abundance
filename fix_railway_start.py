#!/usr/bin/env python3
"""
Fix Railway start command - use /app/.venv/bin/gunicorn
"""
import requests
import json

SERVICE_ID = "53500724-09c2-411e-b0d1-e451fdfb3fe4"
API_TOKEN = "75b41108-dfc5-4f12-ae69-67a917511e23"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# Railway installs packages in /app/.venv/bin/
# So we use the absolute path to gunicorn
new_start_command = "/app/.venv/bin/gunicorn -k gevent -w 1 --timeout 0 -b 0.0.0.0:$PORT --chdir flask_frontend app:app"

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

print(f"Setting start command to: {new_start_command}")
response = requests.post(
    "https://backboard.railway.app/graphql/v2",
    json={"query": mutation},
    headers=headers
)

if response.status_code == 200:
    data = response.json()
    if "errors" in data:
        print(f"❌ Error: {data['errors']}")
    else:
        print("✅ Start command updated!")
        print("Now triggering redeploy...")

        # Trigger redeploy by updating a dummy variable
        redeploy_mutation = f"""
        mutation {{
          serviceUpdate(
            id: "{SERVICE_ID}"
            input: {{
              name: "bountiful-creativity"
            }}
          ) {{
            id
          }}
        }}
        """

        redeploy_response = requests.post(
            "https://backboard.railway.app/graphql/v2",
            json={"query": redeploy_mutation},
            headers=headers
        )

        if redeploy_response.status_code == 200:
            print("✅ Redeploy triggered!")
        else:
            print(f"⚠️  Redeploy failed: {redeploy_response.text}")
else:
    print(f"❌ Failed: {response.text}")
