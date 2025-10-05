#!/usr/bin/env python3
"""
Trigger Railway redeploy using GraphQL API
"""
import requests
import json

# IDs
PROJECT_ID = "d9aa9255-34b3-4dc1-8772-3b2d0f35cc55"
SERVICE_ID = "53500724-09c2-411e-b0d1-e451fdfb3fe4"
ENV_ID = "3a3e89e3-4b37-4bc2-93f4-cad3aeb05f84"  # production
API_TOKEN = "75b41108-dfc5-4f12-ae69-67a917511e23"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# Trigger redeploy
mutation = f"""
mutation {{
  deploymentRedeploy(id: "dc32ec31-e264-41e1-98f9-4b9f907b1edf")
}}
"""

print("Triggering redeploy...")
response = requests.post(
    "https://backboard.railway.app/graphql/v2",
    json={"query": mutation},
    headers=headers
)

if response.status_code == 200:
    print("✅ Redeploy triggered successfully!")
    print(response.json())
else:
    print(f"❌ Failed to trigger redeploy: {response.text}")
