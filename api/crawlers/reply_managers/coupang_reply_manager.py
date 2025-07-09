import asyncio
from typing import Dict, Optional, List, Tuple
from playwright.async_api import Page, Browser, async_playwright
import logging
from datetime import datetime
import os
from pathlib import Path
import re

logger = logging.getLogger(__name__)

class CoupangReplyManager:
    """쿠팡이츠 답글 관리자"""
    
    def __init__(self, store_info: Dict[str, str]):
        self.store_info = store_info
        self.platform_id = store_info.get('platform_id')
        self.platform_pw = store_info.get('platform_pw')
        self.store_code = store_info.get('store_code')
        self.platform_store_id = store_info.get('platform_code')  # 쿠팡 매장 ID (예: 708561)
        self.screenshots_dir = Path("logs/screenshots/coupang/replies")
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        
    async def login(self, page: Page) -> bool:
        """쿠팡이츠 사장님 사이트 로그인"""
        try:
            logger.info(f"쿠팡이츠 로그인 시작: {self.platform_id}")
            
            # 로그인 페이지로 이동
            await page.goto("https://store.coupangeats.com/merchant/login", wait_until="networkidle")
            await page.wait_for_timeout(2000)

            # 아이디 입력
            await page.wait_for_selector('#loginId', state='visible', timeout=10000)
            await page.fill('#loginId', self.platform_id)
            await page.wait_for_timeout(500)
            
            # 비밀번호 입력
            await page.fill('#password', self.platform_pw)
            await page.wait_for_timeout(500)
            
            # 로그인 버튼 클릭
            await page.click('button[type="submit"].merchant-submit-btn')
            
            # 로그인 완료 대기
            await page.wait_for_timeout(5000)
            
            # 로그인 성공 확인 (리뷰 페이지로 리다이렉트 되거나 대시보드 표시)
            current_url = page.url
            if "login" not in current_url:
                logger.info("쿠팡이츠 로그인 성공")
                return True
            else:
                logger.error("쿠팡이츠 로그인 실패")
                await page.screenshot(path=f"{self.screenshots_dir}/login_failed_{timestamp}.png")
                return False
                
        except Exception as e:
            logger.error(f"로그인 중 오류: {str(e)}")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            await page.screenshot(path=f"{self.screenshots_dir}/login_error_{timestamp}.png")
            return False
        
    async def close_popup(self, page: Page) -> bool:
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
                    close_button = await page.query_selector(selector)
                    if close_button:
                        await close_button.click()
                        logger.info(f"팝업을 닫았습니다 (셀렉터: {selector})")
                        await page.wait_for_timeout(1000)
                        return True
                except:
                    continue
            
            logger.debug("닫을 팝업이 없거나 이미 닫혀있습니다")
            return False
            
        except Exception as e:
            logger.debug(f"팝업 처리 중 예외 발생: {str(e)}")
            return False
    
    async def set_date_range(self, page: Page) -> bool:
        """날짜 범위를 1개월로 설정"""
        try:
            logger.info("날짜 범위 설정 시작")
            
            # 날짜 선택 드롭다운 클릭 - SVG를 포함한 div 클릭
            date_dropdown = await page.query_selector('div.css-1rkgd7l:has(svg)')
            if not date_dropdown:
                # 대체 셀렉터 시도
                date_dropdown = await page.query_selector('svg[width="24"][height="24"].css-k0likx')
                if date_dropdown:
                    await date_dropdown.click()
                else:
                    logger.error("날짜 드롭다운을 찾을 수 없습니다")
                    return False
            else:
                await date_dropdown.click()
                
            await page.wait_for_timeout(1000)
            
            # 1개월 옵션 클릭 - JavaScript로 직접 라벨 클릭
            await page.evaluate('''() => {
                // 모든 라벨을 찾아서 '1개월' 텍스트가 있는 것을 찾기
                const labels = document.querySelectorAll('label');
                for (const label of labels) {
                    if (label.textContent && label.textContent.trim() === '1개월') {
                        // 라벨 클릭
                        label.click();
                        // SVG 요소도 클릭
                        const svg = label.querySelector('svg');
                        if (svg) {
                            svg.click();
                        }
                        console.log('1개월 옵션 클릭 완료');
                        return true;
                    }
                }
                return false;
            }''')
            
            logger.info("1개월 옵션 선택 완료")
            await page.wait_for_timeout(1000)
            
            # 조회 버튼 클릭 - 더 정확한 셀렉터 사용
            search_button = await page.query_selector('button.button--primaryOutlined:has-text("조회")')
            if not search_button:
                # 대체 셀렉터
                search_button = await page.query_selector('button:has(span:has-text("조회"))')
            
            if search_button:
                await search_button.click()
                logger.info("조회 버튼 클릭 완료")
                await page.wait_for_timeout(3000)  # 데이터 로딩 대기
            else:
                logger.warning("조회 버튼을 찾을 수 없습니다")
                
            return True
            
        except Exception as e:
            logger.error(f"날짜 범위 설정 실패: {str(e)}")
            return False

    async def navigate_to_reviews(self, page: Page) -> bool:
        """리뷰 관리 페이지로 이동"""
        try:
            logger.info("리뷰 관리 페이지로 이동")
            
            # 리뷰 페이지로 이동
            await page.goto("https://store.coupangeats.com/merchant/management/reviews", wait_until="networkidle")
            await page.wait_for_timeout(3000)
            
            # 팝업 닫기 추가
            await self.close_popup(page)
            
            # 매장 선택 (드롭다운에서)
            store_selector = f'li:has-text("{self.platform_store_id}")'
            if await page.locator(store_selector).count() > 0:
                await page.click(store_selector)
                await page.wait_for_timeout(2000)
                logger.info(f"매장 선택 완료: {self.platform_store_id}")
            
            # 날짜 설정 (1개월) - 수정된 로직
            await self.set_date_range(page)
            
            # 미답변 탭 클릭 - 더 확실한 방법
            try:
                # 현재 URL과 페이지 정보 확인
                current_url = page.url
                logger.info(f"🌐 현재 URL: {current_url}")
                
                # 현재 날짜 범위 확인
                try:
                    date_display = await page.query_selector('div.css-1rkgd7l')
                    if date_display:
                        date_text = await date_display.text_content()
                        logger.info(f"📅 현재 날짜 범위: {date_text}")
                    else:
                        logger.warning("날짜 범위 정보를 찾을 수 없음")
                except Exception as e:
                    logger.warning(f"날짜 범위 확인 실패: {str(e)}")
                
                # 모든 탭 확인
                all_tabs = await page.query_selector_all('[role="tab"]')
                logger.info(f"🔍 페이지의 모든 탭:")
                for i, tab in enumerate(all_tabs):
                    try:
                        tab_text = await tab.text_content()
                        is_selected = await tab.get_attribute('aria-selected')
                        logger.info(f"   탭 {i+1}: '{tab_text}' (선택됨: {is_selected})")
                    except:
                        pass
                
                # 미답변 탭 찾기 - 실제 HTML 구조에 맞게 수정
                tab_clicked = False
                
                # 방법 1: 정확한 구조로 미답변 탭 찾기
                try:
                    # div.css-jzkpn6 안의 span:has-text("미답변") 찾기
                    unanswered_tab = await page.query_selector('div.css-jzkpn6:has(span:text("미답변"))')
                    if unanswered_tab:
                        # 클릭 전 상태 확인
                        tab_classes = await unanswered_tab.get_attribute('class')
                        logger.info(f"클릭 전 미답변 탭 클래스: {tab_classes}")
                        
                        await unanswered_tab.click()
                        await page.wait_for_timeout(3000)
                        
                        # 클릭 후 상태 확인
                        tab_classes_after = await unanswered_tab.get_attribute('class')
                        logger.info(f"클릭 후 미답변 탭 클래스: {tab_classes_after}")
                        
                        # 파란색 활성 상태인지 확인 (클래스 변화 확인)
                        if tab_classes != tab_classes_after:
                            logger.info("✅ 미답변 탭 클릭 성공 - 상태 변화 감지")
                            tab_clicked = True
                        else:
                            logger.warning("⚠️ 미답변 탭 클릭했지만 상태 변화 없음")
                except Exception as e:
                    logger.debug(f"방법 1 실패: {str(e)}")
                
                # 방법 2: span을 직접 클릭
                if not tab_clicked:
                    try:
                        span_element = await page.query_selector('span:text("미답변")')
                        if span_element:
                            await span_element.click()
                            await page.wait_for_timeout(3000)
                            logger.info("미답변 span 직접 클릭 시도")
                            tab_clicked = True
                    except Exception as e:
                        logger.debug(f"방법 2 실패: {str(e)}")
                
                # 방법 3: JavaScript로 강제 클릭
                if not tab_clicked:
                    try:
                        await page.evaluate("""
                            const tabs = document.querySelectorAll('div.css-jzkpn6');
                            for (let tab of tabs) {
                                if (tab.textContent.includes('미답변')) {
                                    tab.click();
                                    console.log('JavaScript로 미답변 탭 클릭');
                                    break;
                                }
                            }
                        """)
                        await page.wait_for_timeout(3000)
                        logger.info("JavaScript로 미답변 탭 클릭 시도")
                        tab_clicked = True
                    except Exception as e:
                        logger.debug(f"방법 3 실패: {str(e)}")
                
                if not tab_clicked:
                    logger.warning("⚠️ 미답변 탭을 찾을 수 없음 - 전체 탭에서 검색")
                
                await page.wait_for_timeout(5000)  # 탭 전환 대기시간 증가
                
                # 현재 활성 탭 다시 확인 및 미답변 개수 확인
                try:
                    # 미답변 탭의 개수 확인
                    unanswered_tab = await page.query_selector('div.css-jzkpn6:has(span:text("미답변"))')
                    if unanswered_tab:
                        count_element = await unanswered_tab.query_selector('b.css-1k8kvzj')
                        if count_element:
                            count_text = await count_element.text_content()
                            logger.info(f"📊 미답변 리뷰 개수: {count_text}개")
                            
                            if count_text.strip() == "0":
                                logger.warning("🚨 미답변 리뷰가 0개입니다!")
                                logger.warning("   → 모든 리뷰에 이미 답글이 달려있거나, 다른 탭에 있을 수 있습니다.")
                                
                                # 전체 탭으로 전환해서 확인
                                try:
                                    all_tab = await page.query_selector('div.css-jzkpn6:has(span:text("전체"))')
                                    if all_tab:
                                        logger.info("전체 탭으로 전환하여 확인합니다...")
                                        await all_tab.click()
                                        await page.wait_for_timeout(3000)
                                        
                                        # 전체 리뷰 개수 확인
                                        all_count_element = await all_tab.query_selector('b.css-1k8kvzj')
                                        if all_count_element:
                                            all_count = await all_count_element.text_content()
                                            logger.info(f"📊 전체 리뷰 개수: {all_count}개")
                                except Exception as e:
                                    logger.warning(f"전체 탭 확인 실패: {str(e)}")
                            else:
                                logger.info(f"✅ 미답변 리뷰 {count_text}개 확인됨")
                    
                    # 활성 탭 확인
                    active_tab = await page.query_selector('[aria-selected="true"]')
                    if active_tab:
                        tab_text = await active_tab.text_content()
                        logger.info(f"✅ 탭 전환 후 현재 활성 탭: {tab_text}")
                    else:
                        # CSS 클래스로 활성 탭 찾기
                        active_tabs = await page.query_selector_all('div.css-jzkpn6')
                        for tab in active_tabs:
                            try:
                                tab_classes = await tab.get_attribute('class')
                                tab_text = await tab.text_content()
                                if 'active' in tab_classes or '활성' in tab_classes:
                                    logger.info(f"✅ 활성 탭 발견: {tab_text}")
                                    break
                            except:
                                continue
                        else:
                            logger.warning("활성 탭을 찾을 수 없음")
                except Exception as e:
                    logger.warning(f"탭 상태 확인 실패: {str(e)}")
                
                # 테이블 로딩 대기
                try:
                    await page.wait_for_selector('table', timeout=10000)
                    logger.info("테이블 로딩 완료")
                except Exception as e:
                    logger.warning(f"테이블 로딩 실패: {str(e)} - 계속 진행합니다.")
                
            except Exception as tab_e:
                logger.error(f"탭 전환 중 오류: {str(tab_e)}")
            
            return True
            
        except Exception as e:
            logger.error(f"리뷰 페이지 이동 중 오류: {str(e)}")
            return False
    
    def _extract_order_number_from_review_id(self, review_id: str) -> str:
        """review_id에서 주문번호 추출"""
        try:
            # review_id 형식: "coupang_708561_2LJMLY_20250709"
            if not review_id:
                return ""
            
            parts = review_id.split('_')
            if len(parts) >= 3:
                return parts[2]  # 주문번호 부분
            return ""
        except Exception as e:
            logger.error(f"주문번호 추출 실패: {e}")
            return ""
            
    async def find_and_reply_to_review(self, page: Page, review_data: Dict) -> bool:
        """특정 리뷰를 찾아서 답글 등록 (페이지네이션 포함)"""
        try:
            review_content = review_data.get('review_content', '')
            reply_content = review_data.get('reply_content', '')
            review_id = review_data.get('review_id', '')
            # 필드명 표준화: ordered_menu가 올바른 필드명
            order_menu = review_data.get('ordered_menu', '') or review_data.get('order_menu', '')
            # 추가 필드들도 미리 추출
            review_name = review_data.get('review_name', '')
            rating = review_data.get('rating')
            
            logger.info(f"🔍 주문메뉴 필드 확인: ordered_menu='{review_data.get('ordered_menu')}', order_menu='{review_data.get('order_menu')}'")
            logger.info(f"최종 사용할 메뉴: '{order_menu}'")
            logger.info(f"리뷰 ID: '{review_id}'")
            
            # review_id에서 주문번호 추출
            target_order_number = self._extract_order_number_from_review_id(review_id)
            logger.info(f"추출된 주문번호: '{target_order_number}'")
            
            logger.info(f"리뷰 찾기 시작: {review_content[:30]}...")
            
            # 페이지네이션 처리
            current_page = 1
            max_pages = 10  # 최대 10페이지까지 검색
            
            while current_page <= max_pages:
                logger.info(f"페이지 {current_page} 검색 중...")
                
                # 현재 페이지에서 리뷰 검색 (review_id 전달)
                review_found = await self._search_review_in_current_page(
                    page, review_id, order_menu, reply_content, review_name, rating
                )
                
                if review_found:
                    return True
                
                # 다음 페이지로 이동
                has_next = await self._go_to_next_page(page)
                if not has_next:
                    logger.info("더 이상 페이지가 없습니다")
                    break
                    
                current_page += 1
                await page.wait_for_timeout(2000)  # 페이지 로딩 대기
            
            logger.warning(f"모든 페이지를 검색했지만 매칭되는 리뷰를 찾을 수 없음")
            return False
            
        except Exception as e:
            logger.error(f"답글 등록 중 오류: {str(e)}")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            await page.screenshot(path=f"{self.screenshots_dir}/reply_error_{timestamp}.png")
            return False

    async def _search_review_in_current_page(self, page: Page, review_id: str, 
                                            order_menu: str, reply_content: str, 
                                            review_name: str = '', rating: int = None) -> bool:
        """현재 페이지에서 리뷰 검색 - review_name + review_id(주문번호) 매칭"""
        try:
            logger.info(f"📊 찾고자 하는 리뷰 정보:")
            logger.info(f"   - 리뷰어: '{review_name}'")
            logger.info(f"   - 별점: {rating}")
            logger.info(f"   - 리뷰 ID: '{review_id}'")
            logger.info(f"   - 메뉴: '{order_menu}'")
            
            # 모든 리뷰 행 가져오기
            review_rows = await page.query_selector_all('tr')
            
            # 헤더 행 제외
            actual_review_rows = []
            for row in review_rows:
                th_elements = await row.query_selector_all('th')
                if len(th_elements) == 0:
                    actual_review_rows.append(row)
            
            logger.info(f"🔍 총 {len(actual_review_rows)}개 리뷰 행 검색")
            
            # 각 리뷰 행에서 review_name + 주문번호 매칭
            for i, row in enumerate(actual_review_rows):
                try:
                    # 1. 리뷰어 이름 추출
                    page_reviewer = ""
                    try:
                        reviewer_div = await row.query_selector('div.css-hdvjju.eqn7l9b7')
                        if reviewer_div:
                            b_elements = await reviewer_div.query_selector_all('b')
                            if b_elements and len(b_elements) > 0:
                                page_reviewer = await b_elements[0].text_content()
                                page_reviewer = page_reviewer.strip() if page_reviewer else ""
                    except:
                        pass
                    
                    # 2. 주문번호 추출
                    page_order_number = ""
                    try:
                        li_elements = await row.query_selector_all('li')
                        for li in li_elements:
                            strong = await li.query_selector('strong')
                            if strong:
                                strong_text = await strong.text_content()
                                if strong_text and '주문번호' in strong_text:
                                    p_element = await li.query_selector('p')
                                    if p_element:
                                        order_info = await p_element.text_content()
                                        order_info = order_info.strip() if order_info else ""
                                        # "2LJMLYㆍ2025-07-09(주문일)" 형태에서 주문번호 추출
                                        if 'ㆍ' in order_info:
                                            page_order_number = order_info.split('ㆍ')[0].strip()
                                        break
                    except:
                        pass
                    
                    logger.debug(f"리뷰 {i+1}: 이름='{page_reviewer}', 주문번호='{page_order_number}'")
                    
                    # 매칭 확인: review_name + 주문번호
                    if review_name and page_reviewer and review_name == page_reviewer:
                        # 주문번호 매칭 확인
                        target_order_number = self._extract_order_number_from_review_id(review_id)
                        
                        if target_order_number and page_order_number and target_order_number == page_order_number:
                            logger.info(f"🎯 완벽한 매칭 발견! 리뷰어: '{review_name}', 주문번호: '{page_order_number}'")
                            
                            # 답글 버튼 찾기
                            reply_button = await row.query_selector('button.css-1ss7t0c.eqn7l9b2')
                            if not reply_button:
                                reply_button = await row.query_selector('button:has-text("사장님 댓글 등록하기")')
                            
                            if reply_button:
                                logger.info("✅ 답글 버튼 발견 - 답글 등록 시작")
                                
                                # 답글 등록 프로세스
                                await reply_button.click()
                                await page.wait_for_timeout(2000)
                                
                                # 답글 입력
                                reply_textarea = await page.query_selector('textarea')
                                if reply_textarea:
                                    await reply_textarea.fill(reply_content)
                                    await page.wait_for_timeout(1000)
                                    
                                    # 등록 버튼 클릭 - 실제 HTML 구조에 맞게 수정
                                    submit_button = await page.query_selector('button.button.button-size--small.button--primaryContained:has(span.button__inner:text("등록"))')
                                    if not submit_button:
                                        # 대체 셀렉터들 시도
                                        submit_selectors = [
                                            'button.button--primaryContained:has(span:text("등록"))',
                                            'button[class*="button--primaryContained"]:has(span:text("등록"))',
                                            'button:has(span.button__inner:text("등록"))',
                                            'button.button:has(span:text("등록"))'
                                        ]
                                        for selector in submit_selectors:
                                            submit_button = await page.query_selector(selector)
                                            if submit_button:
                                                logger.info(f"등록 버튼 발견 (셀렉터: {selector})")
                                                break
                                    
                                    if submit_button:
                                        await submit_button.click()
                                        await page.wait_for_timeout(3000)
                                        logger.info("✅ 답글 등록 완료!")
                                        return True
                                    else:
                                        logger.error("등록 버튼을 찾을 수 없음")
                                        # 스크린샷 저장하여 디버깅
                                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                        await page.screenshot(path=f"{self.screenshots_dir}/submit_button_missing_{timestamp}.png")
                                        return False
                                else:
                                    logger.error("답글 입력창을 찾을 수 없음")
                                    return False
                            else:
                                logger.warning("📝 답글 버튼이 없음 - 이미 답글이 있는 리뷰")
                                return "ALREADY_REPLIED"
                    
                except Exception as e:
                    logger.error(f"리뷰 {i+1} 처리 중 오류: {str(e)}")
                    continue
            
            logger.warning("매칭되는 리뷰를 찾을 수 없음")
            return False
            
        except Exception as e:
            logger.error(f"리뷰 검색 중 오류: {str(e)}")
            return False
    def _normalize_text(self, text: str) -> str:
        """텍스트 정규화 (공백, 특수문자 제거)"""
        if not text:
            return ""
        # 공백, 줄바꿈, 탭 등 제거
        return re.sub(r'\s+', '', text.strip())

    async def _go_to_next_page(self, page: Page) -> bool:
        """다음 페이지로 이동"""
        try:
            # 페이지네이션 영역에서 다음 버튼 찾기
            next_button = await page.evaluate('''() => {
                const containers = document.querySelectorAll('div[class*="css-"]');
                for (const container of containers) {
                    const buttons = container.querySelectorAll('button');
                    if (buttons.length >= 3) {  // 페이지네이션 버튼들
                        const lastButton = buttons[buttons.length - 1];
                        if (lastButton && lastButton.querySelector('svg') && !lastButton.disabled) {
                            lastButton.click();
                            return true;
                        }
                    }
                }
                return false;
            }''')
            
            if next_button:
                logger.info("다음 페이지로 이동")
                return True
            else:
                logger.info("다음 페이지 버튼을 찾을 수 없거나 비활성화됨")
                return False
                
        except Exception as e:
            logger.error(f"페이지 이동 중 오류: {str(e)}")
            return False
            
    async def post_reply(self, review_data: Dict) -> Tuple[bool, str]:
        """답글 등록 메인 프로세스"""
        async with async_playwright() as p:
            browser = None
            try:
                # 브라우저 실행
                browser = await p.chromium.launch(
                    headless=False,  # 디버깅을 위해 False
                    args=['--disable-blink-features=AutomationControlled']
                )
                
                context = await browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                
                page = await context.new_page()
                
                # 1. 로그인
                if not await self.login(page):
                    return False, "로그인 실패"
                    
                # 2. 리뷰 페이지로 이동
                if not await self.navigate_to_reviews(page):
                    return False, "리뷰 페이지 이동 실패"
                    
                # 3. 리뷰 찾아서 답글 등록
                if await self.find_and_reply_to_review(page, review_data):
                    return True, "답글 등록 성공"
                else:
                    return False, "리뷰 매칭 실패 또는 답글 등록 실패"
                    
            except Exception as e:
                logger.error(f"답글 등록 프로세스 오류: {str(e)}")
                return False, f"오류 발생: {str(e)}"
                
            finally:
                if browser:
                    await browser.close()