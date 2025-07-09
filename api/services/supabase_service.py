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
            logger.debug(f"권한 확인 - user_code: {user_code}, store_code: {store_code}, action: {action}")
            
            # 매장 소유자인지 확인
            response = await self._execute_query(
                self.client.table('platform_reply_rules')
                .select('owner_user_code')
                .eq('store_code', store_code)
            )
            
            logger.debug(f"매장 소유자 조회 결과: {response.data}")
            
            if response.data and response.data[0]['owner_user_code'] == user_code:
                logger.debug(f"매장 소유자 확인됨: {user_code}")
                return True
            
            # 권한 테이블 확인
            response = await self._execute_query(
                self.client.table('user_store_permissions')
                .select('*')
                .eq('user_code', user_code)
                .eq('store_code', store_code)
                .eq('is_active', True)
            )
            
            logger.debug(f"권한 테이블 조회 결과: {response.data}")
            
            if response.data:
                permission = response.data[0]
                # 만료일 확인
                if permission.get('expires_at'):
                    expires_at = datetime.fromisoformat(permission['expires_at'].replace('Z', '+00:00'))
                    if expires_at < datetime.now():
                        logger.debug(f"권한 만료됨: {expires_at}")
                        return False
                
                # 액션별 권한 확인
                permission_map = {
                    'view': 'can_view',
                    'edit': 'can_edit_settings',
                    'reply': 'can_reply',
                    'manage_rules': 'can_manage_rules'
                }
                
                has_permission = permission.get(permission_map.get(action, 'can_view'), False)
                logger.debug(f"권한 확인 결과: {has_permission}")
                return has_permission
            
            logger.debug("권한 없음")
            return False
            
        except Exception as e:
            logger.error(f"권한 확인 오류: {e}")
            return False
        
    async def debug_store_reviews(self, store_code: str) -> Dict:
        """매장 리뷰 디버깅 정보"""
        try:
            debug_info = {}
            
            # 1. 매장 정보 확인
            store_query = self.client.table('platform_reply_rules').select('*').eq('store_code', store_code)
            store_response = await self._execute_query(store_query)
            debug_info['store_info'] = store_response.data
            
            # 2. 전체 리뷰 수 (조건 없이)
            all_reviews_query = self.client.table('reviews').select('*', count='exact').eq('store_code', store_code)
            all_reviews_response = await self._execute_query(all_reviews_query)
            debug_info['total_reviews'] = all_reviews_response.count
            
            # 3. 플랫폼별 리뷰 수
            platforms = ['naver', 'baemin', 'coupang', 'yogiyo']
            platform_counts = {}
            for platform in platforms:
                platform_query = self.client.table('reviews').select('*', count='exact').eq('store_code', store_code).eq('platform', platform)
                platform_response = await self._execute_query(platform_query)
                platform_counts[platform] = platform_response.count
            debug_info['platform_counts'] = platform_counts
            
            # 4. is_deleted 상태별 수
            deleted_query = self.client.table('reviews').select('*', count='exact').eq('store_code', store_code).eq('is_deleted', True)
            deleted_response = await self._execute_query(deleted_query)
            debug_info['deleted_count'] = deleted_response.count
            
            # 5. 최근 네이버 리뷰 샘플 (5개)
            naver_sample_query = self.client.table('reviews').select('review_id, platform, rating, review_date, is_deleted, created_at').eq('store_code', store_code).eq('platform', 'naver').order('created_at', desc=True).limit(5)
            naver_sample_response = await self._execute_query(naver_sample_query)
            debug_info['naver_samples'] = naver_sample_response.data
            
            logger.info(f"디버그 정보: {debug_info}")
            return debug_info
            
        except Exception as e:
            logger.error(f"디버그 조회 오류: {e}")
            return {'error': str(e)}
    
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
            logger.debug(f"리뷰 조회 시작 - store_code: {store_code}, status: {status}, rating: {rating}")
            
            # 먼저 전체 리뷰 개수 확인 (디버깅용)
            count_query = self.client.table('reviews').select('*', count='exact').eq('store_code', store_code)
            count_response = await self._execute_query(count_query)
            logger.debug(f"매장 {store_code}의 전체 리뷰 수: {count_response.count}")
            
            # 실제 쿼리 구성
            query = self.client.table('reviews').select('*').eq('store_code', store_code)
            
            if status:
                query = query.eq('response_status', status)
                logger.debug(f"상태 필터 적용: {status}")
            
            if rating:
                query = query.eq('rating', rating)
                logger.debug(f"별점 필터 적용: {rating}")
            
            # 삭제되지 않은 리뷰만 - 이 조건을 일시적으로 제거하여 테스트
            # query = query.eq('is_deleted', False)
            
            # is_deleted 조건 분리하여 디버깅
            deleted_check_query = self.client.table('reviews').select('*').eq('store_code', store_code).eq('is_deleted', True)
            deleted_response = await self._execute_query(deleted_check_query)
            logger.debug(f"삭제된 리뷰 수: {len(deleted_response.data or [])}")
            
            # 삭제되지 않은 리뷰만 조회
            query = query.or_('is_deleted.is.null,is_deleted.eq.false')
            
            # 최신순 정렬
            query = query.order('created_at', desc=True)
            
            # 페이지네이션
            query = query.range(offset, offset + limit - 1)
            
            response = await self._execute_query(query)
            
            logger.debug(f"리뷰 조회 결과: {len(response.data or [])}개")
            if response.data:
                logger.debug(f"첫 번째 리뷰 샘플: {response.data[0]}")
            
            return response.data or []
            
        except Exception as e:
            logger.error(f"리뷰 조회 오류: {e}")
            logger.exception("상세 오류:")
            return []
    
    async def get_review_stats(self, store_code: str, start_date: Optional[datetime] = None) -> Dict[str, Any]:
        """리뷰 통계 조회"""
        try:
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)
            
            # 전체 리뷰 조회
            reviews_response = self.client.table('reviews').select('*').eq(
                'store_code', store_code
            ).gte('created_at', start_date.isoformat()).execute()
            
            reviews = reviews_response.data
            total_count = len(reviews)
            
            # 답글 관련 통계
            replied_count = len([r for r in reviews if r.get('response_status') == 'posted'])
            pending_count = len([r for r in reviews if r.get('response_status') in ['pending', 'generated', 'ready_to_post']])
            failed_count = len([r for r in reviews if r.get('response_status') == 'failed'])
            
            # 별점별 통계 (rating이 None인 경우 처리)
            rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            for review in reviews:
                rating = review.get('rating')
                if rating and isinstance(rating, (int, float)) and 1 <= rating <= 5:
                    rating_counts[int(rating)] += 1
            
            # 평균 별점 계산 (rating이 있는 리뷰만)
            ratings = [r.get('rating') for r in reviews if r.get('rating') is not None]
            avg_rating = sum(ratings) / len(ratings) if ratings else 0
            
            # 플랫폼별 통계
            platform_counts = {}
            for review in reviews:
                platform = review.get('platform', 'unknown')
                platform_counts[platform] = platform_counts.get(platform, 0) + 1
            
            return {
                'total_reviews': total_count,
                'replied_reviews': replied_count,
                'pending_reviews': pending_count,
                'failed_reviews': failed_count,
                'reply_rate': round((replied_count / total_count * 100) if total_count > 0 else 0, 2),
                'average_rating': round(avg_rating, 2),
                'rating_distribution': rating_counts,
                'platform_distribution': platform_counts,
                'period_start': start_date.isoformat(),
                'period_end': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"리뷰 통계 조회 오류: {str(e)}")
            # 오류 발생 시 기본값 반환
            return {
                'total_reviews': 0,
                'replied_reviews': 0,
                'pending_reviews': 0,
                'failed_reviews': 0,
                'reply_rate': 0,
                'average_rating': 0,
                'rating_distribution': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                'platform_distribution': {},
                'period_start': start_date.isoformat() if start_date else '',
                'period_end': datetime.now().isoformat()
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
    
    async def get_active_stores(self) -> List[Dict[str, Any]]:
        """모든 활성 매장 목록 조회"""
        try:
            response = await self._execute_query(
                self.client.table('platform_reply_rules')
                .select('*')
                .eq('is_active', True)
            )
            return response.data or []
        except Exception as e:
            logger.error(f"활성 매장 조회 오류: {e}")
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
        reply_by: str = None,
        boss_review_needed: bool = None,
        review_reason: str = None,
        urgency_score: float = None
    ) -> bool:
        """리뷰 상태 업데이트"""
        try:
            update_data = {
                'response_status': status,
                'updated_at': datetime.now().isoformat()
            }
            
            if reply_content is not None:
                update_data['ai_response'] = reply_content
                update_data['final_response'] = reply_content
            
            if reply_type is not None:
                update_data['response_method'] = reply_type
            
            if reply_by is not None:
                update_data['response_by'] = reply_by
            
            if boss_review_needed is not None:
                update_data['boss_reply_needed'] = boss_review_needed
                
            if review_reason is not None:
                update_data['review_reason'] = review_reason
            
            # urgency_score를 urgency_level로 변환
            if urgency_score is not None:
                if urgency_score >= 0.8:
                    urgency_level = 'critical'
                elif urgency_score >= 0.6:
                    urgency_level = 'high'
                elif urgency_score >= 0.4:
                    urgency_level = 'medium'
                else:
                    urgency_level = 'low'
                update_data['urgency_level'] = urgency_level
            
            if status == 'posted':
                update_data['response_at'] = datetime.now().isoformat()
            
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

    async def get_reply_generation_history(self, review_id: str) -> List[Dict[str, Any]]:
        """답글 생성 이력 조회"""
        try:
            response = await self._execute_query(
                self.client.table('reply_generation_history')
                .select('*')
                .eq('review_id', review_id)
                .order('created_at', desc=True)
            )
            return response.data or []
        except Exception as e:
            logger.error(f"답글 생성 이력 조회 오류: {e}")
            return []

    async def update_review_response(
        self,
        review_id: str,
        response_status: str = None,
        final_response: str = None,
        ai_response: str = None,
        manual_response: str = None,
        retry_count: int = None,
        error_message: str = None,
        response_by: str = None,
        response_method: str = None
    ) -> bool:
        """리뷰 답글 정보 업데이트"""
        try:
            update_data = {
                'updated_at': datetime.now().isoformat()
            }
            
            if response_status is not None:
                update_data['response_status'] = response_status
                
            if final_response is not None:
                update_data['final_response'] = final_response
                
            if ai_response is not None:
                update_data['ai_response'] = ai_response
                
            if manual_response is not None:
                update_data['manual_response'] = manual_response
                
            if retry_count is not None:
                update_data['retry_count'] = retry_count
                
            if error_message is not None:
                update_data['error_message'] = error_message
                
            if response_by is not None:
                update_data['response_by'] = response_by
                
            if response_method is not None:
                update_data['response_method'] = response_method
                
            if response_status == 'posted':
                update_data['response_at'] = datetime.now().isoformat()
            
            response = await self._execute_query(
                self.client.table('reviews')
                .update(update_data)
                .eq('review_id', review_id)
            )
            
            return bool(response.data)
            
        except Exception as e:
            logger.error(f"리뷰 답글 업데이트 오류: {e}")
            return False

    async def get_reviews_without_reply(self) -> List[Dict]:
        """AI 답글이 생성되지 않은 리뷰 목록 조회"""
        try:
            # 먼저 현재 데이터베이스 상태를 확인
            logger.info("AI 답글이 필요한 리뷰 조회 시작...")
            
            # 단순한 조건으로 시작: ai_response가 없는 모든 리뷰
            response = await self._execute_query(
                self.client.table('reviews').select(
                    'review_id, store_code, review_content, rating, review_name, platform, response_status, boss_reply_needed, ai_response, created_at, ordered_menu, review_date'
                ).or_(
                    'ai_response.is.null,ai_response.eq.'  # ai_response가 null이거나 빈 문자열
                ).or_(
                    'boss_reply_needed.is.null,boss_reply_needed.eq.false'  # boss_reply_needed가 null이거나 false
                ).or_(
                    'is_deleted.is.null,is_deleted.eq.false'  # is_deleted가 null이거나 false (있다면)
                ).order(
                    'created_at', desc=False  # 오래된 것부터
                ).limit(50)  # 한 번에 최대 50개로 줄임
            )
            
            logger.info(f"조회된 원본 리뷰 수: {len(response.data or [])}개")
            
            # 매장별 자동 답글 정책 확인하여 필터링
            filtered_reviews = []
            if response.data:
                for review in response.data:
                    try:
                        # 매장 자동 답글 정책 확인
                        store_rules = await self.get_store_reply_rules(review['store_code'])
                        
                        # 자동 답글이 활성화되어 있는지 확인
                        if not store_rules.get('auto_reply_enabled', True):
                            logger.debug(f"매장 {review['store_code']} 자동 답글 비활성화됨")
                            continue
                        
                        # 별점별 자동 답글 설정 확인
                        rating = review.get('rating')
                        if rating and 1 <= rating <= 5:
                            rating_key = f'rating_{rating}_reply'
                            if store_rules.get(rating_key, True):  # 기본값은 True (답글 활성화)
                                filtered_reviews.append(review)
                                logger.debug(f"리뷰 {review['review_id']} AI 답글 생성 대상에 포함 (별점: {rating})")
                            else:
                                logger.debug(f"매장 {review['store_code']}의 {rating}점 리뷰 자동 답글 비활성화됨")
                        else:
                            # 별점이 없거나 유효하지 않은 경우 기본적으로 포함
                            filtered_reviews.append(review)
                            logger.debug(f"리뷰 {review['review_id']} AI 답글 생성 대상에 포함 (별점 없음)")
                            
                    except Exception as e:
                        logger.error(f"리뷰 {review.get('review_id')} 필터링 중 오류: {str(e)}")
                        # 오류 발생시 기본적으로 포함
                        filtered_reviews.append(review)
            
            logger.info(f"AI 답글 생성 대상 리뷰: {len(filtered_reviews)}개 (필터링 전: {len(response.data or [])}개)")
            
            return filtered_reviews
            
        except Exception as e:
            logger.error(f"답글 미생성 리뷰 조회 오류: {str(e)}")
            return []

    async def save_ai_reply(self, review_id: str, ai_response: str, quality_score: float = 0.8):
        """AI 답글 저장 및 상태 업데이트"""
        try:
            # 리뷰 업데이트
            update_data = {
                'ai_response': ai_response,
                'response_status': 'generated',
                'response_quality_score': quality_score,
                'processed_at': datetime.now().isoformat()
            }
            
            response = await self._execute_query(
                self.client.table('reviews').update(
                    update_data
                ).eq('review_id', review_id)
            )
            
            # 생성 이력 저장
            history_data = {
                'review_id': review_id,
                'generation_type': 'ai_initial',
                'generated_content': ai_response,
                'quality_score': quality_score,
                'model_version': 'gpt-4o-mini',
                'is_selected': True,
                'created_at': datetime.now().isoformat()
            }
            
            await self._execute_query(
                self.client.table('reply_generation_history').insert(history_data)
            )
            
            return True
            
        except Exception as e:
            logger.error(f"AI 답글 저장 오류: {str(e)}")
            return False

    # 기타 메서드들...
    async def get_store_by_code(self, store_code: str) -> Optional[Dict[str, Any]]:
        """매장 코드로 매장 정보 조회"""
        try:
            response = await self._execute_query(
                self.client.table('platform_reply_rules')
                .select('*')
                .eq('store_code', store_code)
                .eq('is_active', True)
            )
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"매장 조회 오류: {e}")
            return None

    async def insert_review(self, review_data: Dict[str, Any]) -> bool:
        """리뷰 데이터 삽입"""
        try:
            response = await self._execute_query(
                self.client.table('reviews').insert(review_data)
            )
            return bool(response.data)
        except Exception as e:
            logger.error(f"리뷰 삽입 오류: {e}")
            return False

    async def check_review_exists(self, review_id: str) -> bool:
        """리뷰 존재 여부 확인"""
        try:
            response = await self._execute_query(
                self.client.table('reviews')
                .select('review_id')
                .eq('review_id', review_id)
            )
            return bool(response.data)
        except Exception as e:
            logger.error(f"리뷰 존재 확인 오류: {e}")
            return False

    async def update_usage(self, user_code: str, reviews_processed: int = 0) -> bool:
        """사용량 업데이트 (UPSERT 방식)"""
        try:
            current_month = datetime.now().strftime('%Y-%m-01')
            
            # 먼저 기존 레코드 조회
            existing = self.client.table('usage_tracking').select('*').eq(
                'user_code', user_code
            ).eq(
                'tracking_month', current_month
            ).execute()
            
            if existing.data:
                # 기존 레코드가 있으면 UPDATE
                update_data = {
                    'reviews_processed': existing.data[0]['reviews_processed'] + reviews_processed,
                    'last_updated': datetime.now().isoformat()
                }
                
                response = self.client.table('usage_tracking').update(
                    update_data
                ).eq(
                    'user_code', user_code
                ).eq(
                    'tracking_month', current_month
                ).execute()
            else:
                # 없으면 INSERT
                insert_data = {
                    'user_code': user_code,
                    'tracking_month': current_month,
                    'reviews_processed': reviews_processed,
                    'stores_count': 0,
                    'last_updated': datetime.now().isoformat()
                }
                
                response = self.client.table('usage_tracking').insert(
                    insert_data
                ).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"사용량 업데이트 오류: {str(e)}")
            return False


# 파일 끝에 추가
def get_supabase_client() -> Client:
    """
    Supabase 클라이언트 반환 (config에서 import)
    subprocess에서 사용하기 위한 wrapper 함수
    """
    from config.supabase_client import get_supabase_client as get_client
    return get_client()

# 싱글톤 인스턴스
_supabase_service = None

def get_supabase_service() -> SupabaseService:
    """
    Supabase 서비스 싱글톤 인스턴스 반환
    """
    global _supabase_service
    if _supabase_service is None:
        _supabase_service = SupabaseService()
    return _supabase_service