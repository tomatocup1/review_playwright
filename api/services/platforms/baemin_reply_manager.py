# -*- coding: utf-8 -*-
"""
배민 답글 등록 매니저 모듈
실제 Playwright를 사용해 배민 사이트에 답글을 등록하는 로직
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
        self.logger = logging.getLogger(__name__)  # logger 추가
        
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
        """브라우저 초기화 (내부 생성용) - headless를 False로 변경하여 디버깅 용이"""
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
        """배민 로그인"""
        try:
            self.logger.info("배민 로그인 시작")
            
            # 페이지가 로그인 페이지인지 확인
            current_url = self.page.url
            self.logger.info(f"현재 URL: {current_url}")
            
            if "login" not in current_url:
                # 로그인 페이지가 아니면 이동
                login_url = "https://biz-member.baemin.com/login"
                self.logger.info(f"로그인 페이지로 재이동: {login_url}")
                await self.page.goto(login_url, wait_until="networkidle", timeout=30000)
            
            # 페이지가 완전히 로드될 때까지 대기
            await self.page.wait_for_load_state("networkidle")
            
            # 로그인 폼 대기
            try:
                await self.page.wait_for_selector('input[name="id"]', timeout=10000)
                self.logger.info("로그인 폼 발견")
            except:
                self.logger.error("로그인 폼을 찾을 수 없음")
                # 스크린샷 저장
                screenshot_path = Path("C:/Review_playwright/logs") / f"login_form_not_found_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await self.page.screenshot(path=str(screenshot_path))
                self.logger.info(f"스크린샷 저장: {screenshot_path}")
                return False
            
            # ID 입력
            self.logger.info(f"아이디 입력: {username[:4]}***")
            await self.page.fill('input[name="id"]', username)
            await asyncio.sleep(0.5)
            
            # 비밀번호 입력
            self.logger.info("비밀번호 입력")
            await self.page.fill('input[name="password"]', password)
            await asyncio.sleep(0.5)
            
            # 로그인 버튼 클릭
            self.logger.info("로그인 버튼 클릭")
            await self.page.click('button[type="submit"]:has-text("로그인")')
            
            # 로그인 완료 대기
            await self.page.wait_for_load_state("networkidle", timeout=10000)
            await asyncio.sleep(3)  # 추가 대기
            
            # 로그인 성공 확인
            current_url = self.page.url
            if "login" not in current_url:
                self.logger.info(f"로그인 성공! 현재 URL: {current_url}")
                self.is_logged_in = True
                return True
            else:
                self.logger.error(f"로그인 실패. 여전히 로그인 페이지: {current_url}")
                return False
                
        except Exception as e:
            self.logger.error(f"로그인 중 오류 발생: {str(e)}")
            # 에러 스크린샷 저장
            try:
                screenshot_path = Path("C:/Review_playwright/logs") / f"login_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await self.page.screenshot(path=str(screenshot_path))
                self.logger.info(f"에러 스크린샷 저장: {screenshot_path}")
            except:
                pass
            return False
            
    async def navigate_to_review_page(self, platform_code: str) -> bool:
        """리뷰 관리 페이지로 이동"""
        try:
            self.logger.info(f"리뷰 관리 페이지로 이동 - platform_code: {platform_code}")
            
            # 리뷰 URL로 직접 이동
            review_url = f'https://self.baemin.com/shops/{platform_code}/reviews'
            self.logger.info(f"리뷰 URL: {review_url}")
            
            # 페이지 이동 전에 현재 URL 확인
            current_url = self.page.url
            self.logger.info(f"이동 전 URL: {current_url}")
            
            # 리뷰 페이지로 이동
            await self.page.goto(review_url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(3)
            
            # 이동 후 URL 확인
            new_url = self.page.url
            self.logger.info(f"이동 후 URL: {new_url}")
            
            # URL이 올바른지 확인
            if f'/shops/{platform_code}/reviews' not in new_url:
                self.logger.error(f"리뷰 페이지 이동 실패. 현재 URL: {new_url}")
                # 다시 시도
                await self.page.goto(review_url, wait_until='networkidle', timeout=30000)
                await asyncio.sleep(3)
            
            # 미답변 탭 클릭 (더 정확한 선택자 사용)
            try:
                # ID로 먼저 시도
                no_comment_button = await self.page.wait_for_selector('button#no-comment', timeout=5000)
                if no_comment_button:
                    await no_comment_button.click()
                    self.logger.info("미답변 탭 클릭 성공 (ID 선택자)")
                    await asyncio.sleep(2)
                else:
                    raise Exception("미답변 탭을 찾을 수 없음")
            except:
                try:
                    # 텍스트로 다시 시도
                    no_comment_button = await self.page.wait_for_selector('button:has-text("미답변")', timeout=3000)
                    if no_comment_button:
                        await no_comment_button.click()
                        self.logger.info("미답변 탭 클릭 성공 (텍스트 선택자)")
                        await asyncio.sleep(2)
                except:
                    self.logger.warning("미답변 탭을 찾을 수 없음 - 계속 진행")
            
            # 최종 URL 확인
            final_url = self.page.url
            if '/reviews' in final_url:
                self.logger.info(f"리뷰 페이지 이동 성공: {final_url}")
                return True
            else:
                self.logger.error(f"리뷰 페이지가 아님: {final_url}")
                return False
                
        except Exception as e:
            self.logger.error(f"리뷰 페이지 이동 실패: {str(e)}")
            # 에러 스크린샷 저장
            try:
                screenshot_path = Path("C:/Review_playwright/logs") / f"review_page_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await self.page.screenshot(path=str(screenshot_path), full_page=True)
                self.logger.info(f"에러 스크린샷 저장: {screenshot_path}")
            except:
                pass
            return False
            
    async def find_review_and_open_reply(self, review_id: str, review_info: dict = None) -> bool:
        """특정 리뷰를 찾고 답글 모드 열기 - 다양한 정보로 매칭"""
        try:
            self.logger.info(f"리뷰 검색 시작 - review_id: {review_id}")
            
            # review_info에서 매칭에 필요한 정보 추출
            if review_info:
                target_name = review_info.get('review_name', '')
                target_content = review_info.get('review_content', '')
                target_rating = review_info.get('rating', 0)
                target_date = review_info.get('review_date', '')
                target_menu = review_info.get('ordered_menu', '')
                
                self.logger.info(f"매칭 정보 - 작성자: {target_name}, 별점: {target_rating}, 날짜: {target_date}")
                self.logger.info(f"리뷰 내용: {target_content[:50]}...")
                self.logger.info(f"주문 메뉴: {target_menu}")
            else:
                self.logger.warning("review_info가 제공되지 않음 - review_id로만 검색")
                target_name = target_content = target_menu = ""
                target_rating = 0
                target_date = ""
            
            # 날짜를 상대적 표현으로 변환
            relative_date = None
            if target_date:
                try:
                    review_date = datetime.strptime(target_date, "%Y-%m-%d").date()
                    today = datetime.now().date()
                    days_diff = (today - review_date).days
                    
                    # 이번 주의 시작일 (월요일) 계산
                    today_weekday = today.weekday()
                    this_week_start = today - timedelta(days=today_weekday)
                    last_week_start = this_week_start - timedelta(days=7)
                    
                    if days_diff == 0:
                        relative_date = "오늘"
                    elif days_diff == 1:
                        relative_date = "어제"
                    elif review_date >= this_week_start:
                        relative_date = "이번주"
                    elif review_date >= last_week_start:
                        relative_date = "지난주"
                    else:
                        relative_date = f"{days_diff}일 전"
                        
                    self.logger.info(f"날짜 변환: {target_date} -> {relative_date}")
                except Exception as e:
                    self.logger.warning(f"날짜 변환 실패: {str(e)}")
            
            # 페이지가 로드될 때까지 대기
            await asyncio.sleep(3)
            
            # 여러 번 시도
            max_attempts = 3
            for attempt in range(max_attempts):
                self.logger.info(f"리뷰 검색 시도 {attempt + 1}/{max_attempts}")
                
                # 리뷰 컨테이너 찾기 (다양한 선택자 시도)
                review_containers = await self.page.query_selector_all('div[class*="ReviewContent"]')
                if not review_containers:
                    review_containers = await self.page.query_selector_all('article[class*="review"]')
                if not review_containers:
                    review_containers = await self.page.query_selector_all('li[class*="review-item"]')
                if not review_containers:
                    review_containers = await self.page.query_selector_all('div.review-container')
                
                self.logger.info(f"{len(review_containers)}개의 리뷰 컨테이너 발견")
                
                # 각 리뷰 컨테이너 검사
                for i, container in enumerate(review_containers):
                    try:
                        # 컨테이너의 전체 텍스트 가져오기
                        container_text = await container.text_content()
                        if not container_text:
                            continue
                        
                        # 디버깅: 처음 몇 개 리뷰의 내용 로깅
                        if i < 5:
                            self.logger.info(f"리뷰 {i+1} 텍스트: {container_text[:150]}...")
                        
                        # 매칭 점수 계산
                        match_score = 0
                        match_details = []
                        
                        # 1. 작성자 이름 매칭
                        if target_name and target_name in container_text:
                            match_score += 2  # 이름은 중요도 높음
                            match_details.append(f"이름 매칭: {target_name}")
                        
                        # 2. 리뷰 내용 매칭 (공백과 줄바꿈 제거하고 비교)
                        if target_content:
                            # 정규화: 공백, 줄바꿈 제거
                            clean_target = ''.join(target_content.split())
                            clean_container = ''.join(container_text.split())
                            
                            # 완전 매칭 또는 부분 매칭
                            if clean_target in clean_container:
                                match_score += 3  # 내용은 가장 중요
                                match_details.append("내용 매칭")
                        
                        # 3. 별점 매칭 - 별점은 표시되지 않을 수 있으므로 가중치 낮음
                        if target_rating:
                            rating_patterns = [
                                f"{target_rating}점",
                                f"별점 {target_rating}",
                                f"⭐{target_rating}",
                                f"★{target_rating}"
                            ]
                            for pattern in rating_patterns:
                                if pattern in container_text:
                                    match_score += 1
                                    match_details.append(f"별점 매칭: {target_rating}")
                                    break
                        
                        # 4. 날짜 매칭
                        if relative_date and relative_date in container_text:
                            match_score += 1
                            match_details.append(f"날짜 매칭: {relative_date}")
                        
                        # 5. 메뉴 매칭
                        if target_menu and target_menu in container_text:
                            match_score += 1
                            match_details.append(f"메뉴 매칭: {target_menu}")
                        
                        # 매칭 점수 확인 (3점 이상이면 해당 리뷰로 판단)
                        if match_score >= 3:
                            self.logger.info(f"리뷰 매칭 성공! 점수: {match_score}, 상세: {', '.join(match_details)}")
                            
                            # 답글 버튼 찾기
                            reply_button = None
                            button_selectors = [
                                'button:has-text("사장님 댓글 등록하기")',
                                'button:has-text("사장님 댓글")',
                                'button:has-text("댓글 등록")',
                                'button:has-text("답글")',
                                'button.reply-button',
                                'button[class*="reply"]'
                            ]
                            
                            for selector in button_selectors:
                                btn = await container.query_selector(selector)
                                if btn and await btn.is_visible():
                                    reply_button = btn
                                    self.logger.info(f"답글 버튼 발견: {selector}")
                                    break
                            
                            if reply_button:
                                # 버튼이 보이도록 스크롤
                                await reply_button.scroll_into_view_if_needed()
                                await asyncio.sleep(1)
                                
                                # 버튼 클릭
                                await reply_button.click()
                                self.logger.info("답글 버튼 클릭 성공")
                                await asyncio.sleep(2)
                                return True
                            else:
                                self.logger.error("답글 버튼을 찾을 수 없음")
                                # 컨테이너 내 모든 버튼 확인
                                all_buttons = await container.query_selector_all('button')
                                for btn in all_buttons:
                                    btn_text = await btn.text_content()
                                    self.logger.debug(f"발견된 버튼: {btn_text}")
                        
                        # 매칭 점수가 낮지만 일부 일치하는 경우 로깅
                        elif match_score > 0:
                            self.logger.debug(f"부분 매칭 - 점수: {match_score}, 상세: {', '.join(match_details)}")
                            
                    except Exception as e:
                        self.logger.error(f"리뷰 컨테이너 {i+1} 처리 중 에러: {str(e)}")
                        continue
                
                # 못 찾았으면 스크롤만 하고 "더보기" 버튼은 클릭하지 않음
                if attempt < max_attempts - 1:
                    self.logger.info("리뷰를 찾지 못함, 스크롤 후 재시도")
                    await self.page.evaluate("window.scrollBy(0, 500)")
                    await asyncio.sleep(2)
            
            # 모든 시도 실패
            self.logger.error("리뷰를 찾을 수 없음")
            
            # 스크린샷 저장
            screenshot_path = Path("C:/Review_playwright/logs") / f"no_review_found_{review_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            self.logger.info(f"스크린샷 저장: {screenshot_path}")
            
            return False
            
        except Exception as e:
            self.logger.error(f"리뷰 검색 중 오류: {str(e)}")
            return False
    
    async def write_and_submit_reply(self, reply_content: str) -> bool:
        """답글 작성 및 제출"""
        try:
            self.logger.info(f"답글 작성 시작: {reply_content[:50]}...")
            
            # 모달이나 팝업이 열릴 때까지 대기
            await asyncio.sleep(2)
            
            # 여러 선택자 시도
            textarea_selectors = [
                'textarea',
                'div[contenteditable="true"]',
                'input[type="text"][placeholder*="답글"]',
                'textarea[placeholder*="답글"]',
                'textarea[placeholder*="댓글"]',
                'textarea[class*="reply"]',
                'textarea[class*="comment"]',
                'div[role="textbox"]'
            ]
            
            textarea_found = False
            textarea_element = None
            
            for selector in textarea_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    for element in elements:
                        if await element.is_visible():
                            textarea_element = element
                            textarea_found = True
                            self.logger.info(f"답글 입력 필드 발견 (selector: {selector})")
                            break
                    if textarea_found:
                        break
                except:
                    continue
            
            if not textarea_found:
                self.logger.error("답글 입력 필드를 찾을 수 없음")
                return False
            
            # 입력 필드 클릭 및 내용 입력
            await textarea_element.click()
            await asyncio.sleep(0.5)
            
            # 기존 내용 지우기
            await self.page.keyboard.press('Control+A')
            await self.page.keyboard.press('Delete')
            
            # 답글 내용 입력
            await textarea_element.type(reply_content, delay=50)
            self.logger.info(f"답글 내용 입력 완료: {len(reply_content)}자")
            
            await asyncio.sleep(1)
            
            # 등록 버튼 찾기 - 수정된 선택자
            register_button_selectors = [
                # 정확한 등록 버튼 선택자
                'button p:has-text("등록")',
                'button span p.Typography_b_b8ew_1bisyd424:has-text("등록")',
                'button span span p:has-text("등록")',
                # 백업 선택자들
                'button:has-text("등록"):not(:has-text("사장님"))',
                'button[type="submit"]:has-text("등록")',
                'button:has(p:has-text("등록"))'
            ]
            
            button_found = False
            register_button = None
            
            # 먼저 모든 버튼을 확인
            all_buttons = await self.page.query_selector_all('button')
            self.logger.info(f"총 {len(all_buttons)}개의 버튼 발견")
            
            for button in all_buttons:
                try:
                    button_text = await button.text_content()
                    if button_text:
                        button_text = button_text.strip()
                        # "등록"만 있고 "사장님"이 없는 버튼
                        if button_text == "등록" or (button_text.endswith("등록") and "사장님" not in button_text):
                            is_visible = await button.is_visible()
                            is_disabled = await button.get_attribute('disabled')
                            if is_visible and not is_disabled:
                                register_button = button
                                button_found = True
                                self.logger.info(f"등록 버튼 발견: '{button_text}'")
                                break
                except:
                    continue
            
            # 백업: 선택자로 다시 시도
            if not button_found:
                for selector in register_button_selectors:
                    try:
                        buttons = await self.page.query_selector_all(selector)
                        for button in buttons:
                            is_visible = await button.is_visible()
                            is_disabled = await button.get_attribute('disabled')
                            if is_visible and not is_disabled:
                                register_button = button
                                button_found = True
                                self.logger.info(f"등록 버튼 발견 (selector: {selector})")
                                break
                        if button_found:
                            break
                    except:
                        continue
            
            if not button_found or not register_button:
                self.logger.error("등록 버튼을 찾을 수 없음")
                # 디버깅을 위한 스크린샷
                screenshot_path = Path("C:/Review_playwright/logs") / f"no_register_button_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await self.page.screenshot(path=str(screenshot_path))
                self.logger.info(f"스크린샷 저장: {screenshot_path}")
                return False
            
            # 등록 버튼 클릭
            await register_button.click()
            self.logger.info("등록 버튼 클릭 완료")
            
            # 등록 완료 대기
            await asyncio.sleep(3)
            
            # 성공 확인
            self.logger.info("답글 등록 프로세스 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"답글 작성 중 오류: {str(e)}")
            # 에러 스크린샷 저장
            try:
                screenshot_path = Path("C:/Review_playwright/logs") / f"reply_write_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await self.page.screenshot(path=str(screenshot_path))
                self.logger.info(f"에러 스크린샷 저장: {screenshot_path}")
            except:
                pass
            return False
    
    async def post_reply(self, reply_content: str) -> bool:
        """
        답글 등록 (write_and_submit_reply와 동일한 기능)
        """
        return await self.write_and_submit_reply(reply_content)
            
    async def register_reply(self, login_id: str, login_pw: str, platform_code: str,
                        review_id: str, reply_content: str, review_info: dict = None) -> Tuple[bool, str]:
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
                
            # 리뷰 찾고 답글 모드 열기 (review_info 전달)
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


# 단독 실행용 함수
async def register_baemin_reply(login_id: str, login_pw: str, platform_code: str,
                                review_id: str, reply_content: str) -> Tuple[bool, str]:
    """
    배민 답글 등록 함수 (외부에서 호출용)
    """
    async with BaeminReplyManager() as manager:
        return await manager.register_reply(login_id, login_pw, platform_code, review_id, reply_content)