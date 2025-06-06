"""
Windows 환경 전용 동기 크롤러 구현
Playwright sync API를 사용하여 Windows 호환성 문제 해결
"""
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright, Page, Browser, Playwright, BrowserContext
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class WindowsSyncBaseCrawler(ABC):
    """Windows 전용 동기 크롤러 베이스 클래스"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.logged_in = False
        self.platform_name = self.__class__.__name__.replace('SyncCrawler', '').lower()
        
        # 스크린샷 저장 경로
        self.screenshot_dir = Path(f"C:/Review_playwright/logs/screenshots/{self.platform_name}")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
    def start_browser(self):
        """브라우저 시작"""
        try:
            logger.info(f"Starting {self.platform_name} browser in sync mode...")
            
            self.playwright = sync_playwright().start()
            
            # 브라우저 실행 옵션
            launch_options = {
                'headless': self.headless,
                'args': [
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process'
                ]
            }
            
            # 브라우저 시작
            self.browser = self.playwright.chromium.launch(**launch_options)
            
            # 컨텍스트 생성
            self.context = self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                ignore_https_errors=True
            )
            
            # 페이지 생성
            self.page = self.context.new_page()
            self.page.set_default_timeout(30000)
            
            logger.info(f"{self.platform_name} browser started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start browser: {str(e)}")
            self.close_browser()
            raise
            
    def close_browser(self):
        """브라우저 종료"""
        try:
            if self.page:
                self.page.close()
                self.page = None
                
            if self.context:
                self.context.close()
                self.context = None
                
            if self.browser:
                self.browser.close()
                self.browser = None
                
            if self.playwright:
                self.playwright.stop()
                self.playwright = None
                
            logger.info(f"{self.platform_name} browser closed")
            
        except Exception as e:
            logger.error(f"Error closing browser: {str(e)}")
            
    def save_screenshot(self, name: str):
        """스크린샷 저장"""
        if not self.page:
            return
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}.png"
            filepath = self.screenshot_dir / filename
            
            self.page.screenshot(path=str(filepath))
            logger.info(f"Screenshot saved: {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save screenshot: {str(e)}")
            
    def wait_and_click(self, selector: str, timeout: int = 5000):
        """요소 대기 후 클릭"""
        try:
            self.page.wait_for_selector(selector, timeout=timeout)
            self.page.click(selector)
            return True
        except Exception as e:
            logger.error(f"Failed to click {selector}: {str(e)}")
            return False
            
    def wait_and_type(self, selector: str, text: str, timeout: int = 5000):
        """요소 대기 후 입력"""
        try:
            self.page.wait_for_selector(selector, timeout=timeout)
            self.page.fill(selector, text)
            return True
        except Exception as e:
            logger.error(f"Failed to type in {selector}: {str(e)}")
            return False
            
    @abstractmethod
    def login(self, username: str, password: str) -> bool:
        """로그인 메서드 (각 플랫폼별 구현 필요)"""
        pass
        
    @abstractmethod
    def get_store_list(self) -> List[Dict[str, Any]]:
        """매장 목록 가져오기"""
        pass
        
    @abstractmethod
    def select_store(self, platform_code: str) -> bool:
        """매장 선택"""
        pass
        
    @abstractmethod
    def get_store_info(self) -> Dict[str, Any]:
        """현재 선택된 매장 정보 가져오기"""
        pass
        
    @abstractmethod
    def get_reviews(self, limit: int = 50) -> List[Dict[str, Any]]:
        """리뷰 목록 가져오기"""
        pass
        
    @abstractmethod
    def post_reply(self, review_id: str, reply_text: str) -> bool:
        """리뷰에 답글 작성"""
        pass


class WindowsCrawlerAdapter:
    """비동기 크롤러를 동기 크롤러로 변환하는 어댑터"""
    
    def __init__(self, sync_crawler_class, headless: bool = True):
        self.sync_crawler = None
        self.sync_crawler_class = sync_crawler_class
        self.headless = headless
        
    def __enter__(self):
        self.sync_crawler = self.sync_crawler_class(headless=self.headless)
        self.sync_crawler.start_browser()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.sync_crawler:
            self.sync_crawler.close_browser()
            
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        self.__enter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        self.__exit__(exc_type, exc_val, exc_tb)
        
    async def start_browser(self):
        """비동기 인터페이스로 브라우저 시작"""
        if not self.sync_crawler:
            self.sync_crawler = self.sync_crawler_class(headless=self.headless)
        self.sync_crawler.start_browser()
        
    async def close_browser(self):
        """비동기 인터페이스로 브라우저 종료"""
        if self.sync_crawler:
            self.sync_crawler.close_browser()
            
    async def login(self, username: str, password: str) -> bool:
        """비동기 인터페이스로 로그인"""
        return self.sync_crawler.login(username, password)
        
    async def get_store_list(self) -> List[Dict[str, Any]]:
        """비동기 인터페이스로 매장 목록 조회"""
        return self.sync_crawler.get_store_list()
        
    async def select_store(self, platform_code: str) -> bool:
        """비동기 인터페이스로 매장 선택"""
        return self.sync_crawler.select_store(platform_code)
        
    async def get_store_info(self) -> Dict[str, Any]:
        """비동기 인터페이스로 매장 정보 조회"""
        return self.sync_crawler.get_store_info()
        
    async def get_reviews(self, limit: int = 50) -> List[Dict[str, Any]]:
        """비동기 인터페이스로 리뷰 조회"""
        return self.sync_crawler.get_reviews(limit)
        
    async def post_reply(self, review_id: str, reply_text: str) -> bool:
        """비동기 인터페이스로 답글 작성"""
        return self.sync_crawler.post_reply(review_id, reply_text)
        
    async def save_screenshot(self, name: str):
        """비동기 인터페이스로 스크린샷 저장"""
        self.sync_crawler.save_screenshot(name)
