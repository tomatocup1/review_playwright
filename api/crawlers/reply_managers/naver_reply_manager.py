"""
네이버 플레이스 답글 관리자
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import asyncio
import json
import re
import logging
import os
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

class NaverReplyManager:
    """네이버 플레이스 답글 관리 클래스"""
    
    def __init__(self, store_info: Dict[str, Any]):
        self.store_info = store_info
        self.platform = 'naver'
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.login_url = "https://nid.naver.com/nidlogin.login"
        self.review_url_template = "https://new.smartplace.naver.com/bizes/place/{platform_code}"
        
    async def login(self, page: Page) -> bool:
        """네이버 로그인"""
        try:
            self.logger.info(f"네이버 로그인 시작: {self.store_info.get('platform_id')}")
            
            # 로그인 페이지로 이동
            await page.goto(self.login_url, wait_until="domcontentloaded")
            await asyncio.sleep(1)
            
            # 이미 로그인되어 있는지 확인
            current_url = page.url
            if "nid.naver.com/nidlogin.login" not in current_url:
                self.logger.info("이미 로그인된 상태")
                return True
            
            # 아이디 입력
            await page.wait_for_selector("#id", state="visible", timeout=5000)
            await page.click("#id")
            # 기존 값 삭제
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Delete")
            await page.type("#id", self.store_info['platform_id'], delay=50)
            
            # 비밀번호 입력
            await page.click("#pw")
            # 기존 값 삭제
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Delete")
            await page.type("#pw", self.store_info['platform_pw'], delay=50)
            
            # 로그인 버튼 클릭
            await page.click("#log\\.login")
            self.logger.info("로그인 버튼 클릭")
            
            # 페이지 전환 대기
            try:
                await page.wait_for_navigation(timeout=10000)
            except:
                await asyncio.sleep(2)
            
            # 현재 URL 확인
            current_url = page.url
            self.logger.info(f"로그인 후 URL: {current_url}")
            
            # 기기 등록 확인 페이지 처리
            if "deviceConfirm" in current_url:
                self.logger.info("기기 등록 확인 페이지 감지")
                
                try:
                    # 등록 버튼 클릭
                    await page.wait_for_selector("#new\\.save", timeout=5000)
                    await page.click("#new\\.save")
                    self.logger.info("기기 등록 버튼 클릭 완료")
                    
                    await page.wait_for_navigation(timeout=5000)
                    
                except Exception as e:
                    self.logger.error(f"기기 등록 버튼 클릭 실패: {str(e)}")
            
            # 2차 인증 페이지 확인
            current_url = page.url
            if "nid.naver.com/login/ext/need2" in current_url:
                self.logger.warning("2차 인증 필요")
                return False
            
            # 로그인 성공 확인
            self.logger.info("네이버 로그인 성공")
            return True
            
        except PlaywrightTimeoutError:
            self.logger.error("네이버 로그인 실패 - 타임아웃")
            return False
            
        except Exception as e:
            self.logger.error(f"네이버 로그인 중 오류: {str(e)}")
            return False
    
    async def navigate_to_review_page(self, page: Page) -> bool:
        """리뷰 관리 페이지로 이동"""
        try:
            # 리뷰 페이지 URL (reviews 추가)
            review_url = f"https://new.smartplace.naver.com/bizes/place/{self.store_info['platform_code']}/reviews"
            self.logger.info(f"리뷰 페이지 이동: {review_url}")
            
            await page.goto(review_url, wait_until="networkidle")
            await page.wait_for_timeout(3000)
            
            # 팝업 처리 (닫기 버튼)
            try:
                close_btn = await page.wait_for_selector('.fn-booking-close1', timeout=3000)
                if close_btn:
                    await close_btn.click()
                    self.logger.info("팝업 닫기 완료")
                    await asyncio.sleep(1)
            except:
                pass  # 팝업이 없을 수 있음
            
            # 추가 팝업 처리
            try:
                # "확인" 버튼이나 "닫기" 버튼 찾기
                confirm_btn = await page.wait_for_selector('button:has-text("확인")', timeout=2000)
                if confirm_btn:
                    await confirm_btn.click()
                    self.logger.info("확인 팝업 닫기 완료")
                    await asyncio.sleep(1)
            except:
                pass
            
            # 기간 선택 버튼 클릭 (7일 선택)
            try:
                period_button = await page.wait_for_selector('button[data-area-code="rv.calendarfilter"]', timeout=5000)
                await period_button.click()
                await page.wait_for_timeout(1000)
                
                # 7일 옵션 선택
                seven_days_option = await page.wait_for_selector('a[data-area-code="rv.calendarweek"]', timeout=3000)
                await seven_days_option.click()
                await page.wait_for_timeout(2000)
                self.logger.info("7일 필터 설정 완료")
            except Exception as e:
                self.logger.info(f"기간 선택 버튼을 찾을 수 없습니다. 기본 기간으로 진행합니다: {str(e)}")
            
            # 리뷰 목록 로딩 대기
            try:
                await page.wait_for_selector('li.pui__X35jYm.Review_pui_review__zhZdn', timeout=5000)
                self.logger.info("리뷰 목록 로딩 완료")
            except:
                # 구버전 셀렉터도 시도
                try:
                    await page.wait_for_selector('.ReviewItem_review_item__root__tAelQ', timeout=3000)
                    self.logger.info("리뷰 목록 로딩 완료 (구버전)")
                except:
                    self.logger.warning("리뷰 목록 로딩 타임아웃 - 계속 진행")
            
            return True
            
        except Exception as e:
            self.logger.error(f"리뷰 페이지 이동 중 오류: {str(e)}")
            return False
    
    async def find_review_element(self, page: Page, review_info: Dict[str, Any]) -> Optional[Any]:
        """특정 리뷰 요소 찾기"""
        try:
            self.logger.info(f"=== 리뷰 찾기 시작 ===")
            self.logger.info(f"찾으려는 리뷰 정보:")
            self.logger.info(f"  - 작성자: {review_info.get('review_name')}")
            self.logger.info(f"  - 날짜: {review_info.get('review_date')}")
            self.logger.info(f"  - 내용: {review_info.get('review_content', '')[:50]}...")
            
            # 스크롤하면서 모든 리뷰 로드
            self.logger.info("리뷰 목록 스크롤 시작...")
            last_review_count = 0
            scroll_attempts = 0
            max_scroll_attempts = 10
            
            while scroll_attempts < max_scroll_attempts:
                # 현재 리뷰 개수 확인
                review_containers = await page.query_selector_all('li.pui__X35jYm.Review_pui_review__zhZdn')
                current_review_count = len(review_containers)
                
                self.logger.info(f"스크롤 {scroll_attempts + 1}회: 현재 리뷰 수 = {current_review_count}")
                
                if current_review_count == last_review_count:
                    # 더 이상 새로운 리뷰가 로드되지 않음
                    self.logger.info("더 이상 로드할 리뷰가 없음")
                    break
                    
                last_review_count = current_review_count
                
                # 페이지 스크롤
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await page.wait_for_timeout(2000)
                scroll_attempts += 1
            
            # 모든 리뷰 컨테이너 다시 가져오기
            review_containers = await page.query_selector_all('li.pui__X35jYm.Review_pui_review__zhZdn')
            
            self.logger.info(f"총 {len(review_containers)}개의 리뷰 컨테이너 발견")
            
            # 현재 페이지의 모든 리뷰 정보 수집 (디버깅용)
            page_reviews = []
            
            for idx, container in enumerate(review_containers):
                try:
                    # 작성자 확인
                    author_elem = await container.query_selector('span.pui__NMi-Dp')
                    if not author_elem:
                        self.logger.debug(f"리뷰 {idx}: 작성자 요소 없음")
                        continue
                    
                    author_text = await author_elem.inner_text()
                    
                    # 날짜 확인 - 작성일 기준
                    date_text = ""
                    date_containers = await container.query_selector_all('div.pui__4rEbt5')
                    for date_container in date_containers:
                        label = await date_container.query_selector('span.pui__ewpNGR')
                        if label:
                            label_text = await label.inner_text()
                            if "작성일" in label_text:
                                date_elem = await date_container.query_selector('time')
                                if date_elem:
                                    date_text = await date_elem.inner_text()
                                    break
                    
                    # 내용 미리보기
                    content_preview = ""
                    content_elem = await container.query_selector('a.pui__xtsQN-')
                    if content_elem:
                        content_preview = (await content_elem.inner_text())[:50]
                    
                    # 이미지 존재 여부
                    has_image = await container.query_selector('div.Review_img_slide_wrap__RaUKa')
                    
                    page_reviews.append({
                        'idx': idx,
                        'author': author_text,
                        'date': date_text,
                        'content': content_preview,
                        'has_image': has_image is not None
                    })
                    
                    self.logger.info(f"리뷰 {idx}: 작성자[{author_text}], 날짜[{date_text}], 이미지[{has_image is not None}], 내용[{content_preview}...]")
                    
                    # 작성자 매칭
                    if author_text.strip() != review_info.get('review_name', '').strip():
                        self.logger.debug(f"  → 작성자 불일치: '{author_text}' != '{review_info.get('review_name')}'")
                        continue
                    
                    self.logger.info(f"  → 작성자 일치! 날짜 확인 중...")
                    
                    # 날짜 매칭
                    if date_text:
                        review_date = review_info.get('review_date')
                        if self._match_date(date_text, review_date):
                            self.logger.info(f"  → 날짜도 일치! 리뷰 찾음: {author_text} - {date_text}")
                            
                            # 리뷰를 화면 중앙으로 스크롤
                            await container.scroll_into_view_if_needed()
                            await asyncio.sleep(1)
                            
                            return container
                        else:
                            self.logger.debug(f"  → 날짜 불일치: '{date_text}' != '{review_date}'")
                    
                    # 날짜가 없거나 매칭되지 않으면 리뷰 내용으로도 확인
                    if content_elem:
                        content_text = await content_elem.inner_text()
                        review_content = review_info.get('review_content', '')
                        
                        # 리뷰 내용의 처음 30자가 일치하면 같은 리뷰로 간주
                        if review_content and (
                            content_text.strip()[:30] == review_content.strip()[:30] or
                            review_content.strip()[:30] in content_text.strip()
                        ):
                            self.logger.info(f"  → 내용 매칭으로 리뷰 찾음: {author_text}")
                            
                            # 리뷰를 화면 중앙으로 스크롤
                            await container.scroll_into_view_if_needed()
                            await asyncio.sleep(1)
                            
                            return container
                        else:
                            self.logger.debug(f"  → 내용도 불일치")
                            
                except Exception as e:
                    self.logger.error(f"리뷰 {idx} 확인 중 오류: {str(e)}")
                    continue
            
            # 리뷰를 찾지 못한 경우
            self.logger.error(f"=== 리뷰를 찾을 수 없음 ===")
            self.logger.error(f"현재 페이지의 모든 리뷰:")
            for review in page_reviews:
                self.logger.error(f"  - {review}")
            
            # 디버깅용 스크린샷
            screenshot_dir = os.path.join("logs", "screenshots", "naver", "reply_errors")
            os.makedirs(screenshot_dir, exist_ok=True)
            await page.screenshot(
                path=os.path.join(screenshot_dir, f"review_not_found_{review_info.get('review_name')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"),
                full_page=True
            )
            
            return None
            
        except Exception as e:
            self.logger.error(f"리뷰 요소 찾기 중 오류: {str(e)}")
            return None
    
    def _match_date(self, naver_date: str, db_date: str) -> bool:
        """날짜 매칭 헬퍼"""
        try:
            # 네이버 날짜 형식: "2025. 6. 30(월)"
            # DB 날짜 형식: "2025-06-30"
            if not naver_date or not db_date:
                return False
            
            # 네이버 날짜에서 숫자만 추출
            naver_parts = re.findall(r'\d+', naver_date)
            if len(naver_parts) >= 3:
                year = naver_parts[0]
                month = naver_parts[1].zfill(2)
                day = naver_parts[2].zfill(2)
                naver_formatted = f"{year}-{month}-{day}"
                
                # DB 날짜와 비교
                db_formatted = str(db_date)[:10]  # YYYY-MM-DD 부분만 추출
                
                self.logger.debug(f"날짜 매칭: {naver_formatted} == {db_formatted}")
                return naver_formatted == db_formatted
            
            return False
            
        except Exception as e:
            self.logger.error(f"날짜 매칭 중 오류: {str(e)}")
            return False
    
    async def post_reply(self, page: Page, review_info: Dict[str, Any], reply_text: str) -> bool:
        """답글 작성"""
        try:
            self.logger.info(f"=== 답글 작성 시작 ===")
            self.logger.info(f"답글 내용: {reply_text[:100]}...")
            
            # 리뷰 요소 찾기
            review_element = await self.find_review_element(page, review_info)
            if not review_element:
                self.logger.error(f"리뷰를 찾을 수 없음: {review_info.get('review_name')}")
                
                # 스크린샷 저장
                screenshot_dir = os.path.join("logs", "screenshots", "naver", "reply_errors")
                os.makedirs(screenshot_dir, exist_ok=True)
                await page.screenshot(
                    path=os.path.join(screenshot_dir, f"no_review_found_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"),
                    full_page=True
                )
                return False
            
            # 답글쓰기 버튼 클릭
            self.logger.info("답글쓰기 버튼 찾는 중...")
            reply_btn = await review_element.query_selector('button[data-area-code="rv.replywrite"]')
            if not reply_btn:
                self.logger.error("답글쓰기 버튼을 찾을 수 없음")
                return False
            
            self.logger.info("답글쓰기 버튼 클릭")
            await reply_btn.click()
            await asyncio.sleep(2)
            
            # 텍스트박스에 답글 입력
            self.logger.info("답글 입력창 찾는 중...")
            textarea = await page.wait_for_selector('#replyWrite', timeout=5000)
            if not textarea:
                self.logger.error("답글 입력창을 찾을 수 없음")
                return False
            
            self.logger.info("답글 텍스트 입력")
            await textarea.fill(reply_text)
            await asyncio.sleep(1)
            
            # 입력된 텍스트 확인
            input_value = await textarea.input_value()
            self.logger.info(f"입력된 텍스트 확인: {input_value[:50]}...")
            
            # 등록 버튼 클릭
            self.logger.info("등록 버튼 찾는 중...")
            submit_btn = await page.query_selector('button[data-area-code="rv.replydone"]')
            if not submit_btn:
                self.logger.error("등록 버튼을 찾을 수 없음")
                return False
            
            # 등록 버튼이 활성화되어 있는지 확인
            is_disabled = await submit_btn.get_attribute('disabled')
            if is_disabled:
                self.logger.error("등록 버튼이 비활성화 상태")
                return False
            
            self.logger.info("등록 버튼 클릭")
            await submit_btn.click()
            
            # 클릭 직후 스크린샷
            screenshot_dir = os.path.join("logs", "screenshots", "naver", "reply_posting")
            os.makedirs(screenshot_dir, exist_ok=True)
            await page.screenshot(
                path=os.path.join(screenshot_dir, f"after_submit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            )
            
            # 등록 완료 대기 및 확인 (최대 15초)
            self.logger.info("답글 등록 확인 중...")
            success = False
            
            for i in range(15):
                await asyncio.sleep(1)
                self.logger.debug(f"등록 확인 시도 {i+1}/15")
                
                # 1. 입력창이 사라졌는지 확인
                try:
                    textarea_still_exists = await page.query_selector('#replyWrite')
                    if not textarea_still_exists:
                        self.logger.info("답글 입력창이 사라짐 - 등록 처리됨")
                        await asyncio.sleep(2)  # 답글이 렌더링될 시간 대기
                        success = True
                        break
                except:
                    pass
                
                # 2. 답글 영역이 나타났는지 확인
                try:
                    reply_section = await review_element.query_selector('div.pui__GbW8H7.pui__BDGQvd')
                    if reply_section:
                        self.logger.info("답글 영역 발견")
                        
                        # 수정/삭제 버튼 확인
                        edit_btn = await reply_section.query_selector('a[data-pui-click-code="rv.replyedit"]')
                        delete_btn = await reply_section.query_selector('a[data-pui-click-code="rv.replydelete"]')
                        if edit_btn and delete_btn:
                            self.logger.info("수정/삭제 버튼 확인됨 - 답글 등록 성공")
                            success = True
                            break
                except Exception as e:
                    self.logger.debug(f"답글 영역 확인 중 오류: {str(e)}")
                
                # 3. 에러 메시지 확인
                try:
                    error_elements = await page.query_selector_all('.Toast_toast__JmAFI')
                    for error_elem in error_elements:
                        error_text = await error_elem.inner_text()
                        self.logger.error(f"에러 메시지 발견: {error_text}")
                        if "오류" in error_text or "실패" in error_text:
                            return False
                except:
                    pass
            
            if success:
                self.logger.info(f"=== 답글 등록 성공: {review_info.get('review_name')} ===")
            
            else:
                self.logger.error(f"=== 답글 등록 확인 실패: {review_info.get('review_name')} ===")
                
                # 실패 스크린샷
                await page.screenshot(
                    path=os.path.join(screenshot_dir, f"failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"),
                    full_page=True
                )
                return False
            
        except Exception as e:
            self.logger.error(f"답글 작성 중 오류: {str(e)}")
            
            # 에러 스크린샷
            try:
                screenshot_dir = os.path.join("logs", "screenshots", "naver", "reply_errors")
                os.makedirs(screenshot_dir, exist_ok=True)
                await page.screenshot(
                    path=os.path.join(screenshot_dir, f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"),
                    full_page=True
                )
            except:
                pass
                
            return False
    
    async def process_single_reply(self, page: Page, review_data: Dict[str, Any]) -> bool:
        """단일 답글 처리"""
        try:
            self.logger.info(f"=== 단일 답글 처리 시작 ===")
            
            review_info = {
                'review_name': review_data.get('review_name'),
                'review_date': review_data.get('review_date'),
                'review_content': review_data.get('review_content')
            }
            
            self.logger.info(f"처리할 리뷰: {review_info}")
            
            reply_text = review_data.get('final_response', review_data.get('ai_response'))
            
            if not reply_text:
                self.logger.error("답글 내용이 없습니다")
                return False
            
            self.logger.info(f"답글 내용: {reply_text[:100]}...")
            
            return await self.post_reply(page, review_info, reply_text)
            
        except Exception as e:
            self.logger.error(f"단일 답글 처리 중 오류: {str(e)}")
            return False