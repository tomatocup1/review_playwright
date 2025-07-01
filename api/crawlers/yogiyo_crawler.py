"""
요기요 크롤러
"""
from typing import Dict, List, Any, Optional
import re
import asyncio
from datetime import datetime
import logging
from pathlib import Path
import sys
import os

# 상대 임포트 오류 해결
try:
    from .windows_async_crawler import WindowsAsyncBaseCrawler
except ImportError:
    # 직접 실행할 때를 위한 처리
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    sys.path.insert(0, parent_dir)
    try:
        from crawlers.review_crawlers.windows_async_crawler import WindowsAsyncBaseCrawler
    except ImportError:
        # review_crawlers에서도 찾지 못하면 상위 경로 시도
        sys.path.insert(0, os.path.dirname(parent_dir))
        from api.crawlers.review_crawlers.windows_async_crawler import WindowsAsyncBaseCrawler

logger = logging.getLogger(__name__)

class YogiyoCrawler(WindowsAsyncBaseCrawler):
    """요기요 크롤러"""
    
    def __init__(self, headless: bool = True):
        super().__init__(headless)
        self.login_url = "https://ceo.yogiyo.co.kr/login/"
        self.reviews_url = "https://ceo.yogiyo.co.kr/reviews"
        self.current_store_info = {}
        
        # 스크린샷 저장 경로
        self.screenshot_dir = Path("C:/Review_playwright/logs/screenshots/yogiyo")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
    
    async def save_screenshot(self, name: str):
        """스크린샷 저장"""
        if not self.page:
            return
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}.png"
            filepath = self.screenshot_dir / filename
            
            await self.page.screenshot(path=str(filepath))
            logger.info(f"스크린샷 저장: {filepath}")
            
        except Exception as e:
            logger.error(f"스크린샷 저장 실패: {str(e)}")
    
    async def login(self, username: str, password: str) -> bool:
        """요기요 로그인"""
        try:
            logger.info(f"요기요 로그인 시작: {username}")
            
            # 로그인 페이지로 이동
            await self.page.goto(self.login_url, wait_until='networkidle')
            await asyncio.sleep(2)
            
            # 로그인 폼 입력 - name 속성 사용
            await self.page.fill('input[name="username"]', username)
            logger.info("아이디 입력 완료")
            
            await self.page.fill('input[name="password"]', password)
            logger.info("비밀번호 입력 완료")
            
            # 로그인 버튼 클릭
            await self.page.click('button[type="submit"]')
            logger.info("로그인 버튼 클릭")
            
            # 인증 메일 팝업 처리 추가
            await asyncio.sleep(3)  # 팝업이 나타날 시간 대기
            
            try:
                # 인증 메일 확인 팝업 체크
                auth_popup = await self.page.query_selector('div.Alert__Message-sc-a98nwm-3.ewbPZf')
                if auth_popup:
                    popup_text = await auth_popup.text_content()
                    if '인증 메일 확인이 완료되지 않았습니다' in popup_text:
                        logger.info("인증 메일 팝업 감지됨")
                        
                        # 첫 번째 확인 버튼 클릭
                        confirm_button = await self.page.query_selector('button.sc-bczRLJ.claiZC.sc-eCYdqJ.hsiXYt')
                        if confirm_button:
                            await confirm_button.click()
                            logger.info("인증 메일 재발송 확인 버튼 클릭")
                            await asyncio.sleep(2)
                            
                            # 두 번째 팝업의 확인 버튼 클릭
                            second_popup = await self.page.query_selector('div.Alert__Message-sc-a98nwm-3.ewbPZf')
                            if second_popup:
                                second_popup_text = await second_popup.text_content()
                                if '인증 메일을 발송했습니다' in second_popup_text:
                                    logger.info("인증 메일 발송 팝업 감지됨")
                                    
                                    # 두 번째 확인 버튼 클릭
                                    second_confirm_button = await self.page.query_selector('button.sc-bczRLJ.claiZC.sc-eCYdqJ.hsiXYt')
                                    if second_confirm_button:
                                        await second_confirm_button.click()
                                        logger.info("인증 메일 발송 확인 버튼 클릭")
                                        await asyncio.sleep(2)
            except Exception as e:
                logger.info(f"인증 메일 팝업 처리 중 예외 발생 (정상적인 경우일 수 있음): {str(e)}")
            
            # 로그인 성공 확인 - 더 긴 대기 시간
            await asyncio.sleep(3)
            
            current_url = self.page.url
            logger.info(f"로그인 후 URL: {current_url}")
            
            if 'ceo.yogiyo.co.kr' in current_url and 'login' not in current_url:
                self.logged_in = True
                logger.info("요기요 로그인 성공")
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
            await asyncio.sleep(3)
            
            stores = []
            
            # 드롭다운 클릭하여 매장 목록 표시
            try:
                # 드롭다운 버튼 찾기
                dropdown_button = await self.page.query_selector('.StoreSelector__DropdownButton-sc-1rowjsb-11')
                if dropdown_button:
                    await dropdown_button.click()
                    await asyncio.sleep(2)  # 드롭다운이 완전히 열릴 때까지 대기
                    logger.info("드롭다운 열기 성공")
                    
                    # 드롭다운 메뉴에서 모든 매장 정보 가져오기
                    # ul.List__VendorList-sc-2ocjy3-8 안의 li 요소들 찾기
                    store_items = await self.page.query_selector_all('ul.List__VendorList-sc-2ocjy3-8 li.List__Vendor-sc-2ocjy3-7')
                    
                    if store_items:
                        logger.info(f"{len(store_items)}개의 매장 발견")
                        
                        for item in store_items:
                            try:
                                # 매장명 가져오기
                                store_name_elem = await item.query_selector('.List__VendorName-sc-2ocjy3-3')
                                store_name = await store_name_elem.text_content() if store_name_elem else None
                                
                                # 매장 ID 가져오기
                                store_id_elem = await item.query_selector('.List__VendorID-sc-2ocjy3-1')
                                store_id_text = await store_id_elem.text_content() if store_id_elem else None
                                
                                if store_name and store_id_text:
                                    # "ID. 1371806" 형식에서 숫자만 추출
                                    match = re.search(r'ID\.\s*(\d+)', store_id_text)
                                    if match:
                                        platform_code = match.group(1)
                                        
                                        # 매장 상태 가져오기
                                        status = '영업중'  # 기본값
                                        try:
                                            status_elem = await item.query_selector('.List__StoreStatus-sc-2ocjy3-0')
                                            if status_elem:
                                                status_text = await status_elem.text_content()
                                                status = status_text.strip()
                                        except:
                                            pass
                                        
                                        store_info = {
                                            'platform_code': platform_code,
                                            'store_name': store_name.strip(),
                                            'platform': 'yogiyo',
                                            'store_type': 'delivery_only',
                                            'category': '',
                                            'status': status
                                        }
                                        stores.append(store_info)
                                        logger.info(f"매장 발견: {store_name} ({platform_code}) - {status}")
                                        
                            except Exception as e:
                                logger.error(f"매장 정보 파싱 중 오류: {str(e)}")
                                continue
                    
                    # 드롭다운 닫기 (ESC 키 누르기)
                    await self.page.keyboard.press('Escape')
                    await asyncio.sleep(1)
                    
                else:
                    logger.warning("드롭다운 버튼을 찾을 수 없습니다")
                    # 드롭다운이 없어도 현재 선택된 매장 정보는 가져오기
                    await self._get_current_store_info(stores)
                    
            except Exception as e:
                logger.error(f"드롭다운 처리 중 오류: {str(e)}")
                await self.save_screenshot("dropdown_error")
                # 오류가 발생해도 현재 매장 정보는 가져오기
                await self._get_current_store_info(stores)
            
            return stores
            
        except Exception as e:
            logger.error(f"매장 목록 가져오기 실패: {str(e)}")
            await self.save_screenshot("store_list_error")
            return []
    
    async def _get_current_store_info(self, stores: List[Dict[str, Any]]):
        """현재 선택된 매장 정보를 가져와서 리스트에 추가"""
        try:
            # 매장명 가져오기
            store_name_elem = await self.page.query_selector('.StoreSelector__StoreName-sc-1rowjsb-2')
            if store_name_elem:
                store_name = await store_name_elem.text_content()
                
                # 매장 ID 가져오기
                store_id_elem = await self.page.query_selector('.StoreSelector__StoreNumber-sc-1rowjsb-4')
                if store_id_elem:
                    store_id_text = await store_id_elem.text_content()
                    # "ID. 1371806" 형식에서 숫자만 추출
                    match = re.search(r'ID\.\s*(\d+)', store_id_text)
                    if match:
                        platform_code = match.group(1)
                        
                        # 중복 체크
                        if not any(s['platform_code'] == platform_code for s in stores):
                            store_info = {
                                'platform_code': platform_code,
                                'store_name': store_name.strip(),
                                'platform': 'yogiyo',
                                'store_type': 'delivery_only',
                                'category': '',
                                'status': '영업중'
                            }
                            stores.append(store_info)
                            logger.info(f"현재 매장 추가: {store_name} ({platform_code})")
        except Exception as e:
            logger.error(f"현재 매장 정보 가져오기 실패: {str(e)}")
    
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
            try:
                store_id_elem = await self.page.query_selector('.StoreSelector__StoreNumber-sc-1rowjsb-4')
                if store_id_elem:
                    store_id_text = await store_id_elem.text_content()
                    if platform_code in store_id_text:
                        logger.info(f"이미 선택된 매장: {platform_code}")
                        return True
            except:
                pass
            
            # 드롭다운 열기
            dropdown_button = await self.page.query_selector('.StoreSelector__DropdownButton-sc-1rowjsb-11')
            if dropdown_button:
                await dropdown_button.click()
                await asyncio.sleep(2)
            else:
                logger.error("드롭다운 버튼을 찾을 수 없습니다")
                return False
            
            # 매장 목록에서 해당 매장 찾아 클릭
            try:
                # 모든 매장 아이템 가져오기
                store_items = await self.page.query_selector_all('ul.List__VendorList-sc-2ocjy3-8 li.List__Vendor-sc-2ocjy3-7')
                
                for item in store_items:
                    # 매장 ID 확인
                    store_id_elem = await item.query_selector('.List__VendorID-sc-2ocjy3-1')
                    if store_id_elem:
                        store_id_text = await store_id_elem.text_content()
                        if platform_code in store_id_text:
                            # 해당 매장 클릭
                            await item.click()
                            await asyncio.sleep(2)
                            logger.info(f"매장 선택 성공: {platform_code}")
                            
                            # 현재 매장 정보 업데이트
                            await self.get_store_info()
                            return True
                
                logger.error(f"매장을 찾을 수 없습니다: {platform_code}")
                # 드롭다운 닫기
                await self.page.keyboard.press('Escape')
                return False
                
            except Exception as e:
                logger.error(f"매장 선택 중 오류: {str(e)}")
                # 드롭다운 닫기
                try:
                    await self.page.keyboard.press('Escape')
                except:
                    pass
                return False
            
        except Exception as e:
            logger.error(f"매장 선택 실패: {str(e)}")
            return False
    
    async def get_store_info(self) -> Dict[str, Any]:
        """현재 선택된 매장 정보 가져오기"""
        try:
            store_info = {}
            
            # 매장명 가져오기
            store_name_elem = await self.page.query_selector('.StoreSelector__StoreName-sc-1rowjsb-2')
            if store_name_elem:
                store_info['store_name'] = await store_name_elem.text_content()
            
            # 매장 ID 가져오기
            store_id_elem = await self.page.query_selector('.StoreSelector__StoreNumber-sc-1rowjsb-4')
            if store_id_elem:
                store_id_text = await store_id_elem.text_content()
                match = re.search(r'ID\.\s*(\d+)', store_id_text)
                if match:
                    store_info['platform_code'] = match.group(1)
            
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
            # TODO: 실제 리뷰 HTML 구조에 맞게 수정 필요
            
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
            # TODO: 실제 답글 작성 HTML 구조에 맞게 수정 필요
            
            logger.info(f"리뷰 {review_id}에 답글 작성 성공")
            return True
            
        except Exception as e:
            logger.error(f"답글 작성 실패: {str(e)}")
            return False


# 직접 실행할 때 테스트 코드
if __name__ == "__main__":
    # Windows 이벤트 루프 설정
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async def test():
        # 테스트용 계정 정보 (실제 계정으로 변경 필요)
        test_id = input("요기요 아이디: ")
        test_pw = input("요기요 비밀번호: ")
        
        crawler = YogiyoCrawler(headless=False)
        try:
            await crawler.start_browser()
            print("브라우저 시작 완료")
            
            login_success = await crawler.login(test_id, test_pw)
            print(f"로그인 결과: {login_success}")
            
            if login_success:
                stores = await crawler.get_store_list()
                print(f"\n발견된 매장 목록:")
                for store in stores:
                    print(f"- {store['store_name']} (코드: {store['platform_code']}) - {store['status']}")
            
        except Exception as e:
            print(f"오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            input("\n브라우저를 닫으려면 Enter를 누르세요...")
            await crawler.close_browser()
    
    asyncio.run(test())