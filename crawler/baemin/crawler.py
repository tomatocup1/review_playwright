"""
배민(배달의민족) 크롤러 구현
Selenium 코드를 Playwright로 마이그레이션
"""
import asyncio
import re
import hashlib
import unicodedata
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import json

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from ..base import BaseCrawler

# 로깅 설정
logger = logging.getLogger(__name__)


class BaeminCrawler(BaseCrawler):
    """배민 크롤러 구현"""
    
    def __init__(self, store_config: Dict):
        super().__init__(store_config)
        self.platform_name = "배민"
        self.base_url = "https://self.baemin.com"
        self.login_url = "https://biz-member.baemin.com/login?returnUrl=https%3A%2F%2Fceo.baemin.com%2F"
        
    async def login(self) -> bool:
        """배민 로그인 처리 (2FA 대응 포함)"""
        max_attempts = 3
        
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"로그인 시도 {attempt}/{max_attempts}")
                await self.page.goto(self.login_url, wait_until='networkidle')
                await asyncio.sleep(3)
                
                # 안티봇 체크
                if await self.check_antibot():
                    logger.warning("안티봇 감지됨")
                    continue
                
                # 로그인 입력
                await self.page.fill('input[name="id"]', self.store_config['platform_id'])
                await self.page.fill('input[name="password"]', self.store_config['platform_pw'])
                
                # 로그인 버튼 클릭
                await self.page.press('input[name="password"]', 'Enter')
                await asyncio.sleep(5)
                
                # 로그인 후 안티봇 체크
                if await self.check_antibot():
                    logger.warning("로그인 후 안티봇 감지됨")
                    continue
                
                # 로그인 에러 체크
                error_alerts = await self.page.query_selector_all('p[role="alert"]')
                if error_alerts:
                    for alert in error_alerts:
                        error_text = await alert.text_content()
                        if error_text:
                            logger.error(f"로그인 에러: {error_text}")
                    
                    if attempt == max_attempts:
                        await self.save_screenshot("login_fail")
                        return False
                    continue
                
                # 팝업 처리
                await self._close_homepage_popups()
                
                # 세션 저장
                await self.save_session()
                
                logger.info("로그인 성공")
                return True
                
            except Exception as e:
                logger.error(f"로그인 중 오류: {str(e)}")
                if attempt == max_attempts:
                    await self.save_screenshot("login_error")
                    return False
                await asyncio.sleep(2)
        
        return False
    
    async def _close_homepage_popups(self):
        """홈페이지 팝업 닫기"""
        popup_selectors = [
            '#btn-close-nday',
            'button[aria-label="닫기"]',
            'div.button-overlay.css-fowwyy'
        ]
        
        for selector in popup_selectors:
            try:
                button = await self.page.wait_for_selector(selector, timeout=2000)
                if button:
                    await button.click()
                    logger.info(f"홈페이지 팝업 닫음: {selector}")
                    await asyncio.sleep(0.5)
            except:
                continue
    
    async def _close_review_page_popups(self):
        """리뷰 페이지 팝업 처리"""
        # 7일간 보지 않기 팝업
        try:
            btn_7day = await self.page.wait_for_selector(
                'button:has-text("7일간 보지 않기")', 
                timeout=2000
            )
            if btn_7day:
                await btn_7day.click()
                logger.info("7일간 보지 않기 클릭")
                await asyncio.sleep(1)
                
                # 1일간 보지 않기
                try:
                    btn_1day = await self.page.wait_for_selector(
                        'button:has-text("1일간 보지 않기")',
                        timeout=2000
                    )
                    if btn_1day:
                        await btn_1day.click()
                        logger.info("1일간 보지 않기 클릭")
                except:
                    pass
        except:
            pass
        
        # 오늘 하루 보지 않기
        try:
            today_btn = await self.page.wait_for_selector(
                'span:has-text("오늘 하루 보지 않기")',
                timeout=2000
            )
            if today_btn:
                await today_btn.click()
                logger.info("오늘 하루 보지 않기 클릭")
        except:
            pass
    
    async def navigate_to_reviews(self, platform_code: str) -> bool:
        """리뷰 페이지로 이동"""
        try:
            url = f"{self.base_url}/shops/{platform_code}/reviews"
            await self.page.goto(url, wait_until='networkidle')
            await asyncio.sleep(3)
            
            # 팝업 처리
            await self._close_review_page_popups()
            
            # 미답변 탭 클릭
            return await self._click_uncommented_tab()
            
        except Exception as e:
            logger.error(f"리뷰 페이지 이동 실패: {str(e)}")
            return False
    
    async def _click_uncommented_tab(self) -> bool:
        """미답변 탭 클릭"""
        max_attempts = 2
        
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"미답변 탭 클릭 시도 {attempt}/{max_attempts}")
                
                # 미답변 탭 선택자들
                tab_selectors = [
                    'button#no-comment[role="tab"]',
                    'button[role="tab"]:has-text("미답변")',
                    'button:has-text("미답변")'
                ]
                
                for selector in tab_selectors:
                    try:
                        tab = await self.page.wait_for_selector(selector, timeout=3000)
                        if tab:
                            # 이미 선택된 상태인지 확인
                            is_selected = await tab.get_attribute('aria-selected')
                            if is_selected == 'true':
                                logger.info("미답변 탭이 이미 선택됨")
                                return True
                            
                            # 클릭
                            await tab.click()
                            await asyncio.sleep(2)
                            
                            # 선택 확인
                            is_selected = await tab.get_attribute('aria-selected')
                            if is_selected == 'true':
                                logger.info("미답변 탭 선택 성공")
                                return True
                            break
                    except:
                        continue
                
                if attempt < max_attempts:
                    await asyncio.sleep(2)
                    
            except Exception as e:
                logger.error(f"미답변 탭 클릭 실패: {str(e)}")
                
        return False
    
    async def get_reviews(self) -> List[Dict]:
        """미답변 리뷰 목록 가져오기"""
        reviews = []
        processed_hashes = set()
        
        try:
            # 스크롤하면서 리뷰 수집
            last_height = await self.page.evaluate('document.body.scrollHeight')
            no_new_content_count = 0
            
            while no_new_content_count < 3:
                # 현재 화면의 리뷰 카드 찾기
                review_cards = await self._find_review_cards()
                
                for card in review_cards:
                    try:
                        review_data = await self._parse_review_card(card)
                        if review_data and review_data['hash'] not in processed_hashes:
                            reviews.append(review_data)
                            processed_hashes.add(review_data['hash'])
                    except Exception as e:
                        logger.error(f"리뷰 파싱 오류: {str(e)}")
                        continue
                
                # 스크롤 다운
                await self.page.evaluate('window.scrollBy(0, window.innerHeight * 0.67)')
                await asyncio.sleep(1.5)
                
                # 새 컨텐츠 확인
                new_height = await self.page.evaluate('document.body.scrollHeight')
                if new_height > last_height:
                    last_height = new_height
                    no_new_content_count = 0
                else:
                    no_new_content_count += 1
            
            logger.info(f"총 {len(reviews)}개 리뷰 수집 완료")
            return reviews
            
        except Exception as e:
            logger.error(f"리뷰 수집 중 오류: {str(e)}")
            return reviews
    
    async def _find_review_cards(self) -> List:
        """리뷰 카드 요소 찾기"""
        selectors = [
            'div[class*="ReviewContent-module"]',
            'div.Container_c_qbca_1utdzds5.ReviewContent-module__Ksg4',
            'div[data-atelier-component="Container"]'
        ]
        
        review_cards = []
        for selector in selectors:
            try:
                cards = await self.page.query_selector_all(selector)
                if cards:
                    # 실제 리뷰인지 검증
                    for card in cards:
                        if await self._is_valid_review_card(card):
                            review_cards.append(card)
                    
                    if review_cards:
                        break
            except:
                continue
        
        return review_cards
    
    async def _is_valid_review_card(self, card) -> bool:
        """유효한 리뷰 카드인지 검증"""
        try:
            # 제외할 텍스트
            excluded_texts = ["평균 별점", "고객이 보는 리뷰 정렬", "사장님!"]
            card_text = await card.text_content()
            
            for text in excluded_texts:
                if text in card_text:
                    return False
            
            # 별점이나 댓글 버튼이 있는지 확인
            has_stars = await card.query_selector('path[fill="#FFC600"]') is not None
            has_comment_btn = await card.query_selector('button:has-text("사장님 댓글")') is not None
            
            return has_stars or has_comment_btn
            
        except:
            return False
    
    async def _parse_review_card(self, card) -> Optional[Dict]:
        """리뷰 카드에서 정보 추출"""
        try:
            # 작성자
            author = "알 수 없음"
            author_els = await card.query_selector_all('span[class*="Typography"]')
            for el in author_els:
                text = await el.text_content()
                if text and len(text) < 20 and text not in ["어제", "오늘", "그제"]:
                    author = text.strip()
                    break
            
            # 별점
            rating = 5
            star_paths = await card.query_selector_all('path[fill="#FFC600"]')
            if star_paths:
                rating = min(len(star_paths), 5)
            
            # 리뷰 내용
            review_text = ""
            content_els = await card.query_selector_all('span[class*="Typography_b_b8ew_1bisyd49"]')
            for el in content_els:
                text = await el.text_content()
                if text and len(text) > 10 and text != author:
                    review_text = text.strip()
                    break
            
            # 주문 메뉴
            order_menu = ""
            menu_els = await card.query_selector_all('span[class*="Badge"]')
            menu_items = []
            for el in menu_els:
                text = await el.text_content()
                if text and text not in ["좋아요", "보통이에요", "아쉬워요"]:
                    menu_items.append(text.strip())
            order_menu = ", ".join(menu_items)
            
            # 날짜 추출
            review_date = await self._extract_review_date(card)
            
            # 답글 버튼 확인
            reply_btn = await card.query_selector('button:has-text("사장님 댓글")')
            if not reply_btn:
                return None
            
            # 리뷰 해시 생성
            review_hash = self._generate_review_hash(
                self.store_config['store_code'],
                author,
                review_text
            )
            
            # data-index 속성 가져오기
            data_index = await card.get_attribute('data-index')
            if not data_index:
                parent = await card.evaluate_handle('el => el.parentElement')
                if parent:
                    data_index = await parent.get_attribute('data-index')
            
            return {
                'hash': review_hash,
                'author': author,
                'rating': rating,
                'review_text': review_text,
                'order_menu': order_menu,
                'review_date': review_date,
                'data_index': data_index,
                'element': card  # 나중에 답글 달 때 사용
            }
            
        except Exception as e:
            logger.error(f"리뷰 파싱 중 오류: {str(e)}")
            return None
    
    def _generate_review_hash(self, store_code: str, author: str, review_text: str) -> str:
        """리뷰 해시 생성"""
        base_str = f"{store_code}_{author}_{review_text}"
        return hashlib.md5(base_str.encode("utf-8")).hexdigest()
    
    async def _extract_review_date(self, card) -> str:
        """리뷰 날짜 추출"""
        try:
            # 상대적 날짜 텍스트 찾기
            date_patterns = ["오늘", "어제", "그제", "일 전", "주 전", "개월 전"]
            date_els = await card.query_selector_all('span')
            
            relative_date = None
            for el in date_els:
                text = await el.text_content()
                if text:
                    for pattern in date_patterns:
                        if pattern in text:
                            relative_date = text.strip()
                            break
                    if relative_date:
                        break
            
            # 상대적 날짜를 실제 날짜로 변환
            if relative_date:
                return self._convert_relative_date(relative_date)
            else:
                return datetime.now().date().isoformat()
                
        except Exception as e:
            logger.error(f"날짜 추출 오류: {str(e)}")
            return datetime.now().date().isoformat()
    
    def _convert_relative_date(self, relative_date: str) -> str:
        """상대적 날짜를 실제 날짜로 변환"""
        today = datetime.now().date()
        
        if relative_date == "오늘":
            return today.isoformat()
        elif relative_date == "어제":
            return (today - timedelta(days=1)).isoformat()
        elif relative_date == "그제" or relative_date == "2일 전":
            return (today - timedelta(days=2)).isoformat()
        elif "일 전" in relative_date:
            try:
                days = int(relative_date.split("일 전")[0].strip())
                return (today - timedelta(days=days)).isoformat()
            except:
                pass
        elif "주 전" in relative_date:
            try:
                weeks = int(relative_date.split("주 전")[0].strip())
                return (today - timedelta(days=weeks * 7)).isoformat()
            except:
                pass
        elif "개월 전" in relative_date or "달 전" in relative_date:
            try:
                if "개월 전" in relative_date:
                    months = int(relative_date.split("개월 전")[0].strip())
                else:
                    months = int(relative_date.split("달 전")[0].strip())
                # 대략적인 계산
                return (today - timedelta(days=months * 30)).isoformat()
            except:
                pass
        
        return today.isoformat()
    
    async def post_reply(self, review_data: Dict, reply_text: str) -> Tuple[bool, Optional[set]]:
        """답글 등록"""
        max_attempts = 3
        detected_prohibited_words = set()
        
        try:
            card_element = review_data['element']
            
            for attempt in range(1, max_attempts + 1):
                try:
                    logger.info(f"댓글 등록 시도 {attempt}/{max_attempts}")
                    
                    # 카드가 보이도록 스크롤
                    await card_element.scroll_into_view_if_needed()
                    await asyncio.sleep(1)
                    
                    # 댓글 버튼 클릭
                    comment_btn = await card_element.query_selector('button:has-text("사장님 댓글")')
                    if not comment_btn:
                        logger.error("댓글 버튼을 찾을 수 없음")
                        return False, None
                    
                    await comment_btn.click()
                    await asyncio.sleep(2)
                    
                    # 텍스트 영역 찾기
                    textarea = await self.page.wait_for_selector('textarea', timeout=5000)
                    if not textarea:
                        logger.error("텍스트 입력 영역을 찾을 수 없음")
                        return False, None
                    
                    # 텍스트 입력
                    await textarea.click()
                    await textarea.fill(reply_text)
                    await asyncio.sleep(1)
                    
                    # 등록 버튼 클릭
                    submit_btn = await self.page.wait_for_selector(
                        'button:has-text("등록")',
                        timeout=3000
                    )
                    if not submit_btn:
                        logger.error("등록 버튼을 찾을 수 없음")
                        return False, None
                    
                    await submit_btn.click()
                    await asyncio.sleep(2)
                    
                    # 금지어 팝업 확인
                    popup = await self.page.query_selector('div[role="alertdialog"]')
                    if popup:
                        popup_text = await popup.text_content()
                        logger.warning(f"금지어 팝업 감지: {popup_text}")
                        
                        # 금지어 추출
                        prohibited_match = re.search(r"'([^']+)'", popup_text)
                        if prohibited_match:
                            prohibited_word = prohibited_match.group(1)
                            detected_prohibited_words.add(prohibited_word)
                        
                        # 확인 버튼 클릭
                        confirm_btn = await popup.query_selector('button:has-text("확인")')
                        if confirm_btn:
                            await confirm_btn.click()
                        
                        if attempt == max_attempts:
                            return False, detected_prohibited_words
                        
                        # 다음 시도를 위해 창 닫기
                        try:
                            cancel_btn = await self.page.query_selector('button:has-text("취소")')
                            if cancel_btn:
                                await cancel_btn.click()
                        except:
                            pass
                        
                        continue
                    
                    # 성공
                    logger.info("댓글 등록 성공")
                    return True, None
                    
                except Exception as e:
                    logger.error(f"댓글 등록 시도 {attempt} 실패: {str(e)}")
                    if attempt == max_attempts:
                        return False, detected_prohibited_words
                    await asyncio.sleep(1)
            
            return False, detected_prohibited_words
            
        except Exception as e:
            logger.error(f"댓글 등록 중 오류: {str(e)}")
            return False, detected_prohibited_words
    
    def clean_reply_text(self, text: str) -> str:
        """답글 텍스트 정리"""
        # 유니코드 정규화
        text = unicodedata.normalize('NFC', text)
        
        # 허용된 문자만 필터링
        filtered = []
        for c in text:
            if ord(c) <= 0xFFFF and (c.isprintable() or c in ('\n', '\r', '\t')):
                filtered.append(c)
        
        return "".join(filtered).strip()
