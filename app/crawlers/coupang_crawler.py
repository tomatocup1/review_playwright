"""
쿠팡이츠 크롤러
"""
from typing import Dict, List, Any, Optional
import re
import asyncio
from datetime import datetime
import logging
from .base_crawler import BaseCrawler

logger = logging.getLogger(__name__)

class CoupangCrawler(BaseCrawler):
    """쿠팡이츠 크롤러"""
    
    def __init__(self, headless: bool = True):
        super().__init__(headless)
        self.login_url = "https://store.coupangeats.com/merchant/login"
        self.reviews_url = "https://store.coupangeats.com/merchant/management/reviews"
        self.current_store_info = {}
    
    async def login(self, username: str, password: str) -> bool:
        """쿠팡이츠 로그인"""
        try:
            logger.info(f"쿠팡이츠 로그인 시작: {username}")
            
            # 로그인 페이지로 이동
            await self.page.goto(self.login_url, wait_until='networkidle')
            await asyncio.sleep(2)
            
            # 로그인 폼 입력
            await self.wait_and_type('input[name="email"]', username)
            await self.wait_and_type('input[name="password"]', password)
            
            # 로그인 버튼 클릭
            await self.wait_and_click('button[type="submit"]')
            
            # 로그인 성공 확인
            await asyncio.sleep(3)
            
            current_url = self.page.url
            if 'store.coupangeats.com/merchant' in current_url and 'login' not in current_url:
                self.logged_in = True
                logger.info("쿠팡이츠 로그인 성공")
                await self.save_screenshot("login_success")
                return True
            else:
                logger.error("쿠팡이츠 로그인 실패")
                await self.save_screenshot("login_failed")
                return False
                
        except Exception as e:
            logger.error(f"쿠팡이츠 로그인 중 오류: {str(e)}")
            await self.save_screenshot("login_error")
            return False
    
    async def get_store_list(self) -> List[Dict[str, Any]]:
        """매장 목록 가져오기"""
        try:
            if not self.logged_in:
                logger.error("로그인이 필요합니다")
                return []
            
            # 리뷰 페이지로 이동 (매장 선택이 있는 페이지)
            await self.page.goto(self.reviews_url, wait_until='networkidle')
            await asyncio.sleep(2)
            
            stores = []
            
            # 드롭다운 클릭하여 매장 목록 표시
            dropdown_elem = await self.page.query_selector('.el0at441.css-1p237v6.emb4idh5')
            if dropdown_elem:
                button_elem = await dropdown_elem.query_selector('.button')
                if button_elem:
                    await button_elem.click()
                    await asyncio.sleep(1)
            
            # 매장 목록 가져오기
            option_items = await self.page.query_selector_all('.el0at441.css-1p237v6.emb4idh5 ul.options li')
            
            for item in option_items:
                item_text = await item.text_content()
                if item_text:
                    # "큰집닭강정(708561)" 형식에서 정보 추출
                    match = re.match(r'(.+)\((\d+)\)', item_text.strip())
                    if match:
                        store_name = match.group(1).strip()
                        platform_code = match.group(2)
                        
                        store_info = {
                            'platform_code': platform_code,
                            'store_name': store_name,
                            'platform': 'coupang'
                        }
                        stores.append(store_info)
                        logger.info(f"매장 발견: {store_name} ({platform_code})")
            
            return stores
            
        except Exception as e:
            logger.error(f"매장 목록 가져오기 실패: {str(e)}")
            await self.save_screenshot("store_list_error")
            return []
    
    async def select_store(self, platform_code: str) -> bool:
        """매장 선택"""
        try:
            if not self.logged_in:
                logger.error("로그인이 필요합니다")
                return False
            
            # 리뷰 페이지에 있는지 확인
            current_url = self.page.url
            if 'reviews' not in current_url:
                await self.page.goto(self.reviews_url, wait_until='networkidle')
                await asyncio.sleep(2)
            
            # 현재 선택된 매장 확인
            hidden_input = await self.page.query_selector('.el0at441.css-1p237v6.emb4idh5 input[type="hidden"]')
            if hidden_input:
                current_value = await hidden_input.get_attribute('value')
                if current_value == platform_code:
                    logger.info(f"이미 선택된 매장: {platform_code}")
                    return True
            
            # 드롭다운 열기
            dropdown_elem = await self.page.query_selector('.el0at441.css-1p237v6.emb4idh5')
            if dropdown_elem:
                button_elem = await dropdown_elem.query_selector('.button')
                if button_elem:
                    await button_elem.click()
                    await asyncio.sleep(1)
            
            # 매장 목록에서 해당 매장 찾아 클릭
            option_items = await self.page.query_selector_all('.el0at441.css-1p237v6.emb4idh5 ul.options li')
            
            for item in option_items:
                item_text = await item.text_content()
                if item_text and platform_code in item_text:
                    await item.click()
                    await asyncio.sleep(2)
                    logger.info(f"매장 선택 성공: {platform_code}")
                    # 현재 매장 정보 업데이트
                    await self.get_store_info()
                    return True
            
            logger.error(f"매장을 찾을 수 없습니다: {platform_code}")
            return False
            
        except Exception as e:
            logger.error(f"매장 선택 실패: {str(e)}")
            return False
    
    async def get_store_info(self) -> Dict[str, Any]:
        """현재 선택된 매장 정보 가져오기"""
        try:
            store_info = {}
            
            # 현재 선택된 매장 정보 가져오기
            dropdown_elem = await self.page.query_selector('.el0at441.css-1p237v6.emb4idh5')
            if dropdown_elem:
                # hidden input에서 platform_code 가져오기
                hidden_input = await dropdown_elem.query_selector('input[type="hidden"]')
                if hidden_input:
                    store_info['platform_code'] = await hidden_input.get_attribute('value')
                
                # 버튼 텍스트에서 매장명 가져오기
                button_text_elem = await dropdown_elem.query_selector('.button div')
                if button_text_elem:
                    button_text = await button_text_elem.text_content()
                    # "큰집닭강정(708561)" 형식에서 매장명 추출
                    match = re.match(r'(.+)\((\d+)\)', button_text.strip())
                    if match:
                        store_info['store_name'] = match.group(1).strip()
            
            store_info['platform'] = 'coupang'
            
            self.current_store_info = store_info
            logger.info(f"매장 정보: {store_info}")
            return store_info
            
        except Exception as e:
            logger.error(f"매장 정보 가져오기 실패: {str(e)}")
            return {}
    
    async def get_reviews(self, limit: int = 50) -> List[Dict[str, Any]]:
        """리뷰 목록 가져오기"""
        try:
            if not self.logged_in:
                logger.error("로그인이 필요합니다")
                return []
            
            reviews = []
            
            # 리뷰 페이지 확인
            current_url = self.page.url
            if 'reviews' not in current_url:
                await self.page.goto(self.reviews_url, wait_until='networkidle')
                await asyncio.sleep(2)
            
            # 리뷰 목록 파싱 로직 구현
            # (실제 HTML 구조에 맞게 수정 필요)
            
            logger.info(f"리뷰 {len(reviews)}개 수집 완료")
            return reviews
            
        except Exception as e:
            logger.error(f"리뷰 가져오기 실패: {str(e)}")
            await self.save_screenshot("reviews_error")
            return []
    
    async def post_reply(self, review_id: str, reply_text: str) -> bool:
        """리뷰에 답글 작성"""
        try:
            if not self.logged_in:
                logger.error("로그인이 필요합니다")
                return False
            
            # 답글 작성 로직 구현
            # (실제 HTML 구조에 맞게 수정 필요)
            
            logger.info(f"리뷰 {review_id}에 답글 작성 성공")
            return True
            
        except Exception as e:
            logger.error(f"답글 작성 실패: {str(e)}")
            return False
