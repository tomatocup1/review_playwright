"""
Supabase 서비스 레이어
데이터베이스 작업을 처리하는 서비스
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

from config.supabase_client import get_supabase_client
from supabase import Client

logger = logging.getLogger(__name__)


class SupabaseService:
    def __init__(self):
        """Supabase 서비스 초기화"""
        self.client: Client = get_supabase_client()
        
    # ==================== 사용자 관련 ====================
    
    async def get_user_by_code(self, user_code: str) -> Optional[Dict]:
        """사용자 코드로 사용자 정보 조회"""
        try:
            response = self.client.table('users').select('*').eq('user_code', user_code).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"사용자 조회 실패: {e}")
            return None
    
    async def check_user_permission(self, user_code: str, store_code: str, action: str) -> bool:
        """사용자 권한 확인"""
        try:
            # PostgreSQL 함수 호출
            response = self.client.rpc('check_user_permission', {
                'p_user_code': user_code,
                'p_store_code': store_code,
                'p_action': action
            }).execute()
            return response.data if response.data else False
        except Exception as e:
            logger.error(f"권한 확인 실패: {e}")
            return False
    
    # ==================== 매장 관련 ====================
    
    async def get_store_by_code(self, store_code: str) -> Optional[Dict]:
        """매장 코드로 매장 정보 조회"""
        try:
            response = self.client.table('platform_reply_rules').select('*').eq('store_code', store_code).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"매장 정보 조회 실패: {e}")
            return None
    
    async def get_active_stores(self) -> List[Dict]:
        """활성 매장 목록 조회"""
        try:
            response = self.client.table('platform_reply_rules')\
                .select('*')\
                .eq('is_active', True)\
                .eq('auto_reply_enabled', True)\
                .execute()
            return response.data
        except Exception as e:
            logger.error(f"활성 매장 조회 실패: {e}")
            return []
    
    async def get_stores_by_owner(self, owner_user_code: str) -> List[Dict]:
        """사용자가 소유한 매장 목록 조회"""
        try:
            response = self.client.table('platform_reply_rules')\
                .select('*')\
                .eq('owner_user_code', owner_user_code)\
                .execute()
            return response.data
        except Exception as e:
            logger.error(f"소유 매장 조회 실패: {e}")
            return []
    
    # ==================== 리뷰 관련 ====================
    
    async def insert_review(self, review_data: dict) -> Optional[Dict]:
        """리뷰 데이터 삽입"""
        try:
            # JSON 필드 처리
            if isinstance(review_data.get('review_images'), list):
                review_data['review_images'] = json.dumps(review_data['review_images'], ensure_ascii=False)
            if isinstance(review_data.get('ordered_menu'), list):
                review_data['ordered_menu'] = json.dumps(review_data['ordered_menu'], ensure_ascii=False)
                
            response = self.client.table('reviews').insert(review_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"리뷰 삽입 실패: {e}")
            raise
    
    async def get_reviews_by_store(self, store_code: str, status: str = None, 
                                  rating: int = None, limit: int = 20, 
                                  offset: int = 0) -> List[Dict]:
        """매장별 리뷰 조회"""
        try:
            query = self.client.table('reviews').select('*').eq('store_code', store_code)
            
            if status:
                query = query.eq('response_status', status)
            if rating:
                query = query.eq('rating', rating)
                
            query = query.order('review_date', desc=True).limit(limit).offset(offset)
            
            response = query.execute()
            
            # JSON 필드 파싱
            for review in response.data:
                if review.get('review_images') and isinstance(review['review_images'], str):
                    review['review_images'] = json.loads(review['review_images'])
                if review.get('ordered_menu') and isinstance(review['ordered_menu'], str):
                    review['ordered_menu'] = json.loads(review['ordered_menu'])
                    
            return response.data
        except Exception as e:
            logger.error(f"리뷰 조회 실패: {e}")
            raise
    
    async def update_review_status(self, review_id: str, status: str, 
                                  reply_content: str = None, reply_type: str = None,
                                  reply_by: str = None) -> Optional[Dict]:
        """리뷰 상태 및 답글 업데이트"""
        try:
            update_data = {
                'response_status': status,
                'updated_at': datetime.now().isoformat()
            }
            
            if reply_content:
                update_data['final_response'] = reply_content
                update_data['response_at'] = datetime.now().isoformat()
            if reply_type:
                update_data['response_method'] = reply_type
            if reply_by:
                update_data['response_by'] = reply_by
                
            response = self.client.table('reviews').update(update_data).eq('review_id', review_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"리뷰 상태 업데이트 실패: {e}")
            raise
    
    async def check_review_exists(self, review_id: str) -> bool:
        """리뷰 존재 여부 확인"""
        try:
            response = self.client.table('reviews').select('review_id').eq('review_id', review_id).execute()
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"리뷰 존재 확인 실패: {e}")
            return False
    
    async def get_review_by_id(self, review_id: str) -> Optional[Dict]:
        """리뷰 ID로 조회"""
        try:
            response = self.client.table('reviews').select('*').eq('review_id', review_id).execute()
            
            if response.data:
                review = response.data[0]
                # JSON 필드 파싱
                if review.get('review_images') and isinstance(review['review_images'], str):
                    review['review_images'] = json.loads(review['review_images'])
                if review.get('ordered_menu') and isinstance(review['ordered_menu'], str):
                    review['ordered_menu'] = json.loads(review['ordered_menu'])
                return review
                
            return None
        except Exception as e:
            logger.error(f"리뷰 조회 실패: {e}")
            raise
    
    async def get_review_stats(self, store_code: str) -> Dict:
        """매장 리뷰 통계"""
        try:
            # 전체 리뷰 수
            total_response = self.client.table('reviews').select('*', count='exact').eq('store_code', store_code).execute()
            total_reviews = total_response.count
            
            # 미답변 리뷰 수
            pending_response = self.client.table('reviews').select('*', count='exact')\
                .eq('store_code', store_code)\
                .eq('response_status', 'pending')\
                .execute()
            pending_reviews = pending_response.count
            
            # 별점별 분포
            rating_stats = {}
            for rating in range(1, 6):
                rating_response = self.client.table('reviews').select('*', count='exact')\
                    .eq('store_code', store_code)\
                    .eq('rating', rating)\
                    .execute()
                rating_stats[f'rating_{rating}'] = rating_response.count
            
            # 평균 별점 계산
            avg_rating_response = self.client.table('reviews').select('rating')\
                .eq('store_code', store_code)\
                .execute()
            
            if avg_rating_response.data:
                ratings = [r['rating'] for r in avg_rating_response.data]
                avg_rating = sum(ratings) / len(ratings)
            else:
                avg_rating = 0
            
            return {
                'total_reviews': total_reviews,
                'pending_reviews': pending_reviews,
                'reply_rate': round((total_reviews - pending_reviews) / total_reviews * 100, 2) if total_reviews > 0 else 0,
                'rating_distribution': rating_stats,
                'average_rating': round(avg_rating, 2)
            }
        except Exception as e:
            logger.error(f"리뷰 통계 조회 실패: {e}")
            raise
    
    # ==================== 사용량 추적 ====================
    
    async def update_usage_tracking(self, user_code: str, reviews_increment: int = 0):
        """사용량 추적 업데이트"""
        try:
            # PostgreSQL 함수 호출
            self.client.rpc('update_usage', {
                'p_user_code': user_code,
                'p_reviews_increment': reviews_increment,
                'p_ai_api_calls_increment': 0,
                'p_web_api_calls_increment': 0,
                'p_manual_replies_increment': 0,
                'p_error_increment': 0
            }).execute()
        except Exception as e:
            logger.error(f"사용량 업데이트 실패: {e}")
    
    async def check_subscription_status(self, user_code: str) -> Dict:
        """구독 상태 확인"""
        try:
            response = self.client.rpc('check_subscription_status', {
                'p_user_code': user_code
            }).execute()
            return response.data[0] if response.data else {
                'is_active': False,
                'remaining_reviews': 0
            }
        except Exception as e:
            logger.error(f"구독 상태 확인 실패: {e}")
            return {'is_active': False, 'remaining_reviews': 0}
    
    # ==================== 알림 관련 ====================
    
    async def create_alert_log(self, alert_data: Dict) -> Optional[Dict]:
        """알림 로그 생성"""
        try:
            response = self.client.table('alert_logs').insert(alert_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"알림 로그 생성 실패: {e}")
            return None
    
    # ==================== 에러 로그 ====================
    
    async def log_error(self, error_data: Dict) -> None:
        """에러 로그 기록"""
        try:
            error_log = {
                'error_code': error_data.get('error_code'),
                'user_code': error_data.get('user_code'),
                'store_code': error_data.get('store_code'),
                'platform_code': error_data.get('platform_code'),
                'category': error_data.get('category', '시스템오류'),
                'severity': error_data.get('severity', 'medium'),
                'error_type': error_data.get('error_type'),
                'error_message': error_data.get('error_message'),
                'stack_trace': error_data.get('stack_trace'),
                'occurred_at': datetime.now().isoformat()
            }
            
            self.client.table('error_logs').insert(error_log).execute()
        except Exception as e:
            logger.error(f"에러 로그 기록 실패: {e}")