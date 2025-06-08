"""
서브프로세스에서 실행되는 크롤러
FastAPI의 이벤트 루프와 분리하여 실행
"""
import sys
import json
import logging
import asyncio
from pathlib import Path

# 프로젝트 경로 추가 - 상대 임포트 오류 해결
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir.parent))

# 이제 임포트
from baemin_sync_crawler import BaeminSyncCrawler
from coupang_crawler import CoupangCrawler
from yogiyo_crawler import YogiyoCrawler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Windows 이벤트 루프 정책 설정
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

async def run_async_crawler(platform, username, password, action, headless):
    """비동기 크롤러 실행"""
    crawler = None
    try:
        if platform == 'coupang':
            crawler = CoupangCrawler(headless=headless)
        elif platform == 'yogiyo':
            crawler = YogiyoCrawler(headless=headless)
        else:
            print(json.dumps({"error": f"Invalid async platform: {platform}"}))
            return
        
        await crawler.start_browser()
        
        if action == 'get_stores':
            # 로그인
            login_success = await crawler.login(username, password)
            if not login_success:
                print(json.dumps({"error": "Login failed", "login_success": False}))
                return
            
            # 매장 목록 가져오기
            stores = await crawler.get_store_list()
            print(json.dumps({"success": True, "stores": stores}))
        else:
            print(json.dumps({"error": f"Unknown action: {action}"}))
            
    except Exception as e:
        import traceback
        logger.error(f"크롤러 실행 중 오류: {str(e)}")
        logger.error(traceback.format_exc())
        print(json.dumps({"error": str(e)}))
    finally:
        if crawler:
            await crawler.close_browser()

def main():
    """서브프로세스 메인 함수"""
    if len(sys.argv) < 5:
        print(json.dumps({"error": "Invalid arguments"}))
        return
    
    platform = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    action = sys.argv[4]
    headless = sys.argv[5].lower() == 'true' if len(sys.argv) > 5 else True
    
    logger.info(f"서브프로세스 시작 - 플랫폼: {platform}, 액션: {action}")
    
    try:
        if platform == 'baemin':
            # 배민은 동기 크롤러 사용
            crawler = BaeminSyncCrawler(headless=headless)
            crawler.start_browser()
            
            if action == 'get_stores':
                # 로그인
                login_success = crawler.login(username, password)
                if not login_success:
                    print(json.dumps({"error": "Login failed", "login_success": False}))
                    return
                
                # 매장 목록 가져오기
                stores = crawler.get_store_list()
                print(json.dumps({"success": True, "stores": stores}))
            else:
                print(json.dumps({"error": f"Unknown action: {action}"}))
                
            crawler.close_browser()
            
        elif platform in ['coupang', 'yogiyo']:  # yogiyo 추가
            # 쿠팡이츠와 요기요는 비동기 크롤러 사용
            asyncio.run(run_async_crawler(platform, username, password, action, headless))
            
        else:
            print(json.dumps({"error": f"Unsupported platform: {platform}"}))
            return
            
    except Exception as e:
        import traceback
        logger.error(f"메인 함수 오류: {str(e)}")
        logger.error(traceback.format_exc())
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    main()