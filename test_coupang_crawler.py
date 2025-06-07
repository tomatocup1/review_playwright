"""
쿠팡이츠 크롤러 테스트 스크립트
"""
import asyncio
import sys
import logging
from pathlib import Path

# 프로젝트 경로 추가
sys.path.insert(0, str(Path(__file__).parent))

from api.crawlers.coupang_crawler import CoupangCrawler

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_coupang_crawler():
    """쿠팡이츠 크롤러 테스트"""
    # 테스트용 계정 정보 (실제 테스트 시 변경 필요)
    test_id = "test_id"  # 실제 쿠팡이츠 아이디로 변경
    test_pw = "test_pw"  # 실제 쿠팡이츠 비밀번호로 변경
    
    crawler = CoupangCrawler(headless=False)  # 테스트를 위해 headless=False
    
    try:
        print("1. 브라우저 시작...")
        await crawler.start_browser()
        print("✓ 브라우저 시작 완료")
        
        print("\n2. 쿠팡이츠 로그인 시도...")
        login_success = await crawler.login(test_id, test_pw)
        
        if login_success:
            print("✓ 로그인 성공!")
            
            print("\n3. 매장 목록 가져오기...")
            stores = await crawler.get_store_list()
            
            if stores:
                print(f"✓ {len(stores)}개의 매장을 찾았습니다:")
                for i, store in enumerate(stores, 1):
                    print(f"   {i}. {store['store_name']} (코드: {store['platform_code']})")
                
                # 첫 번째 매장 선택 테스트
                if len(stores) > 0:
                    first_store = stores[0]
                    print(f"\n4. 첫 번째 매장 선택 테스트: {first_store['store_name']}")
                    select_success = await crawler.select_store(first_store['platform_code'])
                    
                    if select_success:
                        print("✓ 매장 선택 성공!")
                    else:
                        print("✗ 매장 선택 실패")
            else:
                print("✗ 매장을 찾을 수 없습니다")
        else:
            print("✗ 로그인 실패 - 아이디/비밀번호를 확인하세요")
            
    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        
    finally:
        input("\n테스트 완료. Enter를 눌러 브라우저를 닫으세요...")
        await crawler.close_browser()

if __name__ == "__main__":
    # Windows 이벤트 루프 정책 설정
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(test_coupang_crawler())
