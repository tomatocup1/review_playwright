"""
Windows에서 Playwright subprocess 문제를 회피하기 위한 동기 실행 래퍼
"""
import asyncio
import logging
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor
import sys
import os

# 프로젝트 루트 경로 추가
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from playwright.sync_api import sync_playwright
import hashlib

logger = logging.getLogger(__name__)

class SyncReplyExecutor:
    """동기 방식으로 답글 등록을 실행하는 헬퍼 클래스"""
    
    @staticmethod
    def execute_naver_sync(manager, review_data: Dict[str, Any], reply_content: str) -> bool:
        """네이버 답글 등록을 동기 방식으로 실행"""
        try:
            with sync_playwright() as p:
                browser_args = [
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-web-security',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage'
                ]
                
                if sys.platform == 'win32':
                    browser_args.extend([
                        '--disable-gpu',
                        '--disable-software-rasterizer'
                    ])
                
                context = p.chromium.launch_persistent_context(
                    user_data_dir=os.path.join(project_root, 'browser_data', 'naver', 'profile_default'),
                    headless=False,
                    args=browser_args
                )
                
                try:
                    pages = context.pages
                    page = pages[0] if pages else context.new_page()
                    
                    # 동기 버전의 매니저 메서드 호출
                    # 매니저가 async 메서드만 가지고 있다면 별도 구현 필요
                    login_success = SyncReplyExecutor._sync_login_naver(page, manager.store_info)
                    if not login_success:
                        return False
                    
                    nav_success = SyncReplyExecutor._sync_navigate_naver(page)
                    if not nav_success:
                        return False
                    
                    # 답글 등록
                    success = SyncReplyExecutor._sync_post_reply_naver(page, review_data, reply_content)
                    return success
                    
                finally:
                    context.close()
                    
        except Exception as e:
            logger.error(f"네이버 동기 실행 오류: {str(e)}")
            return False
    
    @staticmethod
    def _sync_login_naver(page, store_info):
        """네이버 로그인 (동기)"""
        try:
            platform_id = store_info.get('platform_id')
            platform_pw = store_info.get('platform_pw')
            
            page.goto('https://smartplace.naver.com/')
            page.wait_for_load_state('networkidle')
            
            # 로그인 버튼 클릭
            if page.is_visible('a:has-text("로그인")'):
                page.click('a:has-text("로그인")')
                page.wait_for_timeout(2000)
            
            # 아이디/비밀번호 입력
            page.fill('input#id', platform_id)
            page.fill('input#pw', platform_pw)
            page.click('button#log\\.login')
            
            page.wait_for_timeout(3000)
            
            # 로그인 성공 확인
            return 'smartplace.naver.com' in page.url
            
        except Exception as e:
            logger.error(f"네이버 로그인 실패: {str(e)}")
            return False
    
    @staticmethod
    def _sync_navigate_naver(page):
        """네이버 리뷰 페이지로 이동 (동기)"""
        try:
            # 리뷰 관리 메뉴 클릭
            if page.is_visible('text=리뷰'):
                page.click('text=리뷰')
                page.wait_for_timeout(2000)
            
            return True
            
        except Exception as e:
            logger.error(f"네이버 페이지 이동 실패: {str(e)}")
            return False
    
    @staticmethod
    def _sync_post_reply_naver(page, review_data, reply_content):
        """네이버 답글 등록 (동기)"""
        try:
            review_name = review_data.get('review_name', '')
            review_content = review_data.get('review_content', '')
            
            # 리뷰 검색
            if page.is_visible('input[placeholder*="검색"]'):
                page.fill('input[placeholder*="검색"]', review_name[:3])
                page.wait_for_timeout(1000)
            
            # 리뷰 찾기 (내용으로 매칭)
            review_elements = page.locator('.review-item').all()
            target_review = None
            
            for element in review_elements:
                if review_content[:20] in element.text_content():
                    target_review = element
                    break
            
            if not target_review:
                logger.error("리뷰를 찾을 수 없습니다")
                return False
            
            # 답글 작성 버튼 클릭
            reply_button = target_review.locator('button:has-text("답글")')
            if reply_button.is_visible():
                reply_button.click()
                page.wait_for_timeout(1000)
            
            # 답글 입력
            reply_textarea = page.locator('textarea[placeholder*="답글"]')
            if reply_textarea.is_visible():
                reply_textarea.fill(reply_content)
                page.wait_for_timeout(500)
            
            # 등록 버튼 클릭
            submit_button = page.locator('button:has-text("등록")')
            if submit_button.is_visible():
                submit_button.click()
                page.wait_for_timeout(2000)
            
            return True
            
        except Exception as e:
            logger.error(f"네이버 답글 등록 실패: {str(e)}")
            return False
    
    @staticmethod
    async def execute_naver_async(manager, review_data: Dict[str, Any], reply_content: str) -> bool:
        """비동기 컨텍스트에서 동기 실행을 래핑"""
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(
                executor,
                SyncReplyExecutor.execute_naver_sync,
                manager,
                review_data,
                reply_content
            )
        return result