#!/usr/bin/env python3
"""
Get Railway deployment logs using GraphQL API
"""
import requests
import json

# IDs from deployment
PROJECT_ID = "d9aa9255-34b3-4dc1-8772-3b2d0f35cc55"
SERVICE_ID = "53500724-09c2-411e-b0d1-e451fdfb3fe4"
ENV_ID = "3a3e89e3-4b37-4bc2-93f4-cad3aeb05f84"  # production
API_TOKEN = "75b41108-dfc5-4f12-ae69-67a917511e23"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# Get latest deployment
query = f"""
query {{
  deployments(
    input: {{
      projectId: "{PROJECT_ID}"
      serviceId: "{SERVICE_ID}"
      environmentId: "{ENV_ID}"
    }}
  ) {{
    edges {{
      node {{
        id
        status
        createdAt
        staticUrl
      }}
    }}
  }}
}}
"""

print("Getting deployments...")
response = requests.post(
    "https://backboard.railway.app/graphql/v2",
    json={"query": query},
    headers=headers
)

if response.status_code == 200:
    data = response.json()
    deployments = data.get("data", {}).get("deployments", {}).get("edges", [])

    if deployments:
        latest = deployments[0]["node"]
        deployment_id = latest["id"]
        status = latest["status"]
        url = latest.get("staticUrl", "N/A")

        print(f"\nLatest Deployment:")
        print(f"  ID: {deployment_id}")
        print(f"  Status: {status}")
        print(f"  URL: {url}")

        # Get logs
        print(f"\nGetting logs for deployment {deployment_id}...")

        logs_query = f"""
        query {{
          deploymentLogs(deploymentId: "{deployment_id}") {{
            logs
          }}
        }}
        """

        logs_response = requests.post(
            "https://backboard.railway.app/graphql/v2",
            json={"query": logs_query},
            headers=headers
        )

        if logs_response.status_code == 200:
            logs_data = logs_response.json()
            logs = logs_data.get("data", {}).get("deploymentLogs", {}).get("logs", "")

            if logs:
                print("\n" + "="*80)
                print("DEPLOYMENT LOGS:")
                print("="*80)
                print(logs)
            else:
                print("No logs available")
        else:
            print(f"Failed to get logs: {logs_response.text}")
    else:
        print("No deployments found")
else:
    print(f"Error: {response.text}")
