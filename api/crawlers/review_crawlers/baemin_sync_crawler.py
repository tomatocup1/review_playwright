"""
배달의민족 Windows 동기식 크롤러
비동기 문제를 피하기 위한 동기식 버전
"""
import re
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, Browser, Playwright, BrowserContext

logger = logging.getLogger(__name__)

class BaeminSyncCrawler:
    """배달의민족 동기식 크롤러"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.logged_in = False
        self.login_url = "https://biz-member.baemin.com/login"
        self.self_service_url = "https://self.baemin.com"
        
        # 스크린샷 저장 경로
        self.screenshot_dir = Path("C:/Review_playwright/logs/screenshots/baemin")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
    def start_browser(self):
        """브라우저 시작"""
        try:
            logger.info("배민 브라우저 시작 중...")
            logger.info(f"Headless 모드: {self.headless}")
            
            # Playwright 시작
            try:
                self.playwright = sync_playwright().start()
                logger.info("Playwright 인스턴스 생성 성공")
            except Exception as e:
                logger.error(f"Playwright 시작 실패: {str(e)}")
                raise
            
            # 브라우저 실행 옵션
            launch_options = {
                'headless': self.headless,
                'args': [
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',  # 추가
                    '--disable-gpu',  # 추가
                    '--disable-web-security',  # 추가
                    '--disable-features=IsolateOrigins,site-per-process'  # 추가
                ]
            }
            
            # 브라우저 시작
            try:
                self.browser = self.playwright.chromium.launch(**launch_options)
                logger.info("브라우저 런치 성공")
            except Exception as e:
                logger.error(f"브라우저 런치 실패: {str(e)}")
                logger.error(f"브라우저 실행 파일 경로 문제일 수 있습니다.")
                raise
            
            # 컨텍스트 생성
            try:
                self.context = self.browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    viewport={'width': 1920, 'height': 1080},
                    ignore_https_errors=True  # 추가
                )
                logger.info("브라우저 컨텍스트 생성 성공")
            except Exception as e:
                logger.error(f"컨텍스트 생성 실패: {str(e)}")
                raise
            
            # 페이지 생성
            try:
                self.page = self.context.new_page()
                self.page.set_default_timeout(30000)
                logger.info("페이지 생성 성공")
            except Exception as e:
                logger.error(f"페이지 생성 실패: {str(e)}")
                raise
            
            logger.info("브라우저 시작 성공")
            
        except Exception as e:
            logger.error(f"브라우저 시작 실패 - 전체 에러: {str(e)}")
            logger.error(f"에러 타입: {type(e).__name__}")
            import traceback
            logger.error(f"스택 트레이스:\n{traceback.format_exc()}")
            self.close_browser()
            raise
            
    def close_browser(self):
        """브라우저 종료"""
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            logger.info("브라우저 종료 완료")
        except Exception as e:
            logger.error(f"브라우저 종료 중 오류: {str(e)}")
            
    def save_screenshot(self, name: str):
        """스크린샷 저장"""
        if not self.page:
            return
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}.png"
            filepath = self.screenshot_dir / filename
            
            self.page.screenshot(path=str(filepath))
            logger.info(f"스크린샷 저장: {filepath}")
            
        except Exception as e:
            logger.error(f"스크린샷 저장 실패: {str(e)}")
            
    def login(self, username: str, password: str) -> bool:
        """배민 로그인"""
        try:
            logger.info(f"배민 로그인 시작: {username}")
            
            # 로그인 페이지로 이동
            self.page.goto(self.login_url)
            self.page.wait_for_load_state('networkidle')
            
            # 아이디 입력
            self.page.fill('input[type="text"]', username)
            logger.info("아이디 입력 완료")
            
            # 비밀번호 입력
            self.page.fill('input[type="password"]', password)
            logger.info("비밀번호 입력 완료")
            
            # 로그인 버튼 클릭
            self.page.click('button[type="submit"]')
            logger.info("로그인 버튼 클릭")
            
            # 로그인 처리를 위해 충분한 시간 대기
            logger.info("로그인 처리 대기 중...")
            self.page.wait_for_timeout(5000)  # 5초 대기
            
            # 현재 URL 확인
            current_url = self.page.url
            logger.info(f"로그인 후 URL: {current_url}")
            
            # 단순히 로그인 페이지를 벗어났는지 확인
            if 'login' not in current_url.lower():
                logger.info("로그인 페이지를 벗어남 - 로그인 성공")
                self.logged_in = True
                return True
            else:
                logger.error("여전히 로그인 페이지에 있음 - 로그인 실패")
                return False
                
        except Exception as e:
            logger.error(f"배민 로그인 중 오류: {str(e)}")
            self.save_screenshot("login_error")
            return False
            
    def close_popup(self):
        """팝업 닫기 - 다양한 기간의 '보지 않기' 옵션 처리"""
        try:
            # 팝업이 나타날 때까지 잠시 대기
            self.page.wait_for_timeout(2000)
            
            # 다양한 기간의 "보지 않기" 버튼 선택자
            popup_close_selectors = [
                # 정규표현식을 사용한 패턴 매칭
                'button:has-text("보지 않기")',  # 모든 "보지 않기" 텍스트 포함
                'span:has-text("보지 않기")',
                'div:has-text("보지 않기")',
                # 구체적인 기간별 선택자
                'button:has-text("오늘 하루 보지 않기")',
                'button:has-text("1일간 보지 않기")',
                'button:has-text("3일 동안 보지 않기")',
                'button:has-text("7일간 보지 않기")',
                'button:has-text("30일간 보지 않기")',
                # span 태그 버전
                'span:has-text("오늘 하루 보지 않기")',
                'span:has-text("1일간 보지 않기")',
                'span:has-text("3일 동안 보지 않기")',
                'span:has-text("7일간 보지 않기")',
                'span:has-text("30일간 보지 않기")',
                # 텍스트 직접 매칭
                'text="오늘 하루 보지 않기"',
                'text="1일간 보지 않기"',
                'text="3일 동안 보지 않기"',
                'text="7일간 보지 않기"',
                'text="30일간 보지 않기"',
                # 클래스명으로도 시도
                '.TextButton_b_b8ew_1j0jumh3'
            ]
            
            # 우선순위: 더 긴 기간의 "보지 않기" 버튼을 먼저 찾아서 클릭
            priority_selectors = [
                # 긴 기간부터 우선적으로 처리
                ('button:has-text("30일간 보지 않기")', '30일간'),
                ('span:has-text("30일간 보지 않기")', '30일간'),
                ('button:has-text("7일간 보지 않기")', '7일간'),
                ('span:has-text("7일간 보지 않기")', '7일간'),
                ('button:has-text("3일 동안 보지 않기")', '3일 동안'),
                ('span:has-text("3일 동안 보지 않기")', '3일 동안'),
                ('button:has-text("1일간 보지 않기")', '1일간'),
                ('span:has-text("1일간 보지 않기")', '1일간'),
                ('button:has-text("오늘 하루 보지 않기")', '오늘 하루'),
                ('span:has-text("오늘 하루 보지 않기")', '오늘 하루')
            ]
            
            # 먼저 우선순위 선택자로 시도
            for selector, period in priority_selectors:
                try:
                    if self.page.is_visible(selector):
                        self.page.click(selector)
                        logger.info(f"팝업을 닫았습니다: {period} 보지 않기")
                        self.page.wait_for_timeout(1000)
                        return
                except:
                    continue
            
            # 우선순위 선택자로 못 찾은 경우, 일반 선택자로 시도
            for selector in popup_close_selectors:
                try:
                    if self.page.is_visible(selector):
                        # 버튼 텍스트 가져오기
                        element = self.page.query_selector(selector)
                        if element:
                            text_content = element.text_content()
                            self.page.click(selector)
                            logger.info(f"팝업을 닫았습니다: {text_content}")
                            self.page.wait_for_timeout(1000)
                            return
                except:
                    continue
            
            # "보지 않기"가 포함된 모든 요소를 찾아서 처리
            try:
                # Playwright의 필터 기능을 사용하여 "보지 않기" 텍스트가 있는 요소 찾기
                elements_with_text = self.page.get_by_text("보지 않기")
                count = elements_with_text.count()
                
                if count > 0:
                    logger.info(f"'보지 않기' 텍스트가 포함된 {count}개의 요소 발견")
                    
                    # 첫 번째 보이는 요소 클릭
                    for i in range(count):
                        try:
                            element = elements_with_text.nth(i)
                            if element.is_visible():
                                text_content = element.text_content()
                                element.click()
                                logger.info(f"팝업을 닫았습니다: {text_content}")
                                self.page.wait_for_timeout(1000)
                                return
                        except:
                            continue
            except:
                pass
                        
            logger.info("닫을 팝업이 없거나 이미 닫혀있습니다")
                        
        except Exception as e:
            logger.debug(f"팝업 처리 중 예외 발생: {str(e)}")

    def handle_popups(self):
        """모든 종류의 팝업 처리 - close_popup을 먼저 시도"""
        try:
            # 먼저 "보지 않기" 타입 팝업 처리 시도
            self.close_popup()
            
            # 추가적인 팝업 처리 (닫기, 확인 등)
            self.page.wait_for_timeout(1000)
            
            # 다양한 팝업 닫기 버튼 선택자
            popup_close_selectors = [
                'button:has-text("닫기")',
                'button:has-text("확인")',
                '[aria-label="Close"]',
                '[aria-label="닫기"]',
                '.close-button',
                '.popup-close',
                'button.close',
                # X 버튼
                'button[aria-label="close"]',
                'button[aria-label="닫기"]',
                '[role="button"][aria-label="close"]'
            ]
            
            closed_count = 0
            for selector in popup_close_selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    for element in elements:
                        if element.is_visible():
                            element.click()
                            closed_count += 1
                            logger.info(f"추가 팝업 닫기: {selector}")
                            self.page.wait_for_timeout(500)
                except:
                    continue
            
            if closed_count > 0:
                logger.info(f"추가로 {closed_count}개의 팝업을 닫았습니다")
                    
        except Exception as e:
            logger.debug(f"팝업 처리 중 예외 발생: {str(e)}")

    def get_store_list(self) -> List[Dict[str, Any]]:
        """매장 목록 조회"""
        try:
            logger.info("배민 매장 목록 조회 시작")
            
            # 현재 URL 확인
            current_url = self.page.url
            logger.info(f"현재 페이지 URL: {current_url}")
            
            # 셀프서비스 페이지로 이동
            logger.info("셀프서비스 페이지로 이동")
            self.page.goto(self.self_service_url)
            self.page.wait_for_load_state('networkidle')
            
            # 페이지 로드 대기
            self.page.wait_for_timeout(3000)
            
            # 팝업 닫기
            self.close_popup()

            stores = []
            
            # select 요소 찾기
            try:
                # 다양한 선택자로 시도
                select_selectors = [
                    'select.ShopSelect-module___pC1',
                    'select.Select-module__a623',
                    'select',  # 모든 select 요소
                    '.ShopSelect-module__JWCr select'
                ]
                
                select_element = None
                selector = None
                for sel in select_selectors:
                    try:
                        select_element = self.page.wait_for_selector(sel, timeout=5000)
                        if select_element:
                            selector = sel
                            logger.info(f"Select 요소 발견: {selector}")
                            break
                    except:
                        continue
                
                if select_element:
                    # select 요소의 모든 option 가져오기
                    options = self.page.query_selector_all(f'{selector} option')
                    
                    if options:
                        logger.info(f"{len(options)}개의 옵션 발견")
                        
                        # 배민 서비스 메뉴 목록 (실제 가게가 아닌 것들)
                        service_names = [
                            '배민셀프서비스', '배민외식업광장', '배민상회', 
                            '배민아카데미', '배민로봇', '배민오더',
                            '셀프서비스', '외식업광장', '상회', 
                            '아카데미', '로봇', '오더'
                        ]
                        service_codes = ['self', 'ceo', 'store', 'academy', 'robot', 'order']
                        
                        actual_stores = []  # 실제 가게만 저장
                        
                        for option in options:
                            value = option.get_attribute('value')
                            text = option.text_content()
                            
                            if value and text:
                                text = text.strip()
                                logger.info(f"옵션 발견: {text} (value: {value})")
                                
                                # 서비스 메뉴인지 확인
                                is_service = False
                                for service_name in service_names:
                                    if service_name in text:
                                        is_service = True
                                        logger.info(f"서비스 메뉴 제외: {text}")
                                        break
                                
                                # value가 서비스 코드인지 확인
                                if value in service_codes:
                                    is_service = True
                                    logger.info(f"서비스 코드 제외: {value}")
                                
                                # 실제 가게인 경우만 처리
                                if not is_service and value and text:
                                    # 텍스트에서 매장 정보 파싱
                                    # 예: "[음식배달] 더클램 데이 / 카페·디저트 14545991"
                                    patterns = [
                                        r'\[(.*?)\]\s*(.+?)\s*/\s*(.+?)\s*(\d+)$',  # 끝에 숫자가 있는 경우
                                        r'\[(.*?)\]\s*(.+?)\s*/\s*(.+?)$',  # 숫자가 없는 경우
                                        r'(.+?)\s*/\s*(.+?)\s*(\d+)$',  # 대괄호가 없는 경우
                                    ]
                                    
                                    matched = False
                                    for pattern in patterns:
                                        match = re.match(pattern, text)
                                        if match:
                                            if len(match.groups()) == 4:  # 숫자 포함
                                                store_type = match.group(1)
                                                store_name = match.group(2).strip()
                                                category = match.group(3).strip()
                                                platform_code = match.group(4)
                                            elif len(match.groups()) == 3 and match.group(3).isdigit():  # 대괄호 없고 숫자 있음
                                                store_type = '음식배달'
                                                store_name = match.group(1).strip()
                                                category = match.group(2).strip()
                                                platform_code = match.group(3)
                                            else:  # 숫자 없음
                                                store_type = match.group(1) if '[' in text else '음식배달'
                                                store_name = match.group(2) if '[' in text else match.group(1).strip()
                                                category = match.group(3) if '[' in text else match.group(2).strip()
                                                platform_code = value
                                            
                                            matched = True
                                            break
                                    
                                    if not matched:
                                        # 패턴 매칭 실패 시 기본 파싱
                                        parts = text.split('/')
                                        if parts:
                                            store_name = parts[0].strip()
                                            if '[' in store_name:
                                                store_name = store_name.split(']')[-1].strip()
                                            category = parts[1].strip() if len(parts) > 1 else ''
                                        else:
                                            store_name = text
                                            category = ''
                                        store_type = '음식배달'
                                        platform_code = value
                                    
                                    store_info = {
                                        'platform': 'baemin',
                                        'platform_code': platform_code,
                                        'store_name': store_name,
                                        'store_type': store_type,
                                        'category': category,
                                        'status': '영업중'
                                    }
                                    
                                    actual_stores.append(store_info)
                                    logger.info(f"실제 매장 추가: {store_name} (코드: {platform_code}, 카테고리: {category})")
                        
                        # 실제 가게 확인
                        if not actual_stores:
                            logger.warning("배달의민족에 등록된 실제 가게가 없습니다")
                            logger.info(f"발견된 서비스 메뉴: {[opt.text_content() for opt in options]}")
                            
                            # 현재 URL 확인 (가게 코드가 없는 경우)
                            if 'mypage?' in current_url or current_url.endswith('mypage'):
                                logger.warning("URL에 가게 코드가 없음 - 가게 미등록 상태")
                            
                            # 빈 리스트 반환 (상위에서 에러 처리)
                            return []
                        
                        stores = actual_stores
                        logger.info(f"배민 실제 매장 총 {len(stores)}개 발견")
                        
                    else:
                        logger.warning("option 요소를 찾을 수 없습니다")
                        return []
                else:
                    logger.warning("select 요소를 찾을 수 없습니다")
                    return []
                    
            except Exception as e:
                logger.error(f"매장 목록 파싱 중 오류: {str(e)}")
                self.save_screenshot("store_list_error")
                return []
            
            return stores
            
        except Exception as e:
            logger.error(f"매장 목록 조회 중 오류: {str(e)}")
            self.save_screenshot("store_list_error")
            return []

    def select_store(self, platform_code: str) -> bool:
        """매장 선택"""
        try:
            logger.info(f"매장 선택 시도: {platform_code}")
            
            # 셀프서비스 페이지에서 매장 선택
            select_element = self.page.query_selector('select')
            if select_element:
                select_element.select_option(platform_code)
                logger.info(f"매장 {platform_code} 선택 완료")
                self.page.wait_for_timeout(2000)  # 페이지 로드 대기
                return True
            else:
                logger.error("매장 선택 select 요소를 찾을 수 없습니다")
                return False
                
        except Exception as e:
            logger.error(f"매장 선택 중 오류: {str(e)}")
            return False
            
    def get_store_info(self) -> Dict[str, Any]:
        """현재 선택된 매장 정보 가져오기"""
        try:
            logger.info("매장 정보 조회 시작")
            
            # 현재 선택된 매장의 정보를 가져옴
            store_info = {
                'platform': 'baemin',
                'store_name': '',
                'business_hours': {},
                'store_address': '',
                'store_phone': ''
            }
            
            # TODO: 실제 매장 정보 페이지에서 정보 추출 로직 구현
            # 현재는 기본값 반환
            
            return store_info
            
        except Exception as e:
            logger.error(f"매장 정보 조회 중 오류: {str(e)}")
            return {}
            
    def get_reviews(self, limit: int = 50) -> List[Dict[str, Any]]:
        """리뷰 목록 가져오기"""
        try:
            logger.info(f"리뷰 목록 조회 시작 (최대 {limit}개)")
            
            reviews = []
            
            # TODO: 실제 리뷰 페이지로 이동하여 리뷰 목록 추출 로직 구현
            # 현재는 빈 리스트 반환
            
            logger.info(f"총 {len(reviews)}개의 리뷰 조회 완료")
            return reviews
            
        except Exception as e:
            logger.error(f"리뷰 목록 조회 중 오류: {str(e)}")
            return []
            
    def post_reply(self, review_id: str, reply_text: str) -> bool:
        """리뷰에 답글 작성"""
        try:
            logger.info(f"리뷰 {review_id}에 답글 작성 시작")
            
            # TODO: 실제 답글 작성 로직 구현
            # 현재는 False 반환
            
            logger.warning("답글 작성 기능이 아직 구현되지 않았습니다")
            return False
            
        except Exception as e:
            logger.error(f"답글 작성 중 오류: {str(e)}")
            return False


# 테스트 코드
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    crawler = BaeminSyncCrawler(headless=False)
    try:
        crawler.start_browser()
        print("브라우저 시작 완료")
        
        # 직접 아이디/비밀번호 입력 (테스트용)
        user_id = "hong7704002646"
        password = "bin986200#"
        
        login_success = crawler.login(user_id, password)
        print(f"로그인 결과: {login_success}")
        
        if login_success:
            stores = crawler.get_store_list()
            print(f"\n발견된 매장 목록:")
            for store in stores:
                print(f"- {store['store_name']} (코드: {store['platform_code']}, 카테고리: {store.get('category', '')})")
        
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        input("\n브라우저를 닫으려면 Enter를 누르세요...")
        crawler.close_browser()