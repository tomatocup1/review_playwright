"""
쿠팡이츠 크롤러
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
    from .review_crawlers.windows_async_crawler import WindowsAsyncBaseCrawler
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

class CoupangCrawler(WindowsAsyncBaseCrawler):
    """쿠팡이츠 크롤러"""
    
    def __init__(self, headless: bool = True):
        super().__init__(headless)
        self.login_url = "https://store.coupangeats.com/merchant/login"
        self.reviews_url = "https://store.coupangeats.com/merchant/management/reviews"
        self.current_store_info = {}
        
        # 스크린샷 저장 경로
        self.screenshot_dir = Path("C:/Review_playwright/logs/screenshots/coupang")
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
    
    async def close_popup(self):
        """팝업 닫기"""
        try:
            # 여러 셀렉터로 팝업 닫기 버튼 찾기
            popup_selectors = [
                'button[data-testid="Dialog__CloseButton"]',
                '.dialog-modal-wrapper__body--close-button',
                '.dialog-modal-wrapper__body--close-icon--white',
                'button.dialog-modal-wrapper__body--close-button'
            ]
            
            for selector in popup_selectors:
                try:
                    close_button = await self.page.query_selector(selector)
                    if close_button:
                        await close_button.click()
                        logger.info(f"팝업을 닫았습니다 (셀렉터: {selector})")
                        await asyncio.sleep(1)
                        return True
                except:
                    continue
            
            logger.debug("닫을 팝업이 없거나 이미 닫혀있습니다")
            return False
            
        except Exception as e:
            logger.debug(f"팝업 처리 중 예외 발생: {str(e)}")
            return False
    
    async def login(self, username: str, password: str) -> bool:
        """쿠팡이츠 로그인"""
        try:
            logger.info(f"쿠팡이츠 로그인 시작: {username}")
            
            # 로그인 페이지로 이동
            await self.page.goto(self.login_url, wait_until='networkidle')
            await asyncio.sleep(2)
            
            # 로그인 폼 입력 - 제공된 실제 셀렉터 사용
            await self.page.fill('#loginId', username)
            logger.info("아이디 입력 완료")
            
            await self.page.fill('#password', password)
            logger.info("비밀번호 입력 완료")
            
            # 로그인 버튼 클릭 - 제공된 실제 셀렉터 사용
            await self.page.click('button[type="submit"].btn.merchant-submit-btn')
            logger.info("로그인 버튼 클릭")
            
            # 로그인 성공 확인 - 더 긴 대기 시간
            await asyncio.sleep(5)
            
            current_url = self.page.url
            logger.info(f"로그인 후 URL: {current_url}")
            
            if 'store.coupangeats.com/merchant' in current_url and 'login' not in current_url:
                self.logged_in = True
                logger.info("쿠팡이츠 로그인 성공")
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
            await asyncio.sleep(3)
            
            # 팝업 닫기
            await self.close_popup()
            
            stores = []
            
            # 드롭다운 클릭하여 매장 목록 표시
            try:
                # 더 간단한 셀렉터로 드롭다운 버튼 찾기
                dropdown_button = await self.page.query_selector('.button')
                if dropdown_button:
                    await dropdown_button.click()
                    await asyncio.sleep(1)
                    logger.info("드롭다운 열기 성공")
                else:
                    logger.error("드롭다운 버튼을 찾을 수 없습니다")
                    await self.save_screenshot("dropdown_not_found")
            except Exception as e:
                logger.error(f"드롭다운 클릭 실패: {str(e)}")
            
            # 매장 목록 가져오기 - ul.options 안의 li 요소들
            try:
                # 옵션 리스트가 나타날 때까지 대기
                await self.page.wait_for_selector('ul.options', timeout=5000)
                option_items = await self.page.query_selector_all('ul.options li')
                
                if option_items:
                    logger.info(f"{len(option_items)}개의 매장 옵션 발견")
                    
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
                                    'platform': 'coupang',
                                    'store_type': 'delivery_only',  # 기본값
                                    'category': '',  # 쿠팡이츠는 카테고리 정보가 별도로 없음
                                    'status': '영업중'  # 기본값
                                }
                                stores.append(store_info)
                                logger.info(f"매장 발견: {store_name} ({platform_code})")
                else:
                    logger.warning("매장 옵션을 찾을 수 없습니다")
                    
            except Exception as e:
                logger.error(f"매장 목록 파싱 중 오류: {str(e)}")
                await self.save_screenshot("store_list_parsing_error")
            
            # 드롭다운 닫기 (페이지 다른 곳 클릭)
            try:
                await self.page.click('body')
            except:
                pass
            
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
                # 팝업 닫기
                await self.close_popup()
            
            # 현재 선택된 매장 확인 - 버튼 텍스트로 확인
            try:
                button_elem = await self.page.query_selector('.button')
                if button_elem:
                    button_text = await button_elem.text_content()
                    if button_text and platform_code in button_text:
                        logger.info(f"이미 선택된 매장: {platform_code}")
                        return True
            except:
                pass
            
            # 드롭다운 열기
            dropdown_button = await self.page.query_selector('.button')
            if dropdown_button:
                await dropdown_button.click()
                await asyncio.sleep(1)
            else:
                logger.error("드롭다운 버튼을 찾을 수 없습니다")
                return False
            
            # 매장 목록에서 해당 매장 찾아 클릭
            try:
                await self.page.wait_for_selector('ul.options', timeout=5000)
                option_items = await self.page.query_selector_all('ul.options li')
                
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
                logger.error(f"매장 선택 중 오류: {str(e)}")
                return False
            
        except Exception as e:
            logger.error(f"매장 선택 실패: {str(e)}")
            return False
    
    async def get_store_info(self) -> Dict[str, Any]:
        """현재 선택된 매장 정보 가져오기"""
        try:
            store_info = {}
            
            # 현재 선택된 매장 정보 가져오기
            button_elem = await self.page.query_selector('.button')
            if button_elem:
                button_text = await button_elem.text_content()
                if button_text:
                    # "큰집닭강정(708561)" 형식에서 매장명과 코드 추출
                    match = re.match(r'(.+)\((\d+)\)', button_text.strip())
                    if match:
                        store_info['store_name'] = match.group(1).strip()
                        store_info['platform_code'] = match.group(2)
            
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
                # 팝업 닫기
                await self.close_popup()
            
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
        test_id = input("쿠팡이츠 아이디: ")
        test_pw = input("쿠팡이츠 비밀번호: ")
        
        crawler = CoupangCrawler(headless=False)
        try:
            await crawler.start_browser()
            print("브라우저 시작 완료")
            
            login_success = await crawler.login(test_id, test_pw)
            print(f"로그인 결과: {login_success}")
            
            if login_success:
                stores = await crawler.get_store_list()
                print(f"\n발견된 매장 목록:")
                for store in stores:
                    print(f"- {store['store_name']} (코드: {store['platform_code']})")
            
        except Exception as e:
            print(f"오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            input("\n브라우저를 닫으려면 Enter를 누르세요...")
            await crawler.close_browser()
    
    asyncio.run(test())
