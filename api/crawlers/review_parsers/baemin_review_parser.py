"""
배민 리뷰 파서
네트워크 응답을 가로채서 리뷰 데이터를 추출
"""
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
import asyncio

logger = logging.getLogger(__name__)


class BaeminReviewParser:
    """배민 리뷰 데이터 파서"""
    
    def __init__(self):
        self.collected_reviews = []
        self.api_responses = []
        
    def parse_review_id_to_date(self, review_id: str) -> str:
        """
        리뷰 ID에서 날짜 추출
        review_id: 2025060702259991
        앞 8자리: 20250607 (2025년 06월 07일)
        """
        try:
            date_string = str(review_id)[:8]
            date_obj = datetime.strptime(date_string, '%Y%m%d')
            return date_obj.strftime('%Y-%m-%d')
        except Exception as e:
            logger.error(f"Failed to parse date from review_id {review_id}: {e}")
            return datetime.now().strftime('%Y-%m-%d')

    def parse_review_from_api(self, review_data: Dict) -> Dict:
        """
        API 응답에서 리뷰 데이터 파싱
        """
        try:
            review_id = str(review_data.get('id', ''))
            
            # 메뉴 정보 추출
            menus = []
            for menu in review_data.get('menus', []):
                menus.append({
                    'name': menu.get('name', ''),
                    'contents': menu.get('contents', ''),
                    'recommendation': menu.get('recommendation', 'NONE')
                })
            
            # 이미지 URL 추출
            images = []
            for img in review_data.get('images', []):
                if img.get('displayStatus') == 'DISPLAY':
                    images.append(img.get('imageUrl', ''))
            
            # 배달 리뷰 정보
            delivery_review = review_data.get('deliveryReviews', {})
            
            return {
                'review_id': review_id,
                'member_nickname': review_data.get('memberNickname', ''),
                'rating': float(review_data.get('rating', 0)),
                'contents': review_data.get('contents', ''),
                'menus': menus,
                'images': images,
                'delivery_recommendation': delivery_review.get('recommendation', ''),
                'created_date': self.parse_review_id_to_date(review_id),
                'created_date_text': review_data.get('createdDate', ''),  # '오늘', '어제' 등
                'has_comment': len(review_data.get('comments', [])) > 0,
                'writable_comment': review_data.get('writableComment', True)
            }
        except Exception as e:
            logger.error(f"Failed to parse review data: {e}")
            return None

    async def setup_network_interception(self, page):
        """
        Playwright 페이지에 네트워크 인터셉션 설정
        """
        async def handle_response(response):
            try:
                url = response.url
                
                # 리뷰 API 엔드포인트 확인
                if '/reviews' in url and response.status == 200:
                    content_type = response.headers.get('content-type', '')
                    
                    if 'application/json' in content_type:
                        try:
                            data = await response.json()
                            self.api_responses.append(data)
                            
                            # 리뷰 데이터 파싱
                            if 'reviews' in data:
                                for review in data['reviews']:
                                    parsed_review = self.parse_review_from_api(review)
                                    if parsed_review and not parsed_review['has_comment']:
                                        self.collected_reviews.append(parsed_review)
                                        logger.info(f"Collected review: {parsed_review['review_id']} - {parsed_review['member_nickname']}")
                        except Exception as e:
                            logger.error(f"Failed to parse JSON response: {e}")
            except Exception as e:
                logger.error(f"Error handling response: {e}")
        
        # 응답 핸들러 등록
        page.on('response', handle_response)

    def get_collected_reviews(self) -> List[Dict]:
        """수집된 리뷰 반환"""
        return self.collected_reviews

    def clear_collected_data(self):
        """수집된 데이터 초기화"""
        self.collected_reviews = []
        self.api_responses = []

    def filter_unanswered_reviews(self, reviews: List[Dict]) -> List[Dict]:
        """미답변 리뷰만 필터링"""
        return [r for r in reviews if not r.get('has_comment', False)]
