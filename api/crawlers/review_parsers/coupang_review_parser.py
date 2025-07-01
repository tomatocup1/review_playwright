"""
쿠팡이츠 리뷰 파서
네트워크 응답에서 리뷰 데이터를 추출하고 DB 형식으로 변환
"""
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class CoupangReviewParser:
    def __init__(self):
        """파서 초기화"""
        self.reviews_data = []
        
    def parse_review_date(self, date_string: str) -> str:
        """
        날짜 문자열을 YYYY-MM-DD 형식으로 변환
        "2025-06-07T15:30:00" -> "2025-06-07"
        
        Args:
            date_string: ISO 형식의 날짜 문자열
            
        Returns:
            str: YYYY-MM-DD 형식의 날짜
        """
        try:
            if 'T' in date_string:
                # ISO 형식에서 날짜 부분만 추출
                return date_string.split('T')[0]
            else:
                # 이미 YYYY-MM-DD 형식인 경우
                return date_string
        except Exception as e:
            logger.error(f"날짜 파싱 실패 - date_string: {date_string}, error: {e}")
            return datetime.now().strftime('%Y-%m-%d')
    
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
            # orderReviewId 추출
            order_review_id = str(api_review.get('orderReviewId', ''))
            
            # 날짜 파싱
            created_at = api_review.get('createdAt', '')
            review_date = self.parse_review_date(created_at)
            
            # 이미지 URL 추출
            review_images = api_review.get('reviewImages', [])
            image_urls = [img.get('imageUrl', '') for img in review_images if img.get('imageUrl')]
            
            # 주문 메뉴 정보 추출
            order_items = api_review.get('orderItems', [])
            menu_names = [item.get('menuName', '') for item in order_items if item.get('menuName')]
            
            # 답글 여부 확인
            has_reply = api_review.get('hasReply', False)
            response_status = 'posted' if has_reply else 'pending'
            
            # 배달 평가 정보
            delivery_review = api_review.get('deliveryReview', '')
            
            # DB 형식으로 변환
            db_format = {
                'review_id': f"coupang_{order_review_id}",
                'store_code': store_code,
                'platform': 'coupang',
                'platform_code': platform_code,
                'review_name': api_review.get('customerNickname', '익명'),
                'rating': int(api_review.get('rating', 5)),
                'review_content': api_review.get('reviewText', ''),
                'ordered_menu': json.dumps(menu_names, ensure_ascii=False),
                'delivery_review': delivery_review,
                'review_date': review_date,
                'review_images': json.dumps(image_urls, ensure_ascii=False),
                'response_status': response_status,
                'boss_reply_needed': not has_reply,
                'sentiment_score': None,
                'review_category': None,
                'keywords': None,
                'urgency_level': 'medium',
                'crawled_at': datetime.now().isoformat()
            }
            
            # 기존 답글이 있는 경우
            if has_reply and 'replyText' in api_review:
                db_format['final_response'] = api_review.get('replyText', '')
                db_format['response_at'] = api_review.get('replyCreatedAt', '')
            
            return db_format
            
        except Exception as e:
            logger.error(f"DB 형식 변환 실패 - orderReviewId: {api_review.get('orderReviewId')}, error: {e}")
            raise