"""
테스트 계정 생성 스크립트
"""
import requests
import json

def create_test_account():
    """테스트용 계정 생성"""
    url = "http://localhost:8000/api/auth/register"
    
    # 테스트 계정 정보
    test_data = {
        "email": "test1@example.com",
        "password": "password123",
        "name": "Test User 1",
        "phone": "010-1111-1111",
        "role": "owner",
        "company_name": "Test Company",
        "marketing_consent": False
    }
    
    print("Creating test account...")
    print(f"Email: {test_data['email']}")
    
    try:
        response = requests.post(url, json=test_data)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 201:
            print("Success! Test account created.")
            print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
        elif response.status_code == 400:
            print("Account already exists or validation error.")
            print(f"Error: {response.text}")
        else:
            print("Failed to create account.")
            print(f"Error: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("Cannot connect to server. Make sure the server is running.")
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    create_test_account()
