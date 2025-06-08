import requests

try:
    # API 엔드포인트 테스트
    url = "http://localhost:8000/api/stores/crawl/baemin/test_id/test_pw"
    response = requests.get(url)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
