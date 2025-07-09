# -*- coding: utf-8 -*-
"""
요기요 답글 등록 매니저 모듈
실제 Playwright를 사용해 요기요 사이트에 답글을 등록하는 로직
"""
import os
import asyncio
import time
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class YogiyoReplyManager:
    """
    요기요 답글 등록을 담당하는 매니저 클래스
    """
    
    def __init__(self, browser=None):
        self.browser = browser  # 외부에서 전달받은 browser 사용
        self.context = None
        self.page = None
        self.is_logged_in = False
        self.playwright = None
        self.logger = logging.getLogger(__name__)
        
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
        
    async def initialize_browser(self, headless: bool = False) -> None:
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
        """요기요 사장님 사이트 로그인"""
        try:
            logger.info("=" * 50)
            logger.info("요기요 로그인 시작")
            logger.info("=" * 50)
            
            login_url = "https://ceo.yogiyo.co.kr/login/"
            logger.info(f"로그인 URL: {login_url}")
            
            # 로그인 페이지로 이동
            await self.page.goto(login_url, wait_until='networkidle')
            await self.page.wait_for_timeout(2000)
            logger.info("로그인 페이지 로드 완료")
            
            # 아이디 입력
            await self.page.fill('input[name="username"]', username)
            logger.info(f"아이디 입력 완료: {username}")
            
            # 비밀번호 입력
            await self.page.fill('input[name="password"]', password)
            logger.info("비밀번호 입력 완료")
            
            # 로그인 버튼 클릭
            await self.page.click('button[type="submit"]')
            logger.info("로그인 버튼 클릭")
            
            # 인증 메일 팝업 처리를 위한 대기
            await self.page.wait_for_timeout(3000)
            
            # 인증 메일 팝업 처리
            try:
                # 인증 메일 확인 팝업 체크
                auth_popup_selectors = [
                    'div.AlertMessage-sc-a98nwm-3.ewbPZf',
                    'div.Alert__Message-sc-a98nwm-3.ewbPZf',
                    'div.AlertMessage-sc-a98nwm-3',
                    'div[class*="Alert"]:has-text("인증 메일")'
                ]
                
                auth_popup = None
                for selector in auth_popup_selectors:
                    auth_popup = await self.page.query_selector(selector)
                    if auth_popup:
                        break
                
                if auth_popup:
                    popup_text = await auth_popup.text_content()
                    if '인증 메일 확인이 완료되지 않았습니다' in popup_text:
                        logger.info("인증 메일 팝업 감지됨")
                        
                        # 확인 버튼 클릭
                        confirm_button_selectors = [
                            'button.sc-bczRLJ.claiZC.sc-eCYdqJ.hsiXYt',
                            'div.AlertButtonContainer-sc-a98nwm-4 button',
                            'button:has-text("확인")'
                        ]
                        
                        confirm_button = None
                        for selector in confirm_button_selectors:
                            confirm_button = await self.page.query_selector(selector)
                            if confirm_button and await confirm_button.is_visible():
                                break
                        
                        if confirm_button:
                            await confirm_button.click()
                            logger.info("인증 메일 재발송 확인 버튼 클릭")
                            await self.page.wait_for_timeout(2000)
                            
                            # 두 번째 팝업 처리
                            second_popup = None
                            for selector in auth_popup_selectors:
                                second_popup = await self.page.query_selector(selector)
                                if second_popup:
                                    break
                            
                            if second_popup:
                                second_popup_text = await second_popup.text_content()
                                if '인증 메일을 발송했습니다' in second_popup_text:
                                    logger.info("인증 메일 발송 팝업 감지됨")
                                    
                                    # 두 번째 확인 버튼 클릭
                                    second_confirm_button = None
                                    for selector in confirm_button_selectors:
                                        second_confirm_button = await self.page.query_selector(selector)
                                        if second_confirm_button and await second_confirm_button.is_visible():
                                            break
                                    
                                    if second_confirm_button:
                                        await second_confirm_button.click()
                                        logger.info("인증 메일 발송 확인 버튼 클릭")
                                        await self.page.wait_for_timeout(2000)
                                        
            except Exception as e:
                logger.info(f"인증 메일 팝업 처리 중 예외 (무시): {str(e)}")
            
            # 로그인 완료 대기
            await self.page.wait_for_load_state("networkidle", timeout=10000)
            await asyncio.sleep(3)
            
            # 로그인 성공 확인
            current_url = self.page.url
            if "login" not in current_url:
                logger.info(f"로그인 성공! 현재 URL: {current_url}")
                self.is_logged_in = True
                return True
            else:
                logger.error(f"로그인 실패. 여전히 로그인 페이지: {current_url}")
                return False
                
        except Exception as e:
            logger.error(f"로그인 중 오류 발생: {str(e)}")
            # 에러 스크린샷 저장
            try:
                screenshot_path = Path("C:/Review_playwright/logs") / f"yogiyo_login_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await self.page.screenshot(path=str(screenshot_path))
                logger.info(f"에러 스크린샷 저장: {screenshot_path}")
            except:
                pass
            return False
            
    async def navigate_to_review_page(self, platform_code: str) -> bool:
        """리뷰 관리 페이지로 이동"""
        try:
            logger.info(f"리뷰 관리 페이지로 이동 - platform_code: {platform_code}")
            
            # 리뷰 페이지로 이동
            review_url = "https://ceo.yogiyo.co.kr/reviews"
            logger.info(f"리뷰 URL: {review_url}")
            
            await self.page.goto(review_url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(3)
            
            # 매장 선택 드롭다운 클릭
            store_selector_button = await self.page.query_selector('button.StoreSelector__DropdownButton-sc-1rowjsb-11')
            if store_selector_button:
                await store_selector_button.click()
                logger.info("매장 선택 드롭다운 열기")
                await asyncio.sleep(2)
                
                # 매장 목록에서 해당 매장 찾기
                store_items = await self.page.query_selector_all('li.List__Vendor-sc-2ocjy3-7')
                for item in store_items:
                    store_id_elem = await item.query_selector('span.List__VendorID-sc-2ocjy3-1')
                    if store_id_elem:
                        store_id_text = await store_id_elem.text_content()
                        if platform_code in store_id_text:
                            await item.click()
                            logger.info(f"매장 선택 완료: {platform_code}")
                            await asyncio.sleep(2)
                            break
            
            # 미답변 탭 클릭
            try:
                no_reply_tab = await self.page.wait_for_selector('li.InnerTab__TabItem-sc-14s9mjy-0:has-text("미답변")', timeout=5000)
                if no_reply_tab:
                    await no_reply_tab.click()
                    logger.info("미답변 탭 클릭 성공")
                    await asyncio.sleep(2)
            except:
                logger.warning("미답변 탭을 찾을 수 없음 - 계속 진행")
            
            # 최종 URL 확인
            final_url = self.page.url
            if '/reviews' in final_url:
                logger.info(f"리뷰 페이지 이동 성공: {final_url}")
                return True
            else:
                logger.error(f"리뷰 페이지가 아님: {final_url}")
                return False
                
        except Exception as e:
            logger.error(f"리뷰 페이지 이동 실패: {str(e)}")
            return False
    
    async def navigate_to_reviews(self, platform_code: str) -> bool:
        """리뷰 관리 페이지로 이동 (배달의민족 호환 메서드) - 드롭다운 방식"""
        try:
            logger.info(f"리뷰 페이지 이동 시도 - platform_code: {platform_code}")
            
            # 현재 페이지가 리뷰 페이지가 아니면 이동
            current_url = self.page.url
            if "/reviews" not in current_url:
                review_url = "https://ceo.yogiyo.co.kr/reviews"
                logger.info(f"리뷰 페이지로 이동: {review_url}")
                await self.page.goto(review_url, wait_until='networkidle', timeout=30000)
                await asyncio.sleep(2)
                logger.info("리뷰 페이지 이동 완료")
            
            # 드롭다운을 통해 매장 선택
            logger.info(f"매장 선택 시작: {platform_code}")
            
            # 드롭다운 열기
            dropdown_selector = 'button.StoreSelector__DropdownButton-sc-1rowjsb-11'
            try:
                await self.page.wait_for_selector(dropdown_selector, timeout=10000)
                await self.page.click(dropdown_selector)
                await asyncio.sleep(1)
                logger.info("드롭다운 열기 완료")
            except Exception as e:
                logger.error(f"드롭다운 열기 실패: {str(e)}")
                return False
            
            # 매장 목록에서 해당 매장 찾기
            store_items = await self.page.query_selector_all('li.List__Vendor-sc-2ocjy3-7')
            logger.info(f"{len(store_items)}개의 매장 발견")
            
            for item in store_items:
                try:
                    id_elem = await item.query_selector('span.List__VendorID-sc-2ocjy3-1')
                    if id_elem:
                        store_id_text = await id_elem.text_content()
                        if platform_code in store_id_text:
                            await item.click()
                            logger.info(f"매장 선택 완료: {platform_code}")
                            await asyncio.sleep(2)
                            break
                            
                except Exception as e:
                    logger.error(f"매장 선택 중 오류: {str(e)}")
                    continue
            else:
                logger.error(f"매장을 찾을 수 없습니다: {platform_code}")
                return False
            
            # 미답변 탭 클릭
            try:
                no_reply_tab = await self.page.wait_for_selector('li.InnerTab__TabItem-sc-14s9mjy-0:has-text("미답변")', timeout=5000)
                if no_reply_tab:
                    await no_reply_tab.click()
                    logger.info("미답변 탭 클릭 성공")
                    await asyncio.sleep(2)
            except:
                logger.warning("미답변 탭을 찾을 수 없음 - 계속 진행")
            
            # 최종 URL 확인
            final_url = self.page.url
            if '/reviews' in final_url:
                logger.info(f"리뷰 페이지 이동 성공: {final_url}")
                return True
            else:
                logger.error(f"리뷰 페이지가 아님: {final_url}")
                return False
                
        except Exception as e:
            logger.error(f"리뷰 페이지 이동 실패: {str(e)}")
            return False
            
    async def find_review_and_click_reply(self, review_id: str, review_info: dict = None):
        """리뷰를 찾고 답글 버튼을 클릭 (배달의민족 호환 메서드)"""
        try:
            logger.info(f"리뷰 검색 시작 - review_id: {review_id}")
            
            # review_info에서 매칭에 필요한 정보 추출
            if review_info:
                target_name = review_info.get('review_name', '')
                target_content = review_info.get('review_content', '')
                target_rating = review_info.get('rating', 0)
                target_date = review_info.get('review_date', '')
                target_menu = review_info.get('ordered_menu', '')
                
                logger.info(f"매칭 정보 - 작성자: {target_name}, 별점: {target_rating}, 날짜: {target_date}")
                logger.info(f"리뷰 내용: {target_content[:50]}...")
                logger.info(f"주문 메뉴: {target_menu}")
            else:
                logger.warning("review_info가 제공되지 않음 - review_id로만 검색")
                target_name = target_content = target_menu = ""
                target_rating = 0
                target_date = ""
            
            # 페이지가 로드될 때까지 대기
            await asyncio.sleep(3)
            
            # 여러 번 시도
            max_attempts = 3
            for attempt in range(max_attempts):
                logger.info(f"리뷰 검색 시도 {attempt + 1}/{max_attempts}")
                
                # 리뷰 컨테이너 찾기
                review_containers = await self.page.query_selector_all('div.ReviewItem__Container-sc-1oxgj67-0')
                
                logger.info(f"{len(review_containers)}개의 리뷰 컨테이너 발견")
                
                # 각 리뷰 컨테이너 검사
                for i, container in enumerate(review_containers):
                    try:
                        # 컨테이너의 전체 텍스트 가져오기
                        container_text = await container.text_content()
                        if not container_text:
                            continue
                        
                        # 매칭 점수 계산
                        match_score = 0
                        match_details = []
                        
                        # 1. 작성자 이름 매칭
                        name_elem = await container.query_selector('h6')
                        if name_elem and target_name:
                            name_text = await name_elem.text_content()
                            if target_name in name_text:
                                match_score += 2
                                match_details.append(f"이름 매칭: {target_name}")
                        
                        # 2. 리뷰 내용 매칭
                        content_elem = await container.query_selector('p.ReviewItem__CommentTypography-sc-1oxgj67-3')
                        if content_elem and target_content:
                            content_text = await content_elem.text_content()
                            clean_target = ''.join(target_content.split())
                            clean_content = ''.join(content_text.split())
                            
                            if clean_target in clean_content:
                                match_score += 3
                                match_details.append("내용 매칭")
                        
                        # 3. 별점 매칭
                        if target_rating:
                            rating_elem = await container.query_selector('h6.cknzqP')
                            if rating_elem:
                                rating_text = await rating_elem.text_content()
                                if str(target_rating) in rating_text:
                                    match_score += 1
                                    match_details.append(f"별점 매칭: {target_rating}")
                        
                        # 매칭 점수 확인 (3점 이상이면 해당 리뷰로 판단)
                        if match_score >= 3:
                            logger.info(f"✅ 리뷰 매칭 성공! 점수: {match_score}, 상세: {', '.join(match_details)}")
                            
                            # 답글 버튼 찾기 (요기요는 '댓글쓰기' 버튼)
                            reply_button = await container.query_selector('button:has-text("댓글쓰기")')
                            if not reply_button:
                                reply_button = await container.query_selector('button.sc-bczRLJ.ifUnxI.sc-eCYdqJ.ReviewReply__AddReplyButton-sc-1536a88-9.hsiXYt.fSnQUl')
                            if not reply_button:
                                reply_button = await container.query_selector('button[class*="ReviewReply__AddReplyButton"]')
                            
                            if reply_button:
                                # 버튼이 보이도록 스크롤
                                await reply_button.scroll_into_view_if_needed()
                                await asyncio.sleep(1)
                                
                                # 버튼 클릭
                                await reply_button.click()
                                logger.info("답글 버튼 클릭 성공")
                                await asyncio.sleep(2)
                                return True
                            else:
                                logger.warning("답글 버튼을 찾을 수 없음 - 오래된 리뷰로 추정")
                                return "OLD_REVIEW"
                        
                        # 매칭 점수가 낮지만 일부 일치하는 경우 로깅
                        elif match_score > 0:
                            logger.debug(f"부분 매칭 - 점수: {match_score}, 상세: {', '.join(match_details)}")
                            
                    except Exception as e:
                        logger.error(f"리뷰 컨테이너 {i+1} 처리 중 에러: {str(e)}")
                        continue
                
                # 못 찾았으면 스크롤 후 재시도
                if attempt < max_attempts - 1:
                    logger.info("리뷰를 찾지 못함, 스크롤 후 재시도")
                    await self.page.evaluate("window.scrollBy(0, 500)")
                    await asyncio.sleep(2)
            
            # 모든 시도 실패
            logger.error("리뷰를 찾을 수 없음")
            return False
            
        except Exception as e:
            logger.error(f"리뷰 검색 중 오류: {str(e)}")
            return False
            
    async def find_review_and_open_reply(self, review_id: str, review_info: dict = None) -> bool:
        """특정 리뷰를 찾고 답글 모드 열기"""
        try:
            logger.info(f"리뷰 검색 시작 - review_id: {review_id}")
            
            # review_info에서 매칭에 필요한 정보 추출
            if review_info:
                target_name = review_info.get('review_name', '')
                target_content = review_info.get('review_content', '')
                target_rating = review_info.get('rating', 0)
                target_date = review_info.get('review_date', '')
                target_menu = review_info.get('ordered_menu', '')
                
                logger.info(f"매칭 정보 - 작성자: {target_name}, 별점: {target_rating}, 날짜: {target_date}")
                logger.info(f"리뷰 내용: {target_content[:50]}...")
                logger.info(f"주문 메뉴: {target_menu}")
            else:
                logger.warning("review_info가 제공되지 않음 - review_id로만 검색")
                target_name = target_content = target_menu = ""
                target_rating = 0
                target_date = ""
            
            # 페이지가 로드될 때까지 대기
            await asyncio.sleep(3)
            
            # 여러 번 시도
            max_attempts = 3
            for attempt in range(max_attempts):
                logger.info(f"리뷰 검색 시도 {attempt + 1}/{max_attempts}")
                
                # 리뷰 컨테이너 찾기
                review_containers = await self.page.query_selector_all('div.ReviewItem__Container-sc-1oxgj67-0')
                
                logger.info(f"{len(review_containers)}개의 리뷰 컨테이너 발견")
                
                # 각 리뷰 컨테이너 검사
                for i, container in enumerate(review_containers):
                    try:
                        # 컨테이너의 전체 텍스트 가져오기
                        container_text = await container.text_content()
                        if not container_text:
                            continue
                        
                        # 매칭 점수 계산
                        match_score = 0
                        match_details = []
                        
                        # 1. 작성자 이름 매칭
                        name_elem = await container.query_selector('h6')
                        if name_elem and target_name:
                            name_text = await name_elem.text_content()
                            if target_name in name_text:
                                match_score += 2
                                match_details.append(f"이름 매칭: {target_name}")
                        
                        # 2. 리뷰 내용 매칭
                        content_elem = await container.query_selector('p.ReviewItem__CommentTypography-sc-1oxgj67-3')
                        if content_elem and target_content:
                            content_text = await content_elem.text_content()
                            clean_target = ''.join(target_content.split())
                            clean_content = ''.join(content_text.split())
                            
                            if clean_target in clean_content:
                                match_score += 3
                                match_details.append("내용 매칭")
                        
                        # 3. 별점 매칭
                        if target_rating:
                            rating_elem = await container.query_selector('h6.cknzqP')
                            if rating_elem:
                                rating_text = await rating_elem.text_content()
                                if str(target_rating) in rating_text:
                                    match_score += 1
                                    match_details.append(f"별점 매칭: {target_rating}")
                        
                        # 4. 날짜 매칭
                        date_elem = await container.query_selector('p.jwoVKl')
                        if date_elem and target_date:
                            date_text = await date_elem.text_content()
                            # 날짜 형식 변환 (YYYY-MM-DD -> YYYY.MM.DD)
                            formatted_date = target_date.replace('-', '.')
                            if formatted_date in date_text:
                                match_score += 1
                                match_details.append(f"날짜 매칭: {formatted_date}")
                        
                        # 5. 메뉴 매칭
                        if target_menu and target_menu in container_text:
                            match_score += 1
                            match_details.append(f"메뉴 매칭: {target_menu}")
                        
                        # 매칭 점수 확인 (3점 이상이면 해당 리뷰로 판단)
                        if match_score >= 3:
                            logger.info(f"리뷰 매칭 성공! 점수: {match_score}, 상세: {', '.join(match_details)}")
                            
                            # 답글 버튼 찾기
                            reply_button = await container.query_selector('button.ReviewReply__AddReplyButton-sc-1536a88-9')
                            
                            if reply_button:
                                # 버튼이 보이도록 스크롤
                                await reply_button.scroll_into_view_if_needed()
                                await asyncio.sleep(1)
                                
                                # 버튼 클릭
                                await reply_button.click()
                                logger.info("답글 버튼 클릭 성공")
                                await asyncio.sleep(2)
                                return True
                            else:
                                logger.error("답글 버튼을 찾을 수 없음")
                        
                        # 매칭 점수가 낮지만 일부 일치하는 경우 로깅
                        elif match_score > 0:
                            logger.debug(f"부분 매칭 - 점수: {match_score}, 상세: {', '.join(match_details)}")
                            
                    except Exception as e:
                        logger.error(f"리뷰 컨테이너 {i+1} 처리 중 에러: {str(e)}")
                        continue
                
                # 못 찾았으면 스크롤
                if attempt < max_attempts - 1:
                    logger.info("리뷰를 찾지 못함, 스크롤 후 재시도")
                    await self.page.evaluate("window.scrollBy(0, 500)")
                    await asyncio.sleep(2)
            
            # 모든 시도 실패
            logger.error("리뷰를 찾을 수 없음")
            return False
            
        except Exception as e:
            logger.error(f"리뷰 검색 중 오류: {str(e)}")
            return False
    
    async def write_and_submit_reply(self, reply_content: str) -> bool:
        """답글 작성 및 제출"""
        try:
            logger.info(f"답글 작성 시작: {reply_content[:50]}...")
            
            # 텍스트박스가 나타날 때까지 대기
            await asyncio.sleep(2)
            
            # 텍스트박스 찾기 (요기요 전용 셀렉터)
            textarea_selectors = [
                'textarea.ReviewReply__CustomTextarea-sc-1536a88-4.efgGYK',
                'textarea.ReviewReply__CustomTextarea-sc-1536a88-4',
                'textarea[placeholder="댓글을 입력해주세요."]',
                'textarea[maxlength="1000"]'
            ]
            
            textarea = None
            for selector in textarea_selectors:
                try:
                    textarea = await self.page.wait_for_selector(selector, timeout=3000)
                    if textarea:
                        break
                except:
                    continue
            
            if not textarea:
                logger.error("답글 입력 필드를 찾을 수 없음")
                return False
            
            # 입력 필드 클릭 및 내용 입력
            await textarea.click()
            await asyncio.sleep(0.5)
            
            # 기존 내용 지우기
            await self.page.keyboard.press('Control+A')
            await self.page.keyboard.press('Delete')
            
            # 답글 내용 입력
            await textarea.type(reply_content, delay=50)
            logger.info(f"답글 내용 입력 완료: {len(reply_content)}자")
            
            await asyncio.sleep(1)
            
            # 등록 버튼 찾기 (요기요 전용 셀렉터)
            register_button_selectors = [
                'button.sc-bczRLJ.ifUnxI.sc-eCYdqJ.hsiXYt:has(span.sc-hKMtZM.jULfyC:text("등록"))',
                'button.sc-bczRLJ.ifUnxI.sc-eCYdqJ.hsiXYt:has-text("등록")',
                'button:has(span:has-text("등록"))',
                'button[class*="sc-bczRLJ"]:has-text("등록")'
            ]
            
            register_button = None
            for selector in register_button_selectors:
                try:
                    register_button = await self.page.query_selector(selector)
                    if register_button:
                        break
                except:
                    continue
            
            if not register_button:
                logger.error("등록 버튼을 찾을 수 없음")
                return False
            
            # 등록 버튼 클릭
            await register_button.click()
            logger.info("등록 버튼 클릭 완료")
            
            # 등록 완료 대기
            await asyncio.sleep(3)
            
            # 성공 확인
            logger.info("답글 등록 프로세스 완료")
            return True
            
        except Exception as e:
            logger.error(f"답글 작성 중 오류: {str(e)}")
            return False
    
    async def post_reply(self, reply_content: str) -> bool:
        """답글 등록 (write_and_submit_reply와 동일한 기능)"""
        return await self.write_and_submit_reply(reply_content)
            
    async def register_reply(self, login_id: str, login_pw: str, platform_code: str,
                        review_id: str, reply_content: str, review_info: dict = None) -> Tuple[bool, str]:
        """메인 실행 함수 - 로그인부터 답글 등록까지 전체 프로세스"""
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
            if not await self.find_review_and_open_reply(review_id, review_info):
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