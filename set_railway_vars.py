#!/usr/bin/env python3
"""
Set Railway environment variables using GraphQL API
"""
import requests
import json
import sys

# IDs from railway up output
PROJECT_ID = "d9aa9255-34b3-4dc1-8772-3b2d0f35cc55"
SERVICE_ID = "53500724-09c2-411e-b0d1-e451fdfb3fe4"

# API Token from Railway
API_TOKEN = "75b41108-dfc5-4f12-ae69-67a917511e23"

# Get environment ID first
query_env = """
query {
  project(id: "d9aa9255-34b3-4dc1-8772-3b2d0f35cc55") {
    environments {
      edges {
        node {
          id
          name
        }
      }
    }
  }
}
"""

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# Get environment ID
response = requests.post(
    "https://backboard.railway.app/graphql/v2",
    json={"query": query_env},
    headers=headers
)

if response.status_code != 200:
    print(f"Error getting environment: {response.text}")
    sys.exit(1)

data = response.json()
environments = data.get("data", {}).get("project", {}).get("environments", {}).get("edges", [])

# Find production environment
env_id = None
for env in environments:
    if env["node"]["name"] == "production":
        env_id = env["node"]["id"]
        break

if not env_id:
    print("Production environment not found!")
    sys.exit(1)

print(f"Found production environment: {env_id}")

# Variables to set
variables = {
    "GEMINI_API_KEY": "AIzaSyCQANQ-oRtHnGOD7AFTySZLxvveqI0tpIA",
    "GOOGLE_API_KEY": "AIzaSyCQANQ-oRtHnGOD7AFTySZLxvveqI0tpIA",
    "TAVILY_API_KEY": "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",
    "SECRET_KEY": "dev-secret-change-in-production",
    "APP_PASSWORD": "Aalen"
}

# Set each variable
for name, value in variables.items():
    mutation = f"""
    mutation {{
      variableUpsert(
        input: {{
          projectId: "{PROJECT_ID}"
          environmentId: "{env_id}"
          serviceId: "{SERVICE_ID}"
          name: "{name}"
          value: "{value}"
        }}
      )
    }}
    """

    response = requests.post(
        "https://backboard.railway.app/graphql/v2",
        json={"query": mutation},
        headers=headers
    )

    if response.status_code == 200:
        print(f"✅ Set {name}")
    else:
        print(f"❌ Failed to set {name}: {response.text}")

print("\n🎉 All environment variables set! The deployment will restart automatically.")
print("Check your app at: https://bountiful-creativity-production-7649.up.railway.app")
