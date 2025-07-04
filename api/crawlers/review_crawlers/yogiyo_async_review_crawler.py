"""
요기요 비동기 리뷰 크롤러
Windows 환경에서 Playwright를 사용한 비동기 크롤링
"""
import re
import json
import logging
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import os
from dotenv import load_dotenv
from supabase import create_client, Client
from cryptography.fernet import Fernet

# .env 파일 로드
load_dotenv()

# 직접 실행과 모듈 import 모두 지원
try:
    from .windows_async_crawler import WindowsAsyncBaseCrawler
except ImportError:
    # 직접 실행시
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from windows_async_crawler import WindowsAsyncBaseCrawler

logger = logging.getLogger(__name__)


class YogiyoAsyncReviewCrawler(WindowsAsyncBaseCrawler):
    """요기요 비동기 리뷰 크롤러"""
    
    def __init__(self, headless: bool = True):
        super().__init__(headless)
        self.platform_name = 'yogiyo'
        self.reviews_data = []
        self.current_store_info = {}
        
        # 리뷰 스크린샷 저장 경로
        self.review_screenshot_dir = Path("C:/Review_playwright/logs/screenshots/yogiyo_reviews")
        self.review_screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        # Supabase 클라이언트 초기화
        self.supabase: Client = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_ANON_KEY')
        )
        
        # 암호화 키 (실제로는 환경변수나 안전한 곳에 저장해야 함)
        self.cipher_suite = None
        encryption_key = os.getenv('ENCRYPTION_KEY')
        if encryption_key:
            self.cipher_suite = Fernet(encryption_key.encode())
    
    async def start(self):
        """브라우저 시작 (호환성을 위한 별칭)"""
        await self.start_browser()
    
    async def close(self):
        """브라우저 종료 (호환성을 위한 별칭)"""
        await self.close_browser()
        
    def decrypt_password(self, encrypted_password: str) -> str:
        """암호화된 비밀번호 복호화"""
        if self.cipher_suite and encrypted_password:
            try:
                return self.cipher_suite.decrypt(encrypted_password.encode()).decode()
            except Exception as e:
                logger.error(f"비밀번호 복호화 실패: {str(e)}")
                return encrypted_password
        return encrypted_password
    
    async def get_store_credentials(self, store_code: str) -> Dict[str, Any]:
        """Supabase에서 매장 로그인 정보 가져오기"""
        try:
            response = self.supabase.table('platform_reply_rules').select(
                'platform_code, store_name, platform_id, platform_pw'
            ).eq('store_code', store_code).eq('platform', 'yogiyo').single().execute()
            
            if response.data:
                data = response.data
                # 비밀번호 복호화
                if 'platform_pw' in data:
                    data['platform_pw'] = self.decrypt_password(data['platform_pw'])
                return data
            else:
                logger.error(f"매장 정보를 찾을 수 없습니다: {store_code}")
                return None
                
        except Exception as e:
            logger.error(f"매장 정보 조회 실패: {str(e)}")
            return None
    
    async def login_with_store_code(self, store_code: str) -> bool:
        """store_code를 사용하여 자동 로그인"""
        credentials = await self.get_store_credentials(store_code)
        if not credentials:
            return False
        
        username = credentials.get('platform_id')
        password = credentials.get('platform_pw')
        
        if not username or not password:
            logger.error("로그인 정보가 불완전합니다")
            return False
        
        # 로그인 시도
        login_success = await self.login(username, password)
        
        if login_success:
            # 로그인 성공 후 리뷰 페이지로 명시적으로 이동
            logger.info("로그인 성공, 리뷰 페이지로 이동 중...")
            review_url = "https://ceo.yogiyo.co.kr/reviews"
            await self.page.goto(review_url)
            await self.page.wait_for_load_state('networkidle')
            logger.info("리뷰 페이지 이동 완료")
            
            # platform_code 저장
            self.current_store_info['platform_code'] = credentials.get('platform_code')
            self.current_store_info['store_name'] = credentials.get('store_name')
        
        return login_success
    
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
                # 인증 메일 확인 팝업 체크 - 클래스명 수정
                auth_popup_selectors = [
                    'div.AlertMessage-sc-a98nwm-3.ewbPZf',
                    'div.Alert__Message-sc-a98nwm-3.ewbPZf',
                    'div.AlertMessage-sc-a98nwm-3'
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
                        
                        # 첫 번째 확인 버튼 클릭
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
                logger.info(f"인증 메일 팝업 처리 중 예외 발생 (정상적인 경우일 수 있음): {str(e)}")
            
            # 로그인 성공 확인 - 더 긴 대기 시간
            await self.page.wait_for_timeout(3000)
            
            current_url = self.page.url
            logger.info(f"로그인 후 URL: {current_url}")
            
            # URL 확인으로 로그인 성공 판단
            if 'ceo.yogiyo.co.kr' in current_url and 'login' not in current_url:
                self.logged_in = True
                logger.info("✓ 요기요 로그인 성공")
                return True
            else:
                # 추가로 에러 메시지 확인
                error_selectors = [
                    'div.error-message',
                    'div[class*="error"]',
                    'span[class*="error"]',
                    'p[class*="error"]'
                ]
                
                error_found = False
                for selector in error_selectors:
                    error_element = await self.page.query_selector(selector)
                    if error_element:
                        error_text = await error_element.text_content()
                        logger.error(f"로그인 실패: {error_text}")
                        error_found = True
                        break
                
                if not error_found:
                    logger.error("로그인 실패: 알 수 없는 오류")
                
                await self.save_screenshot("login_failed")
                return False
                
        except Exception as e:
            logger.error(f"로그인 중 예외 발생: {str(e)}")
            await self.save_screenshot("login_error")
            return False
    
    async def get_store_list(self) -> List[Dict[str, Any]]:
        """매장 목록 가져오기"""
        try:
            logger.info("매장 목록 조회 시작")
            
            # 현재 페이지가 리뷰 페이지가 아니면 이동
            current_url = self.page.url
            if "/reviews" not in current_url:
                await self.navigate_to_reviews()
            
            # 드롭다운 버튼 클릭
            dropdown_selector = 'button.StoreSelector__DropdownButton-sc-1rowjsb-11'
            await self.wait_and_click(dropdown_selector)
            await self.page.wait_for_timeout(1000)
            
            # 매장 목록 가져오기
            store_list = []
            store_items = await self.page.query_selector_all('li.List__Vendor-sc-2ocjy3-7')
            
            for item in store_items:
                try:
                    # 매장명
                    name_elem = await item.query_selector('p.List__VendorName-sc-2ocjy3-3')
                    store_name = await name_elem.text_content() if name_elem else ""
                    
                    # 매장 ID
                    id_elem = await item.query_selector('span.List__VendorID-sc-2ocjy3-1')
                    store_id_text = await id_elem.text_content() if id_elem else ""
                    store_id = re.search(r'ID\.\s*(\d+)', store_id_text).group(1) if store_id_text else ""
                    
                    # 상태
                    status_elem = await item.query_selector('p.List__StoreStatus-sc-2ocjy3-0')
                    status = await status_elem.text_content() if status_elem else ""
                    
                    store_info = {
                        'platform_code': store_id,
                        'store_name': store_name,
                        'status': status
                    }
                    store_list.append(store_info)
                    logger.info(f"매장 발견: {store_name} (ID: {store_id})")
                    
                except Exception as e:
                    logger.error(f"매장 정보 파싱 오류: {str(e)}")
                    continue
            
            return store_list
            
        except Exception as e:
            logger.error(f"매장 목록 조회 실패: {str(e)}")
            return []
    
    async def select_store_by_platform_code(self, platform_code: str) -> bool:
        """Supabase에서 가져온 platform_code로 매장 선택"""
        try:
            logger.info(f"매장 선택 시작: {platform_code}")
            
            # 현재 페이지가 리뷰 페이지가 아니면 이동
            current_url = self.page.url
            if "/reviews" not in current_url:
                await self.navigate_to_reviews()
            
            # 잠시 대기
            await self.page.wait_for_timeout(2000)
            
            # 드롭다운 열기
            dropdown_selector = 'button.StoreSelector__DropdownButton-sc-1rowjsb-11'
            await self.wait_and_click(dropdown_selector)
            await self.page.wait_for_timeout(1000)
            
            # 매장 목록에서 해당 매장 찾기
            store_items = await self.page.query_selector_all('li.List__Vendor-sc-2ocjy3-7')
            
            for item in store_items:
                try:
                    id_elem = await item.query_selector('span.List__VendorID-sc-2ocjy3-1')
                    if id_elem:
                        store_id_text = await id_elem.text_content()
                        if platform_code in store_id_text:
                            await item.click()
                            logger.info(f"매장 선택 완료: {platform_code}")
                            await self.page.wait_for_timeout(2000)
                            
                            # 현재 매장 정보 저장
                            await self.update_current_store_info()
                            return True
                            
                except Exception as e:
                    logger.error(f"매장 선택 중 오류: {str(e)}")
                    continue
            
            logger.error(f"매장을 찾을 수 없습니다: {platform_code}")
            return False
            
        except Exception as e:
            logger.error(f"매장 선택 실패: {str(e)}")
            return False
    
    async def select_store(self, platform_code: str) -> bool:
        """특정 매장 선택 (기존 메서드 유지)"""
        return await self.select_store_by_platform_code(platform_code)
    
    async def update_current_store_info(self):
        """현재 선택된 매장 정보 업데이트"""
        try:
            # 매장명
            name_elem = await self.page.query_selector('span.StoreSelector__StoreName-sc-1rowjsb-2')
            store_name = await name_elem.text_content() if name_elem else ""
            
            # 매장 ID
            id_elem = await self.page.query_selector('p.StoreSelector__StoreNumber-sc-1rowjsb-4')
            store_id_text = await id_elem.text_content() if id_elem else ""
            store_id = re.search(r'ID\.\s*(\d+)', store_id_text).group(1) if store_id_text else ""
            
            self.current_store_info = {
                'platform_code': store_id,
                'store_name': store_name
            }
            logger.info(f"현재 매장 정보: {store_name} (ID: {store_id})")
            
        except Exception as e:
            logger.error(f"매장 정보 업데이트 실패: {str(e)}")
    
    async def get_store_info(self) -> Dict[str, Any]:
        """현재 선택된 매장 정보 가져오기"""
        return self.current_store_info
    
    async def navigate_to_reviews(self) -> bool:
        """리뷰 페이지로 이동 (이미 리뷰 페이지에 있으면 스킵)"""
        try:
            current_url = self.page.url
            if "/reviews" in current_url:
                logger.info("이미 리뷰 페이지에 있습니다")
                return True
            
            review_url = "https://ceo.yogiyo.co.kr/reviews"
            logger.info(f"리뷰 페이지로 이동: {review_url}")
            await self.page.goto(review_url)
            await self.page.wait_for_load_state('networkidle')
            await self.page.wait_for_timeout(2000)
            logger.info("리뷰 페이지 이동 완료")
            return True
            
        except Exception as e:
            logger.error(f"리뷰 페이지 이동 실패: {str(e)}")
            return False
    
    async def click_unanswered_tab(self) -> bool:
        """미답변 탭 클릭"""
        try:
            # 미답변 탭 선택자들
            unanswered_selectors = [
                'li.InnerTab__TabItem-sc-14s9mjy-0:has-text("미답변")',
                'li:has-text("미답변")',
                '//li[contains(text(), "미답변")]'
            ]
            
            for selector in unanswered_selectors:
                try:
                    # 탭이 보일 때까지 대기
                    await self.page.wait_for_selector(selector, timeout=5000)
                    await self.page.click(selector)
                    logger.info("미답변 탭 클릭 완료")
                    await self.page.wait_for_timeout(2000)
                    return True
                except:
                    continue
            
            logger.error("미답변 탭을 찾을 수 없습니다")
            return False
            
        except Exception as e:
            logger.error(f"미답변 탭 클릭 실패: {str(e)}")
            return False
    
    def generate_review_id(self, platform: str, original_id: str) -> str:
        """리뷰 ID 생성"""
        return f"{platform}_{original_id}"
    
    def parse_review_data(self, review_json: Dict[str, Any], platform_code: str, store_code: str) -> Dict[str, Any]:
        """API 응답에서 리뷰 데이터 파싱"""
        try:
            # 기본 정보
            review_id_number = str(review_json.get('id', ''))
            
            # 날짜 변환
            time_str = review_json.get('time', '')
            if time_str:
                review_date = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
            else:
                review_date = datetime.now().strftime('%Y-%m-%d')
            
            # 이미지 URL 추출
            review_images = []
            for img in review_json.get('review_images', []):
                if isinstance(img, dict) and 'full' in img:
                    review_images.append(img['full'])
            
            # 리뷰 데이터 구성 (DB 스키마에 맞춤)
            review_data = {
                'review_id': self.generate_review_id('yogiyo', review_id_number),
                'platform': 'yogiyo',
                'platform_code': platform_code,
                'store_code': store_code,
                'review_name': review_json.get('nickname', '익명'),
                'rating': int(review_json.get('rating', 5)),
                'review_content': review_json.get('comment', ''),
                'review_date': review_date,
                'ordered_menu': review_json.get('menu_summary', ''),
                'review_images': review_images,
                'delivery_review': ''  # 요기요는 별도 배달 리뷰 없음
            }
            
            return review_data
            
        except Exception as e:
            logger.error(f"리뷰 파싱 오류: {str(e)}")
            return None
    
    async def get_reviews_with_pagination(self, platform_code: str, store_code: str, limit: int = 50) -> List[Dict[str, Any]]:
        """네트워크 응답 가로채기를 통한 리뷰 수집 (페이지네이션 지원)"""
        try:
            logger.info("=" * 50)
            logger.info(f"리뷰 수집 시작 - 매장: {platform_code}")
            logger.info("=" * 50)
            
            # 리뷰 페이지로 이동
            if not await self.navigate_to_reviews():
                return []
            
            # 미답변 탭 클릭
            await self.click_unanswered_tab()
            
            collected_reviews = []
            collected_review_ids = set()  # 중복 방지를 위한 ID 집합
            page_num = 1
            api_call_count = 0
            
            # 네트워크 응답 핸들러
            async def handle_response(response):
                nonlocal collected_reviews, collected_review_ids, api_call_count
                
                # 리뷰 API 응답인지 확인
                if "/vendor/" in response.url and "/reviews/" in response.url:
                    # API URL 로깅
                    logger.info(f"리뷰 관련 API 응답 감지: {response.url}")
                    
                    # 미답변 API만 처리 (no_reply_only=true)
                    if "no_reply_only=true" in response.url:
                        try:
                            data = await response.json()
                            api_call_count += 1
                            
                            # 리뷰 배열 확인
                            reviews = data
                            if isinstance(data, dict):
                                reviews = data.get('results', data.get('reviews', []))
                            
                            if isinstance(reviews, list):
                                logger.info(f"API에서 {len(reviews)}개 리뷰 발견")
                                
                                for review in reviews:
                                    # 원본 ID
                                    original_id = str(review.get('id', ''))
                                    
                                    # 중복 체크
                                    if original_id in collected_review_ids:
                                        continue
                                    
                                    # has_reply가 False인 것만 수집 (미답변)
                                    if not review.get('reply'):
                                        parsed_review = self.parse_review_data(review, platform_code, store_code)
                                        if parsed_review:
                                            collected_reviews.append(parsed_review)
                                            collected_review_ids.add(original_id)
                                            logger.info(f"미답변 리뷰 수집: {parsed_review['review_name']} - {parsed_review['rating']}점")
                            
                        except Exception as e:
                            logger.error(f"API 응답 처리 오류: {str(e)}")
                    else:
                        # 전체 리뷰 API는 무시
                        if "no_reply_only=false" in response.url:
                            logger.info("전체 리뷰 API 응답은 무시합니다")
            
            # 네트워크 리스너 등록
            self.page.on("response", handle_response)
            
            try:
                # 페이지 새로고침으로 API 호출 유도
                logger.info("페이지 새로고침으로 API 호출 유도")
                await self.page.reload()
                await self.page.wait_for_timeout(2000)
                
                # 미답변 탭 다시 클릭 (새로고침 후 필요)
                await self.click_unanswered_tab()
                await self.page.wait_for_timeout(3000)
                
                # API 호출이 없었다면 다시 시도
                if api_call_count == 0:
                    logger.info("API 호출이 감지되지 않아 다시 시도")
                    await self.page.reload()
                    await self.page.wait_for_timeout(2000)
                    await self.click_unanswered_tab()
                    await self.page.wait_for_timeout(3000)
                
                # 페이지네이션 처리
                while len(collected_reviews) < limit:
                    current_count = len(collected_reviews)
                    
                    # 다음 페이지 버튼 찾기
                    next_button_selectors = [
                        'button[aria-label="다음 페이지"]',
                        'button:has-text("다음")',
                        '//button[contains(@aria-label, "다음")]'
                    ]
                    
                    next_button = None
                    for selector in next_button_selectors:
                        try:
                            next_button = await self.page.query_selector(selector)
                            if next_button:
                                break
                        except:
                            continue
                    
                    if next_button:
                        is_disabled = await next_button.get_attribute('disabled')
                        if is_disabled:
                            logger.info("마지막 페이지 도달")
                            break
                        
                        # 다음 페이지 클릭
                        await next_button.click()
                        page_num += 1
                        logger.info(f"페이지 {page_num}로 이동")
                        await self.page.wait_for_timeout(2000)
                        
                        # 새 리뷰가 로드되었는지 확인
                        if len(collected_reviews) == current_count:
                            logger.info("더 이상 새로운 리뷰가 없습니다")
                            break
                    else:
                        logger.info("다음 페이지 버튼을 찾을 수 없습니다")
                        break
                
                logger.info(f"총 {len(collected_reviews)}개의 미답변 리뷰 수집 완료")
                
                return collected_reviews[:limit]
                
            finally:
                # 리스너 제거
                self.page.remove_listener("response", handle_response)
                
        except Exception as e:
            logger.error(f"리뷰 수집 중 오류: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    async def _parse_reviews_from_dom(self, platform_code: str, store_code: str) -> List[Dict[str, Any]]:
        """DOM에서 직접 리뷰 파싱"""
        reviews = []
        try:
            logger.info("DOM에서 리뷰 파싱 시작")
            
            # 리뷰 컨테이너 선택자들
            review_selectors = [
                'div.ReviewItem__Container-sc-1oxgj67-0',
                'div[class*="ReviewItem"]',
                'div[class*="review-item"]',
                'div[class*="Review"]'
            ]
            
            review_containers = []
            for selector in review_selectors:
                containers = await self.page.query_selector_all(selector)
                if containers:
                    review_containers = containers
                    logger.info(f"{len(containers)}개의 리뷰 컨테이너 발견 (선택자: {selector})")
                    break
            
            for idx, container in enumerate(review_containers):
                try:
                    # 답글이 있는지 확인
                    reply_exists = await container.query_selector('div[class*="Reply"]')
                    if reply_exists:
                        continue  # 답글이 있으면 스킵
                    
                    # 작성자명
                    name_elem = await container.query_selector('h6')
                    review_name = await name_elem.text_content() if name_elem else f"익명{idx+1}"
                    
                    # 별점
                    rating_elem = await container.query_selector('h6.cknzqP')
                    rating_text = await rating_elem.text_content() if rating_elem else "5.0"
                    rating = int(float(rating_text))
                    
                    # 날짜
                    date_elem = await container.query_selector('p.jwoVKl')
                    date_text = await date_elem.text_content() if date_elem else ""
                    review_date = self._parse_date(date_text)
                    
                    # 리뷰 내용
                    content_elem = await container.query_selector('p.ReviewItem__CommentTypography-sc-1oxgj67-3')
                    if not content_elem:
                        content_elem = await container.query_selector('p[class*="Comment"]')
                    review_content = await content_elem.text_content() if content_elem else ""
                    
                    # 주문 메뉴
                    menu_elem = await container.query_selector('p.jlzcvj')
                    ordered_menu = await menu_elem.text_content() if menu_elem else ""
                    
                    # 이미지
                    image_elems = await container.query_selector_all('img[alt="리뷰 이미지"]')
                    review_images = []
                    for img in image_elems:
                        src = await img.get_attribute('src')
                        if src:
                            review_images.append(src)
                    
                    # 리뷰 ID 생성
                    original_id = f"dom_{platform_code}_{idx}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    
                    review_data = {
                        'review_id': self.generate_review_id('yogiyo', original_id),
                        'original_id': original_id,
                        'platform': 'yogiyo',
                        'platform_code': platform_code,
                        'store_code': store_code,
                        'review_name': review_name.strip(),
                        'rating': rating,
                        'review_content': review_content.strip(),
                        'review_date': review_date,
                        'ordered_menu': ordered_menu.strip(),
                        'review_images': review_images,
                        'delivery_review': '',
                        'has_reply': False,
                        'rating_taste': 0,
                        'rating_quantity': 0,
                        'rating_delivery': 0
                    }
                    
                    reviews.append(review_data)
                    logger.info(f"DOM 리뷰 수집: {review_name} - {rating}점")
                    
                except Exception as e:
                    logger.error(f"DOM 리뷰 파싱 오류: {str(e)}")
                    continue
            
            logger.info(f"DOM에서 {len(reviews)}개 리뷰 파싱 완료")
            
        except Exception as e:
            logger.error(f"DOM 파싱 중 오류: {str(e)}")
        
        return reviews
    
    def _parse_date(self, date_str: str) -> str:
        """날짜 문자열 파싱"""
        try:
            if not date_str:
                return datetime.now().strftime('%Y-%m-%d')
            
            # "2025.05.21" 형식
            if '.' in date_str:
                parts = date_str.split('.')
                if len(parts) == 3:
                    return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
            
            # 기본값
            return datetime.now().strftime('%Y-%m-%d')
            
        except:
            return datetime.now().strftime('%Y-%m-%d')
    
    async def get_reviews(self, limit: int = 50) -> List[Dict[str, Any]]:
        """리뷰 목록 가져오기 (WindowsAsyncBaseCrawler 인터페이스 구현)"""
        if not self.current_store_info:
            logger.error("매장이 선택되지 않았습니다")
            return []
        
        platform_code = self.current_store_info.get('platform_code')
        # store_code는 실제 구현에서는 DB에서 가져와야 함
        store_code = f"YOGIYO_{platform_code}"
        
        return await self.get_reviews_with_pagination(platform_code, store_code, limit)
    
    async def post_reply(self, review_id: str, reply_text: str) -> bool:
        """리뷰에 답글 작성"""
        try:
            logger.info(f"답글 작성 시작 - 리뷰 ID: {review_id}")
            
            # 해당 리뷰 찾기
            review_containers = await self.page.query_selector_all('div.ReviewItem__Container-sc-1oxgj67-0')
            
            target_container = None
            for container in review_containers:
                # 리뷰 내용이나 작성자로 매칭 (실제로는 더 정확한 매칭 필요)
                content_elem = await container.query_selector('p.ReviewItem__CommentTypography-sc-1oxgj67-3')
                if content_elem:
                    content = await content_elem.text_content()
                    # 여기서는 간단히 내용 일부로 매칭 (실제로는 ID로 매칭해야 함)
                    if content in self.reviews_data:
                        target_container = container
                        break
            
            if not target_container:
                logger.error("리뷰를 찾을 수 없습니다")
                return False
            
            # 댓글쓰기 버튼 클릭
            reply_button = await target_container.query_selector('button:has-text("댓글쓰기")')
            if not reply_button:
                logger.error("댓글쓰기 버튼을 찾을 수 없습니다")
                return False
            
            await reply_button.click()
            logger.info("댓글쓰기 버튼 클릭")
            await self.page.wait_for_timeout(1000)
            
            # 텍스트 입력
            textarea = await self.page.query_selector('textarea[placeholder="댓글을 입력해주세요."]')
            if not textarea:
                logger.error("텍스트 입력 영역을 찾을 수 없습니다")
                return False
            
            await textarea.click()
            await textarea.fill(reply_text)
            logger.info(f"답글 입력 완료: {reply_text[:50]}...")
            
            # 등록 버튼 클릭
            submit_button = await self.page.query_selector('button:has-text("등록")')
            if not submit_button:
                logger.error("등록 버튼을 찾을 수 없습니다")
                return False
            
            await submit_button.click()
            logger.info("답글 등록 버튼 클릭")
            
            # 등록 완료 대기
            await self.page.wait_for_timeout(3000)
            return True
            
        except Exception as e:
            logger.error(f"답글 작성 중 오류: {str(e)}")
            await self.save_screenshot("reply_error")
            return False
    
    async def save_screenshot(self, name: str):
        """리뷰 관련 스크린샷 저장"""
        if not self.page:
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}.png"
            filepath = self.review_screenshot_dir / filename
            
            await self.page.screenshot(path=str(filepath))
            logger.info(f"스크린샷 저장: {filepath}")
            
        except Exception as e:
            logger.error(f"스크린샷 저장 실패: {str(e)}")