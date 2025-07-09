"""
요기요 Windows 동기식 리뷰 크롤러
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

class YogiyoSyncReviewCrawler:
    """요기요 동기식 리뷰 크롤러 - 사용자 제공 정확한 셀렉터 사용"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.logged_in = False
        self.platform_name = 'yogiyo'
        self.reviews_data = []
        self.current_store_info = {}
        
        # 스크린샷 저장 경로
        self.screenshot_dir = Path(f"C:/Review_playwright/logs/screenshots/{self.platform_name}")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        # 리뷰 스크린샷 저장 경로
        self.review_screenshot_dir = Path("C:/Review_playwright/logs/screenshots/yogiyo_reviews")
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
        """요기요 사장님 사이트 로그인 - 사용자 제공 정확한 셀렉터 사용"""
        try:
            logger.info("=" * 50)
            logger.info("요기요 로그인 시작")
            logger.info("=" * 50)
            
            login_url = "https://ceo.yogiyo.co.kr/login/"
            logger.info(f"로그인 URL: {login_url}")
            
            # 로그인 페이지로 이동
            self.page.goto(login_url, wait_until='networkidle')
            self.page.wait_for_timeout(3000)
            logger.info("로그인 페이지 로드 완료")
            
            # 아이디 입력 - 사용자 제공 정확한 셀렉터
            try:
                # input[name="username"] 사용
                self.page.fill('input[name="username"]', username)
                logger.info(f"아이디 입력 완료: {username}")
            except Exception as e:
                logger.error(f"아이디 입력 실패: {str(e)}")
                return False
            
            # 비밀번호 입력 - 사용자 제공 정확한 셀렉터  
            try:
                # input[name="password"] 사용
                self.page.fill('input[name="password"]', password)
                logger.info("비밀번호 입력 완료")
            except Exception as e:
                logger.error(f"비밀번호 입력 실패: {str(e)}")
                return False
            
            # 로그인 버튼 클릭 - 사용자 제공 정확한 셀렉터
            try:
                # 로그인 버튼의 span을 포함하는 버튼 클릭
                self.page.click('span:has-text("로그인")')
                logger.info("로그인 버튼 클릭")
            except Exception as e:
                # 대체 방법으로 button type=submit 시도
                try:
                    self.page.click('button[type="submit"]')
                    logger.info("로그인 버튼 클릭 (대체 방법)")
                except Exception as e2:
                    logger.error(f"로그인 버튼 클릭 실패: {str(e)} / {str(e2)}")
                    return False
            
            # 로그인 처리 대기
            self.page.wait_for_timeout(5000)
            
            # 로그인 성공 확인
            current_url = self.page.url
            logger.info(f"로그인 후 URL: {current_url}")
            
            # URL 확인으로 로그인 성공 판단
            if 'ceo.yogiyo.co.kr' in current_url and 'login' not in current_url:
                self.logged_in = True
                logger.info("=" * 50)
                logger.info("✓ 요기요 로그인 성공!")
                logger.info("=" * 50)
                return True
            else:
                logger.error("로그인 실패 - URL 확인")
                self.save_screenshot("login_failed")
                return False
                
        except Exception as e:
            logger.error(f"로그인 중 오류: {str(e)}")
            self.save_screenshot("login_error")
            return False

    def navigate_to_reviews(self, platform_code: str = None) -> bool:
        """리뷰 페이지로 이동"""
        try:
            logger.info("========== 리뷰 페이지 이동 시작 ==========")
            
            # 리뷰 페이지 URL로 직접 이동
            review_url = "https://ceo.yogiyo.co.kr/reviews"
            logger.info(f"리뷰 페이지로 이동: {review_url}")
            
            self.page.goto(review_url, wait_until='networkidle')
            self.page.wait_for_timeout(3000)
            logger.info("리뷰 페이지 로드 완료")
            
            return True
            
        except Exception as e:
            logger.error(f"리뷰 페이지 이동 실패: {str(e)}")
            return False

    def select_store_by_platform_code(self, platform_code: str) -> bool:
        """드롭다운에서 매장 선택 - 사용자 제공 정확한 셀렉터"""
        try:
            logger.info(f"매장 선택 시작: {platform_code}")
            
            # 드롭다운 버튼 클릭 - 사용자 제공 셀렉터
            dropdown_button_selector = 'button.StoreSelector__DropdownButton-sc-1rowjsb-11'
            
            try:
                dropdown_button = self.page.query_selector(dropdown_button_selector)
                if dropdown_button and dropdown_button.is_visible():
                    dropdown_button.click()
                    logger.info("드롭다운 버튼 클릭 성공")
                    self.page.wait_for_timeout(2000)
                else:
                    logger.error("드롭다운 버튼을 찾을 수 없습니다")
                    return False
            except Exception as e:
                logger.error(f"드롭다운 버튼 클릭 실패: {str(e)}")
                return False
            
            # 매장 목록에서 해당 매장 찾기 - 사용자 제공 셀렉터
            try:
                # 매장 목록이 나타날 때까지 대기
                self.page.wait_for_selector('ul.List__VendorList-sc-2ocjy3-8', timeout=5000)
                
                # 모든 매장 항목 가져오기
                vendor_items = self.page.query_selector_all('li.List__Vendor-sc-2ocjy3-7')
                
                for item in vendor_items:
                    try:
                        # 매장 ID 추출 - 사용자 제공 셀렉터
                        vendor_id_element = item.query_selector('span.List__VendorID-sc-2ocjy3-1')
                        if vendor_id_element:
                            vendor_id_text = vendor_id_element.text_content()
                            # "ID. 1371806" 형식에서 숫자 추출
                            if vendor_id_text and platform_code in vendor_id_text:
                                # 매장명 가져오기
                                vendor_name_element = item.query_selector('p.List__VendorName-sc-2ocjy3-3')
                                vendor_name = vendor_name_element.text_content() if vendor_name_element else ""
                                
                                logger.info(f"매장 발견: {vendor_name} ({vendor_id_text})")
                                
                                # 매장 클릭
                                item.click()
                                self.page.wait_for_timeout(3000)
                                logger.info(f"매장 선택 성공: {platform_code}")
                                return True
                    except Exception as e:
                        logger.debug(f"매장 항목 처리 중 오류: {str(e)}")
                        continue
                
                logger.error(f"매장을 찾을 수 없습니다: {platform_code}")
                return False
                
            except Exception as e:
                logger.error(f"매장 목록 처리 중 오류: {str(e)}")
                return False
            
        except Exception as e:
            logger.error(f"매장 선택 실패: {str(e)}")
            return False

    def click_unanswered_tab(self) -> bool:
        """미답변 탭 클릭 - 사용자 제공 정확한 셀렉터"""
        try:
            logger.info("미답변 탭 클릭 시도")
            
            # 미답변 탭 셀렉터 - 사용자 제공
            unanswered_tab_selector = 'li.InnerTab__TabItem-sc-14s9mjy-0:has-text("미답변")'
            
            try:
                unanswered_tab = self.page.query_selector(unanswered_tab_selector)
                if unanswered_tab and unanswered_tab.is_visible():
                    unanswered_tab.click()
                    logger.info("미답변 탭 클릭 성공")
                    self.page.wait_for_timeout(3000)
                    return True
                else:
                    logger.warning("미답변 탭을 찾을 수 없습니다")
                    return False
            except Exception as e:
                logger.error(f"미답변 탭 클릭 실패: {str(e)}")
                return False
            
        except Exception as e:
            logger.error(f"미답변 탭 처리 실패: {str(e)}")
            return False

    def get_reviews_with_pagination(self, platform_code: str, store_code: str, limit: int = 50) -> List[Dict[str, Any]]:
        """페이지네이션을 통한 리뷰 수집 - 사용자 제공 정확한 셀렉터"""
        try:
            logger.info(f"========== 요기요 리뷰 수집 시작 ==========")
            logger.info(f"매장 코드: {platform_code}")
            logger.info(f"스토어 코드: {store_code}")
            logger.info(f"최대 수집 개수: {limit}")
            
            collected_reviews = []
            
            # 1. 리뷰 페이지로 이동
            if not self.navigate_to_reviews(platform_code):
                logger.error("리뷰 페이지 이동 실패")
                return []
            
            # 2. 매장 선택
            if not self.select_store_by_platform_code(platform_code):
                logger.error("매장 선택 실패")
                return []
            
            # 3. 미답변 탭 클릭
            if not self.click_unanswered_tab():
                logger.warning("미답변 탭 클릭 실패 - 전체 리뷰로 진행")
            
            # 4. 리뷰 수집
            page_num = 1
            max_pages = 10  # 최대 10페이지까지 확장
            empty_page_count = 0  # 빈 페이지 카운트
            
            while len(collected_reviews) < limit and page_num <= max_pages:
                logger.info(f"\n========== 요기요 페이지 {page_num} 처리 시작 ==========")
                
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
                    if self._go_to_next_page():
                        page_num += 1
                        self.page.wait_for_timeout(3000)
                    else:
                        logger.info("더 이상 페이지가 없습니다 - 수집 종료")
                        break
                else:
                    break
            
            logger.info(f"========== 총 {len(collected_reviews)}개의 요기요 리뷰 수집 완료 ==========")
            return collected_reviews
                
        except Exception as e:
            logger.error(f"요기요 리뷰 수집 중 오류: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def _extract_reviews_from_page(self, platform_code: str, store_code: str) -> List[Dict[str, Any]]:
        """현재 페이지에서 리뷰 추출 - 사용자 제공 정확한 셀렉터"""
        reviews = []
        
        try:
            # 리뷰 컨테이너 - 사용자 제공 셀렉터
            review_containers = self.page.query_selector_all('div.ReviewItem__Container-sc-1oxgj67-0')
            
            logger.info(f"페이지에서 {len(review_containers)}개 리뷰 컨테이너 발견")
            
            for idx, container in enumerate(review_containers):
                try:
                    # 작성자 이름 - 사용자 제공 셀렉터
                    reviewer_name_elem = container.query_selector('h6.Typography__StyledTypography-sc-r9ksfy-0.dZvFzq')
                    reviewer_name = reviewer_name_elem.text_content().strip() if reviewer_name_elem else "익명"
                    
                    # 별점 - 여러 방법으로 시도
                    rating = 5  # 기본값
                    
                    # 방법 1: 사용자 제공 셀렉터로 별점 텍스트 찾기
                    try:
                        rating_elem = container.query_selector('h6.Typography__StyledTypography-sc-r9ksfy-0.cknzqP')
                        if rating_elem:
                            rating_text = rating_elem.text_content().strip()
                            if rating_text and rating_text.replace('.', '').isdigit():
                                rating = int(float(rating_text))
                                if rating > 5:  # 10점 체계라면 2로 나눠기
                                    rating = rating // 2
                        logger.debug(f"별점 (방법1): {rating}점")
                    except Exception as e:
                        logger.debug(f"별점 계산 방법1 실패: {str(e)}")
                    
                    # 방법 2: 별 아이콘 개수로 찾기
                    try:
                        star_icons = container.query_selector_all('svg.star-icon, .star, [class*="star"]')
                        if star_icons and len(star_icons) <= 5:
                            rating = len(star_icons)
                            logger.debug(f"별점 (방법2): {rating}점 (아이콘 {len(star_icons)}개)")
                    except Exception as e:
                        logger.debug(f"별점 계산 방법2 실패: {str(e)}")
                    
                    # 최대 5점으로 제한
                    rating = min(rating, 5)
                    
                    # 리뷰 내용 - 사용자 제공 셀렉터
                    review_content_elem = container.query_selector('p.Typography__StyledTypography-sc-r9ksfy-0.hLRURJ')
                    review_content = review_content_elem.text_content().strip() if review_content_elem else ""
                    
                    # 날짜 - 사용자 제공 셀렉터
                    date_elem = container.query_selector('p.Typography__StyledTypography-sc-r9ksfy-0.jwoVKl')
                    date_text = date_elem.text_content().strip() if date_elem else ""
                    review_date = self._parse_relative_date(date_text)
                    logger.debug(f"날짜 변환: '{date_text}' → '{review_date}'")
                    
                    # 주문 메뉴 - 사용자 제공 셀렉터
                    menu_elem = container.query_selector('p.Typography__StyledTypography-sc-r9ksfy-0.jlzcvj')
                    ordered_menu = menu_elem.text_content().strip() if menu_elem else ""
                    
                    # 리뷰 이미지들 - 사용자 제공 셀렉터
                    image_elems = container.query_selector_all('img.ReviewItem__Image-sc-1oxgj67-1')
                    review_images = [img.get_attribute('src') for img in image_elems if img.get_attribute('src')]
                    
                    # 답글 여부 확인 - 답글쓰기 버튼이 있으면 답글 없음
                    reply_button = container.query_selector('button:has-text("댓글쓰기")')
                    has_reply = reply_button is None  # 댓글쓰기 버튼이 없으면 이미 답글 있음
                    
                    # 리뷰 ID 생성 (날짜 + 리뷰어 + 내용 해시로 고유성 확보)
                    import hashlib
                    content_hash = hashlib.md5(f"{reviewer_name}{review_content}{review_date}".encode()).hexdigest()[:8]
                    review_id = f"yogiyo_{platform_code}_{content_hash}_{datetime.now().strftime('%Y%m%d')}"
                    
                    review_data = {
                        'review_id': review_id,
                        'original_id': f"yogiyo_{platform_code}_{content_hash}",
                        'platform': 'yogiyo',
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
                        'writableComment': not has_reply
                    }
                    
                    reviews.append(review_data)
                    logger.info(f"[요기요] 리뷰 {idx + 1} 수집: {reviewer_name} - {rating}점 - {review_content[:30]}...")
                    
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

    def _parse_relative_date(self, date_text: str) -> str:
        """상대적 날짜 파싱 ('8시간 전', '1일 전' 등)"""
        try:
            if not date_text:
                return datetime.now().strftime('%Y.%m.%d')
            
            # 이미 정상적인 날짜 형식인지 확인
            import re
            if re.match(r'\d{4}[.-]\d{1,2}[.-]\d{1,2}', date_text):
                # YYYY-MM-DD 또는 YYYY.MM.DD 형식
                return date_text.replace('-', '.').replace(' ', '')
            
            now = datetime.now()
            
            # "시간 전" 파싱
            hour_match = re.search(r'(\d+)시간\s*전', date_text)
            if hour_match:
                hours_ago = int(hour_match.group(1))
                target_date = now - timedelta(hours=hours_ago)
                return target_date.strftime('%Y.%m.%d')
            
            # "일 전" 파싱
            day_match = re.search(r'(\d+)일\s*전', date_text)
            if day_match:
                days_ago = int(day_match.group(1))
                target_date = now - timedelta(days=days_ago)
                return target_date.strftime('%Y.%m.%d')
            
            # "달 전" 파싱
            month_match = re.search(r'(\d+)달\s*전', date_text)
            if month_match:
                months_ago = int(month_match.group(1))
                target_date = now - timedelta(days=months_ago * 30)  # 대략적인 계산
                return target_date.strftime('%Y.%m.%d')
            
            # "년 전" 파싱
            year_match = re.search(r'(\d+)년\s*전', date_text)
            if year_match:
                years_ago = int(year_match.group(1))
                target_date = now - timedelta(days=years_ago * 365)
                return target_date.strftime('%Y.%m.%d')
            
            # "어제" 파싱
            if '어제' in date_text:
                target_date = now - timedelta(days=1)
                return target_date.strftime('%Y.%m.%d')
            
            # "오늘" 파싱
            if '오늘' in date_text:
                return now.strftime('%Y.%m.%d')
            
            # 파싱할 수 없는 경우 오늘 날짜 반환
            logger.info(f"날짜 파싱 실패: '{date_text}' - 오늘 날짜 사용")
            return now.strftime('%Y.%m.%d')
            
        except Exception as e:
            logger.error(f"날짜 파싱 오류: {date_text} - {str(e)}")
            return datetime.now().strftime('%Y.%m.%d')

    def _go_to_next_page(self) -> bool:
        """다음 페이지로 이동"""
        try:
            # 다음 페이지 버튼 선택자들
            next_selectors = [
                'button:has-text("다음")',
                'a:has-text("다음")',
                '.next',
                '.pagination .next',
                '[aria-label="다음"]'
            ]
            
            for selector in next_selectors:
                try:
                    if self.page.is_visible(selector):
                        self.page.click(selector)
                        self.page.wait_for_load_state('networkidle')
                        return True
                except:
                    continue
            
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
            
            logger.info(f"[DB] {len(reviews)}개 요기요 리뷰 저장 시작...")
            
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
            
            logger.info(f"[DB] 요기요 리뷰 저장 완료: 성공 {saved_count}개, 중복 {duplicate_count}개, 실패 {failed_count}개")
            
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
        return self.get_reviews_with_pagination(platform_code, store_code, limit)

    def get_reviews_and_save(self, platform_code: str, store_code: str, store_info: Dict = None, limit: int = 50) -> Dict[str, Any]:
        """리뷰 수집 후 Supabase에 저장 (중복 필터링)"""
        try:
            # 기존 리뷰 ID 목록 가져오기 (중복 방지)
            existing_review_ids = set()
            if store_info:
                try:
                    supabase = get_supabase_client()
                    # 해당 매장의 기존 리뷰 ID 조회
                    existing_reviews = supabase.table('reviews').select('review_id').eq('platform_code', platform_code).eq('platform', 'yogiyo').execute()
                    existing_review_ids = {r['review_id'] for r in existing_reviews.data}
                    logger.info(f"기존 리뷰 {len(existing_review_ids)}개 확인")
                except Exception as e:
                    logger.error(f"기존 리뷰 조회 실패: {str(e)}")
            
            # 리뷰 수집
            reviews = self.get_reviews_with_pagination(platform_code, store_code, limit)
            
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
            logger.info(f"요기요 답글 작성 시작 - 리뷰 ID: {review_data.get('original_id', '')}")
            
            # 요기요 답글 작성 로직 구현 (실제 구조에 맞게)
            return True
            
        except Exception as e:
            logger.error(f"요기요 답글 작성 중 오류: {str(e)}")
            self.save_screenshot("reply_error")
            return False


# 테스트 코드
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    crawler = YogiyoSyncReviewCrawler(headless=False)
    try:
        crawler.start_browser()
        print("브라우저 시작 완료")
        
        # 테스트용 로그인 정보 (실제 정보로 교체 필요)
        user_id = "test_yogiyo_id"
        password = "test_password"
        
        login_success = crawler.login(user_id, password)
        print(f"로그인 결과: {login_success}")
        
        if login_success:
            # 실제 매장 코드로 테스트
            platform_code = "1371806"  # 예시 매장 코드
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