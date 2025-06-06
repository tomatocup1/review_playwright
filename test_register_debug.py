"""
회원가입 디버깅 테스트
"""
import requests
import json

def test_register_debug():
    """회원가입 상세 디버깅"""
    url = "http://localhost:8000/api/auth/register"
    
    # 다양한 테스트 케이스
    test_cases = [
        {
            "name": "정상 케이스",
            "data": {
                "email": "test@example.com",
                "password": "password123",
                "name": "테스트사용자",
                "phone": "010-1234-5678",
                "role": "owner",
                "company_name": "테스트회사",
                "marketing_consent": False
            }
        },
        {
            "name": "전화번호 없이",
            "data": {
                "email": "test2@example.com",
                "password": "password123",
                "name": "테스트사용자2",
                "role": "owner",
                "marketing_consent": False
            }
        },
        {
            "name": "잘못된 전화번호 형식",
            "data": {
                "email": "test3@example.com",
                "password": "password123",
                "name": "테스트사용자3",
                "phone": "01012345678",  # 하이픈 없음
                "role": "owner",
                "marketing_consent": False
            }
        }
    ]
    
    for test in test_cases:
        print(f"\n테스트: {test['name']}")
        print(f"데이터: {json.dumps(test['data'], ensure_ascii=False, indent=2)}")
        
        try:
            response = requests.post(url, json=test['data'])
            print(f"상태 코드: {response.status_code}")
            
            if response.status_code == 422:
                print("유효성 검사 오류:")
                error_data = response.json()
                print(json.dumps(error_data, ensure_ascii=False, indent=2))
            elif response.status_code == 201:
                print("성공!")
            else:
                print(f"응답: {response.text}")
                
        except Exception as e:
            print(f"오류: {e}")

if __name__ == "__main__":
    test_register_debug()
