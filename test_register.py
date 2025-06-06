"""
회원가입 API 테스트
"""
import requests
import json
import random
import string

def generate_random_email():
    """랜덤 이메일 생성"""
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"test_{random_str}@example.com"

def test_register():
    """회원가입 테스트"""
    url = "http://localhost:8000/api/auth/register"
    
    # 테스트 데이터
    test_data = {
        "email": generate_random_email(),
        "password": "testpassword123",
        "name": "테스트사용자",
        "phone": "010-1234-5678",
        "role": "owner",
        "company_name": "테스트회사",
        "marketing_consent": False
    }
    
    print("회원가입 테스트 시작...")
    print(f"요청 URL: {url}")
    print(f"요청 데이터: {json.dumps(test_data, ensure_ascii=False, indent=2)}")
    
    try:
        response = requests.post(url, json=test_data)
        
        print(f"\n응답 상태 코드: {response.status_code}")
        
        if response.status_code == 201:
            print("✓ 회원가입 성공!")
            print(f"응답 데이터: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
        else:
            print("✗ 회원가입 실패!")
            print(f"에러 응답: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("✗ 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
    except Exception as e:
        print(f"✗ 테스트 중 오류 발생: {e}")

def test_duplicate_email():
    """중복 이메일 테스트"""
    url = "http://localhost:8000/api/auth/register"
    
    # 동일한 이메일로 두 번 가입 시도
    email = "duplicate@example.com"
    test_data = {
        "email": email,
        "password": "testpassword123",
        "name": "중복테스트",
        "phone": "010-9999-9999",
        "role": "owner",
        "marketing_consent": False
    }
    
    print("\n\n중복 이메일 테스트 시작...")
    
    try:
        # 첫 번째 가입 시도
        response1 = requests.post(url, json=test_data)
        print(f"첫 번째 가입 시도: {response1.status_code}")
        
        # 두 번째 가입 시도 (중복)
        response2 = requests.post(url, json=test_data)
        print(f"두 번째 가입 시도: {response2.status_code}")
        
        if response2.status_code == 400:
            print("✓ 중복 이메일 방지 기능 정상 작동!")
            print(f"에러 메시지: {response2.json().get('detail')}")
        else:
            print("✗ 중복 이메일 방지 기능 오류!")
            
    except Exception as e:
        print(f"✗ 테스트 중 오류 발생: {e}")

if __name__ == "__main__":
    test_register()
    test_duplicate_email()
