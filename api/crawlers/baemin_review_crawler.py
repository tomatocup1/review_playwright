"""
배민 리뷰 크롤링 및 답글 등록 전용 크롤러
"""
import re
import json
import logging
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
import asyncio

from playwright.async_api import async_playwright, Page
from .windows_async_crawler import WindowsAsyncBaseCrawler
from api.crawlers.review_parsers.baemin_review_parser import BaeminReviewParser
# baemin_sync_review_crawler.py 상단에 추가
from api.utils.date_parser import parse_relative_date

logger = logging.getLogger(__name__)


class BaeminReviewCrawler(WindowsAsyncBaseCrawler):
    """배민 리뷰 전용 크롤러"""
    
    def __init__(self, headless: bool = True):
        super().__init__(headless)
        self.login_url = "https://biz-member.baemin.com/login"
        self.reviews_data = []
        
        # 스크린샷 저장 경로
        self.screenshot_dir = Path("C:/Review_playwright/logs/screenshots/baemin_reviews")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
    async def login(self, username: str, password: str) -> bool:
        """배민 사장님 사이트 로그인"""
        try:
            logger.info(f"배민 로그인 시작: {username}")
            
            await self.page.goto(self.login_url)
            await self.page.wait_for_load_state('networkidle')
            
            # 로그인 폼 입력
            await self.page.fill('input[name="id"]', username)
            await self.page.fill('input[name="password"]', password)
            
            # 로그인 버튼 클릭
            await self.page.click('button[type="submit"]')
            
            # 로그인 완료 대기
            await self.page.wait_for_timeout(5000)
            
            # 로그인 성공 확인
            current_url = self.page.url
            if 'login' not in current_url.lower():
                logger.info("로그인 성공")
                self.logged_in = True
                return True
            else:
                logger.error("로그인 실패")
                return False
                
        except Exception as e:
            logger.error(f"로그인 중 오류: {str(e)}")
            return False
    
    async def navigate_to_reviews(self, platform_code: str) -> bool:
        """리뷰 페이지로 이동"""
        try:
            review_url = f"https://self.baemin.com/shops/{platform_code}/reviews"
            logger.info(f"리뷰 페이지로 이동: {review_url}")
            
            await self.page.goto(review_url)
            await self.page.wait_for_load_state('networkidle')
            await self.page.wait_for_timeout(2000)
            
            # 미답변 탭 클릭
            try:
                # 미답변 탭 버튼 찾기
                unanswered_button = await self.page.query_selector('button#no-comment')
                if unanswered_button:
                    await unanswered_button.click()
                    logger.info("미답변 탭 클릭")
                    await self.page.wait_for_timeout(1000)
            except:
                logger.info("미답변 탭을 찾을 수 없거나 이미 선택됨")
            
            return True
            
        except Exception as e:
            logger.error(f"리뷰 페이지 이동 실패: {str(e)}")
            return False
    
    def generate_review_id(self, platform: str, store_code: str, review_id: str) -> str:
        """리뷰 고유 ID 생성 (해시값)"""
        raw_string = f"{platform}_{store_code}_{review_id}"
        return hashlib.md5(raw_string.encode()).hexdigest()
    
    async def get_reviews(self, platform_code: str, store_code: str, limit: int = 50) -> List[Dict[str, Any]]:
        """리뷰 목록 가져오기"""
        try:
            logger.info(f"리뷰 목록 조회 시작 - 매장: {platform_code}")
            
            # 리뷰 페이지로 이동
            if not await self.navigate_to_reviews(platform_code):
                return []
            
            # API 응답을 저장할 리스트
            self.reviews_data = []
            
            # 네트워크 응답 캡처 핸들러
            async def handle_response(response):
                try:
                    if '/api/v1/reviews' in response.url and response.status == 200:
                        data = await response.json()
                        if 'reviews' in data:
                            self.reviews_data.extend(data['reviews'])
                            logger.info(f"API 응답에서 {len(data['reviews'])}개 리뷰 캡처")
                except Exception as e:
                    logger.error(f"응답 파싱 실패: {str(e)}")
            
            # 응답 리스너 등록
            self.page.on('response', handle_response)
            
            # 페이지 새로고침하여 API 호출 유도
            await self.page.reload()
            await self.page.wait_for_timeout(3000)
            
            # 리스너 제거
            self.page.remove_listener('response', handle_response)
            
            # 캡처된 리뷰 데이터 처리
            reviews = []
            for review in self.reviews_data[:limit]:
                try:
                    # 리뷰 고유 ID 생성
                    review_id = self.generate_review_id('baemin', store_code, str(review.get('id')))
                    
                    # 리뷰 데이터 파싱
                    parsed_review = {
                        'review_id': review_id,
                        'platform': 'baemin',
                        'platform_code': platform_code,
                        'store_code': store_code,
                        'original_id': review.get('id'),
                        'review_name': review.get('memberNickname', '익명'),
                        'rating': int(review.get('rating', 0)),
                        'review_content': review.get('contents', ''),
                        'review_date': review.get('createdDate', '오늘'),
                        'ordered_menu': ', '.join([m.get('name', '') for m in review.get('menus', [])]),
                        'review_images': [img.get('imageUrl', '') for img in review.get('images', [])],
                        'delivery_review': review.get('deliveryReviews', {}).get('recommendation', ''),
                        'has_reply': len(review.get('comments', [])) > 0,
                        'writableComment': review.get('writableComment', True)
                    }
                    
                    # 미답변 리뷰만 추가
                    if not parsed_review['has_reply'] and parsed_review['writableComment']:
                        reviews.append(parsed_review)
                        logger.info(f"리뷰 추가: {parsed_review['review_name']} - {parsed_review['rating']}점")
                        
                except Exception as e:
                    logger.error(f"리뷰 파싱 중 오류: {str(e)}")
                    continue
            
            logger.info(f"총 {len(reviews)}개의 미답변 리뷰 조회 완료")
            return reviews
            
        except Exception as e:
            logger.error(f"리뷰 목록 조회 중 오류: {str(e)}")
            return []
    
    async def find_review_element(self, review_id: str):
        """특정 리뷰 요소 찾기"""
        try:
            # 모든 리뷰 컨테이너 찾기
            review_containers = await self.page.query_selector_all('.ReviewContent-module__Ksg4')
            
            for container in review_containers:
                # 리뷰 작성자 이름으로 매칭 시도
                name_element = await container.query_selector('span.Typography_b_b8ew_1bisyd47')
                if name_element:
                    name = await name_element.text_content()
                    # 여기서는 이름으로 매칭하지만, 실제로는 더 정확한 방법 필요
                    return container
            
            return None
            
        except Exception as e:
            logger.error(f"리뷰 요소 찾기 실패: {str(e)}")
            return None
    
    async def post_reply(self, review_data: Dict[str, Any], reply_text: str) -> bool:
        """리뷰에 답글 작성"""
        try:
            logger.info(f"답글 작성 시작 - 리뷰: {review_data['review_name']}")
            
            # 페이지에서 해당 리뷰 찾기
            review_element = await self.find_review_element(review_data['review_id'])
            if not review_element:
                logger.error("리뷰 요소를 찾을 수 없습니다")
                return False
            
            # 답글 등록 버튼 찾기
            reply_button = await review_element.query_selector('button:has-text("사장님 댓글 등록하기")')
            if not reply_button:
                logger.error("답글 등록 버튼을 찾을 수 없습니다")
                return False
            
            # 버튼 클릭
            await reply_button.click()
            logger.info("답글 등록 버튼 클릭")
            await self.page.wait_for_timeout(1000)
            
            # 텍스트 입력 영역 찾기
            textarea = await self.page.query_selector('textarea')
            if not textarea:
                logger.error("텍스트 입력 영역을 찾을 수 없습니다")
                return False
            
            # 기존 텍스트 삭제하고 새 답글 입력
            await textarea.click()
            await textarea.press('Control+A')
            await textarea.type(reply_text)
            logger.info(f"답글 입력 완료: {reply_text[:50]}...")
            
            # 등록 버튼 찾기
            submit_button = await self.page.query_selector('button:has-text("등록")')
            if not submit_button:
                logger.error("등록 버튼을 찾을 수 없습니다")
                return False
            
            # 등록 버튼 클릭
            await submit_button.click()
            logger.info("답글 등록 버튼 클릭")
            
            # 등록 완료 대기
            await self.page.wait_for_timeout(3000)
            
            # 스크린샷 저장
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = self.screenshot_dir / f"reply_posted_{timestamp}.png"
            await self.page.screenshot(path=str(screenshot_path))
            
            return True
            
        except Exception as e:
            logger.error(f"답글 작성 중 오류: {str(e)}")
            return False