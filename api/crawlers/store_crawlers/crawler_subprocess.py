"""
서브프로세스에서 실행되는 크롤러
FastAPI의 이벤트 루프와 분리하여 실행
"""
import sys
import json
import logging
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

# 프로젝트 경로 추가 - 상대 임포트 오류 해결
current_dir = Path(__file__).parent  # store_crawlers
crawlers_dir = current_dir.parent  # crawlers
api_dir = crawlers_dir.parent  # api
project_root = api_dir.parent  # Review_playwright

# sys.path에 필요한 경로 추가
sys.path.insert(0, str(project_root))  # 프로젝트 루트
sys.path.insert(0, str(api_dir))  # api 디렉토리

# 디버깅을 위한 경로 출력
print(f"[DEBUG] current_dir: {current_dir}", file=sys.stderr)
print(f"[DEBUG] crawlers_dir: {crawlers_dir}", file=sys.stderr)
print(f"[DEBUG] api_dir: {api_dir}", file=sys.stderr)
print(f"[DEBUG] project_root: {project_root}", file=sys.stderr)
print(f"[DEBUG] sys.path: {sys.path[:3]}", file=sys.stderr)

# 필요한 크롤러만 조건부로 임포트
# 배민 크롤러는 항상 필요
from crawlers.review_crawlers.baemin_sync_crawler import BaeminSyncCrawler

# 쿠팡, 요기요, 네이버는 필요할 때만 임포트
CoupangCrawler = None
YogiyoCrawler = None
NaverCrawler = None

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
            # 쿠팡 크롤러를 필요할 때만 임포트
            try:
                from crawlers.coupang_crawler import CoupangCrawler
                crawler = CoupangCrawler(headless=headless)
            except ImportError as e:
                print(json.dumps({
                    "error": f"Failed to import CoupangCrawler: {str(e)}",
                    "error_type": "IMPORT_ERROR"
                }))
                return
        elif platform == 'yogiyo':
            # 요기요 크롤러를 필요할 때만 임포트
            try:
                from crawlers.yogiyo_crawler import YogiyoCrawler
                crawler = YogiyoCrawler(headless=headless)
            except ImportError as e:
                print(json.dumps({
                    "error": f"Failed to import YogiyoCrawler: {str(e)}",
                    "error_type": "IMPORT_ERROR"
                }))
                return
        elif platform == 'naver':
            # 네이버 크롤러를 필요할 때만 임포트
            try:
                from crawlers.naver_crawler import NaverCrawler
                crawler = NaverCrawler()
            except ImportError as e:
                print(json.dumps({
                    "error": f"Failed to import NaverCrawler: {str(e)}",
                    "error_type": "IMPORT_ERROR"
                }))
                return
        else:
            print(json.dumps({
                "error": f"Invalid async platform: {platform}",
                "error_type": "INVALID_PLATFORM"
            }))
            return
            
        
        # 브라우저 시작 시도
        try:
            await asyncio.wait_for(crawler.start_browser(), timeout=30)
        except asyncio.TimeoutError:
            print(json.dumps({
                "error": "Browser start timeout",
                "error_type": "BROWSER_START_TIMEOUT",
                "platform": platform
            }))
            return
        
        if action == 'get_stores':
            # 로그인 시도
            try:
                login_success = await asyncio.wait_for(
                    crawler.login(username, password),
                    timeout=60
                )
                if not login_success:
                    print(json.dumps({
                        "error": "Login failed",
                        "error_type": "LOGIN_FAILED",
                        "login_success": False,
                        "platform": platform
                    }))
                    return
            except asyncio.TimeoutError:
                print(json.dumps({
                    "error": "Login timeout",
                    "error_type": "LOGIN_TIMEOUT",
                    "platform": platform
                }))
                return
            
            # 매장 목록 가져오기
            try:
                stores = await asyncio.wait_for(
                    crawler.get_store_list(),
                    timeout=60
                )
                print(json.dumps({
                    "success": True,
                    "stores": stores,
                    "platform": platform
                }))
            except asyncio.TimeoutError:
                print(json.dumps({
                    "error": "Store list timeout",
                    "error_type": "STORE_LIST_TIMEOUT",
                    "platform": platform
                }))
                return
            
        else:
            print(json.dumps({
                "error": f"Unknown action: {action}",
                "error_type": "UNKNOWN_ACTION"
            }))
            
    except Exception as e:
        import traceback
        error_details = {
            "error": str(e),
            "error_type": "CRAWLER_EXCEPTION",
            "platform": platform,
            "traceback": traceback.format_exc()
        }
        logger.error(f"크롤러 실행 중 오류: {json.dumps(error_details)}")
        print(json.dumps(error_details))
    finally:
        if crawler:
            try:
                await asyncio.wait_for(crawler.close_browser(), timeout=10)
            except:
                pass

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
                
                # 실제 가게가 없는 경우 특별 처리
                if not stores:
                    print(json.dumps({
                        "success": False,
                        "error": "배달의민족에 등록된 가게가 없습니다",
                        "error_type": "NO_STORES_REGISTERED",
                        "stores": []
                    }))
                else:
                    print(json.dumps({"success": True, "stores": stores}))
            else:
                print(json.dumps({"error": f"Unknown action: {action}"}))
                
            crawler.close_browser()
            
        elif platform == 'naver':
            # 네이버는 비동기 크롤러 사용하지만 별도 처리
            async def run_naver_crawler():
                from crawlers.naver_crawler import NaverCrawler
                crawler = NaverCrawler()
                
                async with async_playwright() as p:
                    # 네이버 크롤러의 create_browser_context 메서드 사용
                    browser, context, page = await crawler.create_browser_context(
                        p, 
                        username,  # platform_id
                        headless=headless
                    )
                    
                    try:
                        if action == 'get_stores':
                            # 로그인
                            login_success = await crawler.login(page, username, password)
                            if not login_success:
                                return {
                                    "error": "Login failed", 
                                    "error_type": "LOGIN_FAILED",
                                    "login_success": False,
                                    "platform": platform
                                }
                            
                            # 매장 목록 가져오기
                            stores = await crawler.get_stores(page)
                            
                            return {
                                "success": True,
                                "stores": stores,
                                "platform": platform,
                                "login_success": True,
                                "count": len(stores),
                                "message": f"성공적으로 {len(stores)}개의 매장을 가져왔습니다."
                            }
                        else:
                            return {
                                "error": f"Unknown action: {action}",
                                "error_type": "UNKNOWN_ACTION"
                            }
                            
                    except Exception as e:
                        import traceback
                        return {
                            "error": str(e),
                            "error_type": "CRAWLER_EXCEPTION",
                            "platform": platform,
                            "traceback": traceback.format_exc()
                        }
                    finally:
                        await browser.close()
            
            # 비동기 함수 실행
            result = asyncio.run(run_naver_crawler())
            
            # 결과 출력
            print(json.dumps(result, ensure_ascii=False))
            
        elif platform in ['coupang', 'yogiyo']:
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