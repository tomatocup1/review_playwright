import requests
import json

# 로그인하여 토큰 받기
login_url = "http://localhost:8000/api/auth/login"
login_data = {
    "email": "test.owner@example.com",  # email 필드로 변경
    "password": "test_hash_here"  # 테스트 비밀번호
}

# 로그인 시도
print("로그인 시도 중...")
try:
    # JSON 형식으로 전송
    response = requests.post(login_url, json=login_data)
    print(f"로그인 응답 상태: {response.status_code}")
    print(f"로그인 응답: {response.text}")
    
    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token")
        print(f"토큰 획득: {token[:20]}...")
        
        # 리뷰 조회
        store_code = "STR_20250607112756_854269"
        reviews_url = f"http://localhost:8000/api/reviews/{store_code}?limit=20&offset=0"
        headers = {"Authorization": f"Bearer {token}"}
        
        print(f"\n리뷰 조회 중: {reviews_url}")
        review_response = requests.get(reviews_url, headers=headers)
        print(f"리뷰 조회 상태: {review_response.status_code}")
        print(f"응답 Content-Type: {review_response.headers.get('content-type')}")
        print(f"응답 길이: {len(review_response.text)}")
        
        # 상태 코드가 500이면 에러 응답 확인
        if review_response.status_code == 500:
            print(f"서버 에러 응답: {review_response.text}")
        elif review_response.text:
            try:
                data = review_response.json()
                print(f"리뷰 데이터: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}...")
            except json.JSONDecodeError as e:
                print(f"JSON 파싱 오류: {e}")
                print(f"응답 텍스트: {review_response.text[:200]}...")
        else:
            print("빈 응답")
        
except requests.exceptions.ConnectionError:
    print("서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
except Exception as e:
    print(f"오류 발생: {type(e).__name__}: {e}")
