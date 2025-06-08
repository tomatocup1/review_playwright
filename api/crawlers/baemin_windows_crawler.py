"""
배달의민족 Windows 비동기 크롤러
"""
import re
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
import asyncio
import sys

# Windows 이벤트 루프 정책은 main.py와 windows_async_crawler.py에서 이미 설정됨
# 여기서는 설정하지 않음

from playwright.async_api import async_playwright, Page, Browser, Playwright, BrowserContext

logger = logging.getLogger(__name__)

# 상대 임포트 오류 수정 - 직접 실행할 때와 모듈로 임포트할 때 모두 작동
try:
    from .windows_async_crawler import WindowsAsyncBaseCrawler
except ImportError:
    # 직접 실행시 사용
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from crawlers.windows_async_crawler import WindowsAsyncBaseCrawler

class BaeminWindowsCrawler(WindowsAsyncBaseCrawler):
    """배달의민족 Windows 비동기 크롤러"""
    
    def __init__(self, headless: bool = True):
        super().__init__(headless)
        self.login_url = "https://biz-member.baemin.com/login"
        self.self_service_url = "https://self.baemin.com"
        
        # 스크린샷 저장 경로
        self.screenshot_dir = Path("C:/Review_playwright/logs/screenshots/baemin")
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
        """배민 로그인"""
        try:
            logger.info(f"배민 로그인 시작: {username}")
            
            # 로그인 페이지로 이동
            await self.page.goto(self.login_url)
            await self.page.wait_for_load_state('networkidle')
            
            await self.save_screenshot("login_page")
            
            # 아이디 입력
            await self.page.fill('input[type="text"]', username)
            logger.info("아이디 입력 완료")
            
            # 비밀번호 입력
            await self.page.fill('input[type="password"]', password)
            logger.info("비밀번호 입력 완료")
            
            # 로그인 버튼 클릭
            await self.page.click('button[type="submit"]')
            logger.info("로그인 버튼 클릭")
            
            # 로그인 처리를 위해 충분한 시간 대기
            logger.info("로그인 처리 대기 중...")
            await self.page.wait_for_timeout(5000)  # 5초 대기
            
            # 현재 URL 확인
            current_url = self.page.url
            logger.info(f"로그인 후 URL: {current_url}")
            
            # 스크린샷 저장
            await self.save_screenshot("after_login")
            
            # 단순히 로그인 페이지를 벗어났는지 확인
            if 'login' not in current_url.lower():
                logger.info("로그인 페이지를 벗어남 - 로그인 성공")
                self.logged_in = True
                return True
            else:
                logger.error("여전히 로그인 페이지에 있음 - 로그인 실패")
                return False
                
        except Exception as e:
            logger.error(f"배민 로그인 중 오류: {str(e)}")
            await self.save_screenshot("login_error")
            return False
            
    async def close_popup(self):
        """팝업 닫기"""
        try:
            # 팝업이 나타날 때까지 잠시 대기
            await self.page.wait_for_timeout(2000)
            
            # "오늘 하루 보지 않기" 버튼 찾아서 클릭
            popup_close_selectors = [
                'button:has-text("오늘 하루 보지 않기")',
                'span:has-text("오늘 하루 보지 않기")',
                'text="오늘 하루 보지 않기"',
                '.TextButton_b_b8ew_1j0jumh3'  # 클래스명으로도 시도
            ]
            
            for selector in popup_close_selectors:
                try:
                    if await self.page.is_visible(selector):
                        await self.page.click(selector)
                        logger.info(f"팝업을 닫았습니다: {selector}")
                        await self.page.wait_for_timeout(1000)
                        return
                except:
                    continue
                    
            logger.info("닫을 팝업이 없거나 이미 닫혀있습니다")
                    
        except Exception as e:
            logger.debug(f"팝업 처리 중 예외 발생: {str(e)}")
            
    async def get_store_list(self) -> List[Dict[str, Any]]:
        """매장 목록 조회"""
        try:
            logger.info("배민 매장 목록 조회 시작")
            
            # 현재 URL 확인
            current_url = self.page.url
            logger.info(f"현재 페이지 URL: {current_url}")
            
            # 셀프서비스 페이지로 이동
            logger.info("셀프서비스 페이지로 이동")
            await self.page.goto(self.self_service_url)
            await self.page.wait_for_load_state('networkidle')
            
            # 페이지 로드 대기
            await self.page.wait_for_timeout(3000)
            
            # 팝업 닫기
            await self.close_popup()
            
            await self.save_screenshot("self_service_page")
            
            stores = []
            
            # select 요소 찾기
            try:
                # 다양한 선택자로 시도
                select_selectors = [
                    'select.ShopSelect-module___pC1',
                    'select.Select-module__a623',
                    'select',  # 모든 select 요소
                    '.ShopSelect-module__JWCr select'
                ]
                
                select_element = None
                selector = None
                for sel in select_selectors:
                    try:
                        select_element = await self.page.wait_for_selector(sel, timeout=5000)
                        if select_element:
                            selector = sel
                            logger.info(f"Select 요소 발견: {selector}")
                            break
                    except:
                        continue
                
                if select_element and selector:
                    # select 요소의 모든 option 가져오기
                    options = await self.page.query_selector_all(f'{selector} option')
                    
                    if options:
                        logger.info(f"{len(options)}개의 매장 발견")
                        
                        for option in options:
                            value = await option.get_attribute('value')
                            text = await option.text_content()
                            
                            if value and text:
                                logger.info(f"옵션 발견: {text}")
                                
                                # 텍스트에서 매장 정보 파싱
                                # 예: "[음식배달] 더클램 데이 / 카페·디저트 14545991"
                                # 정규식 패턴 수정 - 마지막 숫자 부분을 선택적으로
                                patterns = [
                                    r'\[(.*?)\]\s*(.+?)\s*/\s*(.+?)\s*(\d+)$',  # 끝에 숫자가 있는 경우
                                    r'\[(.*?)\]\s*(.+?)\s*/\s*(.+?)$',  # 숫자가 없는 경우
                                    r'(.+?)\s*/\s*(.+?)\s*(\d+)$',  # 대괄호가 없는 경우
                                ]
                                
                                matched = False
                                for pattern in patterns:
                                    match = re.match(pattern, text.strip())
                                    if match:
                                        if len(match.groups()) == 4:  # 숫자 포함
                                            store_type = match.group(1)
                                            store_name = match.group(2).strip()
                                            category = match.group(3).strip()
                                            platform_code = match.group(4)
                                        elif len(match.groups()) == 3 and match.group(3).isdigit():  # 대괄호 없고 숫자 있음
                                            store_type = '음식배달'
                                            store_name = match.group(1).strip()
                                            category = match.group(2).strip()
                                            platform_code = match.group(3)
                                        else:  # 숫자 없음
                                            store_type = match.group(1) if '[' in text else '음식배달'
                                            store_name = match.group(2) if '[' in text else match.group(1).strip()
                                            category = match.group(3) if '[' in text else match.group(2).strip()
                                            platform_code = value
                                        
                                        matched = True
                                        break
                                
                                if not matched:
                                    # 패턴 매칭 실패 시 기본 파싱
                                    parts = text.strip().split('/')
                                    if parts:
                                        store_name = parts[0].strip()
                                        if '[' in store_name:
                                            store_name = store_name.split(']')[-1].strip()
                                        category = parts[1].strip() if len(parts) > 1 else ''
                                    else:
                                        store_name = text.strip()
                                        category = ''
                                    store_type = '음식배달'
                                    platform_code = value
                                
                                store_info = {
                                    'platform': 'baemin',
                                    'platform_code': platform_code,
                                    'store_name': store_name,
                                    'store_type': store_type,
                                    'category': category,
                                    'status': '영업중'
                                }
                                
                                stores.append(store_info)
                                logger.info(f"매장 추가: {store_name} (코드: {platform_code}, 카테고리: {category})")
                    else:
                        logger.warning("option 요소를 찾을 수 없습니다")
                else:
                    logger.warning("select 요소를 찾을 수 없습니다")
                    
            except Exception as e:
                logger.error(f"매장 목록 파싱 중 오류: {str(e)}")
                await self.save_screenshot("store_list_error")
            
            if not stores:
                logger.warning("매장 목록을 찾을 수 없습니다")
                return [{
                    'platform': 'baemin',
                    'platform_code': 'TEST_001',
                    'store_name': '(테스트) 매장을 찾을 수 없습니다',
                    'store_type': '테스트',
                    'category': '',
                    'status': '확인필요'
                }]
            
            logger.info(f"배민 매장 총 {len(stores)}개 발견")
            return stores
            
        except Exception as e:
            logger.error(f"매장 목록 조회 중 오류: {str(e)}")
            await self.save_screenshot("store_list_error")
            return []
    
    async def select_store(self, platform_code: str) -> bool:
        """매장 선택"""
        try:
            logger.info(f"매장 선택 시도: {platform_code}")
            
            # 셀프서비스 페이지에서 매장 선택
            select_element = await self.page.query_selector('select')
            if select_element:
                await select_element.select_option(platform_code)
                logger.info(f"매장 {platform_code} 선택 완료")
                await self.page.wait_for_timeout(2000)  # 페이지 로드 대기
                return True
            else:
                logger.error("매장 선택 select 요소를 찾을 수 없습니다")
                return False
                
        except Exception as e:
            logger.error(f"매장 선택 중 오류: {str(e)}")
            return False
            
    async def get_store_info(self) -> Dict[str, Any]:
        """현재 선택된 매장 정보 가져오기"""
        try:
            logger.info("매장 정보 조회 시작")
            
            # 현재 선택된 매장의 정보를 가져옴
            store_info = {
                'platform': 'baemin',
                'store_name': '',
                'business_hours': {},
                'store_address': '',
                'store_phone': ''
            }
            
            # TODO: 실제 매장 정보 페이지에서 정보 추출 로직 구현
            # 현재는 기본값 반환
            
            return store_info
            
        except Exception as e:
            logger.error(f"매장 정보 조회 중 오류: {str(e)}")
            return {}
            
    async def get_reviews(self, limit: int = 50) -> List[Dict[str, Any]]:
        """리뷰 목록 가져오기"""
        try:
            logger.info(f"리뷰 목록 조회 시작 (최대 {limit}개)")
            
            reviews = []
            
            # TODO: 실제 리뷰 페이지로 이동하여 리뷰 목록 추출 로직 구현
            # 현재는 빈 리스트 반환
            
            logger.info(f"총 {len(reviews)}개의 리뷰 조회 완료")
            return reviews
            
        except Exception as e:
            logger.error(f"리뷰 목록 조회 중 오류: {str(e)}")
            return []
            
    async def post_reply(self, review_id: str, reply_text: str) -> bool:
        """리뷰에 답글 작성"""
        try:
            logger.info(f"리뷰 {review_id}에 답글 작성 시작")
            
            # TODO: 실제 답글 작성 로직 구현
            # 현재는 False 반환
            
            logger.warning("답글 작성 기능이 아직 구현되지 않았습니다")
            return False
            
        except Exception as e:
            logger.error(f"답글 작성 중 오류: {str(e)}")
            return False


# 직접 실행 시 테스트 코드
if __name__ == "__main__":
    # 직접 실행할 때만 이벤트 루프 정책 설정
    if sys.platform == 'win32':
        # ProactorEventLoop를 사용 (subprocess 지원)
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async def test():
        crawler = BaeminWindowsCrawler(headless=False)
        try:
            await crawler.start_browser()
            print("브라우저 시작 완료")
            
            # 직접 아이디/비밀번호 입력 (테스트용)
            user_id = "hong7704002646"
            password = "bin986200#"
            
            login_success = await crawler.login(user_id, password)
            print(f"로그인 결과: {login_success}")
            
            if login_success:
                stores = await crawler.get_store_list()
                print(f"\n발견된 매장 목록:")
                for store in stores:
                    print(f"- {store['store_name']} (코드: {store['platform_code']}, 카테고리: {store.get('category', '')})")
            
        except Exception as e:
            print(f"오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            input("\n브라우저를 닫으려면 Enter를 누르세요...")
            await crawler.close_browser()
    
    asyncio.run(test())