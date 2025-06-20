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

    # =============================================
    # 새로 추가되는 메서드들 (매장 정책 및 답글 생성 이력)
    # =============================================

    async def get_store_reply_rules(self, store_code: str) -> Dict[str, Any]:
        """매장별 답글 정책 조회"""
        try:
            response = await self._execute_query(
                self.client.table('platform_reply_rules')
                .select('*')
                .eq('store_code', store_code)
                .eq('is_active', True)
            )
            
            if response.data:
                rules = response.data[0]
                
                # SQL 스키마의 실제 필드명에 맞춰 반환
                return {
                    'store_code': rules.get('store_code', store_code),
                    'store_name': rules.get('store_name', ''),
                    'platform': rules.get('platform', ''),
                    'platform_code': rules.get('platform_code', ''),
                    
                    # 답글 정책 설정
                    'greeting_start': rules.get('greeting_start', '안녕하세요'),
                    'greeting_end': rules.get('greeting_end', '감사합니다'),
                    'role': rules.get('role', ''),
                    'tone': rules.get('tone', ''),
                    'prohibited_words': rules.get('prohibited_words', []),
                    'max_length': rules.get('max_length', 300),
                    
                    # 별점별 자동 답글 활성화 설정
                    'rating_5_reply': rules.get('rating_5_reply', True),
                    'rating_4_reply': rules.get('rating_4_reply', True),
                    'rating_3_reply': rules.get('rating_3_reply', True),
                    'rating_2_reply': rules.get('rating_2_reply', True),
                    'rating_1_reply': rules.get('rating_1_reply', True),
                    
                    # 운영 설정
                    'auto_reply_enabled': rules.get('auto_reply_enabled', True),
                    'auto_reply_hours': rules.get('auto_reply_hours', '10:00-20:00'),
                    'reply_delay_minutes': rules.get('reply_delay_minutes', 30),
                    'weekend_enabled': rules.get('weekend_enabled', True),
                    'holiday_enabled': rules.get('holiday_enabled', False),
                    
                    # 품질 관리
                    'quality_check_enabled': rules.get('quality_check_enabled', True),
                    'manual_review_threshold': rules.get('manual_review_threshold', 0.3),
                    'learning_mode': rules.get('learning_mode', False),
                    
                    # 기타 정보
                    'owner_user_code': rules.get('owner_user_code', ''),
                    'store_type': rules.get('store_type', 'delivery_only'),
                    'store_address': rules.get('store_address', ''),
                    'store_phone': rules.get('store_phone', ''),
                    'business_hours': rules.get('business_hours', {}),
                    'avg_rating': rules.get('avg_rating', 0.0),
                    'total_reviews_processed': rules.get('total_reviews_processed', 0)
                }
            else:
                # 매장 정보가 없는 경우 기본값 반환
                logger.warning(f"매장 정책을 찾을 수 없습니다: {store_code}")
                return self._get_default_reply_rules(store_code)
                
        except Exception as e:
            logger.error(f"매장 정책 조회 오류: {e}")
            return self._get_default_reply_rules(store_code)
    
    def _get_default_reply_rules(self, store_code: str) -> Dict[str, Any]:
        """기본 답글 정책 반환"""
        return {
            'store_code': store_code,
            'store_name': '매장',
            'platform': '',
            'platform_code': '',
            'greeting_start': '안녕하세요',
            'greeting_end': '감사합니다',
            'role': '친절한 사장님',
            'tone': '친근함',
            'prohibited_words': [],
            'max_length': 300,
            'rating_5_reply': True,
            'rating_4_reply': True,
            'rating_3_reply': True,
            'rating_2_reply': True,
            'rating_1_reply': True,
            'auto_reply_enabled': True,
            'auto_reply_hours': '10:00-20:00',
            'reply_delay_minutes': 30,
            'weekend_enabled': True,
            'holiday_enabled': False,
            'quality_check_enabled': True,
            'manual_review_threshold': 0.3,
            'learning_mode': False,
            'owner_user_code': '',
            'store_type': 'delivery_only',
            'store_address': '',
            'store_phone': '',
            'business_hours': {},
            'avg_rating': 0.0,
            'total_reviews_processed': 0
        }

    async def save_reply_generation_history(
        self,
        review_id: str,
        user_code: str = None,
        generation_type: str = 'ai_initial',
        prompt_used: str = '',
        model_version: str = 'gpt-4o-mini',
        generated_content: str = '',
        quality_score: float = 0.0,
        processing_time_ms: int = 0,
        token_usage: int = 0,
        is_selected: bool = False
    ) -> bool:
        """답글 생성 이력 저장"""
        try:
            data = {
                'review_id': review_id,
                'user_code': user_code,
                'generation_type': generation_type,
                'prompt_used': prompt_used,
                'model_version': model_version,
                'generated_content': generated_content,
                'quality_score': quality_score,
                'processing_time_ms': processing_time_ms,
                'token_usage': token_usage,
                'is_selected': is_selected,
                'created_at': datetime.now().isoformat()
            }
            
            response = await self._execute_query(
                self.client.table('reply_generation_history').insert(data)
            )
            
            return bool(response.data)
            
        except Exception as e:
            logger.error(f"답글 생성 이력 저장 오류: {e}")
            return False