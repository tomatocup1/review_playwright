"""
네이버 스마트플레이스 크롤러
"""
from typing import List, Dict, Any, Optional
import asyncio
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import logging
from datetime import datetime
import os
import re
import json
import hashlib
import platform

from .base_crawler import BaseCrawler
from api.services.encryption import decrypt_password

logger = logging.getLogger(__name__)

class NaverCrawler(BaseCrawler):
    """네이버 스마트플레이스 크롤러"""
    
    def __init__(self, headless: bool = False):
        super().__init__(headless=headless)  # headless 매개변수 전달
        self.platform_name = "naver"
        self.base_url = "https://new.smartplace.naver.com"
        self.login_url = "https://nid.naver.com/nidlogin.login"
        # 브라우저 프로필 저장 경로
        self.browser_data_dir = os.path.join("logs", "browser_profiles", "naver")
        os.makedirs(self.browser_data_dir, exist_ok=True)
            
    def _get_browser_profile_path(self, platform_id: str) -> str:
        """계정별 브라우저 프로필 경로 생성"""
        # 이메일을 해시화하여 디렉토리명으로 사용
        account_hash = hashlib.md5(platform_id.encode()).hexdigest()[:10]
        profile_path = os.path.join(self.browser_data_dir, f"profile_{account_hash}")
        os.makedirs(profile_path, exist_ok=True)
        return profile_path
        
    def _get_consistent_user_agent(self) -> str:
        """일관된 User-Agent 반환"""
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    async def create_browser_context(self, p, platform_id: str, headless: bool = False) -> tuple:
        """일관된 브라우저 컨텍스트 생성"""
        # 프로필 경로
        profile_path = self._get_browser_profile_path(platform_id)
        
        # 브라우저 실행 인수 (--user-data-dir 제거)
        browser_args = [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
            '--start-maximized',
            '--disable-extensions',
            '--disable-default-apps',
            '--disable-sync',
            '--disable-translate',
            '--metrics-recording-only',
            '--safebrowsing-disable-auto-update',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-features=TranslateUI',
            '--disable-ipc-flooding-protection',
            '--password-store=basic',
            '--use-mock-keychain',
            '--force-color-profile=srgb',
        ]
        
        # 브라우저 시작
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=profile_path,  # 여기에 직접 지정
            headless=headless,
            args=browser_args,
            viewport={'width': 1280, 'height': 720},
            user_agent=self._get_consistent_user_agent(),
            locale='ko-KR',
            timezone_id='Asia/Seoul',
            permissions=[],
            ignore_https_errors=True,
            java_script_enabled=True,
            bypass_csp=True,
            extra_http_headers={
                'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
                'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"'
            }
        )
        
        # 기존 페이지가 있으면 사용, 없으면 새로 생성
        pages = browser.pages
        if pages:
            page = pages[0]
        else:
            page = await browser.new_page()
        
        # JavaScript로 자동화 감지 방지
        await browser.add_init_script("""
            // Webdriver 속성 제거
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Chrome 속성 추가
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            // 플러그인 추가
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {
                        0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        length: 1,
                        name: "Chrome PDF Plugin"
                    }
                ]
            });
            
            // 언어 설정
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ko-KR', 'ko', 'en-US', 'en']
            });
            
            // 플랫폼 설정
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32'
            });
            
            // 벤더 설정
            Object.defineProperty(navigator, 'vendor', {
                get: () => 'Google Inc.'
            });
            
            // Permission 관련 수정
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        
        return browser, browser, page  # context 대신 browser를 반환 (persistent context이므로)
    
    async def start_browser(self):
        """네이버 전용 브라우저 시작 (persistent context 사용)"""
        try:
            # Playwright 시작
            self.playwright = await async_playwright().start()
            
            # 기본 platform_id 사용 (나중에 로그인할 때 실제 계정의 프로필 사용)
            default_profile = "default"
            profile_path = os.path.join(self.browser_data_dir, default_profile)
            os.makedirs(profile_path, exist_ok=True)
            
            # 브라우저 실행 인수
            browser_args = [
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--start-maximized',
                '--disable-extensions',
                '--disable-default-apps',
                '--disable-sync',
                '--disable-translate',
                '--metrics-recording-only',
                '--safebrowsing-disable-auto-update',
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
            self.browser = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=profile_path,
                headless=self.headless,
                args=browser_args,
                viewport={'width': 1280, 'height': 720},
                user_agent=self._get_consistent_user_agent(),
                locale='ko-KR',
                timezone_id='Asia/Seoul',
                permissions=[],
                ignore_https_errors=True,
                java_script_enabled=True,
                bypass_csp=True,
                extra_http_headers={
                    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
                    'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"Windows"'
                }
            )
            
            # 기존 페이지가 있으면 사용, 없으면 새로 생성
            pages = self.browser.pages
            if pages:
                self.page = pages[0]
            else:
                self.page = await self.browser.new_page()
            
            # 타임아웃 설정
            self.page.set_default_timeout(30000)  # 30초
            
            # JavaScript로 자동화 감지 방지
            await self.browser.add_init_script("""
                // Webdriver 속성 제거
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Chrome 속성 추가
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
                
                // 플러그인 추가
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {
                            0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "Chrome PDF Plugin"
                        }
                    ]
                });
                
                // 언어 설정
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ko-KR', 'ko', 'en-US', 'en']
                });
                
                // 플랫폼 설정
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Win32'
                });
                
                // 벤더 설정
                Object.defineProperty(navigator, 'vendor', {
                    get: () => 'Google Inc.'
                });
                
                // Permission 관련 수정
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)
            
            logger.info(f"{self.platform_name} 브라우저 시작 완료 (persistent context)")
        except Exception as e:
            logger.error(f"브라우저 시작 실패: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            await self.close_browser()
            raise

    async def login(self, page: Page, platform_id: str, platform_pw: str) -> bool:
        """네이버 로그인"""
        try:
            logger.info(f"네이버 로그인 시작: {platform_id}")
            
            # 로그인 페이지로 이동
            await page.goto(self.login_url, wait_until="domcontentloaded")
            await asyncio.sleep(1)  # 2초에서 1초로 단축
            
            # 이미 로그인되어 있는지 확인
            current_url = page.url
            if "nid.naver.com/nidlogin.login" not in current_url:
                logger.info("이미 로그인된 상태")
                # 스마트플레이스로 바로 이동
                await page.goto(self.base_url, wait_until="domcontentloaded")
                await asyncio.sleep(1)  # 2초에서 1초로 단축
                return True
            
            # 스크린샷 저장 디렉토리 설정
            screenshot_dir = os.path.join("logs", "screenshots", "naver")
            os.makedirs(screenshot_dir, exist_ok=True)
            
            # 아이디 입력
            await page.wait_for_selector("#id", state="visible", timeout=5000)
            await page.click("#id")
            # 기존 값 삭제
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Delete")
            await page.type("#id", platform_id, delay=50)  # delay 100에서 50으로 단축
            
            # 비밀번호 입력
            await page.click("#pw")
            # 기존 값 삭제
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Delete")
            
            # 비밀번호 처리
            if platform_pw.startswith("gAAAAA"):
                logger.warning("암호화된 비밀번호 감지, 복호화 시도")
                try:
                    from api.services.encryption import decrypt_password
                    decrypted_pw = decrypt_password(platform_pw)
                except Exception as e:
                    logger.error(f"복호화 실패: {str(e)}")
                    decrypted_pw = platform_pw
            else:
                decrypted_pw = platform_pw
            
            await page.type("#pw", decrypted_pw, delay=50)  # delay 100에서 50으로 단축
            
            # 로그인 버튼 클릭
            await page.click("#log\\.login")
            logger.info("로그인 버튼 클릭")
            
            # 페이지 전환 대기 - wait_for_navigation 사용
            try:
                await page.wait_for_navigation(timeout=10000)  # 명시적 navigation 대기
            except:
                await asyncio.sleep(2)  # navigation 실패 시에만 대기
            
            # 현재 URL 확인
            current_url = page.url
            logger.info(f"로그인 후 URL: {current_url}")
            
            # 기기 등록 확인 페이지 처리
            if "deviceConfirm" in current_url:
                logger.info("기기 등록 확인 페이지 감지")
                
                try:
                    # 등록 버튼 클릭
                    await page.wait_for_selector("#new\\.save", timeout=5000)
                    await page.click("#new\\.save")
                    logger.info("기기 등록 버튼 클릭 완료")
                    
                    await page.wait_for_navigation(timeout=5000)  # 페이지 전환 대기
                    
                    # 프로필에 기기 등록 정보 저장
                    profile_info_file = os.path.join(self._get_browser_profile_path(platform_id), "device_registered.json")
                    with open(profile_info_file, 'w') as f:
                        json.dump({
                            "registered": True,
                            "date": datetime.now().isoformat(),
                            "platform_id": platform_id
                        }, f)
                    
                except Exception as e:
                    logger.error(f"기기 등록 버튼 클릭 실패: {str(e)}")
            
            # 2차 인증 페이지 확인
            current_url = page.url
            if "nid.naver.com/login/ext/need2" in current_url:
                logger.warning("2차 인증 필요")
                return False
            
            # 스마트플레이스로 이동
            await page.goto(self.base_url, wait_until="domcontentloaded")
            await asyncio.sleep(2)  # 3초에서 2초로 단축
            
            # 로그인 상태 확인
            current_url = page.url
            if "smartplace.naver.com" in current_url:
                try:
                    # 로그인 버튼이 있는지 확인
                    login_button = await page.query_selector("a[href*='login']")
                    if login_button:
                        logger.error("로그인 버튼이 존재 - 로그인 실패")
                        return False
                    
                    logger.info("네이버 로그인 성공")
                    return True
                    
                except:
                    logger.info("로그인 상태 확인 중 에러, 성공으로 간주")
                    return True
            else:
                logger.error(f"스마트플레이스 진입 실패 - 현재 URL: {current_url}")
                return False
                
        except Exception as e:
            logger.error(f"네이버 로그인 중 오류: {str(e)}")
            try:
                screenshot_dir = os.path.join("logs", "screenshots", "naver", "errors")
                os.makedirs(screenshot_dir, exist_ok=True)
                await page.screenshot(
                    path=os.path.join(screenshot_dir, f"login_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                )
            except:
                pass
            return False
            
    async def get_stores(self, page: Page) -> List[Dict[str, Any]]:
        """네이버 스마트플레이스에서 매장 목록 가져오기"""
        try:
            stores = []
            
            # 이미 스마트플레이스 페이지에 있는지 확인
            if "smartplace.naver.com" not in page.url:
                await page.goto(self.base_url, wait_until="networkidle")
                await asyncio.sleep(2)
            
            # 내 업체 섹션 찾기
            try:
                await page.wait_for_selector(".Main_my_business__XkbsM", timeout=15000)
                
                # 모든 업체 정보를 먼저 수집 (DOM 요소가 사라지기 전에)
                store_infos = await page.evaluate("""
                    () => {
                        const stores = [];
                        const cards = document.querySelectorAll('.Main_my_business__XkbsM .Main_card_item__bTDIT');
                        
                        cards.forEach((card, index) => {
                            const nameElement = card.querySelector('.Main_title__P_c6n');
                            const name = nameElement ? nameElement.textContent.trim() : `매장${index + 1}`;
                            
                            // href에서 매장 코드 추출 시도
                            const linkElement = card.querySelector('a');
                            let code = null;
                            if (linkElement && linkElement.href) {
                                const match = linkElement.href.match(/\/bizes\/place\/(\d+)/);
                                if (match) {
                                    code = match[1];
                                }
                            }
                            
                            stores.push({
                                name: name,
                                code: code,
                                index: index
                            });
                        });
                        
                        return stores;
                    }
                """)
                
                logger.info(f"발견된 내 업체 수: {len(store_infos)}")
                
                # 수집된 정보를 바탕으로 처리
                for store_info in store_infos:
                    try:
                        if store_info['code']:
                            # 이미 코드가 있으면 바로 추가
                            store_data = {
                                "store_name": store_info['name'],  # name → store_name으로 변경
                                "platform_code": store_info['code'],
                                "url": f"https://new.smartplace.naver.com/bizes/place/{store_info['code']}",
                                "platform": "naver",
                                "store_type": "스마트플레이스",
                                "category": None,
                                "brand_name": None,
                                "status": "영업중"
                            }
                            stores.append(store_data)
                            logger.info(f"업체 정보 추출 성공 (href): {store_data}")
                        else:
                            # 코드가 없으면 클릭해서 가져오기
                            # 매번 새로 요소를 찾기
                            cards = await page.query_selector_all('.Main_my_business__XkbsM .Main_card_item__bTDIT')
                            if store_info['index'] < len(cards):
                                card = cards[store_info['index']]
                                await card.click()
                                await asyncio.sleep(1)
                                
                                # URL 변경 대기
                                try:
                                    await page.wait_for_function(
                                        "window.location.href.includes('/bizes/place/')",
                                        timeout=3000
                                    )
                                except:
                                    logger.warning(f"업체 {store_info['name']} URL 변경 대기 실패")
                                    continue
                                
                                # URL에서 업체 코드 추출
                                current_url = page.url
                                match = re.search(r'/bizes/place/(\d+)', current_url)
                                
                                if match:
                                    store_code = match.group(1)
                                    store_data = {
                                        "store_name": store_info['name'],  # name → store_name으로 변경
                                        "platform_code": store_code,
                                        "url": current_url,
                                        "platform": "naver",
                                        "store_type": "스마트플레이스",
                                        "category": None,
                                        "brand_name": None,
                                        "status": "영업중"
                                    }
                                    stores.append(store_data)
                                    logger.info(f"업체 정보 추출 성공 (클릭): {store_data}")
                                
                                # 다음 매장을 위해 뒤로가기
                                await page.go_back()
                                await asyncio.sleep(1)
                                # 내 업체 섹션이 다시 로드될 때까지 대기
                                await page.wait_for_selector(".Main_my_business__XkbsM", timeout=5000)
                            
                    except Exception as e:
                        logger.error(f"업체 정보 추출 중 오류 ({store_info['name']}): {str(e)}")
                        continue
                        
            except Exception as e:
                logger.error(f"내 업체 섹션 처리 중 오류: {str(e)}")
                return []
            
            logger.info(f"총 {len(stores)}개의 내 업체 정보 추출 완료")
            return stores
            
        except Exception as e:
            logger.error(f"네이버 매장 목록 가져오기 중 오류: {str(e)}")
        return []
    
    # BaseCrawler의 추상 메서드 구현 (기존과 동일)
    async def get_store_list(self) -> List[Dict[str, Any]]:
        """매장 목록 가져오기 (BaseCrawler 호환)"""
        if self.page:
            return await self.get_stores(self.page)
        else:
            logger.error("페이지 객체가 없습니다. login을 먼저 수행하세요.")
            return []
    
    async def select_store(self, store_id: str) -> bool:
        """매장 선택 (BaseCrawler 호환)"""
        try:
            store_url = f"https://new.smartplace.naver.com/bizes/place/{store_id}"
            await self.page.goto(store_url, wait_until="networkidle")
            await asyncio.sleep(2)
            logger.info(f"매장 선택 완료: {store_id}")
            return True
        except Exception as e:
            logger.error(f"매장 선택 실패: {str(e)}")
            return False
    
    async def get_store_info(self, store_id: str) -> Optional[Dict[str, Any]]:
        """매장 정보 가져오기 (BaseCrawler 호환)"""
        try:
            if await self.select_store(store_id):
                return {
                    "store_id": store_id,
                    "platform": "naver",
                    "url": self.page.url
                }
            return None
        except Exception as e:
            logger.error(f"매장 정보 가져오기 실패: {str(e)}")
            return None
    
    async def get_reviews(self, store_id: str, count: int = 100) -> List[Dict[str, Any]]:
        """리뷰 가져오기 (BaseCrawler 호환)"""
        return await self.crawl_reviews(self.page, store_id, store_code=None)
            
    async def crawl_reviews(self, page: Page, platform_code: str, store_code: str = None) -> List[Dict[str, Any]]:
        """네이버 스마트플레이스 리뷰 크롤링"""
        from .review_parsers.naver_review_parser import NaverReviewParser
        
        reviews = []
        parser = NaverReviewParser()
        
        try:
            # 리뷰 페이지로 이동
            review_url = f"https://new.smartplace.naver.com/bizes/place/{platform_code}/reviews"
            logger.info(f"리뷰 페이지로 이동: {review_url}")
            await page.goto(review_url, wait_until="networkidle")
            await page.wait_for_timeout(3000)
            
            # 기간 선택 버튼 클릭 (7일 선택)
            try:
                period_button = await page.wait_for_selector('button[data-area-code="rv.calendarfilter"]', timeout=5000)
                await period_button.click()
                await page.wait_for_timeout(1000)
                
                # 7일 옵션 선택
                seven_days_option = await page.wait_for_selector('a[data-area-code="rv.calendarweek"]', timeout=3000)
                await seven_days_option.click()
                await page.wait_for_timeout(2000)
            except:
                logger.info("기간 선택 버튼을 찾을 수 없습니다. 기본 기간으로 진행합니다.")
            
            # 스크롤하면서 모든 리뷰 로드
            last_review_count = 0
            scroll_attempts = 0
            max_scroll_attempts = 50
            
            while scroll_attempts < max_scroll_attempts:
                # 현재 리뷰 개수 확인
                review_elements = await page.query_selector_all('li.pui__X35jYm.Review_pui_review__zhZdn')
                current_review_count = len(review_elements)
                
                if current_review_count == last_review_count:
                    # 더 이상 새로운 리뷰가 로드되지 않음
                    break
                    
                last_review_count = current_review_count
                
                # 페이지 스크롤
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await page.wait_for_timeout(2000)
                scroll_attempts += 1
                
                logger.info(f"스크롤 {scroll_attempts}회 - 현재 리뷰 수: {current_review_count}")
            
            # 모든 리뷰 파싱
            review_elements = await page.query_selector_all('li.pui__X35jYm.Review_pui_review__zhZdn')
            logger.info(f"총 {len(review_elements)}개의 리뷰 발견")
            
            for idx, review_element in enumerate(review_elements):
                try:
                    # 더보기 버튼 처리
                    more_button = await review_element.query_selector('a.pui__wFzIYl[data-pui-click-code="text"]')
                    if more_button:
                        await more_button.click()
                        await page.wait_for_timeout(500)
                    
                    # 태그 더보기 버튼 처리
                    tag_more_button = await review_element.query_selector('a.pui__jhpEyP.pui__ggzZJ8[data-pui-click-code="rv.keywordmore"]')
                    if tag_more_button:
                        await tag_more_button.click()
                        await page.wait_for_timeout(500)
                    
                    # 리뷰 데이터 추출 부분 (665번 라인 근처)
                    # store_code가 전달되면 사용하고, 없으면 platform_code 사용
                    review_data = await parser.parse_review_element(page, review_element, store_code or platform_code)
                    if review_data:
                        reviews.append(review_data)
                        logger.info(f"리뷰 {idx + 1} 파싱 완료")
                        
                except Exception as e:
                    logger.error(f"리뷰 {idx + 1} 파싱 중 오류: {str(e)}")
                    continue
            
            logger.info(f"총 {len(reviews)}개의 리뷰 파싱 완료")
            
            # 스크린샷 저장
            screenshot_path = os.path.join("logs", "screenshots", "naver", f"reviews_{platform_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            await page.screenshot(path=screenshot_path)
            
            return reviews
            
        except Exception as e:
            logger.error(f"리뷰 크롤링 중 오류 발생: {str(e)}")
            # 에러 스크린샷 저장
            error_screenshot_path = os.path.join("logs", "screenshots", "errors", f"naver_reviews_error_{platform_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            os.makedirs(os.path.dirname(error_screenshot_path), exist_ok=True)
            await page.screenshot(path=error_screenshot_path)
            raise

    async def _expand_review_content(self, page: Page):
        """리뷰 내용 더보기 버튼 모두 클릭"""
        try:
            # 모든 더보기 버튼 찾기
            more_buttons = await page.query_selector_all('a.pui__wFzIYl[data-pui-click-code="text"]')
            
            for button in more_buttons:
                try:
                    is_visible = await button.is_visible()
                    if is_visible:
                        await button.click()
                        await asyncio.sleep(0.3)
                except Exception:
                    continue
                    
            logger.info(f"{len(more_buttons)}개의 더보기 버튼 처리")
            
        except Exception as e:
            logger.warning(f"더보기 버튼 처리 실패: {str(e)}")

    async def _expand_review_keywords(self, page: Page):
        """키워드 펼쳐보기 버튼 모두 클릭"""
        try:
            # 키워드 더보기 버튼 찾기
            keyword_buttons = await page.query_selector_all('a.pui__ggzZJ8[data-pui-click-code="rv.keywordmore"]')
            
            for button in keyword_buttons:
                try:
                    is_visible = await button.is_visible()
                    if is_visible:
                        await button.click()
                        await asyncio.sleep(0.3)
                except Exception:
                    continue
                    
            logger.info(f"{len(keyword_buttons)}개의 키워드 펼치기 처리")
            
        except Exception as e:
            logger.warning(f"키워드 펼치기 처리 실패: {str(e)}")

    async def _check_and_load_more_reviews(self, page: Page) -> bool:
        """더 많은 리뷰 로드 (스크롤 방식)"""
        try:
            # 현재 리뷰 개수
            before_count = len(await page.query_selector_all('li.pui__X35jYm.Review_pui_review__zhZdn'))
            
            # 페이지 끝까지 스크롤
            await page.evaluate("""
                window.scrollTo({
                    top: document.body.scrollHeight,
                    behavior: 'smooth'
                });
            """)
            
            await asyncio.sleep(3)
            
            # 스크롤 후 리뷰 개수
            after_count = len(await page.query_selector_all('li.pui__X35jYm.Review_pui_review__zhZdn'))
            
            # 리뷰가 추가로 로드되었는지 확인
            return after_count > before_count
            
        except Exception as e:
            logger.warning(f"추가 리뷰 로드 확인 실패: {str(e)}")
            return False

    async def capture_screenshot(self, page: Page, filename: str):
        """스크린샷 캡처"""
        try:
            screenshot_dir = os.path.join("logs", "screenshots", "naver")
            os.makedirs(screenshot_dir, exist_ok=True)
            
            screenshot_path = os.path.join(screenshot_dir, f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            await page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"스크린샷 저장: {screenshot_path}")
            
        except Exception as e:
            logger.error(f"스크린샷 저장 실패: {str(e)}")
        
    async def post_reply(self, page: Page, review_id: str, reply_text: str) -> bool:
        """네이버 답글 등록 (추후 구현)"""
        logger.info(f"네이버 답글 등록 - 추후 구현 예정: {review_id}")
        return False