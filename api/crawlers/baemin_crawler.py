"""
배달의민족 크롤러
"""
from typing import Dict, List, Any, Optional
import re
import asyncio
from datetime import datetime
import logging
from .base_crawler import BaseCrawler

logger = logging.getLogger(__name__)

class BaeminCrawler(BaseCrawler):
    """배달의민족 크롤러"""
    
    def __init__(self, headless: bool = True):
        super().__init__(headless)
        self.login_url = "https://biz-member.baemin.com/login"
        self.self_service_url = "https://self.baemin.com/"
        self.current_store_info = {}
    
    async def login(self, username: str, password: str) -> bool:
        """배민 로그인"""
        try:
            logger.info(f"배민 로그인 시작: {username}")
            
            # 로그인 페이지로 이동
            await self.page.goto(self.login_url, wait_until='networkidle')
            await asyncio.sleep(2)
            
            # 로그인 폼 입력
            await self.wait_and_type('input[name="id"]', username)
            await self.wait_and_type('input[name="password"]', password)
            
            # 로그인 버튼 클릭
            await self.wait_and_click('button[type="submit"]')
            
            # 로그인 성공 확인 (셀프서비스 페이지로 리다이렉트 또는 특정 요소 확인)
            await asyncio.sleep(3)
            
            # 로그인 성공 여부 확인
            current_url = self.page.url
            if 'self.baemin.com' in current_url or 'ceo.baemin.com' in current_url:
                self.logged_in = True
                logger.info("배민 로그인 성공")
                await self.save_screenshot("login_success")
                return True
            else:
                logger.error("배민 로그인 실패")
                await self.save_screenshot("login_failed")
                return False
                
        except Exception as e:
            logger.error(f"배민 로그인 중 오류: {str(e)}")
            await self.save_screenshot("login_error")
            return False
    
    async def get_store_list(self) -> List[Dict[str, Any]]:
        """매장 목록 가져오기"""
        try:
            if not self.logged_in:
                logger.error("로그인이 필요합니다")
                return []
            
            # 셀프서비스 페이지로 이동
            await self.page.goto(self.self_service_url, wait_until='networkidle')
            await asyncio.sleep(2)
            
            stores = []
            
            # 매장 선택 셀렉트 박스 찾기
            select_element = await self.page.query_selector('select.Select-module__a623')
            if select_element:
                # 옵션 목록 가져오기
                options = await self.page.query_selector_all('select.Select-module__a623 option')
                
                for option in options:
                    value = await option.get_attribute('value')
                    text = await option.text_content()
                    
                    # 텍스트에서 정보 파싱
                    # 예: "[음식배달] 왓더버거 용인동백점 / 패스트푸드 14697037 왓더버거"
                    match = re.search(r'\[([^\]]+)\]\s*([^/]+)\s*/\s*([^\s]+)\s*(\d+)\s*(.+)', text)
                    if match:
                        store_info = {
                            'platform_code': value,
                            'store_type': match.group(1),
                            'store_name': match.group(2).strip(),
                            'category': match.group(3),
                            'store_id': match.group(4),
                            'brand_name': match.group(5).strip()
                        }
                        stores.append(store_info)
                        logger.info(f"매장 발견: {store_info['store_name']} ({store_info['platform_code']})")
            
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
            
            # 셀렉트 박스에서 매장 선택
            select_element = await self.page.query_selector('select.Select-module__a623')
            if select_element:
                await select_element.select_option(platform_code)
                await asyncio.sleep(2)
                
                # 선택 확인
                selected_value = await self.page.eval_on_selector(
                    'select.Select-module__a623',
                    'el => el.value'
                )
                
                if selected_value == platform_code:
                    logger.info(f"매장 선택 성공: {platform_code}")
                    # 현재 매장 정보 업데이트
                    await self.get_store_info()
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"매장 선택 실패: {str(e)}")
            return False
    
    async def get_store_info(self) -> Dict[str, Any]:
        """현재 선택된 매장 정보 가져오기"""
        try:
            store_info = {}
            
            # 매장 이름
            store_name_elem = await self.page.query_selector('.ShopSelect-module__b8Mn')
            if store_name_elem:
                store_name_text = await store_name_elem.text_content()
                # "[음식배달] 왓더버거 용인동백점" 형식에서 매장명만 추출
                match = re.search(r'\[([^\]]+)\]\s*(.+)', store_name_text)
                if match:
                    store_info['store_type'] = match.group(1)
                    store_info['store_name'] = match.group(2).strip()
            
            # 매장 정보 (ID, 카테고리, 브랜드)
            store_detail_elem = await self.page.query_selector('.ShopSelect-module__j4Qm')
            if store_detail_elem:
                detail_text = await store_detail_elem.text_content()
                # "14697037 | 패스트푸드 | 왓더버거" 형식 파싱
                parts = detail_text.split('|')
                if len(parts) >= 3:
                    store_info['platform_code'] = parts[0].strip()
                    store_info['category'] = parts[1].strip()
                    store_info['brand_name'] = parts[2].strip()
            
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
            
            # 리뷰 페이지로 이동 (배민 셀프서비스의 리뷰 섹션)
            # URL은 실제 배민 셀프서비스의 리뷰 페이지 URL로 변경 필요
            review_url = f"{self.self_service_url}reviews"
            await self.page.goto(review_url, wait_until='networkidle')
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
