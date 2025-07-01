"""
네이버 플레이스 답글 등록 서브프로세스
"""
import asyncio
import sys
import json
import os
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from api.crawlers.reply_managers.naver_reply_manager import NaverReplyManager
from api.services.error_logger import error_logger, initialize_error_logger
from config.supabase_client import get_supabase_client

async def main(review_ids: List[str], store_info: Dict[str, Any], reply_contents: Dict[str, str]):
    """네이버 답글 등록 메인 함수"""
    context = None
    
    try:
        # Supabase 클라이언트
        supabase = get_supabase_client()
        
        # error_logger 초기화
        initialize_error_logger(supabase)
        
        # 리뷰 데이터 조회
        reviews_response = supabase.table('reviews').select('*').in_('review_id', review_ids).execute()
        reviews = reviews_response.data
        
        if not reviews:
            print(json.dumps({
                'success': False,
                'error': '처리할 리뷰가 없습니다'
            }))
            return
        
        # 답글 관리자 초기화
        reply_manager = NaverReplyManager(store_info)
        
        # Playwright 브라우저 시작
        async with async_playwright() as p:
            # 브라우저 프로필 디렉토리 설정
            platform_id = store_info['platform_id']
            account_hash = hashlib.md5(platform_id.encode()).hexdigest()[:10]
            browser_data_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'browser_data', 'naver')
            profile_path = os.path.join(browser_data_dir, f"profile_{account_hash}")
            os.makedirs(profile_path, exist_ok=True)
            
            # 브라우저 실행 인수
            browser_args = [
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-site-isolation-trials',
                '--no-zygote',
                '--single-process',
                '--disable-gpu',
                '--window-size=1280,720',
                '--start-maximized',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-features=TranslateUI',
                '--disable-ipc-flooding-protection',
                '--password-store=basic',
                '--use-mock-keychain',
                '--force-color-profile=srgb',
            ]
            
            # persistent context로 브라우저 시작
            context = await p.chromium.launch_persistent_context(
                user_data_dir=profile_path,
                headless=False,  # False로 설정하여 브라우저 창 표시
                args=browser_args,
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='ko-KR',
                timezone_id='Asia/Seoul',
                permissions=[],
                ignore_https_errors=True,
                java_script_enabled=True,
                bypass_csp=True,
                extra_http_headers={
                    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                    'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"Windows"',
                }
            )
            
            # 페이지 가져오기 (persistent context는 이미 페이지가 있음)
            pages = context.pages
            page = pages[0] if pages else await context.new_page()
            
            # JavaScript 실행 (자동화 감지 방지)
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false,
                });
                
                window.navigator.chrome = {
                    runtime: {},
                };
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ko-KR', 'ko', 'en-US', 'en'],
                });
                
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
                
                // Permission 관련 수정
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)
            
            # 로그인
            login_success = await reply_manager.login(page)
            if not login_success:
                raise Exception("네이버 로그인 실패")
            
            # 리뷰 페이지로 이동
            nav_success = await reply_manager.navigate_to_review_page(page)
            if not nav_success:
                raise Exception("리뷰 페이지 이동 실패")
            
            # 각 리뷰에 대해 답글 등록
            success_count = 0
            failed_reviews = []
            
            for review in reviews:
                try:
                    # reply_contents에서 해당 리뷰의 답글 내용 가져오기
                    reply_content = reply_contents.get(review['review_id'], '')
                    if not reply_content:
                        continue
                    
                    # 리뷰 정보에 답글 내용 추가
                    review['reply_content'] = reply_content
                    review['final_response'] = reply_content
                    review['ai_response'] = reply_content
                    
                    # 답글 등록 처리
                    success = await reply_manager.process_single_reply(page, review)
                    
                    if success:
                        success_count += 1
                        # DB 상태 업데이트
                        supabase.table('reviews').update({
                            'response_status': 'posted',
                            'response_at': datetime.now().isoformat(),
                            'response_method': 'ai_auto',
                            'final_response': reply_content,
                            'updated_at': datetime.now().isoformat()
                        }).eq('review_id', review['review_id']).execute()
                    else:
                        failed_reviews.append(review['review_id'])
                        
                    # 답글 간 대기시간
                    await asyncio.sleep(3)
                    
                except Exception as e:
                    await error_logger.log_error(
                        error_type="naver_reply_error",
                        error_message=str(e),
                        platform="naver",
                        store_info=store_info,
                        review_info={'review_id': review.get('review_id')}
                    )
                    failed_reviews.append(review.get('review_id'))
            
            # 결과 반환
            result = {
                'success': True,
                'total': len(reviews),
                'success_count': success_count,
                'failed_count': len(failed_reviews),
                'failed_reviews': failed_reviews
            }
            
            print(json.dumps(result))
            
    except Exception as e:
        await error_logger.log_error(
            error_type="naver_subprocess_error",
            error_message=str(e),
            platform="naver",
            store_info=store_info
        )
        print(json.dumps({
            'success': False,
            'error': str(e)
        }))
        
    finally:
        if context:
            try:
                await context.close()
            except Exception as e:
                # 브라우저 종료 중 발생하는 예외는 무시
                pass

if __name__ == "__main__":
    """명령줄 인자 처리"""
    try:
        if len(sys.argv) < 4:
            raise ValueError("review_ids, store_info, reply_contents 인자가 필요합니다")
        
        review_ids = json.loads(sys.argv[1])
        store_info = json.loads(sys.argv[2])
        reply_contents = json.loads(sys.argv[3])
        
        # 성공 플래그
        execution_completed = False
        
        try:
            asyncio.run(main(review_ids, store_info, reply_contents))
            execution_completed = True
        except Exception as main_error:
            # main 함수 실행 중 발생한 에러만 처리
            if "Target page, context or browser has been closed" not in str(main_error):
                raise main_error
            else:
                # 브라우저 종료 관련 에러는 무시하고 성공으로 처리
                execution_completed = True
        
    except json.JSONDecodeError as e:
        print(json.dumps({
            'success': False,
            'error': f"JSON 파싱 오류: {str(e)}"
        }))
        sys.exit(1)
    except ValueError as e:
        print(json.dumps({
            'success': False,
            'error': str(e)
        }))
        sys.exit(1)
    except Exception as e:
        # 예상치 못한 에러만 출력
        if not execution_completed:
            print(json.dumps({
                'success': False,
                'error': f"예기치 않은 오류: {str(e)}"
            }))
            sys.exit(1)
    
    # 정상 종료
    sys.exit(0)