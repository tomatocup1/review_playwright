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
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Page, Browser, BrowserContext
from pathlib import Path
import re
import json
# from ..utils.error_handler import log_login_error, log_reply_error, ErrorType  # 임시 주석 처리

# 임시 더미 클래스 및 함수
class ErrorType:
    UI_CHANGED = "UI_CHANGED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    CAPTCHA_REQUIRED = "CAPTCHA_REQUIRED"
    ELEMENT_NOT_FOUND = "ELEMENT_NOT_FOUND"
    REPLY_INPUT_NOT_FOUND = "REPLY_INPUT_NOT_FOUND"

async def log_login_error(**kwargs):
    logger.error(f"Login error: {kwargs}")

async def log_reply_error(**kwargs):
    logger.error(f"Reply error: {kwargs}")

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 프로젝트 루트 설정
PROJECT_ROOT = Path("C:/Review_playwright")


class BaeminReplyManager:
    """
    배민 답글 등록을 담당하는 매니저 클래스
    """
    
    def __init__(self, browser_or_context):
        self.browser = browser_or_context
        self.page: Optional[Page] = None
        self.context = None
        self.is_context_provided = isinstance(browser_or_context, BrowserContext)
        self.is_logged_in = False
        self.playwright = None
        logger.info(f"배민 매니저 초기화 (Context provided: {self.is_context_provided})")
    
    async def close_popup(self):
        """팝업 닫기 - 다양한 기간의 '보지 않기' 옵션 처리"""
        try:
            # 팝업이 나타날 때까지 잠시 대기
            await asyncio.sleep(2)
            
            # 우선순위: 더 긴 기간의 "보지 않기" 버튼을 먼저 찾아서 클릭
            priority_selectors = [
                # 긴 기간부터 우선적으로 처리
                ('button:has-text("30일간 보지 않기")', '30일간'),
                ('span:has-text("30일간 보지 않기")', '30일간'),
                ('button:has-text("7일간 보지 않기")', '7일간'),
                ('span:has-text("7일간 보지 않기")', '7일간'),
                ('button:has-text("3일 동안 보지 않기")', '3일 동안'),
                ('span:has-text("3일 동안 보지 않기")', '3일 동안'),
                ('button:has-text("1일간 보지 않기")', '1일간'),
                ('span:has-text("1일간 보지 않기")', '1일간'),
                ('button:has-text("오늘 하루 보지 않기")', '오늘 하루'),
                ('span:has-text("오늘 하루 보지 않기")', '오늘 하루')
            ]
            
            # 먼저 우선순위 선택자로 시도
            for selector, period in priority_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.click()
                        logger.info(f"팝업을 닫았습니다: {period} 보지 않기")
                        await asyncio.sleep(1)
                        return True
                except:
                    continue
            
            # "보지 않기"가 포함된 모든 요소를 찾아서 처리
            try:
                # 모든 버튼과 span 요소 확인
                elements = await self.page.query_selector_all('button, span')
                for element in elements:
                    try:
                        text = await element.text_content()
                        if text and "보지 않기" in text and await element.is_visible():
                            await element.click()
                            logger.info(f"팝업을 닫았습니다: {text.strip()}")
                            await asyncio.sleep(1)
                            return True
                    except:
                        continue
            except:
                pass
                
            logger.debug("닫을 팝업이 없거나 이미 닫혀있습니다")
            return False
            
        except Exception as e:
            logger.debug(f"팝업 처리 중 예외 발생: {str(e)}")
            return False

    async def handle_popups(self):
        """모든 종류의 팝업 처리"""
        try:
            # 먼저 "보지 않기" 타입 팝업 처리 시도
            await self.close_popup()
            
            # 추가적인 팝업 처리 (닫기, 확인 등)
            await asyncio.sleep(1)
            
            # 다양한 팝업 닫기 버튼 선택자
            popup_close_selectors = [
                'button:has-text("닫기")',
                'button:has-text("확인")',
                '[aria-label="Close"]',
                '[aria-label="닫기"]',
                '.close-button',
                '.popup-close',
                'button.close',
                'button[aria-label="close"]',
                'button[aria-label="닫기"]',
                '[role="button"][aria-label="close"]'
            ]
            
            closed_count = 0
            for selector in popup_close_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    for element in elements:
                        if await element.is_visible():
                            await element.click()
                            closed_count += 1
                            logger.info(f"추가 팝업 닫기: {selector}")
                            await asyncio.sleep(0.5)
                except:
                    continue
            
            if closed_count > 0:
                logger.info(f"추가로 {closed_count}개의 팝업을 닫았습니다")
                
        except Exception as e:
            logger.debug(f"팝업 처리 중 예외 발생: {str(e)}")
    
    async def __aenter__(self):
        await self.initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        
    async def initialize(self):
        """브라우저 컨텍스트 및 페이지 초기화"""
        try:
            # 이미 페이지가 있으면 초기화하지 않음
            if self.page:
                logger.info("페이지가 이미 존재합니다")
                return
                
            if self.is_context_provided:
                self.context = self.browser
                logger.info("제공된 BrowserContext 사용")
            else:
                # 더 자세한 설정으로 컨텍스트 생성
                self.context = await self.browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='ko-KR',
                    timezone_id='Asia/Seoul',
                    accept_downloads=False,
                    ignore_https_errors=True
                )
                self.context.set_default_timeout(60000)
            
            # 페이지가 없을 때만 생성
            if not self.page:
                self.page = await self.context.new_page()
                
                # 페이지 타임아웃 설정
                self.page.set_default_timeout(30000)
                
                # 팝업 차단
                self.page.on('popup', lambda popup: asyncio.create_task(popup.close()))
                
                logger.info("페이지 초기화 완료")
            
        except Exception as e:
            logger.error(f"초기화 실패: {str(e)}")
            raise
            
    async def login(self, username: str, password: str) -> bool:
        """
        배민 사장님사이트 로그인
        """
        try:
            logger.info("배민 로그인 시작")
            
            # 페이지가 없으면 초기화
            if not self.page:
                logger.error("페이지가 초기화되지 않았습니다")
                return False
            
            # CEO 페이지로 먼저 이동
            await self.page.goto('https://biz-member.baemin.com/login', wait_until='networkidle')
            await asyncio.sleep(2)
            
            current_url = self.page.url
            logger.info(f"초기 이동 후 URL: {current_url}")
            
            # 이미 로그인되어 있는지 확인 (mypage도 로그인 상태로 간주)
            if ('ceo.baemin.com' in current_url or 'self.baemin.com' in current_url or 'mypage' in current_url) and 'login' not in current_url:
                logger.info("이미 로그인되어 있습니다")
                self.is_logged_in = True
                return True
            
            # 로그인 페이지로 리다이렉트 확인
            if 'login' in current_url:
                logger.info("로그인 페이지로 리다이렉트됨")
            else:
                # 로그인 페이지로 직접 이동
                login_url = 'https://biz-member.baemin.com/login?returnUrl=https%3A%2F%2Fceo.baemin.com%2F'
                logger.info(f"로그인 페이지로 직접 이동: {login_url}")
                await self.page.goto(login_url, wait_until='domcontentloaded', timeout=30000)
                await asyncio.sleep(3)
            
            # 로그인 폼 처리
            try:
                # 페이지가 완전히 로드될 때까지 대기
                await self.page.wait_for_load_state('networkidle', timeout=10000)
                
                # ID 입력 필드 찾기 - 더 구체적인 셀렉터 사용
                id_input = None
                id_selectors = [
                    'input#username',
                    'input[name="username"]',
                    'input[placeholder*="아이디"]',
                    'input[autocomplete="username"]',
                    'input[type="text"]:not([type="hidden"])'
                ]
                
                for selector in id_selectors:
                    try:
                        elements = await self.page.query_selector_all(selector)
                        for element in elements:
                            if await element.is_visible():
                                id_input = element
                                logger.info(f"ID 입력 필드 찾음: {selector}")
                                break
                        if id_input:
                            break
                    except:
                        continue
                
                if not id_input:
                    # 스크린샷 저장
                    screenshot_path = PROJECT_ROOT / 'logs' / f'login_no_id_field_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
                    await self.page.screenshot(path=str(screenshot_path), full_page=True)
                    logger.error(f"ID 입력 필드를 찾을 수 없습니다. 스크린샷: {screenshot_path}")
                    
                    # 페이지 소스 일부 로깅
                    page_content = await self.page.content()
                    logger.info(f"페이지 HTML 일부: {page_content[:500]}...")
                    
                    # 에러 로깅
                    await log_login_error(
                        platform='baemin',
                        username=username,
                        error_type=ErrorType.UI_CHANGED,
                        error_message="로그인 페이지에서 ID 입력 필드를 찾을 수 없습니다",
                        screenshot_path=str(screenshot_path),
                        current_url=self.page.url
                    )
                    
                    raise Exception("ID 입력 필드를 찾을 수 없습니다")
                
                # ID 입력
                await id_input.click()
                await asyncio.sleep(0.5)
                await id_input.fill('')
                await asyncio.sleep(0.5)
                await id_input.type(username, delay=100)
                await asyncio.sleep(1)
                
                # 비밀번호 입력 필드 찾기
                pw_input = None
                pw_selectors = [
                    'input#password',
                    'input[name="password"]',
                    'input[placeholder*="비밀번호"]',
                    'input[autocomplete="current-password"]',
                    'input[type="password"]'
                ]
                
                for selector in pw_selectors:
                    try:
                        elements = await self.page.query_selector_all(selector)
                        for element in elements:
                            if await element.is_visible():
                                pw_input = element
                                logger.info(f"비밀번호 입력 필드 찾음: {selector}")
                                break
                        if pw_input:
                            break
                    except:
                        continue
                
                if not pw_input:
                    # 스크린샷 저장
                    screenshot_path = PROJECT_ROOT / 'logs' / f'login_no_pw_field_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
                    await self.page.screenshot(path=str(screenshot_path), full_page=True)
                    
                    # 에러 로깅
                    await log_login_error(
                        platform='baemin',
                        username=username,
                        error_type=ErrorType.UI_CHANGED,
                        error_message="로그인 페이지에서 비밀번호 입력 필드를 찾을 수 없습니다",
                        screenshot_path=str(screenshot_path),
                        current_url=self.page.url
                    )
                    
                    raise Exception("비밀번호 입력 필드를 찾을 수 없습니다")
                
                # 비밀번호 입력
                await pw_input.click()
                await asyncio.sleep(0.5)
                await pw_input.fill('')
                await asyncio.sleep(0.5)
                await pw_input.type(password, delay=100)
                await asyncio.sleep(1)
                
                # 로그인 버튼 찾기
                login_button = None
                login_button_selectors = [
                    'button[type="submit"]',
                    'button:has-text("로그인")',
                    'input[type="submit"]',
                    'button.login-button',
                    'button#loginBtn',
                    'button[class*="login"]'
                ]
                
                for selector in login_button_selectors:
                    try:
                        elements = await self.page.query_selector_all(selector)
                        for element in elements:
                            if await element.is_visible():
                                text = await element.text_content()
                                if '로그인' in str(text) or not text:  # 텍스트가 없는 submit 버튼도 포함
                                    login_button = element
                                    logger.info(f"로그인 버튼 찾음: {selector}")
                                    break
                        if login_button:
                            break
                    except:
                        continue
                
                if login_button:
                    await login_button.click()
                    logger.info("로그인 버튼 클릭")
                else:
                    # Enter 키로 로그인 시도
                    logger.info("로그인 버튼을 찾을 수 없어 Enter 키로 시도")
                    await pw_input.press('Enter')
                
                # 로그인 처리 대기
                logger.info("로그인 처리 대기 중...")
                await asyncio.sleep(5)
                
                # 로그인 성공 확인
                try:
                    # URL 변경 대기
                    await self.page.wait_for_function(
                        "() => (window.location.href.includes('ceo.baemin.com') || window.location.href.includes('self.baemin.com')) && !window.location.href.includes('login')",
                        timeout=10000
                    )
                    logger.info("로그인 성공 - 메인 페이지로 이동됨")
                    self.is_logged_in = True
                    return True
                except:
                    # URL 직접 확인
                    final_url = self.page.url
                    logger.info(f"로그인 후 URL: {final_url}")
                    
                    if ('ceo.baemin.com' in final_url or 'self.baemin.com' in final_url or 'mypage' in final_url) and 'login' not in final_url:
                        logger.info("로그인 성공")
                        self.is_logged_in = True
                        return True
                    else:
                        # 에러 메시지 확인
                        error_text = ""
                        try:
                            error_msg = await self.page.query_selector('.error-message, .alert-danger, [class*="error"]')
                            if error_msg:
                                error_text = await error_msg.text_content()
                                logger.error(f"로그인 에러 메시지: {error_text}")
                        except:
                            pass
                        
                        logger.error("로그인 실패 - URL이 변경되지 않음")
                        # 에러 스크린샷
                        screenshot_path = PROJECT_ROOT / 'logs' / f'login_failed_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
                        await self.page.screenshot(path=str(screenshot_path))
                        logger.info(f"로그인 실패 스크린샷: {screenshot_path}")
                        
                        # 에러 유형 판단
                        error_type = ErrorType.INVALID_CREDENTIALS
                        if "잘못" in error_text or "오류" in error_text or "일치" in error_text:
                            error_type = ErrorType.INVALID_CREDENTIALS
                        elif "잠긴" in error_text or "잠겨" in error_text:
                            error_type = ErrorType.ACCOUNT_LOCKED
                        elif "보안" in error_text or "인증" in error_text:
                            error_type = ErrorType.CAPTCHA_REQUIRED
                        
                        # 에러 로깅
                        await log_login_error(
                            platform='baemin',
                            username=username,
                            error_type=error_type,
                            error_message=error_text or "로그인 실패 - URL이 변경되지 않음",
                            screenshot_path=str(screenshot_path),
                            current_url=final_url
                        )
                        
                        return False
            except Exception as e:
                logger.error(f"로그인 폼 처리 중 오류: {str(e)}")
                # 스크린샷 저장
                try:
                    screenshot_path = PROJECT_ROOT / 'logs' / f'login_error_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
                    await self.page.screenshot(path=str(screenshot_path))
                    logger.info(f"로그인 에러 스크린샷 저장: {screenshot_path}")
                except:
                    pass
                return False
                
        except Exception as e:
            logger.error(f"로그인 중 오류 발생: {str(e)}")
            return False
    
    async def navigate_to_reviews(self, platform_code: str) -> bool:
        """리뷰 관리 페이지로 이동"""
        try:
            # 새로운 URL 형식으로 시도
            review_url = f"https://self.baemin.com/shops/{platform_code}/reviews"
            logger.info(f"리뷰 페이지 이동 시도: {review_url}")
            
            await self.page.goto(review_url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(3)
            
            current_url = self.page.url
            logger.info(f"리뷰 페이지 로드 완료. 현재 URL: {current_url}")
            
            # 페이지 로드 확인
            if 'reviews' in current_url:
                logger.info("리뷰 페이지 도착 성공")
                
                # 팝업 처리 추가
                await self.handle_popups()

                # 미답변 탭 클릭 시도
                try:
                    no_comment_tab = await self.page.wait_for_selector('#no-comment', timeout=5000)
                    await no_comment_tab.click()
                    logger.info("미답변 탭 클릭 완료")
                    await asyncio.sleep(2)
                except:
                    try:
                        no_comment_tab = await self.page.wait_for_selector('button:has-text("미답변")', timeout=3000)
                        await no_comment_tab.click()
                        logger.info("미답변 탭 클릭 완료 (대체 선택자)")
                        await asyncio.sleep(2)
                    except:
                        logger.warning("미답변 탭을 찾을 수 없습니다 - 계속 진행")
                
                return True
            else:
                # 구 URL 형식 시도
                review_url_old = f'https://ceo.baemin.com/shop/{platform_code}/review'
                logger.info(f"새 URL 실패, 구 URL로 재시도: {review_url_old}")
                
                await self.page.goto(review_url_old, wait_until='networkidle', timeout=30000)
                await asyncio.sleep(3)
                
                return True
                
        except Exception as e:
            logger.error(f"리뷰 페이지 이동 실패: {str(e)}")
            return False
    
    async def find_review_and_click_reply(self, review_id: str, review_info: dict = None):
        """리뷰를 찾고 답글 버튼을 클릭 - original_id 기반 매칭 + 필드별 매칭"""
        try:
            logger.info(f"리뷰 검색 시작 - Review ID: {review_id}")
            
            # review_id에서 original_id 추출
            original_id = review_id.replace('baemin_', '') if 'baemin_' in review_id else review_id
            logger.info(f"Original ID 추출: {original_id}")
            
            # 필드별 매칭을 위한 정보 추출
            if review_info:
                review_name = review_info.get('review_name', '')
                rating = review_info.get('rating', 0)
                review_content = review_info.get('review_content', '')
                ordered_menu = review_info.get('ordered_menu', '')
                logger.info(f"필드별 매칭 정보: name={review_name}, rating={rating}, content={review_content[:30]}..., menu={ordered_menu}")
            
            # 페이지가 로드될 때까지 대기
            await asyncio.sleep(3)
            
            # 크롤러와 동일한 방식으로 DOM에서 리뷰 찾기
            max_attempts = 10
            for attempt in range(max_attempts):
                logger.info(f"리뷰 검색 시도 {attempt + 1}/{max_attempts}")
                
                # 다양한 리뷰 컨테이너 셀렉터 시도
                review_selectors = [
                    'div[class*="ReviewContent"]',
                    'div[class*="review-content"]',
                    'div[class*="review-item"]',
                    'article[class*="review"]',
                    '.review-card',
                    '[data-testid*="review"]',
                    'div[data-review-id]'  # 크롤러에서 사용하는 데이터 속성
                ]
                
                for selector in review_selectors:
                    try:
                        review_cards = await self.page.query_selector_all(selector)
                        if review_cards:
                            logger.info(f"{len(review_cards)}개의 리뷰 카드 발견 (selector: {selector})")
                            
                            # 각 리뷰 카드에서 original_id 매칭
                            for card in review_cards:
                                # 데이터 속성에서 ID 확인
                                data_id = await card.get_attribute('data-review-id')
                                if data_id == original_id:
                                    logger.info(f"✅ 데이터 속성으로 매칭 성공: {data_id}")
                                    return await self._click_reply_button(card)
                                
                                # 숨겨진 input 필드에서 ID 확인
                                hidden_inputs = await card.query_selector_all('input[type="hidden"]')
                                for input_elem in hidden_inputs:
                                    input_value = await input_elem.get_attribute('value')
                                    if input_value == original_id:
                                        logger.info(f"✅ 숨겨진 입력으로 매칭 성공: {input_value}")
                                        return await self._click_reply_button(card)
                                
                                # 텍스트 내용에서 ID 확인 (마지막 수단)
                                card_text = await card.inner_text()
                                if original_id in card_text:
                                    logger.info(f"✅ 텍스트 내용으로 매칭 성공: {original_id}")
                                    return await self._click_reply_button(card)
                                
                                # 필드별 매칭 (review_info가 있을 때만)
                                if review_info:
                                    match_score = await self._calculate_match_score(card, review_info)
                                    if match_score >= 3:  # 매칭 임계값
                                        logger.info(f"✅ 필드별 매칭 성공: 점수 {match_score}")
                                        return await self._click_reply_button(card)
                                    
                    except Exception as e:
                        logger.debug(f"셀렉터 {selector} 처리 중 오류: {str(e)}")
                        continue
                
                # 스크롤해서 더 많은 리뷰 로드
                try:
                    await self.page.evaluate('window.scrollBy(0, 800)')
                    await asyncio.sleep(2)
                    logger.info("페이지 스크롤 완료")
                except Exception as e:
                    logger.debug(f"페이지 스크롤 중 오류: {str(e)}")
                    await asyncio.sleep(1)
            
            logger.warning(f"리뷰를 찾을 수 없음: {review_id}")
            
            # 디버그 스크린샷
            debug_path = PROJECT_ROOT / 'logs' / f'review_not_found_{review_id}.png'
            await self.page.screenshot(path=str(debug_path), full_page=True)
            logger.info(f"디버그 스크린샷 저장: {debug_path}")
            
            # 에러 로깅
            await log_reply_error(
                platform='baemin',
                store_code=getattr(self, 'current_store_code', 'unknown'),
                store_name=getattr(self, 'current_store_name', 'unknown'),
                review_id=review_id,
                error_type=ErrorType.ELEMENT_NOT_FOUND,
                error_message=f"리뷰를 찾을 수 없습니다. Review ID: {review_id}",
                screenshot_path=str(debug_path),
                current_url=self.page.url
            )
            
            return False
            
        except Exception as e:
            logger.error(f"리뷰 검색 중 오류: {str(e)}")
            return False
    
    async def _calculate_match_score(self, card, review_info: dict) -> int:
        """필드별 매칭 점수 계산 (기존 답글 매니저 로직 기반)"""
        try:
            score = 0
            card_text = await card.inner_text()
            
            # 1. 리뷰어 이름 매칭 (2점)
            review_name = review_info.get('review_name', '')
            if review_name and review_name in card_text:
                score += 2
                logger.debug(f"리뷰어 이름 매칭: {review_name}")
            
            # 2. 리뷰 내용 매칭 (3점 - 가장 중요)
            review_content = review_info.get('review_content', '')
            if review_content and review_content.strip():
                # 텍스트 정규화해서 비교
                normalized_content = self._normalize_text(review_content)
                normalized_card_text = self._normalize_text(card_text)
                if normalized_content in normalized_card_text:
                    score += 3
                    logger.debug(f"리뷰 내용 매칭: {review_content[:30]}...")
            
            # 3. 별점 매칭 (1점)
            rating = review_info.get('rating', 0)
            if rating > 0:
                # 별점 이미지나 텍스트 확인
                try:
                    star_elements = await card.query_selector_all('svg[class*="star"], img[alt*="별"], .star')
                    if len(star_elements) == rating:
                        score += 1
                        logger.debug(f"별점 매칭: {rating}점")
                    # 텍스트에서 별점 확인
                    elif f"{rating}점" in card_text or f"★" * rating in card_text:
                        score += 1
                        logger.debug(f"별점 텍스트 매칭: {rating}점")
                except:
                    pass
            
            # 4. 주문메뉴 매칭 (1점)
            ordered_menu = review_info.get('ordered_menu', '')
            if ordered_menu and ordered_menu in card_text:
                score += 1
                logger.debug(f"주문메뉴 매칭: {ordered_menu}")
            
            logger.debug(f"필드별 매칭 점수: {score}/7")
            return score
            
        except Exception as e:
            logger.error(f"매칭 점수 계산 중 오류: {str(e)}")
            return 0
    
    def _normalize_text(self, text: str) -> str:
        """텍스트 정규화 (공백, 줄바꿈 제거)"""
        if not text:
            return ""
        import re
        return re.sub(r'\s+', '', text.strip())
    
    async def _click_reply_button(self, card) -> bool:
        """답글 버튼 클릭 헬퍼 메서드"""
        try:
            # 답글 버튼 찾기
            reply_button_selectors = [
                'button:has-text("사장님 댓글 등록")',
                'button:has-text("사장님댓글 등록")',
                'button:has-text("댓글 등록")',
                'button:has-text("답글")',
                'button[class*="reply"]',
                '.reply-button'
            ]
            
            for btn_selector in reply_button_selectors:
                try:
                    reply_button = await card.query_selector(btn_selector)
                    if reply_button and await reply_button.is_visible():
                        await reply_button.scroll_into_view_if_needed()
                        await asyncio.sleep(0.5)
                        await reply_button.click()
                        logger.info(f"답글 버튼 클릭 성공: {btn_selector}")
                        await asyncio.sleep(2)
                        return True
                except Exception as e:
                    logger.debug(f"답글 버튼 클릭 시도 실패 ({btn_selector}): {str(e)}")
                    continue
            
            logger.warning("답글 버튼을 찾을 수 없음 - 오래된 리뷰로 추정")
            return "OLD_REVIEW"
            
        except Exception as e:
            logger.error(f"답글 버튼 클릭 중 오류: {str(e)}")
            return False
    
    async def write_and_submit_reply(self, reply_text: str) -> bool:
        """답글 작성 및 등록"""
        try:
            logger.info("답글 텍스트 입력 시작")
            
            await asyncio.sleep(2)
            
            # textarea 찾기 - 사용자가 제공한 정확한 HTML 구조에 맞게 수정
            textarea_selectors = [
                # 정확한 HTML 구조에 맞는 선택자들
                'textarea.TextArea_b_b8ew_12i8sxif.c_b149_13c33de8.TextArea_b_b8ew_12i8sxih[rows="3"]',  # 모든 클래스 포함
                'textarea.TextArea_b_b8ew_12i8sxif[placeholder=""][rows="3"]',  # 핵심 클래스 + 속성
                'textarea[class*="TextArea_b_b8ew_12i8sxif"][class*="c_b149_13c33de8"][rows="3"]',  # 부분 매칭
                'textarea[class*="TextArea_b_b8ew_12i8sxif"][placeholder=""][rows="3"]',  # 핵심 클래스 + 빈 placeholder
                'textarea.TextArea_b_b8ew_12i8sxif[rows="3"]',  # 핵심 클래스 + rows
                'textarea[placeholder=""][rows="3"]',  # 빈 placeholder + rows
                # 백업 선택자들
                'textarea.TextArea_b_b8ew_12i8sxif',  # 핵심 클래스만
                'textarea[class*="TextArea_b_b8ew_12i8sxif"]',  # 핵심 클래스 부분 매칭
                'textarea[rows="3"]',  # rows 속성
                'textarea',  # 일반 textarea
                # 모달 내부 검색 (백업)
                'div[role="dialog"] textarea',
                'div[class*="modal"] textarea',
                'div[class*="Modal"] textarea'
            ]
            
            textarea = None
            for selector in textarea_selectors:
                try:
                    textarea = await self.page.wait_for_selector(selector, timeout=5000, state='visible')
                    if textarea:
                        logger.info(f"textarea 발견: {selector}")
                        break
                except:
                    continue
            
            if not textarea:
                logger.error("답글 입력 필드를 찾을 수 없습니다")
                # 스크린샷
                screenshot_path = PROJECT_ROOT / 'logs' / f'no_textarea_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
                await self.page.screenshot(path=str(screenshot_path))
                
                # 에러 로깅
                await log_reply_error(
                    platform='baemin',
                    store_code=getattr(self, 'current_store_code', 'unknown'),
                    store_name=getattr(self, 'current_store_name', 'unknown'),
                    review_id=getattr(self, 'current_review_id', 'unknown'),
                    error_type=ErrorType.REPLY_INPUT_NOT_FOUND,
                    error_message="답글 작성을 위한 textarea를 찾을 수 없습니다",
                    screenshot_path=str(screenshot_path),
                    current_url=self.page.url
                )
                
                return False
            
            # 입력 필드 클릭 및 포커스
            await textarea.click()
            await asyncio.sleep(0.5)
            
            # 기존 텍스트 지우기
            await textarea.press('Control+a')
            await asyncio.sleep(0.2)
            await textarea.press('Delete')
            await asyncio.sleep(0.5)
            
            # 텍스트 입력
            await textarea.type(reply_text, delay=50)
            logger.info(f"답글 텍스트 입력 완료: {len(reply_text)}자")
            
            await asyncio.sleep(1)
            
            # 등록 버튼 찾기 - 사용자가 제공한 정확한 HTML 구조에 맞게 수정
            submit_button_selectors = [
                # 정확한 HTML 구조 기반 선택자들
                'button:has(span.Button_b_b8ew_1w1nuchm p.Typography_b_b8ew_1bisyd424:has-text("등록"))',  # 정확한 중첩 구조
                'button:has(span.Button_b_b8ew_1w1nuchm:has-text("등록"))',  # span 포함 구조
                'button:has(p.Typography_b_b8ew_1bisyd424:has-text("등록"))',  # p 태그 직접 매칭
                'button:has(p.c_b149_13c33de7.Typography_b_b8ew_1bisyd424:has-text("등록"))',  # 모든 클래스 포함
                'button:has(span span p:has-text("등록"))',  # span > span > p 구조
                # 기존 작동하는 선택자들 (우선순위 높게)
                'button.Button_b_b8ew_1w1nucha[data-disabled="false"][data-loading="false"]:has-text("등록")',  # 현재 작동하는 선택자
                'button[class*="Button_b_b8ew_1w1nucha"][data-disabled="false"]:has-text("등록")',  # 부분 매칭
                'button[data-disabled="false"][data-loading="false"]:has-text("등록")',  # 상태 기반
                # 백업 선택자들
                'button[data-atelier-component="Button"]:has(p:has-text("등록"))',  # 정확한 구조
                'button.Button_b_b8ew_1w1nucha:has(p:has-text("등록"))',  # 정확한 클래스
                'button[data-disabled="false"]:has(p:has-text("등록"))',  # 활성화된 버튼
                'button:has-text("등록")',
                'button[type="button"]:has(p:has-text("등록"))',
                'button:has-text("작성")',
                'button:has-text("확인")',
                # 모달 내부 등록 버튼 (백업)
                'div[role="dialog"] button:has-text("등록")',
                'div[class*="modal"] button:has-text("등록")',
                'div[class*="Modal"] button:has-text("등록")'
            ]
            
            submit_button = None
            for selector in submit_button_selectors:
                try:
                    submit_button = await self.page.wait_for_selector(selector, timeout=3000, state='visible')
                    if submit_button:
                        # 버튼이 활성화되어 있는지 확인
                        is_disabled = await submit_button.get_attribute('disabled')
                        if not is_disabled:
                            logger.info(f"등록 버튼 찾음: {selector}")
                            break
                except:
                    continue
            
            if not submit_button:
                logger.error("등록 버튼을 찾을 수 없습니다")
                
                # 스크린샷
                screenshot_path = PROJECT_ROOT / 'logs' / f'no_submit_button_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
                await self.page.screenshot(path=str(screenshot_path))
                
                # 에러 로깅
                await log_reply_error(
                    platform='baemin',
                    store_code=getattr(self, 'current_store_code', 'unknown'),
                    store_name=getattr(self, 'current_store_name', 'unknown'),
                    review_id=getattr(self, 'current_review_id', 'unknown'),
                    error_type=ErrorType.ELEMENT_NOT_FOUND,
                    error_message="답글 등록 버튼을 찾을 수 없습니다",
                    reply_text=reply_text[:100],
                    screenshot_path=str(screenshot_path),
                    current_url=self.page.url
                )
                
                return False
            
            # 등록 버튼 클릭
            await submit_button.click()
            logger.info("등록 버튼 클릭 완료")
            
            # 등록 완료 대기
            await asyncio.sleep(3)
            
            logger.info("답글 등록 완료")
            return True
            
        except Exception as e:
            logger.error(f"답글 작성 중 오류: {str(e)}")
            try:
                error_screenshot = PROJECT_ROOT / "logs" / f"reply_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await self.page.screenshot(path=str(error_screenshot))
                logger.info(f"에러 스크린샷 저장: {error_screenshot}")
            except:
                pass
            return False
    
    async def close(self):
        """브라우저 정리"""
        try:
            if self.page:
                await self.page.close()
                logger.info("페이지 종료 완료")
        except Exception as e:
            logger.error(f"페이지 종료 중 오류: {str(e)}")
        
        try:
            if self.context and not self.is_context_provided:
                await self.context.close()
                logger.info("컨텍스트 종료 완료")
        except Exception as e:
            logger.error(f"컨텍스트 종료 중 오류: {str(e)}")
        
        try:
            # 자체 생성한 browser만 종료
            if hasattr(self, 'playwright') and self.playwright:
                if hasattr(self, 'browser') and self.browser:
                    await self.browser.close()
                    logger.info("브라우저 종료 완료")
                await self.playwright.stop()
                logger.info("Playwright 종료 완료")
        except Exception as e:
            logger.error(f"브라우저/Playwright 종료 중 오류: {str(e)}")