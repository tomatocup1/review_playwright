"""
배민 답글 등록 서브프로세스
메인 프로세스와 분리되어 실행되는 스크립트
"""
import sys
import json
import asyncio
import logging
import os
import traceback
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

# 프로젝트 루트 경로 설정
current_file = Path(__file__).resolve()
platforms_dir = current_file.parent
services_dir = platforms_dir.parent
api_dir = services_dir.parent
project_root = api_dir.parent

# Python 경로에 추가
sys.path.insert(0, str(project_root))

# 로깅 설정을 import 전에 수행
log_dir = Path("C:/Review_playwright/logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(
            log_dir / f"subprocess_{sys.argv[1] if len(sys.argv) > 1 else 'unknown'}.log",
            encoding='utf-8'
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# 경로 정보 로깅
logger.info(f"Current file: {current_file}")
logger.info(f"Project root: {project_root}")
logger.info(f"Python path[0]: {sys.path[0]}")

# Import 시도
try:
    # 직접 import
    from api.services.platforms.baemin_reply_manager import BaeminReplyManager
    logger.info("모듈 import 성공")
except Exception as e:
    logger.error(f"Import 실패: {e}")
    # 대체 경로 시도
    try:
        # 절대 경로로 모듈 직접 import
        import importlib.util
        
        # baemin_reply_manager 모듈 로드
        baemin_manager_path = project_root / "api" / "services" / "platforms" / "baemin_reply_manager.py"
        spec_manager = importlib.util.spec_from_file_location("baemin_reply_manager", baemin_manager_path)
        baemin_reply_manager = importlib.util.module_from_spec(spec_manager)
        spec_manager.loader.exec_module(baemin_reply_manager)
        BaeminReplyManager = baemin_reply_manager.BaeminReplyManager
        
        logger.info("대체 import 성공")
    except Exception as e2:
        logger.error(f"대체 import도 실패: {e2}")
        sys.exit(1)

# 프로젝트 루트 설정
PROJECT_ROOT = Path("C:/Review_playwright")

async def main():
    """메인 실행 함수"""
    # 인자 파싱
    if len(sys.argv) < 6:
        logger.error(f"필수 인자 부족. 받은 인자 수: {len(sys.argv)}, 인자: {sys.argv}")
        print("ERROR: 필수 인자가 부족합니다. (review_id, platform_id, platform_pw, platform_code, response_text)")
        sys.exit(1)
    
    review_id = sys.argv[1]
    platform_id = sys.argv[2]
    platform_pw = sys.argv[3]
    platform_code = sys.argv[4]
    response_text = sys.argv[5] if len(sys.argv) > 5 else ""
    
    # 리뷰 정보 파싱 (6번째 인자)
    review_info = None
    if len(sys.argv) >= 7:
        try:
            review_info = json.loads(sys.argv[6])
            logger.info(f"리뷰 정보 수신: {review_info}")
        except Exception as e:
            logger.error(f"리뷰 정보 파싱 실패: {e}")
            # 파싱 실패해도 계속 진행
    
    # 인자 검증
    if not all([review_id, platform_id, platform_pw, platform_code]):
        missing = []
        if not review_id: missing.append('review_id')
        if not platform_id: missing.append('platform_id')
        if not platform_pw: missing.append('platform_pw')
        if not platform_code: missing.append('platform_code')
        logger.error(f"필수 인자가 비어있음: {', '.join(missing)}")
        print(f"ERROR: 필수 인자가 비어있습니다: {', '.join(missing)}")
        sys.exit(1)
    
    # response_text가 비어있으면 기본 메시지 사용
    if not response_text or response_text == "None" or response_text == "null" or response_text.strip() == "":
        response_text = "소중한 리뷰 감사합니다! 더 나은 서비스로 보답하겠습니다."
        logger.warning(f"답글 내용이 비어있어 기본 메시지 사용. 받은 값: '{response_text}'")
    else:
        logger.info(f"AI 생성 답글 사용: {response_text[:50]}...")
    
    # 실제 사용할 답글 내용
    reply_content = response_text
    
    logger.info(f"답글 등록 프로세스 시작: review_id={review_id}")
    logger.info(f"플랫폼 정보: platform_code={platform_code}, platform_id={platform_id[:4]}*** ")
    logger.info(f"답글 내용: {reply_content[:100]}...")
    logger.info(f"답글 내용 길이: {len(reply_content)}자")
    
    playwright = None
    browser = None
    context = None
    manager = None
    page = None
    
    try:
        # Playwright 직접 실행
        logger.info("Playwright 초기화 중...")
        playwright = await async_playwright().start()
        
        # 브라우저 생성 (새로운 브라우저 인스턴스)
        logger.info("브라우저 생성 중...")
        browser = await playwright.chromium.launch(
            headless=False,  # 디버깅을 위해 False
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=site-per-process',
                '--allow-running-insecure-content',
                '--disable-notifications',
                '--disable-popup-blocking',
                '--start-maximized'
            ],
            downloads_path='C:/Review_playwright/downloads'
        )
        
        # 새로운 컨텍스트 생성 (쿠키/세션 없는 깨끗한 상태)
        logger.info("새로운 브라우저 컨텍스트 생성 중...")
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='ko-KR',
            timezone_id='Asia/Seoul',
            ignore_https_errors=True,
            java_script_enabled=True,
            accept_downloads=True,
            bypass_csp=True
        )
        
        # 타임아웃 설정
        context.set_default_timeout(60000)  # 60초
        
        # 추가 설정
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ko-KR', 'ko', 'en-US', 'en']
            });
            window.chrome = {
                runtime: {}
            };
            Object.defineProperty(navigator, 'permissions', {
                get: () => ({
                    query: () => Promise.resolve({ state: 'granted' })
                })
            });
        """)
        
        logger.info(f"브라우저 컨텍스트 타입: {type(context)}")
        
        # 페이지 생성 먼저!
        logger.info("페이지 생성 중...")
        page = await context.new_page()
        await asyncio.sleep(1)  # 페이지 초기화 대기
        
        # 페이지가 제대로 생성되었는지 확인
        if not page:
            raise Exception("페이지 생성 실패")
        
        logger.info("페이지 생성 성공")
        
        # 배민 매니저 초기화 (컨텍스트 전달)
        logger.info("배민 매니저 초기화 중...")
        manager = BaeminReplyManager(context)
        
        # 매니저가 이미 생성된 페이지를 사용하도록 설정
        manager.page = page
        manager.context = context
        manager.is_context_provided = True
        
        # initialize를 호출하지 않음! (이미 페이지가 있으므로)
        logger.info("매니저 초기화 완료 (페이지 직접 할당)")
        
        # 로그인 시도 중...
        logger.info("로그인 시도 중...")
        login_success = False
        login_attempts = 0
        max_attempts = 3

        while not login_success and login_attempts < max_attempts:
            try:
                login_attempts += 1
                logger.info(f"로그인 시도 {login_attempts}/{max_attempts}")
                
                # 먼저 로그인 페이지로 이동 (이 부분 추가!)
                login_url = "https://biz-member.baemin.com/login"
                logger.info(f"로그인 페이지로 이동: {login_url}")
                await page.goto(login_url, wait_until="networkidle", timeout=30000)
                await page.wait_for_load_state("networkidle")

                login_success = await manager.login(platform_id, platform_pw)
                
                if login_success:
                    logger.info("로그인 성공!")
                    break
                else:
                    logger.warning(f"로그인 실패 (시도 {login_attempts}/{max_attempts})")
                    if login_attempts < max_attempts:
                        await asyncio.sleep(3)
                        
            except Exception as e:
                logger.error(f"로그인 시도 중 에러: {str(e)}")
                if login_attempts < max_attempts:
                    await asyncio.sleep(3)
                
        if not login_success:
            logger.error(f"로그인 실패. 현재 URL: {page.url}")
            # 스크린샷 저장
            screenshot_path = os.path.join(
                str(log_dir),  # Path를 string으로 변환
                f"login_failed_{review_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            )
            await page.screenshot(path=screenshot_path)
            logger.info(f"로그인 실패 스크린샷 저장: {screenshot_path}")
            raise Exception("로그인 실패")
        
        # 리뷰 페이지로 이동
        logger.info(f"리뷰 페이지 이동 중: platform_code={platform_code}")
        if not await manager.navigate_to_review_page(platform_code):
            raise Exception("리뷰 페이지 이동 실패")
        logger.info("리뷰 페이지 이동 성공")
        
        # 리뷰 찾기 및 답글 작성
        logger.info(f"리뷰 검색 중: review_id={review_id}")
        
        # review_info가 있으면 로그에 기록
        if review_info:
            logger.info("=== 리뷰 상세 정보 ===")
            logger.info(f"- 작성자: {review_info.get('review_name', '')}")
            logger.info(f"- 별점: {review_info.get('rating', '')}")
            logger.info(f"- 내용: {review_info.get('review_content', '')}")
            logger.info(f"- 날짜: {review_info.get('review_date', '')}")
            logger.info(f"- 주문메뉴: {review_info.get('ordered_menu', '')}")
            logger.info("====================")
        
        # 기존 메서드 사용
        if not await manager.find_review_and_open_reply(review_id, review_info):
            current_url = page.url if page else "Unknown"
            logger.error(f"리뷰를 찾을 수 없음. 현재 URL: {current_url}")
            
            if page:
                try:
                    error_screenshot = PROJECT_ROOT / 'logs' / f'review_search_failed_{review_id}.png'
                    await page.screenshot(path=str(error_screenshot), full_page=True)
                    logger.info(f"에러 스크린샷 저장: {error_screenshot}")
                except:
                    pass
            
            raise Exception("리뷰를 찾을 수 없거나 답글 버튼을 클릭할 수 없음")
        
        logger.info("리뷰 찾기 성공, 답글 작성 중...")
        
        # 답글 작성 및 등록
        if not await manager.write_and_submit_reply(reply_content):
            raise Exception("답글 작성/등록 실패")
        
        logger.info("답글 등록 성공!")
        print("SUCCESS")  # 부모 프로세스에 성공 신호
        
        # 성공 후 잠시 대기
        await asyncio.sleep(3)
        
    except Exception as e:
        logger.error(f"답글 등록 실패: {str(e)}")
        logger.error(f"상세 에러:\n{traceback.format_exc()}")
        
        # 현재 페이지 URL 확인
        try:
            if page:
                current_url = page.url
                logger.error(f"에러 발생 시점의 URL: {current_url}")
            elif manager and manager.page:
                current_url = manager.page.url
                logger.error(f"에러 발생 시점의 URL (매니저): {current_url}")
        except:
            pass
        
        # 스크린샷 저장
        try:
            screenshot_page = page or (manager.page if manager else None)
            if screenshot_page:
                error_screenshot = PROJECT_ROOT / 'logs' / f'error_{review_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
                await screenshot_page.screenshot(path=str(error_screenshot), full_page=True)
                logger.info(f"에러 스크린샷 저장: {error_screenshot}")
        except Exception as screenshot_error:
            logger.error(f"스크린샷 저장 실패: {screenshot_error}")
        
        print(f"ERROR: {str(e)}")  # 부모 프로세스에 에러 전달
        
    finally:
        logger.info("브라우저 정리 중...")
        
        # 페이지 수 확인
        if context:
            try:
                pages = context.pages
                logger.info(f"열린 페이지 수: {len(pages)}")
            except:
                pass
        
        # 페이지 종료 (매니저보다 먼저)
        if page and page != manager.page:
            try:
                await page.close()
                logger.info("추가 페이지 종료 완료")
            except:
                pass
        
        # 매니저 종료
        if manager:
            try:
                # 매니저가 페이지를 닫지 않도록 설정
                manager.page = None
                await manager.close()
                logger.info("매니저 종료 완료")
            except Exception as e:
                logger.error(f"매니저 종료 중 오류: {str(e)}")
        
        # 컨텍스트 종료
        if context:
            try:
                await context.close()
                logger.info("컨텍스트 종료 완료")
            except Exception as e:
                logger.error(f"컨텍스트 종료 중 오류: {str(e)}")
        
        # 브라우저 종료
        if browser:
            try:
                await browser.close()
                logger.info("브라우저 종료 완료")
            except Exception as e:
                logger.error(f"브라우저 종료 중 오류: {str(e)}")
        
        # Playwright 종료
        if playwright:
            try:
                await playwright.stop()
                logger.info("Playwright 종료 완료")
            except Exception as e:
                logger.error(f"Playwright 종료 중 오류: {str(e)}")
        
        logger.info("브라우저 정리 완료")

if __name__ == "__main__":
    # 현재 작업 디렉토리 확인
    logger.info(f"Current Working Directory: {os.getcwd()}")
    logger.info(f"Script Location: {__file__}")
    
    # 비동기 실행
    try:
        exit_code = asyncio.run(main())
    except Exception as e:
        logger.error(f"프로그램 실행 중 오류: {str(e)}")
        exit_code = 1
    
    sys.exit(exit_code if exit_code else 0)