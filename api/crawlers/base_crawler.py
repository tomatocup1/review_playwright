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

# Windows에서 asyncio 이벤트 루프 정책 설정
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

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
        
        # 스크린샷 저장 경로
        self.screenshot_dir = Path(f"C:/Review_playwright/logs/screenshots/{self.platform_name}")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
    
    async def __aenter__(self):
        await self.start_browser()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_browser()
    
    async def start_browser(self):
        """브라우저 시작"""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']
            )
            self.page = await self.browser.new_page()
            
            # User-Agent 설정
            await self.page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
            # 타임아웃 설정
            self.page.set_default_timeout(30000)  # 30초
            
            logger.info(f"{self.platform_name} 브라우저 시작")
        except Exception as e:
            logger.error(f"브라우저 시작 실패: {str(e)}")
            raise
    
    async def close_browser(self):
        """브라우저 종료"""
        try:
            if self.page:
                await self.page.close()
                self.page = None
            if self.browser:
                await self.browser.close()
                self.browser = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
            logger.info(f"{self.platform_name} 브라우저 종료")
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
