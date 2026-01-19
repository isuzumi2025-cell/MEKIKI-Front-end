import requests
import sys

try:
    response = requests.get("http://127.0.0.1:8000/api/v1/jobs")
    print(f"Status Code: {response.status_code}")
    if response.status_code != 200:
        print(f"Response: {response.text}")
    else:
        print("Success! Jobs found:", len(response.json()))
except Exception as e:
    print(f"Connection Error: {e}")
