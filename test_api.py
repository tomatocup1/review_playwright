import requests
import json

# API 테스트
token = "YOUR_TOKEN_HERE"  # 실제 토큰으로 교체 필요
store_code = "STR_20250607112756_854269"

url = f"http://localhost:8000/api/reviews/{store_code}?limit=20&offset=0"

# 토큰 없이 먼저 시도
response = requests.get(url)
print(f"Status Code: {response.status_code}")
print(f"Headers: {response.headers}")
print(f"Content Type: {response.headers.get('content-type', 'N/A')}")
print(f"Response Text: {response.text[:200]}...")  # 처음 200자만 출력

try:
    json_data = response.json()
    print(f"JSON Data: {json.dumps(json_data, indent=2)}")
except json.JSONDecodeError as e:
    print(f"JSON Decode Error: {e}")
    print(f"Response is not JSON")
