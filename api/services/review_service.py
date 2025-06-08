"""
리뷰 데이터베이스 서비스
"""
import hashlib
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from .database import Database

logger = logging.getLogger(__name__)


class ReviewService:
    """리뷰 관련 데이터베이스 작업"""
    
    def __init__(self):
        self.db = Database()
    
    def generate_review_id(self, platform: str, store_code: str, review_id: str) -> str:
        """리뷰 고유 ID 생성 (해시값)"""
        raw_string = f"{platform}_{store_code}_{review_id}"
        return hashlib.md5(raw_string.encode()).hexdigest()
    
    async def save_review(self, review_data: Dict[str, Any]) -> bool:
        """리뷰 저장"""
        try:
            # 리뷰 고유 ID 생성
            review_id = self.generate_review_id(
                review_data['platform'],
                review_data['store_code'],
                str(review_data['original_id'])
            )
            
            # 중복 체크
            existing = await self.db.fetch_one(
                "SELECT id FROM reviews WHERE review_id = ?",
                (review_id,)
            )
            
            if existing:
                logger.info(f"이미 존재하는 리뷰: {review_id}")
                return False
            
            # 리뷰 저장
            query = """
                INSERT INTO reviews (
                    review_id, store_code, platform, platform_code,
                    review_name, rating, review_content, ordered_menu,
                    review_date, review_images, response_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            params = (
                review_id,
                review_data['store_code'],
                review_data['platform'],
                review_data['platform_code'],
                review_data.get('review_name', ''),
                review_data['rating'],
                review_data.get('review_content', ''),
                review_data.get('ordered_menu', ''),
                review_data['review_date'],
                review_data.get('review_images', []),
                'pending'
            )
            
            await self.db.execute(query, params)
            logger.info(f"리뷰 저장 완료: {review_id}")
            return True
            
        except Exception as e:
            logger.error(f"리뷰 저장 실패: {str(e)}")
            return False
    
    async def get_pending_reviews(self, store_code: str) -> List[Dict[str, Any]]:
        """미답변 리뷰 조회"""
        try:
            query = """
                SELECT * FROM reviews 
                WHERE store_code = ? AND response_status = 'pending'
                ORDER BY review_date DESC
            """
            
            reviews = await self.db.fetch_all(query, (store_code,))
            return reviews
            
        except Exception as e:
            logger.error(f"미답변 리뷰 조회 실패: {str(e)}")
            return []
    
    async def update_review_response(self, review_id: str, response: str, status: str = 'posted') -> bool:
        """리뷰 답글 상태 업데이트"""
        try:
            query = """
                UPDATE reviews 
                SET ai_response = ?, response_status = ?, response_at = NOW()
                WHERE review_id = ?
            """
            
            await self.db.execute(query, (response, status, review_id))
            logger.info(f"리뷰 답글 상태 업데이트: {review_id}")
            return True
            
        except Exception as e:
            logger.error(f"리뷰 답글 업데이트 실패: {str(e)}")
            return False
    
    async def save_reply_history(self, history_data: Dict[str, Any]) -> bool:
        """답글 생성 이력 저장"""
        try:
            query = """
                INSERT INTO reply_generation_history (
                    review_id, user_code, generation_type,
                    generated_content, quality_score, is_selected
                ) VALUES (?, ?, ?, ?, ?, ?)
            """
            
            params = (
                history_data['review_id'],
                history_data.get('user_code'),
                history_data['generation_type'],
                history_data['generated_content'],
                history_data.get('quality_score', 0.0),
                history_data.get('is_selected', False)
            )
            
            await self.db.execute(query, params)
            return True
            
        except Exception as e:
            logger.error(f"답글 이력 저장 실패: {str(e)}")
            return False
