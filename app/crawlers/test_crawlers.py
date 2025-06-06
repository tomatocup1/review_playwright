"""
크롤러 테스트 스크립트
각 플랫폼별 크롤러 기능을 테스트하는 스크립트
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트 경로를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.crawlers import get_crawler
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_baemin_crawler():
    """배민 크롤러 테스트"""
    print("\n=== 배달의민족 크롤러 테스트 ===")
    
    # 테스트용 로그인 정보 (실제 정보로 교체 필요)
    username = "test_id"
    password = "test_password"
    
    async with get_crawler('baemin', headless=False) as crawler:
        # 로그인 테스트
        login_success = await crawler.login(username, password)
        print(f"로그인 결과: {login_success}")
        
        if login_success:
            # 매장 목록 가져오기
            stores = await crawler.get_store_list()
            print(f"매장 수: {len(stores)}")
            for store in stores[:3]:  # 처음 3개만 출력
                print(f"  - {store['store_name']} ({store['platform_code']})")
            
            # 첫 번째 매장 선택
            if stores:
                selected = await crawler.select_store(stores[0]['platform_code'])
                print(f"매장 선택 결과: {selected}")
                
                # 선택된 매장 정보
                store_info = await crawler.get_store_info()
                print(f"선택된 매장: {store_info}")

async def test_yogiyo_crawler():
    """요기요 크롤러 테스트"""
    print("\n=== 요기요 크롤러 테스트 ===")
    
    # 테스트용 로그인 정보 (실제 정보로 교체 필요)
    username = "test_id"
    password = "test_password"
    
    async with get_crawler('yogiyo', headless=False) as crawler:
        # 로그인 테스트
        login_success = await crawler.login(username, password)
        print(f"로그인 결과: {login_success}")
        
        if login_success:
            # 매장 목록 가져오기
            stores = await crawler.get_store_list()
            print(f"매장 수: {len(stores)}")
            for store in stores[:3]:  # 처음 3개만 출력
                print(f"  - {store['store_name']} ({store['platform_code']})")

async def test_coupang_crawler():
    """쿠팡이츠 크롤러 테스트"""
    print("\n=== 쿠팡이츠 크롤러 테스트 ===")
    
    # 테스트용 로그인 정보 (실제 정보로 교체 필요)
    username = "test_email@example.com"
    password = "test_password"
    
    async with get_crawler('coupang', headless=False) as crawler:
        # 로그인 테스트
        login_success = await crawler.login(username, password)
        print(f"로그인 결과: {login_success}")
        
        if login_success:
            # 매장 목록 가져오기
            stores = await crawler.get_store_list()
            print(f"매장 수: {len(stores)}")
            for store in stores[:3]:  # 처음 3개만 출력
                print(f"  - {store['store_name']} ({store['platform_code']})")

async def main():
    """메인 테스트 함수"""
    # 테스트할 플랫폼 선택
    print("테스트할 플랫폼을 선택하세요:")
    print("1. 배달의민족")
    print("2. 요기요")
    print("3. 쿠팡이츠")
    print("4. 전체 테스트")
    
    choice = input("선택 (1-4): ")
    
    if choice == '1':
        await test_baemin_crawler()
    elif choice == '2':
        await test_yogiyo_crawler()
    elif choice == '3':
        await test_coupang_crawler()
    elif choice == '4':
        await test_baemin_crawler()
        await test_yogiyo_crawler()
        await test_coupang_crawler()
    else:
        print("잘못된 선택입니다.")

if __name__ == "__main__":
    asyncio.run(main())
