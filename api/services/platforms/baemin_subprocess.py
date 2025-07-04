"""
배민 답글 등록 서브프로세스 - 일괄 처리 지원 버전
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

# 로그 파일명을 위한 타임스탬프
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"baemin_subprocess_{timestamp}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(
            log_dir / log_filename,
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

async def process_single_review(manager, review_id, reply_content, review_info=None):
    """단일 리뷰 처리"""
    try:
        logger.info(f"리뷰 처리 시작: {review_id}")
        
        # 리뷰 정보 로깅
        if review_info:
            logger.info("=== 리뷰 상세 정보 ===")
            logger.info(f"- 작성자: {review_info.get('review_name', '')}")
            logger.info(f"- 별점: {review_info.get('rating', '')}")
            logger.info(f"- 내용: {review_info.get('review_content', '')[:50]}...")
            logger.info(f"- 날짜: {review_info.get('review_date', '')}")
            logger.info(f"- 주문메뉴: {review_info.get('ordered_menu', '')}")
            logger.info("====================")
        
        # 리뷰 찾기 및 답글 작성
        if not await manager.find_review_and_open_reply(review_id, review_info):
            logger.error(f"리뷰를 찾을 수 없음: {review_id}")
            return False
        
        logger.info("리뷰 찾기 성공, 답글 작성 중...")
        
        # 답글 작성 및 등록
        if not await manager.write_and_submit_reply(reply_content):
            logger.error(f"답글 작성/등록 실패: {review_id}")
            return False
        
        logger.info(f"답글 등록 성공: {review_id}")
        return True
        
    except Exception as e:
        logger.error(f"리뷰 처리 중 오류: {review_id}, {str(e)}")
        return False

async def main():
    """메인 실행 함수 - 일괄 처리 지원"""
    
    # 인자 파싱 - JSON 형식 지원
    if len(sys.argv) == 2:
        # JSON 형식으로 데이터 전달된 경우 (일괄 처리)
        try:
            data = json.loads(sys.argv[1])
            platform_id = data['platform_id']
            platform_pw = data['platform_pw']
            platform_code = data['platform_code']
            reviews = data['reviews']  # 리뷰 목록
            
            logger.info(f"일괄 처리 모드: {len(reviews)}개 리뷰")
            
        except Exception as e:
            logger.error(f"JSON 파싱 실패: {e}")
            print("ERROR: JSON 데이터 파싱 실패")
            sys.exit(1)
            
    elif len(sys.argv) >= 6:
        # 기존 방식 (단일 리뷰 처리) - 하위 호환성 유지
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
            except Exception as e:
                logger.error(f"리뷰 정보 파싱 실패: {e}")
        
        # 단일 리뷰를 리스트 형태로 변환
        reviews = [{
            'review_id': review_id,
            'reply_content': response_text or "소중한 리뷰 감사합니다! 더 나은 서비스로 보답하겠습니다.",
            'review_info': review_info
        }]
        
        logger.info(f"단일 처리 모드: review_id={review_id}")
        
    else:
        logger.error(f"필수 인자 부족. 받은 인자 수: {len(sys.argv)}")
        print("ERROR: 필수 인자가 부족합니다")
        sys.exit(1)
    
    # 인자 검증
    if not all([platform_id, platform_pw, platform_code]):
        missing = []
        if not platform_id: missing.append('platform_id')
        if not platform_pw: missing.append('platform_pw')
        if not platform_code: missing.append('platform_code')
        logger.error(f"필수 인자가 비어있음: {', '.join(missing)}")
        print(f"ERROR: 필수 인자가 비어있습니다: {', '.join(missing)}")
        sys.exit(1)
    
    logger.info(f"답글 등록 프로세스 시작: platform_code={platform_code}")
    logger.info(f"처리할 리뷰 수: {len(reviews)}개")
    
    playwright = None
    browser = None
    context = None
    manager = None
    page = None
    
    # 처리 결과 추적
    success_count = 0
    failed_reviews = []
    
    try:
        # Playwright 직접 실행
        logger.info("Playwright 초기화 중...")
        playwright = await async_playwright().start()
        
        # 브라우저 생성 (새로운 브라우저 인스턴스)
        logger.info("브라우저 생성 중...")
        browser = await playwright.chromium.launch(
            headless=False,  # 디버깅을 위해 False, 운영시 True로 변경
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
        
        # 페이지 생성
        logger.info("페이지 생성 중...")
        page = await context.new_page()
        await asyncio.sleep(1)  # 페이지 초기화 대기
        
        # 배민 매니저 초기화
        logger.info("배민 매니저 초기화 중...")
        manager = BaeminReplyManager(context)
        manager.page = page
        manager.context = context
        manager.is_context_provided = True
        
        # 로그인 시도
        logger.info("로그인 시도 중...")
        login_success = False
        login_attempts = 0
        max_attempts = 3

        while not login_success and login_attempts < max_attempts:
            try:
                login_attempts += 1
                logger.info(f"로그인 시도 {login_attempts}/{max_attempts}")
                
                # 로그인 페이지로 이동
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
            screenshot_path = os.path.join(
                str(log_dir),
                f"login_failed_{platform_code}_{timestamp}.png"
            )
            await page.screenshot(path=screenshot_path)
            logger.info(f"로그인 실패 스크린샷 저장: {screenshot_path}")
            raise Exception("로그인 실패")
        
        # 리뷰 페이지로 이동
        logger.info(f"리뷰 페이지 이동 중: platform_code={platform_code}")
        if not await manager.navigate_to_review_page(platform_code):
            raise Exception("리뷰 페이지 이동 실패")
        logger.info("리뷰 페이지 이동 성공")
        
        # 각 리뷰에 대해 답글 등록
        for idx, review in enumerate(reviews):
            review_id = review.get('review_id')
            reply_content = review.get('reply_content', '소중한 리뷰 감사합니다!')
            review_info = review.get('review_info')
            
            logger.info(f"[{idx+1}/{len(reviews)}] 리뷰 처리 중: {review_id}")
            
            try:
                # 답글 내용 검증
                if not reply_content or reply_content == "None" or reply_content == "null":
                    reply_content = "소중한 리뷰 감사합니다! 더 나은 서비스로 보답하겠습니다."
                
                # 리뷰 처리
                success = await process_single_review(
                    manager, 
                    review_id, 
                    reply_content, 
                    review_info
                )
                
                if success:
                    success_count += 1
                    logger.info(f"✅ 리뷰 {review_id} 처리 성공")
                else:
                    failed_reviews.append(review_id)
                    logger.warning(f"❌ 리뷰 {review_id} 처리 실패")
                
                # 각 리뷰 처리 후 잠시 대기 (안정성을 위해)
                if idx < len(reviews) - 1:  # 마지막 리뷰가 아닌 경우만
                    await asyncio.sleep(2)
                    
            except Exception as e:
                logger.error(f"리뷰 {review_id} 처리 중 예외: {str(e)}")
                failed_reviews.append(review_id)
                continue
        
        # 최종 결과 로깅
        logger.info(f"=== 처리 결과 ===")
        logger.info(f"전체: {len(reviews)}개")
        logger.info(f"성공: {success_count}개")
        logger.info(f"실패: {len(failed_reviews)}개")
        if failed_reviews:
            logger.info(f"실패한 리뷰 ID: {', '.join(failed_reviews)}")
        logger.info(f"================")
        
        # 결과 반환
        if success_count > 0:
            if len(reviews) == 1:
                # 단일 처리 모드 - 기존 호환성 유지
                print("SUCCESS")
            else:
                # 일괄 처리 모드 - JSON 응답
                result = {
                    "success": True,
                    "total": len(reviews),
                    "success_count": success_count,
                    "failed_count": len(failed_reviews),
                    "failed_reviews": failed_reviews
                }
                print(json.dumps(result, ensure_ascii=False))
        else:
            # 모두 실패한 경우
            print("ERROR: 모든 리뷰 처리 실패")
        
    except Exception as e:
        logger.error(f"답글 등록 실패: {str(e)}")
        logger.error(f"상세 에러:\n{traceback.format_exc()}")
        
        # 현재 페이지 URL 확인
        try:
            if page:
                current_url = page.url
                logger.error(f"에러 발생 시점의 URL: {current_url}")
        except:
            pass
        
        # 스크린샷 저장
        try:
            if page:
                error_screenshot = PROJECT_ROOT / 'logs' / f'error_{platform_code}_{timestamp}.png'
                await page.screenshot(path=str(error_screenshot), full_page=True)
                logger.info(f"에러 스크린샷 저장: {error_screenshot}")
        except Exception as screenshot_error:
            logger.error(f"스크린샷 저장 실패: {screenshot_error}")
        
        print(f"ERROR: {str(e)}")
        
    finally:
        logger.info("브라우저 정리 중...")
        
        # 페이지 수 확인
        if context:
            try:
                pages = context.pages
                logger.info(f"열린 페이지 수: {len(pages)}")
            except:
                pass
        
        # 페이지 종료
        if page:
            try:
                await page.close()
                logger.info("페이지 종료 완료")
            except:
                pass
        
        # 매니저 종료
        if manager:
            try:
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
    logger.info(f"Arguments: {sys.argv}")
    
    # 비동기 실행
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"프로그램 실행 중 오류: {str(e)}")
        print(f"ERROR: {str(e)}")
        sys.exit(1)