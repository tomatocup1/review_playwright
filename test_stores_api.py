"""
매장 목록 API 테스트
"""
import requests
import json

# API 엔드포인트
BASE_URL = "http://localhost:8000"
API_URL = f"{BASE_URL}/api/stores"

# 테스트용 토큰 (실제 로그인 후 받은 토큰으로 교체 필요)
# 브라우저 개발자 도구에서 localStorage의 access_token 값을 복사해서 사용
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0QHRlc3QuY29tIiwidXNlcl9jb2RlIjoiVVNSMzM0MTc4IiwiZXhwIjoxNzQ5MzQ5NjE5fQ.2_HLKEGESaPmsCY_g9CoTDPXQXo3RwTIIFIPAFvt4Gk"

# 헤더 설정
headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

def test_get_stores():
    """매장 목록 조회 테스트"""
    try:
        response = requests.get(API_URL, headers=headers)
        print(f"상태 코드: {response.status_code}")
        print(f"응답 헤더: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n응답 데이터:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            if 'stores' in data:
                print(f"\n총 매장 수: {data.get('total', 0)}")
                print(f"현재 페이지 매장 수: {len(data['stores'])}")
                
                for store in data['stores']:
                    print(f"\n매장: {store['store_name']} ({store['platform']})")
                    print(f"  - 코드: {store['store_code']}")
                    print(f"  - 플랫폼 코드: {store['platform_code']}")
                    print(f"  - 자동답글: {store['auto_reply_enabled']}")
                    print(f"  - 상태: {store['is_active']}")
        else:
            print(f"\n오류 응답:")
            print(response.text)
            
    except Exception as e:
        print(f"요청 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    print("=== 매장 목록 API 테스트 ===")
    print(f"API URL: {API_URL}")
    print("\n주의: ACCESS_TOKEN을 실제 토큰으로 교체해주세요!")
    print("브라우저 개발자 도구 > Application > Local Storage > access_token 값 복사\n")
    
    if ACCESS_TOKEN == "여기에_실제_토큰_붙여넣기":
        print("❌ 토큰을 설정하지 않았습니다. 스크립트를 수정해주세요.")
    else:
        test_get_stores()
