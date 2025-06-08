"""
배민 리뷰 파서
네트워크 응답에서 리뷰 데이터를 추출하고 DB 형식으로 변환
"""
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class BaeminReviewParser:
    def __init__(self):
        """파서 초기화"""
        self.reviews_data = []
        
    def parse_review_id_to_date(self, review_id: str) -> str:
        """
        리뷰 ID에서 날짜 추출
        2025060702259991 -> 2025-06-07
        
        Args:
            review_id: 배민 리뷰 ID
            
        Returns:
            str: YYYY-MM-DD 형식의 날짜
        """
        try:
            # ID의 첫 8자리가 날짜
            date_string = str(review_id)[:8]  # '20250607'
            
            # datetime 객체로 변환
            date_obj = datetime.strptime(date_string, '%Y%m%d')
            
            return date_obj.strftime('%Y-%m-%d')
        except Exception as e:
            logger.error(f"날짜 파싱 실패 - review_id: {review_id}, error: {e}")
            # 실패시 현재 날짜 반환
            return datetime.now().strftime('%Y-%m-%d')
    
    async def extract_reviews_from_network(self, page, platform_code: str) -> List[Dict]:
        """
        네트워크 응답에서 리뷰 데이터 추출
        
        Args:
            page: Playwright page 객체
            platform_code: 플랫폼 매장 코드
            
        Returns:
            list: 파싱된 리뷰 데이터 리스트
        """
        self.reviews_data = []
        
        # 네트워크 응답 리스너 설정
        async def handle_response(response):
            try:
                url = response.url
                
                # 리뷰 API 엔드포인트 확인
                if '/reviews' in url and response.status == 200:
                    # Content-Type 확인
                    content_type = response.headers.get('content-type', '')
                    if 'application/json' in content_type:
                        try:
                            data = await response.json()
                            
                            # 리뷰 데이터가 있는 경우
                            if isinstance(data, dict) and 'reviews' in data:
                                logger.info(f"리뷰 데이터 발견: {len(data['reviews'])}개")
                                self.reviews_data = data['reviews']
                        except Exception as e:
                            logger.error(f"JSON 파싱 실패: {e}")
            except Exception as e:
                logger.error(f"네트워크 응답 처리 실패: {e}")
        
        # 리스너 등록
        page.on('response', handle_response)
        
        try:
            # 리뷰 페이지로 이동
            await page.goto(f"https://self.baemin.com/shops/{platform_code}/reviews", 
                          wait_until='networkidle')
            
            # 데이터 로딩 대기
            await page.wait_for_timeout(3000)
            
            # 미답변 탭 클릭 시도
            try:
                unanswered_tab = await page.query_selector('button[id="no-comment"]')
                if unanswered_tab:
                    await unanswered_tab.click()
                    await page.wait_for_timeout(2000)
            except Exception as e:
                logger.warning(f"미답변 탭 클릭 실패: {e}")
            
        finally:
            # 리스너 제거
            page.remove_listener('response', handle_response)
        
        # 수집된 리뷰 데이터 반환
        return self.reviews_data
    
    def parse_api_response_to_db_format(self, api_review: dict, store_code: str, platform_code: str) -> dict:
        """
        API 응답을 DB 형식으로 변환
        
        Args:
            api_review: API에서 받은 리뷰 데이터
            store_code: 매장 코드
            platform_code: 플랫폼 매장 코드
            
        Returns:
            dict: DB 저장용 형식
        """
        try:
            # 리뷰 ID와 날짜 파싱
            review_id = str(api_review.get('id', ''))
            review_date = self.parse_review_id_to_date(review_id)
            
            # 이미지 URL 추출
            images = api_review.get('images', [])
            image_urls = [img.get('imageUrl', '') for img in images if img.get('imageUrl')]
            
            # 메뉴 정보 추출
            menus = api_review.get('menus', [])
            menu_names = [menu.get('name', '') for menu in menus if menu.get('name')]
            
            # 배달 리뷰 정보
            delivery_reviews = api_review.get('deliveryReviews', {})
            delivery_recommendation = delivery_reviews.get('recommendation', '')
            
            # 답글 여부 확인
            comments = api_review.get('comments', [])
            has_reply = len(comments) > 0
            response_status = 'posted' if has_reply else 'pending'
            
            # DB 형식으로 변환
            db_format = {
                'review_id': review_id,
                'store_code': store_code,
                'platform': 'baemin',
                'platform_code': platform_code,
                'review_name': api_review.get('memberNickname', ''),
                'rating': int(api_review.get('rating', 0)),
                'review_content': api_review.get('contents', ''),
                'ordered_menu': json.dumps(menu_names, ensure_ascii=False),
                'delivery_review': delivery_recommendation,
                'review_date': review_date,
                'review_images': json.dumps(image_urls, ensure_ascii=False),
                'response_status': response_status,
                'boss_reply_needed': not has_reply,  # 답글이 없으면 사장님 답글 필요
                'sentiment_score': None,  # AI 분석 후 업데이트
                'review_category': None,  # AI 분석 후 업데이트
                'keywords': None,  # AI 분석 후 업데이트
                'urgency_level': 'medium',  # 기본값
                'crawled_at': datetime.now().isoformat()
            }
            
            # 기존 답글이 있는 경우
            if comments:
                first_comment = comments[0]
                db_format['final_response'] = first_comment.get('contents', '')
                db_format['response_at'] = first_comment.get('createdAt', '')
            
            return db_format
            
        except Exception as e:
            logger.error(f"DB 형식 변환 실패 - review_id: {api_review.get('id')}, error: {e}")
            raise
    
    def parse_review_from_dom(self, review_element) -> Optional[Dict]:
        """
        DOM에서 직접 리뷰 파싱 (폴백용)
        
        Args:
            review_element: 리뷰 DOM 요소
            
        Returns:
            dict: 파싱된 리뷰 데이터
        """
        try:
            # 작성자
            reviewer_elem = review_element.query_selector('span.Typography_b_b8ew_1bisyd47')
            reviewer_name = reviewer_elem.inner_text() if reviewer_elem else ''
            
            # 날짜
            date_elem = review_element.query_selector('span.Typography_b_b8ew_1bisyd4b')
            review_date_text = date_elem.inner_text() if date_elem else ''
            
            # 별점 (별 개수 세기)
            stars = review_element.query_selector_all('svg[fill="#FFC600"]')
            rating = len(stars)
            
            # 리뷰 내용
            content_elem = review_element.query_selector('span.Typography_b_b8ew_1bisyd49')
            review_content = content_elem.inner_text() if content_elem else ''
            
            # 이미지
            image_elems = review_element.query_selector_all('img[alt="리뷰 사진"]')
            image_urls = [img.get_attribute('src') for img in image_elems]
            
            # 주문 메뉴
            menu_elems = review_element.query_selector_all('li.MenuItem-module__EILP span')
            menu_names = [menu.inner_text() for menu in menu_elems]
            
            # 배달 리뷰
            delivery_elem = review_element.query_selector('span:has-text("좋아요")')
            delivery_review = delivery_elem.inner_text() if delivery_elem else ''
            
            return {
                'reviewer_name': reviewer_name,
                'review_date_text': review_date_text,
                'rating': rating,
                'review_content': review_content,
                'image_urls': image_urls,
                'menu_names': menu_names,
                'delivery_review': delivery_review
            }
            
        except Exception as e:
            logger.error(f"DOM 파싱 실패: {e}")
            return None