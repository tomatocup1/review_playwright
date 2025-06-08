"""
Supabase 서비스 - 리뷰 통계 메서드 추가
"""
import os
from typing import List, Dict, Any, Optional
import logging
from supabase import create_client, Client
from dotenv import load_dotenv
import asyncio
from functools import wraps
from datetime import datetime, timedelta

load_dotenv()
logger = logging.getLogger(__name__)


def async_wrapper(func):
    """동기 함수를 비동기로 래핑"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)
    return wrapper


class SupabaseService:
    """Supabase 데이터베이스 서비스"""
    
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_ANON_KEY")
        
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL과 SUPABASE_ANON_KEY 환경변수를 설정해주세요.")
        
        self._client = None
    
    @property
    def client(self) -> Client:
        """Supabase 클라이언트 반환"""
        if not self._client:
            self._client = create_client(self.url, self.key)
        return self._client
    
    @async_wrapper
    def _execute_query(self, query_builder):
        """쿼리 실행"""
        return query_builder.execute()
    
    # 기존 메서드들...
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """이메일로 사용자 조회"""
        try:
            response = await self._execute_query(
                self.client.table('users').select('*').eq('email', email)
            )
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"사용자 조회 오류: {e}")
            return None
    
    async def check_user_permission(self, user_code: str, store_code: str, action: str) -> bool:
        """사용자 권한 확인"""
        try:
            # 매장 소유자인지 확인
            response = await self._execute_query(
                self.client.table('platform_reply_rules')
                .select('owner_user_code')
                .eq('store_code', store_code)
            )
            
            if response.data and response.data[0]['owner_user_code'] == user_code:
                return True
            
            # 권한 테이블에서 확인
            response = await self._execute_query(
                self.client.table('user_store_permissions')
                .select('*')
                .eq('user_code', user_code)
                .eq('store_code', store_code)
                .eq('is_active', True)
            )
            
            if response.data:
                permission = response.data[0]
                # 만료일 확인
                if permission.get('expires_at'):
                    expires_at = datetime.fromisoformat(permission['expires_at'].replace('Z', '+00:00'))
                    if expires_at < datetime.now():
                        return False
                
                # 액션별 권한 확인
                permission_map = {
                    'view': 'can_view',
                    'edit': 'can_edit_settings',
                    'reply': 'can_reply',
                    'manage_rules': 'can_manage_rules'
                }
                
                return permission.get(permission_map.get(action, 'can_view'), False)
            
            return False
            
        except Exception as e:
            logger.error(f"권한 확인 오류: {e}")
            return False
    
    async def get_reviews_by_store(
        self, 
        store_code: str,
        status: Optional[str] = None,
        rating: Optional[int] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """매장별 리뷰 조회"""
        try:
            query = self.client.table('reviews').select('*').eq('store_code', store_code)
            
            if status:
                query = query.eq('response_status', status)
            
            if rating:
                query = query.eq('rating', rating)
            
            # 삭제되지 않은 리뷰만
            query = query.eq('is_deleted', False)
            
            # 최신순 정렬
            query = query.order('created_at', desc=True)
            
            # 페이지네이션
            query = query.range(offset, offset + limit - 1)
            
            response = await self._execute_query(query)
            return response.data or []
            
        except Exception as e:
            logger.error(f"리뷰 조회 오류: {e}")
            return []
    
    async def get_review_stats(self, store_code: str) -> Dict[str, Any]:
        """매장 리뷰 통계 조회"""
        try:
            # 전체 리뷰 조회 (최근 30일)
            thirty_days_ago = datetime.now() - timedelta(days=30)
            
            response = await self._execute_query(
                self.client.table('reviews')
                .select('*')
                .eq('store_code', store_code)
                .eq('is_deleted', False)
                .gte('created_at', thirty_days_ago.isoformat())
            )
            
            reviews = response.data or []
            
            # 통계 계산
            total_reviews = len(reviews)
            total_rating = sum(review.get('rating', 0) for review in reviews)
            avg_rating = round(total_rating / total_reviews, 1) if total_reviews > 0 else 0.0
            
            # 답변 관련 통계
            replied_reviews = [r for r in reviews if r.get('response_status') == 'posted']
            reply_rate = round((len(replied_reviews) / total_reviews) * 100, 1) if total_reviews > 0 else 0.0
            
            pending_reviews = [r for r in reviews if r.get('response_status') == 'pending']
            
            return {
                'total_reviews': total_reviews,
                'avg_rating': avg_rating,
                'reply_rate': reply_rate,
                'pending_reviews': len(pending_reviews),
                'replied_reviews': len(replied_reviews)
            }
            
        except Exception as e:
            logger.error(f"리뷰 통계 조회 오류: {e}")
            return {
                'total_reviews': 0,
                'avg_rating': 0.0,
                'reply_rate': 0.0,
                'pending_reviews': 0,
                'replied_reviews': 0
            }
    
    async def get_user_stores(self, user_code: str) -> List[Dict[str, Any]]:
        """사용자의 매장 목록 조회"""
        try:
            # 직접 소유한 매장
            response = await self._execute_query(
                self.client.table('platform_reply_rules')
                .select('*')
                .eq('owner_user_code', user_code)
                .eq('is_active', True)
            )
            
            owned_stores = response.data or []
            
            # 권한이 부여된 매장
            response = await self._execute_query(
                self.client.table('user_store_permissions')
                .select('store_code')
                .eq('user_code', user_code)
                .eq('is_active', True)
            )
            
            permitted_store_codes = [p['store_code'] for p in (response.data or [])]
            
            if permitted_store_codes:
                response = await self._execute_query(
                    self.client.table('platform_reply_rules')
                    .select('*')
                    .in_('store_code', permitted_store_codes)
                    .eq('is_active', True)
                )
                
                permitted_stores = response.data or []
            else:
                permitted_stores = []
            
            # 중복 제거하여 합치기
            all_stores = owned_stores.copy()
            owned_store_codes = [s['store_code'] for s in owned_stores]
            
            for store in permitted_stores:
                if store['store_code'] not in owned_store_codes:
                    all_stores.append(store)
            
            return all_stores
            
        except Exception as e:
            logger.error(f"매장 목록 조회 오류: {e}")
            return []
    
    async def get_review_by_id(self, review_id: str) -> Optional[Dict[str, Any]]:
        """리뷰 ID로 조회"""
        try:
            response = await self._execute_query(
                self.client.table('reviews')
                .select('*')
                .eq('review_id', review_id)
            )
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"리뷰 조회 오류: {e}")
            return None
    
    async def update_review_status(
        self,
        review_id: str,
        status: str,
        reply_content: str = None,
        reply_type: str = None,
        reply_by: str = None
    ) -> bool:
        """리뷰 상태 업데이트"""
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
            
            response = await self._execute_query(
                self.client.table('reviews')
                .update(update_data)
                .eq('review_id', review_id)
            )
            
            return bool(response.data)
            
        except Exception as e:
            logger.error(f"리뷰 상태 업데이트 오류: {e}")
            return False
