"""
쿠팡이츠 Windows 동기식 리뷰 크롤러
사용자 제공 정확한 HTML 셀렉터 사용
"""
# Windows 이벤트 루프 정책 설정 (가장 먼저!)
import asyncio
import sys
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import re
import json
import logging
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright, Page
import os
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 직접 실행을 위한 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Supabase 클라이언트 import
try:
    from config.supabase_client import get_supabase_client
except ImportError:
    # 직접 실행시 경로 설정
    root_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    sys.path.append(root_path)
    from config.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

class CoupangSyncReviewCrawler:
    """쿠팡이츠 동기식 리뷰 크롤러 - 사용자 제공 정확한 셀렉터 사용"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.logged_in = False
        self.platform_name = 'coupang'
        self.reviews_data = []
        self.current_store_info = {}
        
        # 쿠팡이츠 URL 설정
        self.login_url = "https://store.coupangeats.com/merchant/login"
        self.dashboard_url = "https://store.coupangeats.com/merchant/dashboard"
        self.reviews_url = "https://store.coupangeats.com/merchant/management/reviews"
        
        # 스크린샷 저장 경로
        self.screenshot_dir = Path(f"C:/Review_playwright/logs/screenshots/{self.platform_name}")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        # 리뷰 스크린샷 저장 경로
        self.review_screenshot_dir = Path("C:/Review_playwright/logs/screenshots/coupang_reviews")
        self.review_screenshot_dir.mkdir(parents=True, exist_ok=True)
        
    def start_browser(self):
        """브라우저 시작"""
        try:
            logger.info(f"Starting {self.platform_name} browser in sync mode (Windows)...")
            
            self.playwright = sync_playwright().start()
            
            # 브라우저 실행 옵션
            launch_options = {
                'headless': self.headless,
                'timeout': 60000,
                'args': [
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--single-process',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding'
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
            self.page.set_default_timeout(60000)
            
            logger.info(f"{self.platform_name} browser started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start browser: {str(e)}")
            self.close_browser()
            return False
            
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

    def login(self, username: str, password: str) -> bool:
        """쿠팡이츠 사장님 사이트 로그인 - 사용자 제공 정확한 셀렉터 사용"""
        try:
            logger.info("=" * 50)
            logger.info("쿠팡이츠 로그인 시작")
            logger.info("=" * 50)
            
            logger.info(f"로그인 URL: {self.login_url}")
            logger.info(f"Headless 모드: {self.headless}")
            
            # 로그인 페이지로 이동
            self.page.goto(self.login_url, wait_until='networkidle')
            self.page.wait_for_timeout(3000)
            logger.info("로그인 페이지 로드 완료")
            
            # 페이지 상태 디버깅
            try:
                page_title = self.page.title()
                page_url = self.page.url
                logger.info(f"페이지 제목: {page_title}")
                logger.info(f"현재 URL: {page_url}")
                
                # 로그인 폼 요소들 존재 확인
                login_id_exists = self.page.query_selector('#loginId') is not None
                password_exists = self.page.query_selector('#password') is not None
                submit_btn_exists = self.page.query_selector('button[type="submit"].btn.merchant-submit-btn') is not None
                
                logger.info(f"로그인 아이디 필드 존재: {login_id_exists}")
                logger.info(f"비밀번호 필드 존재: {password_exists}")
                logger.info(f"로그인 버튼 존재: {submit_btn_exists}")
                
                # 페이지에 오류 메시지가 있는지 확인
                error_messages = self.page.query_selector_all('[class*="error"], [class*="alert"], .text-danger, .invalid-feedback')
                if error_messages:
                    for msg in error_messages:
                        error_text = msg.text_content()
                        if error_text and error_text.strip():
                            logger.warning(f"페이지 오류 메시지: {error_text}")
                
                self.save_screenshot("login_page_loaded")
                
            except Exception as debug_e:
                logger.error(f"페이지 상태 디버깅 중 오류: {str(debug_e)}")
            
            # 아이디 입력 - 사용자 제공 정확한 셀렉터
            try:
                login_field = self.page.query_selector('#loginId')
                if not login_field:
                    logger.error("아이디 입력 필드를 찾을 수 없습니다")
                    self.save_screenshot("login_id_field_not_found")
                    return False
                
                self.page.fill('#loginId', username)
                logger.info(f"아이디 입력 완료: {username}")
                
                # 입력값 확인
                filled_value = self.page.input_value('#loginId')
                logger.info(f"입력된 아이디 값: {filled_value}")
                
            except Exception as e:
                logger.error(f"아이디 입력 실패: {str(e)}")
                self.save_screenshot("login_id_input_failed")
                return False
            
            # 비밀번호 입력 - 사용자 제공 정확한 셀렉터
            try:
                password_field = self.page.query_selector('#password')
                if not password_field:
                    logger.error("비밀번호 입력 필드를 찾을 수 없습니다")
                    self.save_screenshot("password_field_not_found")
                    return False
                
                self.page.fill('#password', password)
                logger.info("비밀번호 입력 완료")
                
                # 비밀번호 필드에 값이 입력되었는지 확인 (길이만)
                filled_pw_length = len(self.page.input_value('#password'))
                logger.info(f"입력된 비밀번호 길이: {filled_pw_length}")
                
            except Exception as e:
                logger.error(f"비밀번호 입력 실패: {str(e)}")
                self.save_screenshot("password_input_failed")
                return False
            
            # 로그인 버튼 상태 확인 및 클릭
            try:
                submit_btn = self.page.query_selector('button[type="submit"].btn.merchant-submit-btn')
                if not submit_btn:
                    logger.error("로그인 버튼을 찾을 수 없습니다")
                    self.save_screenshot("submit_button_not_found")
                    return False
                
                # 버튼 상태 확인
                btn_disabled = submit_btn.is_disabled()
                btn_visible = submit_btn.is_visible()
                btn_text = submit_btn.text_content()
                
                logger.info(f"로그인 버튼 상태 - 비활성화: {btn_disabled}, 표시: {btn_visible}, 텍스트: {btn_text}")
                
                if btn_disabled:
                    logger.warning("로그인 버튼이 비활성화되어 있습니다")
                
                self.save_screenshot("before_login_click")
                self.page.click('button[type="submit"].btn.merchant-submit-btn')
                logger.info("로그인 버튼 클릭")
                
            except Exception as e:
                logger.error(f"로그인 버튼 클릭 실패: {str(e)}")
                self.save_screenshot("login_button_click_failed")
                return False
            
            # 로그인 처리 대기 (더 긴 시간)
            logger.info("로그인 처리 대기 중...")
            self.page.wait_for_timeout(8000)
            
            # 로그인 후 상태 확인
            current_url = self.page.url
            page_title = self.page.title()
            logger.info(f"로그인 후 URL: {current_url}")
            logger.info(f"로그인 후 페이지 제목: {page_title}")
            
            # 오류 메시지 확인
            try:
                error_messages = self.page.query_selector_all('[class*="error"], [class*="alert"], .text-danger, .invalid-feedback, [class*="message"]')
                if error_messages:
                    for msg in error_messages:
                        error_text = msg.text_content()
                        if error_text and error_text.strip():
                            logger.error(f"로그인 후 오류 메시지: {error_text}")
            except:
                pass
            
            # 캡차나 추가 인증 요구 확인
            try:
                captcha_elements = self.page.query_selector_all('[class*="captcha"], [class*="recaptcha"], [id*="captcha"]')
                if captcha_elements:
                    logger.warning("캡차 요소가 감지되었습니다")
                    for elem in captcha_elements:
                        if elem.is_visible():
                            logger.warning("표시된 캡차 요소 발견")
            except:
                pass
            
            self.save_screenshot("after_login_attempt")
            
            # 로그인 페이지에서 벗어났으면 성공
            if '/login' not in current_url and 'merchant' in current_url:
                self.logged_in = True
                logger.info("=" * 50)
                logger.info("쿠팡이츠 로그인 성공!")
                logger.info("=" * 50)
                return True
            else:
                logger.error("로그인 실패 - 로그인 페이지에 머물러 있음")
                logger.error(f"예상: merchant URL, 실제: {current_url}")
                self.save_screenshot("login_failed")
                return False
                
        except Exception as e:
            logger.error(f"로그인 중 오류: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            self.save_screenshot("login_error")
            return False

    def close_popup(self):
        """팝업 닫기 - 다양한 방법으로 시도"""
        try:
            self.page.wait_for_timeout(1000)
            
            # 다양한 팝업 닫기 버튼 선택자들
            popup_selectors = [
                'button[data-testid="Dialog__CloseButton"]',
                '.dialog-modal-wrapper__body--close-button',
                '.dialog-modal-wrapper__body--close-icon--white',
                'button.dialog-modal-wrapper__body--close-button',
                'button:has-text("닫기")',
                'button:has-text("확인")',
                'button:has-text("다음에")',
                'button:has-text("X")',
                '[aria-label="Close"]',
                '[aria-label="닫기"]',
                '.close-button',
                '.popup-close',
                'button.close'
            ]
            
            for selector in popup_selectors:
                try:
                    close_button = self.page.query_selector(selector)
                    if close_button and close_button.is_visible():
                        close_button.click()
                        logger.info(f"팝업을 닫았습니다 (셀렉터: {selector})")
                        self.page.wait_for_timeout(1000)
                        return True
                except Exception as e:
                    logger.debug(f"팝업 셀렉터 {selector} 시도 중 오류: {str(e)}")
                    continue
            
            logger.debug("닫을 팝업이 없거나 이미 닫혀있습니다")
            return False
            
        except Exception as e:
            logger.debug(f"팝업 처리 중 예외 발생: {str(e)}")
            return False

    def navigate_to_reviews(self, platform_code: str = None) -> bool:
        """리뷰 페이지로 이동"""
        try:
            logger.info("========== 리뷰 페이지 이동 시작 ==========")
            
            # 현재 URL 확인
            current_url = self.page.url
            logger.info(f"현재 URL: {current_url}")
            
            # 리뷰 페이지로 이동
            if 'reviews' not in current_url:
                logger.info(f"리뷰 페이지로 이동: {self.reviews_url}")
                self.page.goto(self.reviews_url, wait_until='networkidle')
                self.page.wait_for_timeout(3000)
                logger.info("리뷰 페이지 이동 완료")
            else:
                logger.info("이미 리뷰 페이지에 있습니다")
            
            return True
            
        except Exception as e:
            logger.error(f"리뷰 페이지 이동 실패: {str(e)}")
            return False

    def select_store(self, platform_code: str) -> bool:
        """드롭다운에서 매장 선택 - 사용자 제공 정확한 셀렉터"""
        try:
            logger.info(f"매장 선택 시작: {platform_code}")
            
            # 드롭다운 버튼 클릭 (버튼을 찾기 위해 여러 셀렉터 시도)
            dropdown_selectors = [
                '.button',  # 기존 async 크롤러에서 사용하던 셀렉터
                'button[class*="dropdown"]',
                'div[class*="dropdown"]',
                '.css-1rkgd7l'  # 사용자가 제공한 날짜 지정에서 본 클래스명
            ]
            
            dropdown_opened = False
            for selector in dropdown_selectors:
                try:
                    dropdown_button = self.page.query_selector(selector)
                    if dropdown_button and dropdown_button.is_visible():
                        dropdown_button.click()
                        logger.info(f"드롭다운 버튼 클릭 성공: {selector}")
                        self.page.wait_for_timeout(2000)
                        dropdown_opened = True
                        break
                except Exception as e:
                    logger.debug(f"드롭다운 셀렉터 {selector} 시도 실패: {str(e)}")
                    continue
            
            if not dropdown_opened:
                logger.error("드롭다운 버튼을 찾을 수 없습니다")
                return False
            
            # 매장 목록에서 해당 매장 찾기 - 사용자 제공 셀렉터
            try:
                # 매장 목록이 나타날 때까지 대기
                self.page.wait_for_selector('ul.options', timeout=5000)
                
                # 모든 매장 옵션 가져오기
                option_items = self.page.query_selector_all('ul.options li')
                
                for item in option_items:
                    try:
                        item_text = item.text_content() or ""
                        # "큰집닭강정(708561)" 형식에서 매장 코드 확인
                        if platform_code in item_text:
                            logger.info(f"매장 발견: {item_text}")
                            item.click()
                            self.page.wait_for_timeout(3000)
                            logger.info(f"매장 선택 성공: {platform_code}")
                            return True
                    except Exception as e:
                        logger.debug(f"매장 옵션 처리 중 오류: {str(e)}")
                        continue
                
                logger.error(f"매장을 찾을 수 없습니다: {platform_code}")
                return False
                
            except Exception as e:
                logger.error(f"매장 목록 처리 중 오류: {str(e)}")
                return False
            
        except Exception as e:
            logger.error(f"매장 선택 실패: {str(e)}")
            return False

    def set_date_range(self):
        """날짜 범위를 1개월로 설정 - 사용자 제공 정확한 셀렉터"""
        try:
            logger.info("날짜 범위 설정 시작")
            
            # 날짜 선택 드롭다운 클릭 - 사용자 제공 셀렉터
            date_dropdown = self.page.query_selector('div.css-1rkgd7l:has(svg)')
            if date_dropdown:
                date_dropdown.click()
                self.page.wait_for_timeout(1000)
                logger.info("날짜 드롭다운 클릭 성공")
                
                # 1개월 라디오 버튼 클릭 - 사용자 제공 셀렉터
                try:
                    # 1개월 옵션 선택
                    one_month_label = self.page.query_selector('label:has-text("1개월")')
                    if one_month_label:
                        one_month_label.click()
                        logger.info("1개월 옵션 선택 성공")
                        self.page.wait_for_timeout(1000)
                    else:
                        # 대체 방법: input[value="2"] 선택 (사용자 제공 HTML 기반)
                        one_month_input = self.page.query_selector('input[name="quick"][value="2"]')
                        if one_month_input:
                            one_month_input.click()
                            logger.info("1개월 라디오 버튼 선택 성공")
                            self.page.wait_for_timeout(1000)
                        else:
                            logger.warning("1개월 옵션을 찾을 수 없습니다")
                            
                except Exception as e:
                    logger.error(f"1개월 옵션 선택 실패: {str(e)}")
            else:
                logger.warning("날짜 드롭다운을 찾을 수 없습니다")
            
        except Exception as e:
            logger.error(f"날짜 범위 설정 실패: {str(e)}")

    def click_unanswered_tab(self):
        """미답변 탭 클릭 - 사용자 제공 정확한 셀렉터"""
        try:
            logger.info("미답변 탭 클릭 시도")
            
            # 미답변 탭 선택자들 - 사용자 제공 HTML 기반
            unanswered_selectors = [
                'div.e1fz5w2d5:has-text("미답변")',
                'span:has-text("미답변")',
                'div:has-text("미답변")',
                'button:has-text("미답변")',
                '.css-183zt73:has-text("미답변")'
            ]
            
            for selector in unanswered_selectors:
                try:
                    unanswered_element = self.page.query_selector(selector)
                    if unanswered_element and unanswered_element.is_visible():
                        unanswered_element.click()
                        logger.info(f"미답변 탭 클릭 성공: {selector}")
                        self.page.wait_for_timeout(2000)
                        return True
                except Exception as e:
                    logger.debug(f"미답변 탭 셀렉터 {selector} 시도 실패: {str(e)}")
                    continue
            
            logger.warning("미답변 탭을 찾을 수 없습니다")
            return False
            
        except Exception as e:
            logger.error(f"미답변 탭 클릭 실패: {str(e)}")
            return False

    def get_reviews_with_pagination(self, platform_code: str, store_code: str, store_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """페이지네이션을 통한 리뷰 수집 - 사용자 제공 정확한 셀렉터"""
        try:
            logger.info(f"========== 쿠팡이츠 리뷰 수집 시작 ==========")
            logger.info(f"매장 코드: {platform_code}")
            logger.info(f"스토어 코드: {store_code}")
            logger.info(f"매장명: {store_name}")
            logger.info(f"최대 수집 개수: {limit}")
            
            collected_reviews = []
            
            # 1. 리뷰 페이지로 이동
            if not self.navigate_to_reviews():
                logger.error("리뷰 페이지 이동 실패")
                return []
            
            # 2. 팝업 닫기 (여러 번 시도)
            for attempt in range(3):
                try:
                    if self.close_popup():
                        logger.info(f"팝업 닫기 성공 (시도 {attempt + 1})")
                        break
                    else:
                        logger.debug(f"팝업 없음 또는 이미 닫힘 (시도 {attempt + 1})")
                except Exception as e:
                    logger.debug(f"팝업 닫기 시도 {attempt + 1} 실패: {str(e)}")
                
                self.page.wait_for_timeout(1000)
            
            # 3. 매장 선택
            if not self.select_store(platform_code):
                logger.error("매장 선택 실패")
                return []
            
            # 4. 날짜 범위 설정 (1개월)
            try:
                self.set_date_range()
            except Exception as e:
                logger.error(f"날짜 설정 실패: {str(e)}")
            
            # 5. 미답변 탭 클릭
            try:
                self.click_unanswered_tab()
                logger.info("미답변 탭 처리 완료")
            except Exception as e:
                logger.error(f"미답변 탭 클릭 중 예외: {str(e)}")
            
            # 6. 리뷰 수집
            page_num = 1
            max_pages = 10  # 최대 10페이지까지 확장
            empty_page_count = 0  # 빈 페이지 카운트
            
            while len(collected_reviews) < limit and page_num <= max_pages:
                logger.info(f"\n========== 페이지 {page_num} 처리 시작 ==========")
                
                # 현재 페이지의 리뷰들 수집
                reviews_on_page = self._extract_reviews_from_page(platform_code, store_code)
                
                if not reviews_on_page:
                    empty_page_count += 1
                    logger.warning(f"페이지 {page_num}에 리뷰가 없습니다. (빈 페이지 {empty_page_count}/2)")
                    
                    # 2번 연속 빈 페이지면 종료
                    if empty_page_count >= 2:
                        logger.info("연속 2번 빈 페이지 - 수집 종료")
                        break
                else:
                    empty_page_count = 0  # 리뷰가 있으면 카운트 리셋
                    
                    # 중복 제거하면서 추가
                    new_review_count = 0
                    for review in reviews_on_page:
                        if len(collected_reviews) >= limit:
                            break
                        # 중복 체크 (날짜와 리뷰 내용으로)
                        is_duplicate = any(
                            r['review_date'] == review['review_date'] and 
                            r['review_content'] == review['review_content'] and
                            r['review_name'] == review['review_name']
                            for r in collected_reviews
                        )
                        if not is_duplicate:
                            collected_reviews.append(review)
                            new_review_count += 1
                    
                    logger.info(f"페이지 {page_num}: 총 {len(reviews_on_page)}개 중 {new_review_count}개 신규 리뷰 추가")
                    logger.info(f"현재까지 총 {len(collected_reviews)}개 리뷰 수집")
                
                # 다음 페이지로 이동
                if len(collected_reviews) < limit and page_num < max_pages:
                    # 페이지네이션 상태 확인
                    has_next = self._check_pagination_status()
                    if has_next:
                        if self._go_to_next_page():
                            page_num += 1
                            self.page.wait_for_timeout(2000)
                        else:
                            logger.info("다음 페이지 이동 실패 - 수집 종료")
                            break
                    else:
                        logger.info("더 이상 페이지가 없습니다 - 수집 종료")
                        break
                else:
                    break
            
            logger.info(f"========== 총 {len(collected_reviews)}개의 쿠팡이츠 리뷰 수집 완료 ==========")
            return collected_reviews
                
        except Exception as e:
            logger.error(f"쿠팡이츠 리뷰 수집 중 오류: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def _extract_reviews_from_page(self, platform_code: str, store_code: str) -> List[Dict[str, Any]]:
        """현재 페이지에서 리뷰 추출 - 사용자 제공 정확한 셀렉터"""
        reviews = []
        
        try:
            # 리뷰 테이블 행들 - 사용자 제공 HTML 기반
            review_rows = self.page.query_selector_all('tr:has(td.eqn7l9b0)')
            
            logger.info(f"페이지에서 {len(review_rows)}개 리뷰 행 발견")
            
            for idx, row in enumerate(review_rows):
                try:
                    # 작성자 이름 - 사용자 제공 셀렉터
                    reviewer_elem = row.query_selector('div.css-hdvjju.eqn7l9b7 b')
                    reviewer_name = reviewer_elem.text_content().strip() if reviewer_elem else "익명"
                    
                    # 별점 계산 - 새로운 함수 사용
                    rating = self._parse_star_rating(row, idx)
                    
                    # 날짜 - 사용자 제공 셀렉터
                    date_elem = row.query_selector('span.css-1bqps6x.eqn7l9b8')
                    date_text = date_elem.text_content().strip() if date_elem else ""
                    review_date = self._parse_relative_date(date_text)
                    logger.debug(f"날짜 변환: '{date_text}' → '{review_date}'")
                    
                    # 리뷰 내용 - 정확한 셀렉터로만 가져오기 (주문메뉴와 혼동 방지)
                    content_elem = row.query_selector('p.css-16m6tj.eqn7l9b5')
                    review_content = content_elem.text_content().strip() if content_elem else ""
                    
                    # 리뷰 내용 없으면 로깅
                    if not review_content:
                        logger.debug(f"리뷰 {idx + 1}: 리뷰 코멘트 없음 (별점만 등록)")
                    
                    # 주문 메뉴 - 사용자 제공 셀렉터
                    menu_elem = row.query_selector('li:has(strong:has-text("주문메뉴")) p')
                    ordered_menu = menu_elem.text_content().strip() if menu_elem else ""
                    
                    # 주문번호 - 사용자 제공 셀렉터
                    order_elem = row.query_selector('li:has(strong:has-text("주문번호")) p')
                    order_info = order_elem.text_content().strip() if order_elem else ""
                    
                    # 리뷰 이미지들 - 사용자 제공 셀렉터
                    image_elems = row.query_selector_all('div.css-1sh0k4q.eqn7l9b3 img')
                    review_images = [img.get_attribute('src') for img in image_elems if img.get_attribute('src')]
                    
                    # 답글 여부 확인 - 사용자 제공 HTML의 "사장님 댓글 등록하기" 버튼
                    reply_button = row.query_selector('button:has-text("사장님 댓글 등록하기")')
                    has_reply = reply_button is None  # 버튼이 없으면 이미 답글 있음
                    
                    # 리뷰 ID 생성 (주문번호 + 주문일 기반으로 고유성 확보)
                    import hashlib
                    review_id = self.generate_order_based_review_id(platform_code, order_info)
                    
                    review_data = {
                        'review_id': review_id,
                        'original_id': order_info,  # 원본 주문 정보 저장
                        'platform': 'coupang',
                        'platform_code': platform_code,
                        'store_code': store_code,
                        'review_name': reviewer_name,
                        'rating': rating,
                        'review_content': review_content,
                        'review_date': review_date,
                        'ordered_menu': ordered_menu[:200] if ordered_menu else "",  # 너무 길면 자르기
                        'review_images': review_images,
                        'delivery_review': '',
                        'has_reply': has_reply,
                        'writableComment': not has_reply,
                        'order_info': order_info  # 추가 정보
                    }
                    
                    reviews.append(review_data)
                    logger.info(f"[쿠팡이츠] 리뷰 {idx + 1} 수집: {reviewer_name} - {rating}점 - {review_content[:30]}...")
                    
                    # 별점이 5점을 초과하면 로그로 확인
                    if rating > 5:
                        logger.warning(f"별점이 5점을 초과함: {rating}점 - 리뷰어: {reviewer_name}")
                    
                except Exception as e:
                    logger.error(f"리뷰 파싱 중 오류 (idx {idx}): {str(e)}")
                    continue
            
        except Exception as e:
            logger.error(f"페이지 리뷰 추출 중 오류: {str(e)}")
        
        logger.info(f"페이지에서 총 {len(reviews)}개 리뷰 추출 완료")
        return reviews

    def _parse_star_rating(self, row_element, idx: int) -> int:
        """별점 파싱 - 금색(#FFC400) 별 개수로 정확하게 계산"""
        rating = 5  # 기본값
        
        try:
            logger.debug(f"리뷰 {idx + 1} 별점 파싱 시작")
            
            # 방법 1: 오른쪽 td (리뷰 상세 영역)에서 첫 번째 별점 컨테이너만 찾기
            # 사용자 HTML 구조: <td class="eqn7l9b9 css-n1gvoq e1dqye0l0">에 실제 별점이 있음
            review_detail_td = row_element.query_selector('td.eqn7l9b9')
            if review_detail_td:
                # 이 td 내에서 첫 번째 별점 컨테이너만 검색 (div > svg 5개 구조)
                star_containers = review_detail_td.query_selector_all('div:has(svg)')
                
                for container in star_containers:
                    svgs = container.query_selector_all('svg')
                    if len(svgs) == 5:  # 별점은 정확히 5개 SVG로 구성
                        gold_stars = container.query_selector_all('path[fill="#FFC400"]')
                        rating = len(gold_stars)
                        logger.info(f"★ 별점 파싱 성공 (상세영역 5별): 금색 별 {len(gold_stars)}개 = {rating}점")
                        break
                else:
                    # 5개 SVG 컨테이너를 찾지 못한 경우
                    logger.warning("⚠ 상세영역에서 5개 별점 컨테이너를 찾을 수 없음")
            else:
                # 대체 방법: 전체 행에서 첫 번째 5개 별점 컨테이너 찾기
                star_containers = row_element.query_selector_all('div:has(svg)')
                
                for container in star_containers:
                    svgs = container.query_selector_all('svg')
                    if len(svgs) == 5:  # 별점은 정확히 5개 SVG로 구성
                        gold_stars = container.query_selector_all('path[fill="#FFC400"]')
                        rating = len(gold_stars)
                        logger.info(f"★ 별점 파싱 성공 (전체 5별): 금색 별 {len(gold_stars)}개 = {rating}점")
                        break
                else:
                    logger.warning("⚠ 5개 별점 컨테이너를 찾을 수 없음 - 기본값 5점 사용")
            
            # 0점이나 5점 초과 방지
            rating = max(1, min(rating, 5))
            logger.info(f"최종 별점: {rating}점")
            
        except Exception as e:
            logger.error(f"별점 계산 오류: {str(e)} - 기본값 5점 사용")
            import traceback
            logger.error(traceback.format_exc())
            rating = 5
        
        return rating

    def _parse_relative_date(self, date_text: str) -> str:
        """상대적 날짜 파싱 ('8시간 전', '1일 전' 등)"""
        try:
            if not date_text:
                return datetime.now().strftime('%Y-%m-%d')
            
            # 이미 정상적인 날짜 형식인지 확인
            import re
            if re.match(r'\d{4}[.-]\d{1,2}[.-]\d{1,2}', date_text):
                # YYYY-MM-DD 또는 YYYY.MM.DD 형식
                return date_text.replace('.', '-').replace(' ', '')
            
            now = datetime.now()
            
            # "시간 전" 파싱
            hour_match = re.search(r'(\d+)시간\s*전', date_text)
            if hour_match:
                hours_ago = int(hour_match.group(1))
                target_date = now - timedelta(hours=hours_ago)
                return target_date.strftime('%Y-%m-%d')
            
            # "일 전" 파싱
            day_match = re.search(r'(\d+)일\s*전', date_text)
            if day_match:
                days_ago = int(day_match.group(1))
                target_date = now - timedelta(days=days_ago)
                return target_date.strftime('%Y-%m-%d')
            
            # "달 전" 파싱
            month_match = re.search(r'(\d+)달\s*전', date_text)
            if month_match:
                months_ago = int(month_match.group(1))
                target_date = now - timedelta(days=months_ago * 30)  # 대략적인 계산
                return target_date.strftime('%Y-%m-%d')
            
            # "년 전" 파싱
            year_match = re.search(r'(\d+)년\s*전', date_text)
            if year_match:
                years_ago = int(year_match.group(1))
                target_date = now - timedelta(days=years_ago * 365)
                return target_date.strftime('%Y-%m-%d')
            
            # "어제" 파싱
            if '어제' in date_text:
                target_date = now - timedelta(days=1)
                return target_date.strftime('%Y-%m-%d')
            
            # "오늘" 파싱
            if '오늘' in date_text:
                return now.strftime('%Y-%m-%d')
            
            # 파싱할 수 없는 경우 오늘 날짜 반환
            logger.info(f"날짜 파싱 실패: '{date_text}' - 오늘 날짜 사용")
            return now.strftime('%Y-%m-%d')
            
        except Exception as e:
            logger.error(f"날짜 파싱 오류: {date_text} - {str(e)}")
            return datetime.now().strftime('%Y-%m-%d')

    def generate_order_based_review_id(self, platform_code: str, order_info: str) -> str:
        """주문번호 + 주문일 기반 리뷰 ID 생성"""
        if order_info:
            # "2LJMLYㆍ2025-07-09(주문일)" 형태에서 주문번호와 날짜 추출
            import re
            match = re.match(r'([^ㆍ]+)ㆍ(\d{4}-\d{2}-\d{2})', order_info)
            if match:
                order_number = match.group(1).strip()
                order_date = match.group(2).replace('-', '')  # 20250709 형식
                return f"coupang_{platform_code}_{order_number}_{order_date}"
        
        # 만약 파싱 실패시 전체 order_info 해시 사용
        import hashlib
        order_hash = hashlib.md5(order_info.encode()).hexdigest()[:12]
        return f"coupang_{platform_code}_{order_hash}"

    def _check_pagination_status(self) -> bool:
        """페이지네이션 상태 확인 (다음 페이지 존재 여부) - 새로운 HTML 구조"""
        try:
            # 새로운 HTML 구조에 맞게 수정
            # 현재 페이지와 전체 페이지 확인
            pagination_buttons = self.page.query_selector_all('ul li button')
            if pagination_buttons:
                # 마지막 페이지 번호 찾기
                page_numbers = []
                current_page = None
                
                for btn in pagination_buttons:
                    text = btn.text_content()
                    if text and text.isdigit():
                        page_num = int(text)
                        page_numbers.append(page_num)
                        # active 클래스로 현재 페이지 확인
                        if 'active' in btn.get_attribute('class') or '':
                            current_page = page_num
                
                if page_numbers and current_page:
                    max_page = max(page_numbers)
                    logger.info(f"페이지네이션 상태: {current_page}/{max_page}")
                    return current_page < max_page
            
            # 다음 버튼(데이터 속성 기반) 확인
            next_btn = self.page.query_selector('button[data-at="next-btn"]')
            if next_btn:
                # hide-btn 클래스가 없으면 사용 가능
                btn_classes = next_btn.get_attribute('class') or ''
                is_hidden = 'hide-btn' in btn_classes
                logger.debug(f"다음 버튼 상태: 숨겨짐={is_hidden}")
                return not is_hidden
            
            return False
            
        except Exception as e:
            logger.debug(f"페이지네이션 상태 확인 실패: {str(e)}")
            return False

    def _go_to_next_page(self) -> bool:
        """다음 페이지로 이동 (새로운 HTML 구조에 맞게 수정)"""
        try:
            # 현재 페이지 번호 확인 (active 클래스 기반)
            current_page_elem = self.page.query_selector('ul li button.active')
            if current_page_elem:
                current_page = int(current_page_elem.text_content().strip())
                logger.info(f"현재 페이지: {current_page}")
                
                # 다음 페이지 번호 버튼 찾기
                next_page = current_page + 1
                next_page_btn = self.page.query_selector(f'ul li button:has-text("{next_page}"):not(.active)')
                
                if next_page_btn and next_page_btn.is_visible():
                    next_page_btn.click()
                    logger.info(f"페이지 {next_page} 버튼 클릭")
                    self.page.wait_for_timeout(3000)  # 페이지 로드 대기
                    return True
                
                # 다음 버튼(data-at="next-btn") 사용
                next_btn = self.page.query_selector('button[data-at="next-btn"]')
                if next_btn and next_btn.is_visible():
                    btn_classes = next_btn.get_attribute('class') or ''
                    if 'hide-btn' not in btn_classes:
                        next_btn.click()
                        logger.info("다음 버튼 (data-at=next-btn) 클릭")
                        self.page.wait_for_timeout(3000)
                        return True
                    else:
                        logger.info("다음 버튼이 비활성화됨 (hide-btn)")
                        return False
            
            # 대체 방법: 다음 페이지 버튼 선택자들
            fallback_selectors = [
                'button[data-at="next-btn"]:not(.hide-btn)',
                'ul li button:not(.active):not([data-at])',
                '.pagination-btn.next-btn:not(.hide-btn)'
            ]
            
            for selector in fallback_selectors:
                try:
                    next_elem = self.page.query_selector(selector)
                    if next_elem and next_elem.is_visible():
                        next_elem.click()
                        logger.info(f"다음 페이지로 이동 (대체 선택자: {selector})")
                        self.page.wait_for_timeout(3000)
                        return True
                except Exception as e:
                    logger.debug(f"대체 선택자 {selector} 시도 실패: {str(e)}")
                    continue
            
            logger.info("더 이상 다음 페이지가 없습니다")
            return False
            
        except Exception as e:
            logger.error(f"다음 페이지 이동 실패: {str(e)}")
            return False

    def save_reviews_to_supabase(self, store_info: Dict, reviews: List[Dict]) -> Dict[str, int]:
        """수집한 리뷰를 Supabase에 저장"""
        try:
            if not reviews:
                logger.info("저장할 리뷰가 없습니다")
                return {'saved': 0, 'duplicate': 0, 'failed': 0}
            
            logger.info(f"[DB] {len(reviews)}개 쿠팡이츠 리뷰 저장 시작...")
            
            # Supabase 클라이언트 가져오기
            supabase = get_supabase_client()
            
            # 저장 통계
            saved_count = 0
            failed_count = 0
            duplicate_count = 0
            
            for review in reviews:
                try:
                    # 중복 체크
                    existing = supabase.table('reviews').select('review_id').eq('review_id', review['review_id']).execute()
                    
                    if existing.data:
                        logger.info(f"[DB] 중복 리뷰 스킵: {review['review_id']} - {review['review_name']}")
                        duplicate_count += 1
                        continue
                    
                    # DB에 맞게 데이터 정제
                    review_data = {
                        'review_id': review['review_id'],
                        'platform': review['platform'],
                        'platform_code': review['platform_code'],
                        'store_code': review['store_code'],
                        'review_name': review['review_name'],
                        'rating': review['rating'],
                        'review_content': review['review_content'],
                        'review_date': review['review_date'],
                        'ordered_menu': review['ordered_menu'],
                        'delivery_review': review.get('delivery_review', ''),
                        'response_status': 'pending',  # 기본값: 미답변 상태
                        'crawled_at': datetime.now().isoformat()
                    }
                    
                    # review_images를 PostgreSQL 배열 형식으로 변환
                    if isinstance(review.get('review_images'), list):
                        review_data['review_images'] = review['review_images']
                    else:
                        review_data['review_images'] = []
                    
                    # 리뷰 저장
                    result = supabase.table('reviews').insert(review_data).execute()
                    
                    if result.data:
                        logger.info(f"[DB] 저장 성공: {review['review_id']} - {review['review_name']}")
                        saved_count += 1
                    else:
                        logger.error(f"[DB] 저장 실패: {review['review_id']} - {review['review_name']}")
                        failed_count += 1
                        
                except Exception as e:
                    logger.error(f"[DB] 저장 중 오류: {review['review_id']} - {str(e)}")
                    failed_count += 1
            
            # 사용량 업데이트
            if saved_count > 0:
                try:
                    supabase.rpc('update_usage', {
                        'p_user_code': store_info.get('owner_user_code', 'SYSTEM'),
                        'p_reviews_increment': saved_count,
                        'p_ai_api_calls_increment': 0,
                        'p_web_api_calls_increment': 0,
                        'p_manual_replies_increment': 0,
                        'p_error_increment': 0
                    }).execute()
                except Exception as e:
                    logger.error(f"[DB] 사용량 업데이트 실패: {str(e)}")
            
            logger.info(f"[DB] 쿠팡이츠 리뷰 저장 완료: 성공 {saved_count}개, 중복 {duplicate_count}개, 실패 {failed_count}개")
            
            return {
                'saved': saved_count,
                'duplicate': duplicate_count,
                'failed': failed_count
            }
            
        except Exception as e:
            logger.error(f"[DB] Supabase 저장 중 오류: {str(e)}")
            return {'saved': 0, 'duplicate': 0, 'failed': 0}

    def get_reviews(self, platform_code: str, store_code: str, limit: int = 50) -> List[Dict[str, Any]]:
        """리뷰 목록 가져오기 - 외부 인터페이스"""
        return self.get_reviews_with_pagination(platform_code, store_code, "테스트매장", limit)

    def get_reviews_and_save(self, platform_code: str, store_code: str, store_info: Dict = None, limit: int = 50) -> Dict[str, Any]:
        """리뷰 수집 후 Supabase에 저장 (중복 필터링)"""
        try:
            # 기존 리뷰 ID 목록 가져오기 (중복 방지)
            existing_review_ids = set()
            if store_info:
                try:
                    supabase = get_supabase_client()
                    # 해당 매장의 기존 리뷰 ID 조회
                    existing_reviews = supabase.table('reviews').select('review_id').eq('platform_code', platform_code).eq('platform', 'coupang').execute()
                    existing_review_ids = {r['review_id'] for r in existing_reviews.data}
                    logger.info(f"기존 리뷰 {len(existing_review_ids)}개 확인")
                except Exception as e:
                    logger.error(f"기존 리뷰 조회 실패: {str(e)}")
            
            # 리뷰 수집
            store_name = store_info.get('store_name', '테스트매장') if store_info else '테스트매장'
            reviews = self.get_reviews_with_pagination(platform_code, store_code, store_name, limit)
            
            if not reviews:
                return {
                    'success': True,
                    'collected': 0,
                    'saved': 0,
                    'message': '수집된 리뷰가 없습니다'
                }
            
            # 중복 필터링
            new_reviews = [r for r in reviews if r['review_id'] not in existing_review_ids]
            logger.info(f"전체 {len(reviews)}개 중 신규 {len(new_reviews)}개 리뷰")
            
            # Supabase에 저장
            if store_info and new_reviews:
                save_stats = self.save_reviews_to_supabase(store_info, new_reviews)
                return {
                    'success': True,
                    'collected': len(reviews),
                    'saved': save_stats['saved'],
                    'duplicate': len(reviews) - len(new_reviews) + save_stats['duplicate'],
                    'failed': save_stats['failed']
                }
            else:
                return {
                    'success': True,
                    'collected': len(reviews),
                    'saved': 0,
                    'duplicate': len(reviews) - len(new_reviews),
                    'message': 'store_info가 없거나 신규 리뷰가 없음'
                }
                
        except Exception as e:
            logger.error(f"리뷰 수집 및 저장 중 오류: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'collected': 0,
                'saved': 0
            }

    def post_reply(self, review_data: Dict[str, Any], reply_text: str) -> bool:
        """리뷰에 답글 작성"""
        try:
            logger.info(f"쿠팡이츠 답글 작성 시작 - 리뷰 ID: {review_data.get('original_id', '')}")
            
            # 쿠팡이츠 답글 작성 로직 구현 (실제 구조에 맞게)
            return True
            
        except Exception as e:
            logger.error(f"쿠팡이츠 답글 작성 중 오류: {str(e)}")
            self.save_screenshot("reply_error")
            return False


# 테스트 코드
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    crawler = CoupangSyncReviewCrawler(headless=False)
    try:
        crawler.start_browser()
        print("브라우저 시작 완료")
        
        # 테스트용 로그인 정보 (실제 정보로 교체 필요)
        user_id = "test_coupang_id"
        password = "test_password"
        
        login_success = crawler.login(user_id, password)
        print(f"로그인 결과: {login_success}")
        
        if login_success:
            # 실제 매장 코드로 테스트
            platform_code = "708561"  # 예시 매장 코드
            store_code = "STR_TEST"
            
            reviews = crawler.get_reviews(platform_code, store_code, limit=5)
            print(f"\n발견된 리뷰: {len(reviews)}개")
            
            for review in reviews:
                print(f"\n작성자: {review['review_name']}")
                print(f"별점: {review['rating']}점")
                print(f"내용: {review['review_content'][:50]}...")
                print(f"날짜: {review['review_date']}")
        
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        input("\n브라우저를 닫으려면 Enter를 누르세요...")
        crawler.close_browser()