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
from ..utils.error_handler import log_login_error, log_reply_error, ErrorType

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
            
            # 이미 로그인되어 있는지 확인
            if ('ceo.baemin.com' in current_url or 'self.baemin.com' in current_url) and 'login' not in current_url:
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
                    
                    if ('ceo.baemin.com' in final_url or 'self.baemin.com' in final_url) and 'login' not in final_url:
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
    
    async def find_review_and_click_reply(self, review_id: str) -> bool:
        """리뷰를 찾고 답글 버튼을 클릭"""
        try:
            logger.info(f"리뷰 검색 시작 - Review ID: {review_id}")
            
            # review_id에서 숫자 부분만 추출
            numeric_id = review_id.replace('baemin_', '') if 'baemin_' in review_id else review_id
            logger.info(f"숫자 ID 추출: {numeric_id}")
            
            # 날짜/시간 정보 추출
            if len(numeric_id) >= 12:
                year = numeric_id[0:4]
                month = numeric_id[4:6]
                day = numeric_id[6:8]
                hour = numeric_id[8:10] if len(numeric_id) > 8 else "00"
                minute = numeric_id[10:12] if len(numeric_id) > 10 else "00"
                
                date_patterns = [
                    f"{year}.{month}.{day}",
                    f"{int(month)}/{int(day)}",
                    f"{month}/{day}",
                    f"{year}-{month}-{day}"
                ]
                time_patterns = [f"{hour}:{minute}", f"{int(hour)}:{minute}"]
                
                logger.info(f"날짜 패턴: {date_patterns}, 시간 패턴: {time_patterns}")
            
            # 페이지가 로드될 때까지 대기
            await asyncio.sleep(3)
            
            # 리뷰 찾기 시도
            max_attempts = 15
            for attempt in range(max_attempts):
                logger.info(f"리뷰 검색 시도 {attempt + 1}/{max_attempts}")
                
                # 다양한 리뷰 카드 셀렉터
                review_selectors = [
                    'div[class*="ReviewContent"]',
                    'div[class*="review-content"]',
                    'div[class*="review-item"]',
                    'article[class*="review"]',
                    '.review-card',
                    '[data-testid*="review"]'
                ]
                
                for selector in review_selectors:
                    try:
                        review_cards = await self.page.query_selector_all(selector)
                        if review_cards:
                            logger.info(f"{len(review_cards)}개의 리뷰 카드 발견 (selector: {selector})")
                            
                            for i, card in enumerate(review_cards):
                                try:
                                    card_text = await card.inner_text()
                                    
                                    # 리뷰 매칭 확인
                                    found = False
                                    if numeric_id in card_text:
                                        found = True
                                        logger.info(f"ID로 리뷰 발견: card #{i}")
                                    else:
                                        # 날짜/시간으로 매칭
                                        for date_pattern in date_patterns:
                                            if date_pattern in card_text:
                                                for time_pattern in time_patterns:
                                                    if time_pattern in card_text:
                                                        found = True
                                                        logger.info(f"날짜/시간으로 리뷰 발견: {date_pattern} {time_pattern}")
                                                        break
                                                if found:
                                                    break
                                    
                                    if found:
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
                                            except:
                                                continue
                                        
                                        logger.warning("답글 버튼을 찾을 수 없음")
                                        
                                except Exception as e:
                                    logger.debug(f"카드 #{i} 처리 중 오류: {str(e)}")
                                    continue
                            
                            break  # 다음 selector로 넘어가지 않음
                    except:
                        continue
                
                # 더보기 버튼 클릭 또는 스크롤
                try:
                    more_button = await self.page.query_selector('button:has-text("더보기")')
                    if more_button and await more_button.is_visible():
                        await more_button.click()
                        logger.info("더보기 버튼 클릭")
                        await asyncio.sleep(3)
                    else:
                        # 스크롤
                        await self.page.evaluate('window.scrollBy(0, 500)')
                        await asyncio.sleep(1)
                except:
                    await self.page.evaluate('window.scrollBy(0, 500)')
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
    
    async def write_and_submit_reply(self, reply_text: str) -> bool:
        """답글 작성 및 등록"""
        try:
            logger.info("답글 텍스트 입력 시작")
            
            await asyncio.sleep(2)
            
            # textarea 찾기
            textarea_selectors = [
                'textarea',
                'div[class*="TextArea"] textarea',
                'textarea[placeholder*="댓글"]',
                'textarea[placeholder*="답글"]',
                '.reply-textarea',
                '#reply-textarea'
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
            
            # 등록 버튼 찾기
            submit_button_selectors = [
                'button:has-text("등록")',
                'button[type="button"]:has(p:has-text("등록"))',
                'button:has-text("작성")',
                'button:has-text("확인")',
                'button.submit-button',
                'button[class*="submit"]'
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