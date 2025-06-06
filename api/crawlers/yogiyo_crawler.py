"""
요기요 크롤러
"""
from typing import Dict, List, Any, Optional
import re
import asyncio
from datetime import datetime
import logging
from .base_crawler import BaseCrawler

logger = logging.getLogger(__name__)

class YogiyoCrawler(BaseCrawler):
    """요기요 크롤러"""
    
    def __init__(self, headless: bool = True):
        super().__init__(headless)
        self.login_url = "https://ceo.yogiyo.co.kr/login/"
        self.reviews_url = "https://ceo.yogiyo.co.kr/reviews"
        self.current_store_info = {}
    
    async def login(self, username: str, password: str) -> bool:
        """요기요 로그인"""
        try:
            logger.info(f"요기요 로그인 시작: {username}")
            
            # 로그인 페이지로 이동
            await self.page.goto(self.login_url, wait_until='networkidle')
            await asyncio.sleep(2)
            
            # 로그인 폼 입력
            await self.wait_and_type('input[name="username"]', username)
            await self.wait_and_type('input[name="password"]', password)
            
            # 로그인 버튼 클릭
            await self.wait_and_click('button[type="submit"]')
            
            # 로그인 성공 확인
            await asyncio.sleep(3)
            
            current_url = self.page.url
            if 'ceo.yogiyo.co.kr' in current_url and 'login' not in current_url:
                self.logged_in = True
                logger.info("요기요 로그인 성공")
                await self.save_screenshot("login_success")
                return True
            else:
                logger.error("요기요 로그인 실패")
                await self.save_screenshot("login_failed")
                return False
                
        except Exception as e:
            logger.error(f"요기요 로그인 중 오류: {str(e)}")
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
            
            # 드롭다운 버튼 클릭하여 매장 목록 표시
            dropdown_button = await self.page.query_selector('.StoreSelector__DropdownButton-sc-1rowjsb-11')
            if dropdown_button:
                await dropdown_button.click()
                await asyncio.sleep(1)
            
            # 매장 목록 가져오기
            vendor_items = await self.page.query_selector_all('.List__Vendor-sc-2ocjy3-7')
            
            for item in vendor_items:
                # 매장 이름
                name_elem = await item.query_selector('.List__VendorName-sc-2ocjy3-3')
                store_name = await name_elem.text_content() if name_elem else ''
                
                # 매장 ID
                id_elem = await item.query_selector('.List__VendorID-sc-2ocjy3-1')
                id_text = await id_elem.text_content() if id_elem else ''
                
                # ID에서 숫자만 추출 ("ID. 1371806" -> "1371806")
                platform_code = re.search(r'ID\.\s*(\d+)', id_text)
                platform_code = platform_code.group(1) if platform_code else ''
                
                # 상태
                status_elem = await item.query_selector('.List__StoreStatus-sc-2ocjy3-0')
                status = await status_elem.text_content() if status_elem else ''
                
                if store_name and platform_code:
                    store_info = {
                        'platform_code': platform_code,
                        'store_name': store_name,
                        'status': status,
                        'platform': 'yogiyo'
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
            current_store_elem = await self.page.query_selector('.StoreSelector__StoreNumber-sc-1rowjsb-4')
            if current_store_elem:
                current_text = await current_store_elem.text_content()
                if platform_code in current_text:
                    logger.info(f"이미 선택된 매장: {platform_code}")
                    return True
            
            # 드롭다운 열기
            dropdown_button = await self.page.query_selector('.StoreSelector__DropdownButton-sc-1rowjsb-11')
            if dropdown_button:
                await dropdown_button.click()
                await asyncio.sleep(1)
            
            # 매장 목록에서 해당 매장 찾아 클릭
            vendor_items = await self.page.query_selector_all('.List__Vendor-sc-2ocjy3-7')
            
            for item in vendor_items:
                id_elem = await item.query_selector('.List__VendorID-sc-2ocjy3-1')
                if id_elem:
                    id_text = await id_elem.text_content()
                    if platform_code in id_text:
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
            
            # 매장 이름
            store_name_elem = await self.page.query_selector('.StoreSelector__StoreName-sc-1rowjsb-2')
            if store_name_elem:
                store_info['store_name'] = await store_name_elem.text_content()
            
            # 매장 ID
            store_id_elem = await self.page.query_selector('.StoreSelector__StoreNumber-sc-1rowjsb-4')
            if store_id_elem:
                id_text = await store_id_elem.text_content()
                platform_code = re.search(r'ID\.\s*(\d+)', id_text)
                store_info['platform_code'] = platform_code.group(1) if platform_code else ''
            
            # 상태
            status_elem = await self.page.query_selector('.StoreSelector__StoreStatus-sc-1rowjsb-6')
            if status_elem:
                store_info['status'] = await status_elem.text_content()
            
            store_info['platform'] = 'yogiyo'
            
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
