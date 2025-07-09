"""
Windows 환경을 위한 비동기 크롤러 래퍼
asyncio 이벤트 루프 문제를 해결하기 위한 특별한 처리
"""
import sys
import asyncio, sys
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright, Page, Browser, Playwright, BrowserContext
from abc import ABC, abstractmethod

# Windows에서 asyncio 이벤트 루프 정책 설정
if sys.platform == 'win32':
    # ProactorEventLoop를 사용하여 subprocess 문제 해결
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

logger = logging.getLogger(__name__)

class WindowsAsyncBaseCrawler(ABC):
    """Windows 전용 비동기 크롤러 베이스 클래스"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.logged_in = False
        self.platform_name = self.__class__.__name__.replace('AsyncCrawler', '').lower()
        
        # 스크린샷 저장 경로
        self.screenshot_dir = Path(f"C:/Review_playwright/logs/screenshots/{self.platform_name}")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
    async def start_browser(self, max_retries: int = 3):
        """브라우저 시작 (재시도 로직 포함)"""
        for attempt in range(max_retries):
            try:
                logger.info(f"Starting {self.platform_name} browser in async mode (Windows)... (attempt {attempt + 1}/{max_retries})")
                
                # 이전 시도의 리소스 정리
                if attempt > 0:
                    await self.close_browser()
                    await asyncio.sleep(2)  # 잠시 대기
                
                self.playwright = await asyncio.wait_for(
                    async_playwright().start(), 
                    timeout=30.0
                )
                
                # 브라우저 실행 옵션
                launch_options = {
                    'headless': self.headless,
                    'timeout': 60000,  # 60초 타임아웃
                    'args': [
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-gpu',
                        '--disable-web-security',
                        '--disable-features=IsolateOrigins,site-per-process',
                        '--single-process',  # 단일 프로세스 모드
                        '--disable-background-timer-throttling',
                        '--disable-backgrounding-occluded-windows',
                        '--disable-renderer-backgrounding'
                    ]
                }
                
                # 브라우저 시작
                self.browser = await asyncio.wait_for(
                    self.playwright.chromium.launch(**launch_options),
                    timeout=60.0
                )
                
                # 컨텍스트 생성
                self.context = await self.browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080},
                    ignore_https_errors=True
                )
                
                # 페이지 생성
                self.page = await self.context.new_page()
                self.page.set_default_timeout(30000)
                
                logger.info(f"{self.platform_name} browser started successfully")
                return  # 성공시 반환
                
            except asyncio.TimeoutError:
                logger.warning(f"Browser start timeout (attempt {attempt + 1}/{max_retries})")
                await self.close_browser()
                if attempt == max_retries - 1:
                    raise Exception("브라우저 시작 타임아웃")
                    
            except Exception as e:
                logger.error(f"Failed to start browser (attempt {attempt + 1}/{max_retries}): {str(e)}")
                await self.close_browser()
                if attempt == max_retries - 1:
                    raise Exception(f"브라우저 시작 실패: {str(e)}")
                    
                # 다음 시도 전 잠시 대기
                await asyncio.sleep(3)
            
    async def close_browser(self):
        """브라우저 종료"""
        try:
            if self.page:
                await self.page.close()
                self.page = None
                
            if self.context:
                await self.context.close()
                self.context = None
                
            if self.browser:
                await self.browser.close()
                self.browser = None
                
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
                
            logger.info(f"{self.platform_name} browser closed")
            
        except Exception as e:
            logger.error(f"Error closing browser: {str(e)}")
            
    async def save_screenshot(self, name: str):
        """스크린샷 저장"""
        if not self.page:
            return
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}.png"
            filepath = self.screenshot_dir / filename
            
            await self.page.screenshot(path=str(filepath))
            logger.info(f"Screenshot saved: {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save screenshot: {str(e)}")
            
    async def wait_and_click(self, selector: str, timeout: int = 5000):
        """요소 대기 후 클릭"""
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            await self.page.click(selector)
            return True
        except Exception as e:
            logger.error(f"Failed to click {selector}: {str(e)}")
            return False
            
    async def wait_and_type(self, selector: str, text: str, timeout: int = 5000):
        """요소 대기 후 입력"""
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            await self.page.fill(selector, text)
            return True
        except Exception as e:
            logger.error(f"Failed to type in {selector}: {str(e)}")
            return False
            
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
