"""
매장 API 테스트 스크립트
"""
import asyncio
import httpx
import json
from datetime import datetime

# 테스트용 사용자 정보 (test_register.py에서 생성한 계정)
TEST_USER = {
    "email": "test1@example.com",
    "password": "password123"
}

# API 베이스 URL
BASE_URL = "http://localhost:8000"

async def login():
    """로그인하여 토큰 획득"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": TEST_USER["email"],
                "password": TEST_USER["password"]
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print("[OK] Login successful")
            return data["access_token"]
        else:
            print(f"[ERROR] Login failed: {response.status_code}")
            print(response.text)
            return None

async def test_crawl_stores(token: str):
    """매장 크롤링 테스트"""
    headers = {"Authorization": f"Bearer {token}"}
    
    # 테스트용 배민 계정 정보 (실제 계정으로 교체 필요)
    test_data = {
        "platform": "baemin",
        "platform_id": "test_id",
        "platform_pw": "test_pw"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/stores/crawl",
            json=test_data,
            headers=headers,
            timeout=30.0  # 크롤링은 시간이 걸릴 수 있으므로 타임아웃 증가
        )
        
        print(f"\n=== Store Crawl Test ===")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"[OK] Crawl successful")
            print(f"Platform: {data.get('platform')}")
            print(f"Store Count: {data.get('count')}")
            if data.get('stores'):
                for store in data['stores'][:3]:  # 처음 3개만 출력
                    print(f"  - {store['store_name']} ({store['platform_code']})")
        else:
            print(f"[ERROR] Crawl failed")
            print(response.text)

async def test_register_store(token: str):
    """매장 등록 테스트"""
    headers = {"Authorization": f"Bearer {token}"}
    
    # 테스트용 매장 등록 데이터
    test_data = {
        "platform": "baemin",
        "platform_id": "test_id",
        "platform_pw": "test_pw",
        "platform_code": "test_store_001",
        "store_name": "Test Store",
        "greeting_start": "안녕하세요",
        "greeting_end": "감사합니다",
        "role": "친절한 사장님",
        "tone": "친근한",
        "max_length": 300,
        "rating_5_reply": True,
        "rating_4_reply": True,
        "rating_3_reply": True,
        "rating_2_reply": True,
        "rating_1_reply": True,
        "auto_reply_enabled": True,
        "auto_reply_hours": "10:00-20:00",
        "reply_delay_minutes": 30,
        "weekend_enabled": True,
        "holiday_enabled": False
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/stores/register",
            json=test_data,
            headers=headers
        )
        
        print(f"\n=== Store Register Test ===")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"[OK] Register Success: {data.get('success')}")
            print(f"Message: {data.get('message')}")
            if data.get('store_code'):
                print(f"Store Code: {data.get('store_code')}")
        else:
            print(f"[ERROR] Register failed")
            print(response.text)

async def test_list_stores(token: str):
    """매장 목록 조회 테스트"""
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/stores",
            headers=headers
        )
        
        print(f"\n=== Store List Test ===")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"[OK] List successful")
            print(f"Total Stores: {data.get('total')}")
            print(f"Current Page: {data.get('page')}")
            if data.get('stores'):
                for store in data['stores']:
                    print(f"  - {store['store_name']} ({store['platform']}) - {store['store_code']}")
        else:
            print(f"[ERROR] List failed")
            print(response.text)

async def main():
    """메인 테스트 함수"""
    print("=== Store API Test Start ===")
    print(f"Time: {datetime.now()}")
    
    # 1. 로그인
    token = await login()
    if not token:
        print("Test stopped due to login failure")
        return
    
    # 2. 매장 목록 조회
    await test_list_stores(token)
    
    # 3. 매장 크롤링 테스트 (실제 계정이 있을 때만)
    # await test_crawl_stores(token)
    
    # 4. 매장 등록 테스트
    await test_register_store(token)
    
    # 5. 다시 매장 목록 조회
    await test_list_stores(token)
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(main())
