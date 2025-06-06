"""
배달의민족 Windows 동기 크롤러
"""
import logging
import time
from typing import Dict, List, Any
from .windows_sync_crawler import WindowsSyncBaseCrawler

logger = logging.getLogger(__name__)

class BaeminSyncCrawler(WindowsSyncBaseCrawler):
    """배달의민족 Windows 동기 크롤러"""
    
    def __init__(self, headless: bool = True):
        super().__init__(headless)
        self.platform_name = 'baemin'
        self.base_url = 'https://ceo.baemin.com'
        
    def login(self, username: str, password: str) -> bool:
        """배민 사장님 사이트 로그인"""
        try:
            logger.info(f"Logging in to Baemin CEO site...")
            
            # 로그인 페이지로 이동
            self.page.goto(f'{self.base_url}/login')
            
            # 페이지 로드 대기
            self.page.wait_for_load_state('networkidle')
            
            # 로그인 전 스크린샷
            self.save_screenshot('baemin_login_page')
            
            # 아이디 입력
            id_input = 'input[name="username"], input[placeholder*="아이디"], #username, #loginId'
            if not self.wait_and_type(id_input, username):
                logger.error("Failed to input username")
                return False
                
            # 비밀번호 입력
            pw_input = 'input[name="password"], input[type="password"], #password, #loginPw'
            if not self.wait_and_type(pw_input, password):
                logger.error("Failed to input password")
                return False
                
            # 로그인 버튼 클릭
            login_button = 'button[type="submit"], button:has-text("로그인"), .login-button'
            if not self.wait_and_click(login_button):
                logger.error("Failed to click login button")
                return False
                
            # 로그인 후 페이지 로드 대기
            time.sleep(3)
            self.page.wait_for_load_state('networkidle')
            
            # 로그인 성공 여부 확인
            current_url = self.page.url
            if 'login' not in current_url:
                logger.info("Login successful")
                self.logged_in = True
                self.save_screenshot('baemin_after_login')
                return True
            else:
                logger.error("Login failed - still on login page")
                self.save_screenshot('baemin_login_failed')
                return False
                
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            self.save_screenshot('baemin_login_error')
            return False
            
    def get_store_list(self) -> List[Dict[str, Any]]:
        """매장 목록 가져오기"""
        try:
            if not self.logged_in:
                logger.error("Not logged in")
                return []
                
            logger.info("Getting store list...")
            
            # 매장 목록 페이지로 이동
            self.page.goto(f'{self.base_url}/store/list')
            self.page.wait_for_load_state('networkidle')
            
            stores = []
            
            # 매장 목록 추출
            store_elements = self.page.query_selector_all('.store-item, .shop-item, [data-store-id]')
            
            for element in store_elements:
                try:
                    store_name = element.query_selector('.store-name, .shop-name').inner_text()
                    store_id = element.get_attribute('data-store-id') or element.get_attribute('data-shop-id')
                    
                    if store_name and store_id:
                        stores.append({
                            'platform_code': store_id,
                            'store_name': store_name.strip(),
                            'platform': 'baemin'
                        })
                except:
                    continue
                    
            logger.info(f"Found {len(stores)} stores")
            return stores
            
        except Exception as e:
            logger.error(f"Error getting store list: {str(e)}")
            self.save_screenshot('baemin_store_list_error')
            return []
            
    def select_store(self, platform_code: str) -> bool:
        """매장 선택"""
        try:
            logger.info(f"Selecting store: {platform_code}")
            
            # 매장 선택 링크 찾기
            store_link = f'[data-store-id="{platform_code}"], [data-shop-id="{platform_code}"]'
            
            if self.wait_and_click(store_link):
                self.page.wait_for_load_state('networkidle')
                logger.info("Store selected successfully")
                return True
            else:
                logger.error("Failed to select store")
                return False
                
        except Exception as e:
            logger.error(f"Error selecting store: {str(e)}")
            return False
            
    def get_store_info(self) -> Dict[str, Any]:
        """매장 정보 가져오기"""
        try:
            logger.info("Getting store info...")
            
            info = {
                'store_name': '',
                'store_address': '',
                'store_phone': '',
                'business_hours': {}
            }
            
            # 매장명
            name_element = self.page.query_selector('.store-title, .shop-title, h1')
            if name_element:
                info['store_name'] = name_element.inner_text().strip()
                
            # 주소
            addr_element = self.page.query_selector('.store-address, .shop-address')
            if addr_element:
                info['store_address'] = addr_element.inner_text().strip()
                
            # 전화번호
            phone_element = self.page.query_selector('.store-phone, .shop-phone')
            if phone_element:
                info['store_phone'] = phone_element.inner_text().strip()
                
            logger.info(f"Store info retrieved: {info['store_name']}")
            return info
            
        except Exception as e:
            logger.error(f"Error getting store info: {str(e)}")
            return {}
            
    def get_reviews(self, limit: int = 50) -> List[Dict[str, Any]]:
        """리뷰 목록 가져오기"""
        try:
            logger.info(f"Getting reviews (limit: {limit})...")
            
            # 리뷰 페이지로 이동
            self.page.goto(f'{self.base_url}/review/list')
            self.page.wait_for_load_state('networkidle')
            
            reviews = []
            
            # 리뷰 목록 추출
            review_elements = self.page.query_selector_all('.review-item')[:limit]
            
            for element in review_elements:
                try:
                    review = {
                        'review_id': element.get_attribute('data-review-id'),
                        'reviewer_name': element.query_selector('.reviewer-name').inner_text(),
                        'rating': len(element.query_selector_all('.star.active')),
                        'review_text': element.query_selector('.review-text').inner_text(),
                        'review_date': element.query_selector('.review-date').inner_text(),
                        'has_reply': bool(element.query_selector('.reply-text'))
                    }
                    reviews.append(review)
                except:
                    continue
                    
            logger.info(f"Found {len(reviews)} reviews")
            return reviews
            
        except Exception as e:
            logger.error(f"Error getting reviews: {str(e)}")
            self.save_screenshot('baemin_reviews_error')
            return []
            
    def post_reply(self, review_id: str, reply_text: str) -> bool:
        """답글 작성"""
        try:
            logger.info(f"Posting reply to review {review_id}")
            
            # 답글 버튼 클릭
            reply_button = f'[data-review-id="{review_id}"] .reply-button'
            if not self.wait_and_click(reply_button):
                return False
                
            # 답글 입력
            reply_input = f'[data-review-id="{review_id}"] .reply-input, textarea'
            if not self.wait_and_type(reply_input, reply_text):
                return False
                
            # 답글 등록 버튼 클릭
            submit_button = f'[data-review-id="{review_id}"] .submit-reply'
            if not self.wait_and_click(submit_button):
                return False
                
            time.sleep(2)
            logger.info("Reply posted successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error posting reply: {str(e)}")
            return False
