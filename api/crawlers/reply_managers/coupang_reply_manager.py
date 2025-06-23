import asyncio
from typing import Dict, Optional, List, Tuple
from playwright.async_api import Page, Browser, async_playwright
import logging
from datetime import datetime
import os
from pathlib import Path
import re

logger = logging.getLogger(__name__)

class CoupangReplyManager:
    """쿠팡이츠 답글 관리자"""
    
    def __init__(self, store_info: Dict[str, str]):
        self.store_info = store_info
        self.platform_id = store_info.get('platform_id')
        self.platform_pw = store_info.get('platform_pw')
        self.store_code = store_info.get('store_code')
        self.platform_store_id = store_info.get('platform_code')  # 쿠팡 매장 ID (예: 708561)
        self.screenshots_dir = Path("logs/screenshots/coupang/replies")
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        
    async def login(self, page: Page) -> bool:
        """쿠팡이츠 사장님 사이트 로그인"""
        try:
            logger.info(f"쿠팡이츠 로그인 시작: {self.platform_id}")
            
            # 로그인 페이지로 이동
            await page.goto("https://store.coupangeats.com/merchant/login", wait_until="networkidle")
            await page.wait_for_timeout(2000)
            
            # 스크린샷 저장
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            await page.screenshot(path=f"{self.screenshots_dir}/login_page_{timestamp}.png")
            
            # 아이디 입력
            await page.wait_for_selector('#loginId', state='visible', timeout=10000)
            await page.fill('#loginId', self.platform_id)
            await page.wait_for_timeout(500)
            
            # 비밀번호 입력
            await page.fill('#password', self.platform_pw)
            await page.wait_for_timeout(500)
            
            # 로그인 버튼 클릭
            await page.click('button[type="submit"].merchant-submit-btn')
            
            # 로그인 완료 대기
            await page.wait_for_timeout(5000)
            
            # 로그인 성공 확인 (리뷰 페이지로 리다이렉트 되거나 대시보드 표시)
            current_url = page.url
            if "login" not in current_url:
                logger.info("쿠팡이츠 로그인 성공")
                await page.screenshot(path=f"{self.screenshots_dir}/login_success_{timestamp}.png")
                return True
            else:
                logger.error("쿠팡이츠 로그인 실패")
                await page.screenshot(path=f"{self.screenshots_dir}/login_failed_{timestamp}.png")
                return False
                
        except Exception as e:
            logger.error(f"로그인 중 오류: {str(e)}")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            await page.screenshot(path=f"{self.screenshots_dir}/login_error_{timestamp}.png")
            return False
        
    async def close_popup(self, page: Page) -> bool:
        """팝업 닫기"""
        try:
            # 여러 셀렉터로 팝업 닫기 버튼 찾기
            popup_selectors = [
                'button[data-testid="Dialog__CloseButton"]',
                '.dialog-modal-wrapper__body--close-button',
                '.dialog-modal-wrapper__body--close-icon--white',
                'button.dialog-modal-wrapper__body--close-button'
            ]
            
            for selector in popup_selectors:
                try:
                    close_button = await page.query_selector(selector)
                    if close_button:
                        await close_button.click()
                        logger.info(f"팝업을 닫았습니다 (셀렉터: {selector})")
                        await page.wait_for_timeout(1000)
                        return True
                except:
                    continue
            
            logger.debug("닫을 팝업이 없거나 이미 닫혀있습니다")
            return False
            
        except Exception as e:
            logger.debug(f"팝업 처리 중 예외 발생: {str(e)}")
            return False
    
    async def set_date_range(self, page: Page) -> bool:
        """날짜 범위를 1개월로 설정"""
        try:
            logger.info("날짜 범위 설정 시작")
            
            # 날짜 선택 드롭다운 클릭 - SVG를 포함한 div 클릭
            date_dropdown = await page.query_selector('div.css-1rkgd7l:has(svg)')
            if not date_dropdown:
                # 대체 셀렉터 시도
                date_dropdown = await page.query_selector('svg[width="24"][height="24"].css-k0likx')
                if date_dropdown:
                    await date_dropdown.click()
                else:
                    logger.error("날짜 드롭다운을 찾을 수 없습니다")
                    return False
            else:
                await date_dropdown.click()
                
            await page.wait_for_timeout(1000)
            
            # 1개월 옵션 클릭 - JavaScript로 직접 라벨 클릭
            await page.evaluate('''() => {
                // 모든 라벨을 찾아서 '1개월' 텍스트가 있는 것을 찾기
                const labels = document.querySelectorAll('label');
                for (const label of labels) {
                    if (label.textContent && label.textContent.trim() === '1개월') {
                        // 라벨 클릭
                        label.click();
                        // SVG 요소도 클릭
                        const svg = label.querySelector('svg');
                        if (svg) {
                            svg.click();
                        }
                        console.log('1개월 옵션 클릭 완료');
                        return true;
                    }
                }
                return false;
            }''')
            
            logger.info("1개월 옵션 선택 완료")
            await page.wait_for_timeout(1000)
            
            # 조회 버튼 클릭 - 더 정확한 셀렉터 사용
            search_button = await page.query_selector('button.button--primaryOutlined:has-text("조회")')
            if not search_button:
                # 대체 셀렉터
                search_button = await page.query_selector('button:has(span:has-text("조회"))')
            
            if search_button:
                await search_button.click()
                logger.info("조회 버튼 클릭 완료")
                await page.wait_for_timeout(3000)  # 데이터 로딩 대기
            else:
                logger.warning("조회 버튼을 찾을 수 없습니다")
                
            return True
            
        except Exception as e:
            logger.error(f"날짜 범위 설정 실패: {str(e)}")
            return False

    async def navigate_to_reviews(self, page: Page) -> bool:
        """리뷰 관리 페이지로 이동"""
        try:
            logger.info("리뷰 관리 페이지로 이동")
            
            # 리뷰 페이지로 이동
            await page.goto("https://store.coupangeats.com/merchant/management/reviews", wait_until="networkidle")
            await page.wait_for_timeout(3000)
            
            # 팝업 닫기 추가
            await self.close_popup(page)
            
            # 매장 선택 (드롭다운에서)
            store_selector = f'li:has-text("{self.platform_store_id}")'
            if await page.locator(store_selector).count() > 0:
                await page.click(store_selector)
                await page.wait_for_timeout(2000)
                logger.info(f"매장 선택 완료: {self.platform_store_id}")
            
            # 날짜 설정 (1개월) - 수정된 로직
            await self.set_date_range(page)
            
            # 미답변 탭 클릭
            await page.click('div:has-text("미답변").css-jzkpn6.e1kgpv5e2')
            await page.wait_for_timeout(3000)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            await page.screenshot(path=f"{self.screenshots_dir}/reviews_page_{timestamp}.png")
            
            return True
            
        except Exception as e:
            logger.error(f"리뷰 페이지 이동 중 오류: {str(e)}")
            return False
            
    async def find_and_reply_to_review(self, page: Page, review_data: Dict) -> bool:
        """특정 리뷰를 찾아서 답글 등록 (페이지네이션 포함)"""
        try:
            review_content = review_data.get('review_content', '')
            reply_content = review_data.get('reply_content', '')
            order_menu = review_data.get('ordered_menu', '')
            
            logger.info(f"리뷰 찾기 시작: {review_content[:30]}...")
            
            # 페이지네이션 처리
            current_page = 1
            max_pages = 10  # 최대 10페이지까지 검색
            
            while current_page <= max_pages:
                logger.info(f"페이지 {current_page} 검색 중...")
                
                # 현재 페이지에서 리뷰 검색
                review_found = await self._search_review_in_current_page(
                    page, review_content, order_menu, reply_content
                )
                
                if review_found:
                    return True
                
                # 다음 페이지로 이동
                has_next = await self._go_to_next_page(page)
                if not has_next:
                    logger.info("더 이상 페이지가 없습니다")
                    break
                    
                current_page += 1
                await page.wait_for_timeout(2000)  # 페이지 로딩 대기
            
            logger.warning(f"모든 페이지를 검색했지만 매칭되는 리뷰를 찾을 수 없음")
            return False
            
        except Exception as e:
            logger.error(f"답글 등록 중 오류: {str(e)}")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            await page.screenshot(path=f"{self.screenshots_dir}/reply_error_{timestamp}.png")
            return False

    async def _search_review_in_current_page(self, page: Page, review_content: str, 
                                            order_menu: str, reply_content: str) -> bool:
        """현재 페이지에서 리뷰 검색"""
        try:
            # 모든 리뷰 행 가져오기
            review_rows = await page.query_selector_all('tr')
            
            for row in review_rows:
                try:
                    # 리뷰 텍스트 요소 찾기
                    review_text_element = await row.query_selector('p.css-16m6tj.eqn7l9b5')
                    if not review_text_element:
                        continue
                        
                    found_review_text = await review_text_element.text_content()
                    
                    # 리뷰 내용 매칭 (공백 제거하여 비교)
                    if self._normalize_text(review_content) in self._normalize_text(found_review_text):
                        logger.info(f"매칭되는 리뷰 발견: {found_review_text[:50]}...")
                        
                        # 주문 메뉴도 확인 (선택적)
                        if order_menu:
                            menu_element = await row.query_selector('li:has-text("주문메뉴") p')
                            if menu_element:
                                menu_text = await menu_element.text_content()
                                if order_menu not in menu_text:
                                    logger.info("주문 메뉴가 일치하지 않음, 다음 리뷰 확인")
                                    continue
                        
                        # 사장님 댓글 등록하기 버튼 찾기
                        reply_button = await row.query_selector('button.css-1ss7t0c.eqn7l9b2')
                        if not reply_button:
                            # 대체 셀렉터
                            reply_button = await row.query_selector('button:has-text("사장님 댓글 등록하기")')
                        
                        if reply_button:
                            await reply_button.click()
                            await page.wait_for_timeout(2000)
                            
                            # 텍스트박스에 답글 입력
                            textarea = await page.wait_for_selector('textarea[name="review"]', state='visible', timeout=5000)
                            await textarea.fill(reply_content)
                            await page.wait_for_timeout(1000)
                            
                            # 등록 버튼 클릭
                            submit_button = await page.query_selector('button:has-text("등록").button--primaryContained')
                            if not submit_button:
                                # 대체 셀렉터
                                submit_button = await page.query_selector('button.button--primaryContained:has-text("등록")')
                            
                            if submit_button:
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                await page.screenshot(path=f"{self.screenshots_dir}/before_submit_{timestamp}.png")
                                
                                await submit_button.click()
                                await page.wait_for_timeout(3000)
                                
                                logger.info("답글 등록 완료")
                                await page.screenshot(path=f"{self.screenshots_dir}/after_submit_{timestamp}.png")
                                return True
                            else:
                                logger.error("등록 버튼을 찾을 수 없음")
                        else:
                            logger.warning("답글 버튼을 찾을 수 없음 - 이미 답글이 있을 수 있음")
                            
                except Exception as e:
                    logger.error(f"리뷰 행 처리 중 오류: {str(e)}")
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"페이지 내 리뷰 검색 중 오류: {str(e)}")
            return False

    def _normalize_text(self, text: str) -> str:
        """텍스트 정규화 (공백, 특수문자 제거)"""
        if not text:
            return ""
        # 공백, 줄바꿈, 탭 등 제거
        return re.sub(r'\s+', '', text.strip())

    async def _go_to_next_page(self, page: Page) -> bool:
        """다음 페이지로 이동"""
        try:
            # 페이지네이션 영역에서 다음 버튼 찾기
            next_button = await page.evaluate('''() => {
                const containers = document.querySelectorAll('div[class*="css-"]');
                for (const container of containers) {
                    const buttons = container.querySelectorAll('button');
                    if (buttons.length >= 3) {  // 페이지네이션 버튼들
                        const lastButton = buttons[buttons.length - 1];
                        if (lastButton && lastButton.querySelector('svg') && !lastButton.disabled) {
                            lastButton.click();
                            return true;
                        }
                    }
                }
                return false;
            }''')
            
            if next_button:
                logger.info("다음 페이지로 이동")
                return True
            else:
                logger.info("다음 페이지 버튼을 찾을 수 없거나 비활성화됨")
                return False
                
        except Exception as e:
            logger.error(f"페이지 이동 중 오류: {str(e)}")
            return False
            
    async def post_reply(self, review_data: Dict) -> Tuple[bool, str]:
        """답글 등록 메인 프로세스"""
        async with async_playwright() as p:
            browser = None
            try:
                # 브라우저 실행
                browser = await p.chromium.launch(
                    headless=False,  # 디버깅을 위해 False
                    args=['--disable-blink-features=AutomationControlled']
                )
                
                context = await browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                
                page = await context.new_page()
                
                # 1. 로그인
                if not await self.login(page):
                    return False, "로그인 실패"
                    
                # 2. 리뷰 페이지로 이동
                if not await self.navigate_to_reviews(page):
                    return False, "리뷰 페이지 이동 실패"
                    
                # 3. 리뷰 찾아서 답글 등록
                if await self.find_and_reply_to_review(page, review_data):
                    return True, "답글 등록 성공"
                else:
                    return False, "리뷰 매칭 실패 또는 답글 등록 실패"
                    
            except Exception as e:
                logger.error(f"답글 등록 프로세스 오류: {str(e)}")
                return False, f"오류 발생: {str(e)}"
                
            finally:
                if browser:
                    await browser.close()