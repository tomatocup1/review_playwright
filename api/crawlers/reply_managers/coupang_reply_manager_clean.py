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
    """쿠팡이츠 답글 관리자 - 정확한 매칭 로직"""
    
    def __init__(self, store_info: Dict[str, str]):
        self.store_info = store_info
        self.platform_id = store_info.get('platform_id')
        self.platform_pw = store_info.get('platform_pw')
        self.store_code = store_info.get('store_code')
        self.platform_store_id = store_info.get('platform_code')
        self.screenshots_dir = Path("logs/screenshots/coupang/replies")
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        
    async def find_and_reply_to_review(self, page: Page, review_data: Dict) -> bool:
        """리뷰를 찾아서 답글 등록"""
        try:
            # 리뷰 데이터 추출
            review_content = review_data.get('review_content', '')
            reply_content = review_data.get('reply_content', '')
            ordered_menu = review_data.get('ordered_menu', '')
            review_name = review_data.get('review_name', '')
            rating = review_data.get('rating')
            
            logger.info(f"📊 찾고자 하는 리뷰:")
            logger.info(f"   - 리뷰어: '{review_name}'")
            logger.info(f"   - 별점: {rating}")
            logger.info(f"   - 내용: '{review_content}'")
            logger.info(f"   - 메뉴: '{ordered_menu}'")
            
            # 모든 리뷰 행 가져오기
            review_rows = await page.query_selector_all('tr')
            
            # 헤더 행 제외
            actual_review_rows = []
            for row in review_rows:
                th_elements = await row.query_selector_all('th')
                if len(th_elements) == 0:
                    actual_review_rows.append(row)
            
            logger.info(f"🔍 총 {len(actual_review_rows)}개 리뷰 행 검색")
            
            # 각 리뷰 행에서 정확한 매칭 시도
            for i, row in enumerate(actual_review_rows):
                try:
                    # 1. 리뷰어 이름 추출
                    page_reviewer = ""
                    try:
                        reviewer_elem = await row.query_selector('div.css-hdvjju.eqn7l9b7 b')
                        if reviewer_elem:
                            page_reviewer = await reviewer_elem.text_content()
                            page_reviewer = page_reviewer.strip() if page_reviewer else ""
                    except:
                        pass
                    
                    # 2. 별점 추출
                    page_rating = 0
                    try:
                        star_svgs = await row.query_selector_all('svg[fill="#FFC400"]')
                        page_rating = len(star_svgs)
                    except:
                        pass
                    
                    # 3. 리뷰 내용 추출
                    page_content = ""
                    try:
                        content_elem = await row.query_selector('p.css-16m6tj.eqn7l9b5')
                        if content_elem:
                            page_content = await content_elem.text_content()
                            page_content = page_content.strip() if page_content else ""
                    except:
                        pass
                    
                    # 4. 주문메뉴 추출
                    page_menu = ""
                    try:
                        li_elements = await row.query_selector_all('li')
                        for li in li_elements:
                            strong = await li.query_selector('strong')
                            if strong:
                                strong_text = await strong.text_content()
                                if strong_text and '주문메뉴' in strong_text:
                                    p_element = await li.query_selector('p')
                                    if p_element:
                                        page_menu = await p_element.text_content()
                                        page_menu = page_menu.strip() if page_menu else ""
                                        break
                    except:
                        pass
                    
                    logger.debug(f"리뷰 {i+1}: 이름='{page_reviewer}', 별점={page_rating}, 내용='{page_content[:20]}...', 메뉴='{page_menu}'")
                    
                    # 매칭 확인
                    matches = []
                    
                    # 이름 매칭
                    if review_name and page_reviewer:
                        if review_name == page_reviewer:
                            matches.append("이름")
                        else:
                            continue
                    
                    # 별점 매칭
                    if rating and page_rating:
                        if rating == page_rating:
                            matches.append("별점")
                        else:
                            continue
                    
                    # 내용 매칭 (있는 경우만)
                    if review_content and review_content.strip():
                        if page_content and self._normalize_text(review_content) == self._normalize_text(page_content):
                            matches.append("내용")
                        else:
                            continue
                    
                    # 메뉴 매칭
                    if ordered_menu and page_menu:
                        if self._normalize_text(ordered_menu) == self._normalize_text(page_menu):
                            matches.append("메뉴")
                        else:
                            continue
                    
                    # 매칭 성공 조건
                    if review_content and review_content.strip():
                        # 내용이 있는 경우: 4개 모두 매칭
                        required = ["이름", "별점", "내용", "메뉴"]
                    else:
                        # 내용이 없는 경우: 3개 매칭
                        required = ["이름", "별점", "메뉴"]
                    
                    if all(match in matches for match in required):
                        logger.info(f"🎯 완벽한 매칭 발견! 매칭 조건: {matches}")
                        
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
                                
                                # 등록 버튼 클릭
                                submit_button = await page.query_selector('button:has-text("등록")')
                                if submit_button:
                                    await submit_button.click()
                                    await page.wait_for_timeout(3000)
                                    logger.info("✅ 답글 등록 완료!")
                                    return True
                                else:
                                    logger.error("등록 버튼을 찾을 수 없음")
                                    return False
                            else:
                                logger.error("답글 입력창을 찾을 수 없음")
                                return False
                        else:
                            logger.warning("📝 답글 버튼이 없음 - 오래된 리뷰")
                            return "OLD_REVIEW"
                    
                except Exception as e:
                    logger.error(f"리뷰 {i+1} 처리 중 오류: {str(e)}")
                    continue
            
            logger.warning("매칭되는 리뷰를 찾을 수 없음")
            return False
            
        except Exception as e:
            logger.error(f"리뷰 검색 중 오류: {str(e)}")
            return False
    
    def _normalize_text(self, text: str) -> str:
        """텍스트 정규화"""
        if not text:
            return ""
        return re.sub(r'\s+', ' ', text).strip()