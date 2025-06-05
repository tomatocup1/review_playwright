"""
Base crawler class for all platform crawlers
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime
import json
from pathlib import Path

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from playwright_stealth import stealth_async

# 로깅 설정
logger = logging.getLogger(__name__)


class BaseCrawler(ABC):
    """플랫폼 크롤러의 기본 클래스"""
    
    def __init__(self, store_config: Dict):
        """
        Args:
            store_config: 매장 설정 정보
                - store_code: 매장 코드
                - platform_id: 플랫폼 로그인 ID
                - platform_pw: 플랫폼 로그인 비밀번호
                - platform_code: 플랫폼상의 매장 ID
                - store_name: 매장명
        """
        self.store_config = store_config
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.session_storage_path = Path(f"sessions/{store_config['platform_id']}.json")
        
    async def initialize(self):
        """브라우저 초기화"""
        self.playwright = await async_playwright().start()
        
        # 브라우저 설정
        self.browser = await self.playwright.chromium.launch(
            headless=False,  # 개발 중에는 False, 프로덕션에서는 True
            args=[
                '--start-maximized',
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-web-security',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        
        # 세션 저장 경로 확인
        self.session_storage_path.parent.mkdir(exist_ok=True)
        
        # 컨텍스트 생성 (세션 복원 시도)
        context_options = {
            'viewport': None,  # 전체 화면 사용
            'locale': 'ko-KR',
            'timezone_id': 'Asia/Seoul',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        # 저장된 세션이 있으면 로드
        if self.session_storage_path.exists():
            try:
                with open(self.session_storage_path, 'r', encoding='utf-8') as f:
                    storage_state = json.load(f)
                context_options['storage_state'] = storage_state
                logger.info(f"세션 복원: {self.store_config['platform_id']}")
            except Exception as e:
                logger.warning(f"세션 복원 실패: {e}")
        
        self.context = await self.browser.new_context(**context_options)
        self.page = await self.context.new_page()
        
        # Stealth 플러그인 적용 (안티봇 우회)
        await stealth_async(self.page)
        
    async def save_session(self):
        """현재 세션 저장"""
        try:
            storage_state = await self.context.storage_state()
            with open(self.session_storage_path, 'w', encoding='utf-8') as f:
                json.dump(storage_state, f, ensure_ascii=False, indent=2)
            logger.info(f"세션 저장 완료: {self.store_config['platform_id']}")
        except Exception as e:
            logger.error(f"세션 저장 실패: {e}")
    
    async def close(self):
        """브라우저 종료"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def check_antibot(self) -> bool:
        """안티봇 감지 체크"""
        antibot_texts = [
            '로봇이',
            '자동화된',
            '확인하십시오',
            'captcha',
            'recaptcha'
        ]
        
        page_content = await self.page.content()
        for text in antibot_texts:
            if text.lower() in page_content.lower():
                logger.warning(f"안티봇 감지: {text}")
                return True
        
        return False
    
    async def close_popups(self):
        """일반적인 팝업 닫기"""
        popup_selectors = [
            'button:has-text("닫기")',
            'button:has-text("확인")',
            'button[aria-label="닫기"]',
            'button[aria-label="close"]',
            'button.close',
            'button.btn-close'
        ]
        
        for selector in popup_selectors:
            try:
                button = await self.page.wait_for_selector(selector, timeout=1000)
                if button:
                    await button.click()
                    logger.info(f"팝업 닫기: {selector}")
                    await asyncio.sleep(0.5)
            except:
                continue
    
    @abstractmethod
    async def login(self) -> bool:
        """플랫폼 로그인 처리"""
        pass
    
    @abstractmethod
    async def get_reviews(self) -> List[Dict]:
        """미답변 리뷰 목록 가져오기"""
        pass
    
    @abstractmethod
    async def post_reply(self, review_id: str, reply_text: str) -> bool:
        """답글 등록"""
        pass
    
    async def save_screenshot(self, prefix: str = ""):
        """스크린샷 저장 (디버깅용)"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshots/{prefix}_{self.store_config['store_code']}_{timestamp}.png"
        Path("screenshots").mkdir(exist_ok=True)
        await self.page.screenshot(path=filename, full_page=True)
        logger.info(f"스크린샷 저장: {filename}")
        return filename
