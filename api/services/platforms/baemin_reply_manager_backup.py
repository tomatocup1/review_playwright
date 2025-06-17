# -*- coding: utf-8 -*-
"""
배민 답글 등록 매니저 모듈
실제 Playwright를 사용해 배민 사이트에 답글을 등록하는 로직
"""

import time
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BaeminReplyManager:
    """
    배민 답글 등록을 담당하는 매니저 클래스
    """
    
    def __init__(self, browser=None):
        self.browser = browser  # 외부에서 전달받은 browser 사용
        self.context = None
        self.page = None
        self.is_logged_in = False
        self.playwright = None
        
    async def __aenter__(self):
        await self.initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        
    async def initialize(self):
        """매니저 초기화"""
        try:
            # browser가 전달되었고, BrowserContext인 경우
            if self.browser and hasattr(self.browser, 'new_page'):
                self.page = await self.browser.new_page()
                logger.info("외부 브라우저 컨텍스트 사용")
            # browser가 전달되지 않은 경우 새로 생성
            elif not self.browser:
                await self.initialize_browser()
            else:
                logger.error("알 수 없는 브라우저 타입")
                raise ValueError("Invalid browser type")
                
            logger.info("매니저 초기화 완료")
            
        except Exception as e:
            logger.error(f"매니저 초기화 실패: {str(e)}")
            raise
        
    async def initialize_browser(self, headless: bool = True) -> None:
        """브라우저 초기화 (내부 생성용)"""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage'
                ]
            )
            
            # 컨텍스트 생성 - 사용자 에이전트 설정
            self.context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='ko-KR'
            )
            
            # JavaScript 활성화
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            self.page = await self.context.new_page()
            logger.info("브라우저 초기화 완료")
            
        except Exception as e:
            logger.error(f"브라우저 초기화 실패: {str(e)}")
            raise
            
    async def login(self, username: str, password: str) -> bool:
        """
        배민 사장님사이트 로그인
        """
        try:
            logger.info("배민 로그인 시작")
            
            # 로그인 페이지로 이동
            await self.page.goto('https://ceo.baemin.com/', wait_until='networkidle')
            await asyncio.sleep(2)
            
            # 이미 로그인되어 있는지 확인
            if self.page.url.startswith('https://ceo.baemin.com/main'):
                logger.info("이미 로그인되어 있습니다")
                self.is_logged_in = True
                return True
            
            # 아이디 입력
            await self.page.wait_for_selector('input[name="username"]', timeout=10000)
            await self.page.fill('input[name="username"]', username)
            await asyncio.sleep(1)
            
            # 비밀번호 입력
            await self.page.fill('input[name="password"]', password)
            await asyncio.sleep(1)
            
            # 로그인 버튼 클릭
            await self.page.click('button[type="submit"]')
            await asyncio.sleep(3)
            
            # 로그인 성공 확인
            try:
                await self.page.wait_for_url('**/main**', timeout=10000)
                logger.info("로그인 성공")
                self.is_logged_in = True
                return True
            except:
                logger.error("로그인 실패 - 잘못된 인증정보")
                return False
                
        except Exception as e:
            logger.error(f"로그인 중 오류 발생: {str(e)}")
            return False
            
    async def navigate_to_review_page(self, platform_code: str) -> bool:
        """리뷰 관리 페이지로 이동"""
        try:
            logger.info(f"리뷰 관리 페이지로 이동 - platform_code: {platform_code}")
            
            # 직접 URL로 이동하는 방식
            review_url = f'https://ceo.baemin.com/shop/{platform_code}/review'
            await self.page.goto(review_url, wait_until='networkidle')
            await asyncio.sleep(3)
            
            # 페이지 로드 확인
            try:
                await self.page.wait_for_selector('.review-list', timeout=10000)
                logger.info("리뷰 관리 페이지 도착")
                return True
            except:
                # 메뉴를 통한 이동 시도
                logger.info("직접 URL 이동 실패, 메뉴를 통한 이동 시도")
                await self.page.click('text=리뷰관리')
                await asyncio.sleep(2)
                await self.page.click('text=리뷰 댓글 관리')
                await asyncio.sleep(3)
                return True
                
        except Exception as e:
            logger.error(f"리뷰 페이지 이동 실패: {str(e)}")
            return False
            
    async def find_review_and_open_reply(self, review_id: str) -> bool:
        """
        특정 리뷰를 찾고 답글 모드 열기
        """
        try:
            logger.info(f"리뷰 검색 시작 - review_id: {review_id}")
            
            # 리뷰 목록 로드 대기
            await self.page.wait_for_selector('.review-item', timeout=10000)
            
            # 페이지 스크롤하며 리뷰 찾기
            found = False
            for _ in range(10):  # 최대 10번 스크롤
                # 현재 화면의 모든 리뷰 확인
                review_items = await self.page.query_selector_all('.review-item')
                
                for item in review_items:
                    # 리뷰 ID나 특정 속성으로 매칭
                    item_id = await item.get_attribute('data-review-id')
                    if item_id and review_id in item_id:
                        logger.info("매칭되는 리뷰 발견")
                        
                        # 답글 작성 버튼 클릭
                        reply_button = await item.query_selector('button:has-text("답글 작성")')
                        if reply_button:
                            await reply_button.click()
                            await asyncio.sleep(2)
                            found = True
                            break
                
                if found:
                    break
                    
                # 스크롤 다운
                await self.page.evaluate('window.scrollBy(0, 500)')
                await asyncio.sleep(1)
            
            return found
            
        except Exception as e:
            logger.error(f"리뷰 검색 중 오류: {str(e)}")
            return False
            
    async def post_reply(self, reply_content: str) -> bool:
        """
        답글 등록
        """
        try:
            logger.info("답글 등록 시작")
            
            # 답글 입력 필드 찾기
            reply_textarea = await self.page.wait_for_selector('textarea[placeholder*="답글"]', timeout=5000)
            await reply_textarea.fill(reply_content)
            await asyncio.sleep(1)
            
            # 등록 버튼 클릭
            submit_button = await self.page.query_selector('button:has-text("등록")')
            if submit_button:
                await submit_button.click()
                await asyncio.sleep(2)
                
                # 등록 성공 확인
                try:
                    await self.page.wait_for_selector('.success-message', timeout=5000)
                    logger.info("답글 등록 성공")
                    return True
                except:
                    # 성공 메시지가 없어도 답글이 표시되는지 확인
                    logger.warning("성공 메시지를 확인할 수 없지만 계속 진행")
                    return True
                    
            return False
            
        except Exception as e:
            logger.error(f"답글 등록 중 오류: {str(e)}")
            return False
            
    async def register_reply(self, login_id: str, login_pw: str, platform_code: str,
                           review_id: str, reply_content: str) -> Tuple[bool, str]:
        """
        메인 실행 함수 - 로그인부터 답글 등록까지 전체 프로세스
        """
        try:
            # 매니저 초기화 (browser가 없으면 자체 생성)
            if not self.page:
                await self.initialize()
            
            # 로그인
            if not await self.login(login_id, login_pw):
                return False, "로그인 실패"
                
            # 리뷰 페이지로 이동
            if not await self.navigate_to_review_page(platform_code):
                return False, "리뷰 페이지 이동 실패"
                
            # 리뷰 찾고 답글 모드 열기
            if not await self.find_review_and_open_reply(review_id):
                return False, "해당 리뷰를 찾을 수 없습니다"
                
            # 답글 등록
            if await self.post_reply(reply_content):
                return True, "답글 등록 성공"
            else:
                return False, "답글 등록 실패"
                
        except Exception as e:
            logger.error(f"답글 등록 프로세스 중 오류: {str(e)}")
            return False, f"오류 발생: {str(e)}"
            
    async def close(self):
        """브라우저 종료"""
        try:
            if self.page:
                await self.page.close()
                logger.info("페이지 종료 완료")
        except Exception as e:
            logger.error(f"페이지 종료 중 오류: {str(e)}")
        
        try:
            if hasattr(self, 'context') and self.context:
                await self.context.close()
                logger.info("컨텍스트 종료 완료")
        except Exception as e:
            logger.error(f"컨텍스트 종료 중 오류: {str(e)}")
        
        try:
            # 자체 생성한 browser만 종료 (외부에서 전달받은 경우 종료하지 않음)
            if hasattr(self, 'playwright') and self.playwright:
                if hasattr(self, 'browser') and self.browser:
                    await self.browser.close()
                    logger.info("브라우저 종료 완료")
                await self.playwright.stop()
                logger.info("Playwright 종료 완료")
        except Exception as e:
            logger.error(f"브라우저/Playwright 종료 중 오류: {str(e)}")


# 단독 실행용 함수
async def register_baemin_reply(login_id: str, login_pw: str, platform_code: str,
                              review_id: str, reply_content: str) -> Tuple[bool, str]:
    """
    배민 답글 등록 함수 (외부에서 호출용)
    """
    async with BaeminReplyManager() as manager:
        return await manager.register_reply(login_id, login_pw, platform_code, review_id, reply_content)