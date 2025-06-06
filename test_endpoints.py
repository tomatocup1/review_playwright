"""
서버 엔드포인트 테스트
"""
import requests
import sys
import time

def test_server():
    base_url = "http://localhost:8000"
    
    print("서버 연결 테스트 시작...\n")
    
    # 1. 홈페이지 테스트
    try:
        response = requests.get(base_url)
        print(f"✓ 홈페이지 접속: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("✗ 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
        return
    
    # 2. API 문서 테스트
    try:
        response = requests.get(f"{base_url}/docs")
        print(f"✓ API 문서 접속: {response.status_code}")
    except Exception as e:
        print(f"✗ API 문서 접속 실패: {e}")
    
    # 3. 헬스체크 테스트
    try:
        response = requests.get(f"{base_url}/health")
        print(f"✓ 헬스체크: {response.status_code}")
        if response.status_code == 200:
            print(f"  응답: {response.json()}")
    except Exception as e:
        print(f"✗ 헬스체크 실패: {e}")
    
    # 4. 로그인 페이지 테스트
    try:
        response = requests.get(f"{base_url}/login")
        print(f"✓ 로그인 페이지: {response.status_code}")
    except Exception as e:
        print(f"✗ 로그인 페이지 실패: {e}")

if __name__ == "__main__":
    test_server()
