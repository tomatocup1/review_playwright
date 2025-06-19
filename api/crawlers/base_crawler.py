"""
베이스 크롤러 클래스
모든 플랫폼별 크롤러가 상속받는 기본 클래스
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio
import sys
from playwright.async_api import async_playwright, Page, Browser, Playwright
import logging
from pathlib import Path
import nest_asyncio
from ..utils.error_handler import log_login_error, log_crawling_error, log_reply_error, ErrorType

# Windows에서 asyncio 중첩 실행 허용
nest_asyncio.apply()

# Windows 전용 설정
if sys.platform == 'win32':
    # ProactorEventLoop 대신 SelectorEventLoop 사용
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 로거 설정
logger = logging.getLogger(__name__)

class BaseCrawler(ABC):
    """플랫폼 크롤러 베이스 클래스"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.logged_in = False
        self.platform_name = self.__class__.__name__.replace('Crawler', '').lower()
        self.platform = self.platform_name  # 에러 처리를 위한 속성 추가
        
        # 스크린샷 저장 경로
        self.screenshot_dir = Path(f"C:/Review_playwright/logs/screenshots/{self.platform_name}")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        # 에러 스크린샷 저장 경로
        self.error_screenshot_dir = Path(f"C:/Review_playwright/logs/screenshots/errors/{self.platform_name}")
        self.error_screenshot_dir.mkdir(parents=True, exist_ok=True)
    
    async def __aenter__(self):
        await self.start_browser()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_browser()
    
    async def start_browser(self):
        """브라우저 시작"""
        try:
            # Windows에서 안정적인 실행을 위해 이벤트 루프 확인
            try:
                loop = asyncio.get_running_loop()
                if sys.platform == 'win32' and isinstance(loop, asyncio.ProactorEventLoop):
                    logger.warning("ProactorEventLoop detected, switching to SelectorEventLoop")
                    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            except:
                pass
            
            self.playwright = await async_playwright().start()
            
            # 브라우저 실행 옵션
            launch_options = {
                'headless': self.headless,
                'args': [
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-gpu'
                ]
            }
            
            # Windows에서 추가 옵션
            if sys.platform == 'win32':
                launch_options['handle_sigint'] = False
                launch_options['handle_sigterm'] = False
                launch_options['handle_sighup'] = False
            
            self.browser = await self.playwright.chromium.launch(**launch_options)
            
            # 브라우저 컨텍스트 생성 (더 안정적)
            context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                ignore_https_errors=True
            )
            
            self.page = await context.new_page()
            
            # 타임아웃 설정
            self.page.set_default_timeout(30000)  # 30초
            
            logger.info(f"{self.platform_name} 브라우저 시작 완료")
        except Exception as e:
            logger.error(f"브라우저 시작 실패: {str(e)}")
            # 실패 시 정리
            await self.close_browser()
            raise
    
    async def close_browser(self):
        """브라우저 종료"""
        try:
            if self.page:
                try:
                    await self.page.close()
                except:
                    pass
                self.page = None
            
            if self.browser:
                try:
                    await self.browser.close()
                except:
                    pass
                self.browser = None
            
            if self.playwright:
                try:
                    await self.playwright.stop()
                except:
                    pass
                self.playwright = None
            
            logger.info(f"{self.platform_name} 브라우저 종료 완료")
        except Exception as e:
            logger.error(f"브라우저 종료 중 오류: {str(e)}")
    
    async def save_screenshot(self, name: str):
        """스크린샷 저장"""
        if not self.page:
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}.png"
            filepath = self.screenshot_dir / filename
            
            await self.page.screenshot(path=str(filepath))
            logger.info(f"스크린샷 저장: {filepath}")
        except Exception as e:
            logger.error(f"스크린샷 저장 실패: {str(e)}")
    
    async def save_error_screenshot(self, error_type: str):
        """에러 스크린샷 저장"""
        if not self.page:
            return None
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"error_{error_type}_{timestamp}.png"
            filepath = self.error_screenshot_dir / filename
            
            await self.page.screenshot(path=str(filepath), full_page=True)
            logger.info(f"에러 스크린샷 저장: {filepath}")
            return str(filepath)
        except Exception as e:
            logger.error(f"에러 스크린샷 저장 실패: {str(e)}")
            return None
    
    async def wait_and_click(self, selector: str, timeout: int = 5000):
        """요소 대기 후 클릭"""
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            await self.page.click(selector)
            return True
        except Exception as e:
            logger.error(f"클릭 실패 {selector}: {str(e)}")
            return False
    
    async def wait_and_type(self, selector: str, text: str, timeout: int = 5000):
        """요소 대기 후 입력"""
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            await self.page.fill(selector, text)
            return True
        except Exception as e:
            logger.error(f"입력 실패 {selector}: {str(e)}")
            return False
    
    async def handle_error(self, error_type: str, error_message: str, **kwargs):
        """에러 처리 및 로깅"""
        # 로컬 파일 로깅
        logger.error(f"{self.platform} 크롤러 에러 - {error_type}: {error_message}")
        
        # 스크린샷 저장 (가능한 경우)
        screenshot_path = None
        if hasattr(self, 'page') and self.page:
            try:
                screenshot_path = await self.save_error_screenshot(error_type)
            except:
                pass
        
        # 현재 URL 가져오기
        current_url = None
        if hasattr(self, 'page') and self.page:
            try:
                current_url = self.page.url
            except:
                pass
        
        # DB 로깅을 위한 데이터 준비
        error_data = {
            "platform": self.platform,
            "error_type": error_type,
            "error_message": error_message,
            "screenshot_path": screenshot_path,
            "current_url": current_url,
            **kwargs
        }
        
        # 에러 데이터 반환 (상위에서 DB 로깅)
        return error_data
    
    async def safe_execute(self, func, *args, **kwargs):
        """안전한 함수 실행 (타임아웃 및 재시도 포함)"""
        max_retries = kwargs.pop('max_retries', 3)
        timeout = kwargs.pop('timeout', 30000)  # 30초
        retry_delay_base = kwargs.pop('retry_delay_base', 2)  # 기본 재시도 대기 시간
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # 타임아웃 설정
                if hasattr(self, 'page') and self.page:
                    self.page.set_default_timeout(timeout)
                
                # 함수가 코루틴인지 확인
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                return result
                
            except asyncio.TimeoutError as e:
                last_error = e
                error_msg = f"타임아웃 발생 (시도 {attempt + 1}/{max_retries})"
                logger.warning(f"{self.platform} - {error_msg}")
                
                if attempt < max_retries - 1:
                    # 재시도 전 대기 (지수 백오프)
                    wait_time = retry_delay_base * (2 ** attempt)  # 2, 4, 8초
                    logger.info(f"{wait_time}초 후 재시도...")
                    await asyncio.sleep(wait_time)
                    
                    # 페이지 새로고침 시도
                    if hasattr(self, 'page') and self.page:
                        try:
                            await self.page.reload()
                        except:
                            pass
                            
            except Exception as e:
                last_error = e
                error_msg = str(e)
                logger.warning(f"{self.platform} - 시도 {attempt + 1}/{max_retries} 실패: {error_msg}")
                
                if attempt < max_retries - 1:
                    # 재시도 전 대기
                    wait_time = retry_delay_base * (attempt + 1)  # 2, 4, 6초
                    logger.info(f"{wait_time}초 후 재시도...")
                    await asyncio.sleep(wait_time)
        
        # 최종 실패
        raise Exception(f"최대 재시도 횟수 {max_retries}회 초과. 마지막 에러: {str(last_error)}")
    
    async def check_login_status(self) -> bool:
        """로그인 상태 확인 (각 플랫폼별로 오버라이드 가능)"""
        return self.logged_in
    
    async def handle_popup(self):
        """팝업 처리 (각 플랫폼별로 오버라이드 가능)"""
        pass
    
    @abstractmethod
    async def login(self, username: str, password: str) -> bool:
        """로그인 메서드 (각 플랫폼별 구현 필요)"""
        pass
    
    @abstractmethod
    async def get_store_list(self) -> List[Dict[str, Any]]:
        """매장 목록 가져오기"""
        pass
    
    @abstractmethod
    async def select_store(self, platform_code: str) -> bool:
        """매장 선택"""
        pass
    
    @abstractmethod
    async def get_store_info(self) -> Dict[str, Any]:
        """현재 선택된 매장 정보 가져오기"""
        pass
    
    @abstractmethod
    async def get_reviews(self, limit: int = 50) -> List[Dict[str, Any]]:
        """리뷰 목록 가져오기"""
        pass
    
    @abstractmethod
    async def post_reply(self, review_id: str, reply_text: str) -> bool:
        """리뷰에 답글 작성"""
        pass