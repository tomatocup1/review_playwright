"""
크롤링 엔드포인트 디버그 테스트
"""
import asyncio
import httpx
import json

async def test_crawl_with_auth():
    """인증된 상태로 크롤링 테스트"""
    
    # 1. 먼저 로그인
    async with httpx.AsyncClient() as client:
        login_response = await client.post(
            "http://localhost:8000/api/auth/login",
            json={
                "email": "test1@example.com",
                "password": "password123"
            }
        )
        
        if login_response.status_code != 200:
            print("Login failed!")
            return
            
        token = login_response.json()["access_token"]
        print(f"Login successful, token obtained")
        
        # 2. 크롤링 테스트
        headers = {"Authorization": f"Bearer {token}"}
        crawl_data = {
            "platform": "baemin",
            "platform_id": "test_id",
            "platform_pw": "test_pw"
        }
        
        print("\nSending crawl request...")
        print(f"Data: {json.dumps(crawl_data, indent=2)}")
        
        try:
            response = await client.post(
                "http://localhost:8000/api/stores/crawl",
                json=crawl_data,
                headers=headers,
                timeout=60.0  # 60초 타임아웃
            )
            
            print(f"\nResponse status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            
            if response.status_code == 500:
                print("\nServer Error Details:")
                print(response.text)
            else:
                print("\nResponse body:")
                print(json.dumps(response.json(), indent=2, ensure_ascii=False))
                
        except httpx.TimeoutException:
            print("Request timed out!")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_crawl_with_auth())
