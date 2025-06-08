"""
Step 3 & 4: ReplyPostingService - 실제 플랫폼 답글 등록 서비스

이 서비스는 AI로 생성된 답글을 실제 플랫폼(배민, 요기요, 쿠팡이츠)에 등록하는 
핵심 비즈니스 로직을 담당합니다.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import time

from api.services.supabase_service import SupabaseService
from api.crawlers.baemin_reply_manager import BaeminReplyManager
from api.crawlers.reply_manager import ReplyManager

logger = logging.getLogger(__name__)


class ReplyPostingService:
    """
    답글 등록 서비스 클래스
    
    주요 기능:
    1. 단일 답글 등록
    2. 매장별 일괄 답글 등록  
    3. 전체 매장 일괄 답글 등록
    4. 답글 처리 상태 추적
    5. 에러 처리 및 재시도 로직
    """
    
    def __init__(self, supabase_service: SupabaseService):
        """
        ReplyPostingService 초기화
        
        Args:
            supabase_service: Supabase 데이터베이스 서비스
        """
        self.supabase = supabase_service
        self.logger = logger
        
        # 플랫폼별 답글 매니저 초기화
        self.reply_managers = {
            'baemin': BaeminReplyManager(),
            'yogiyo': ReplyManager(),  # 요기요용 (기본 매니저)
            'coupang': ReplyManager(), # 쿠팡이츠용 (기본 매니저)
        }
        
        # 설정값들
        self.MAX_RETRY_COUNT = 3
        self.RETRY_DELAY_SECONDS = 5
        self.PROCESSING_TIMEOUT = 300  # 5분
        
    async def post_single_reply(
        self, 
        review_id: str, 
        reply_content: str, 
        user_code: str
    ) -> Dict[str, Any]:
        """
        단일 답글을 실제 플랫폼에 등록
        
        Args:
            review_id: 리뷰 ID
            reply_content: 등록할 답글 내용
            user_code: 답글 등록하는 사용자 코드
            
        Returns:
            Dict: 등록 결과 정보
        """
        start_time = time.time()
        
        try:
            # 1. 리뷰 정보 조회
            review = await self.supabase.get_review_by_id(review_id)
            if not review:
                return {
                    'success': False,
                    'error': '리뷰를 찾을 수 없습니다',
                    'review_id': review_id
                }
            
            # 2. 매장 정보 및 로그인 정보 조회
            store_info = await self.supabase.get_store_reply_rules(review['store_code'])
            if not store_info:
                return {
                    'success': False,
                    'error': '매장 정보를 찾을 수 없습니다',
                    'review_id': review_id
                }
            
            # 3. 답글 등록 전 검증
            validation_result = await self._validate_reply_posting(review, reply_content, store_info)
            if not validation_result['is_valid']:
                return {
                    'success': False,
                    'error': f'답글 등록 검증 실패: {validation_result[\"error\"]}',
                    'review_id': review_id,
                    'error_details': validation_result
                }
            
            # 4. 상태를 'processing'으로 업데이트
            await self.supabase.update_review_status(
                review_id=review_id,
                status='processing',
                reply_by=user_code
            )
            
            # 5. 플랫폼별 답글 등록 실행
            platform = store_info.get('platform', '')
            posting_result = await self._execute_reply_posting(
                review=review,
                reply_content=reply_content,
                store_info=store_info,
                platform=platform
            )
            
            # 6. 결과에 따른 상태 업데이트
            processing_time = int((time.time() - start_time) * 1000)
            
            if posting_result['success']:
                # 성공시 상태 업데이트
                await self.supabase.update_review_status(
                    review_id=review_id,
                    status='posted',
                    reply_content=reply_content,
                    reply_type='manual',  # API를 통한 수동 등록
                    reply_by=user_code,
                    final_response=reply_content
                )
                
                # 매장 통계 업데이트
                await self._update_store_stats(store_info['store_code'])
                
                return {
                    'success': True,
                    'review_id': review_id,
                    'platform': platform,
                    'store_name': store_info.get('store_name', ''),
                    'processing_time': processing_time,
                    'final_status': 'posted'
                }
            else:
                # 실패시 상태 업데이트
                await self.supabase.update_review_status(
                    review_id=review_id,
                    status='failed',
                    error_message=posting_result.get('error', '알 수 없는 오류')
                )
                
                return {
                    'success': False,
                    'error': posting_result.get('error', '알 수 없는 오류'),
                    'review_id': review_id,
                    'error_details': posting_result,
                    'retry_count': posting_result.get('retry_count', 0),
                    'can_retry': posting_result.get('can_retry', True),
                    'processing_time': processing_time
                }
                
        except Exception as e:
            self.logger.error(f"답글 등록 중 예외 발생: {e}")
            
            # 에러 상태로 업데이트
            await self.supabase.update_review_status(
                review_id=review_id,
                status='failed',
                error_message=str(e)
            )
            
            return {
                'success': False,
                'error': f'시스템 오류: {str(e)}',
                'review_id': review_id,
                'processing_time': int((time.time() - start_time) * 1000)
            }
    
    async def get_pending_replies(
        self, 
        store_code: str, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        매장의 처리 대기 중인 답글 목록 조회
        
        Args:
            store_code: 매장 코드
            limit: 조회할 답글 수
            
        Returns:
            List[Dict]: 대기 중인 답글 목록
        """
        try:
            # 처리 가능한 상태의 리뷰들 조회
            pending_statuses = ['ready_to_post', 'generated']
            reviews = await self.supabase.get_reviews_by_store(
                store_code=store_code,
                status=pending_statuses,
                limit=limit
            )
            
            # 답글 내용이 있는 것만 필터링
            valid_reviews = []
            for review in reviews:
                reply_content = review.get('ai_response') or review.get('manual_response')
                if reply_content and reply_content.strip():
                    valid_reviews.append(review)
            
            return valid_reviews
            
        except Exception as e:
            self.logger.error(f"대기 답글 조회 중 오류: {e}")
            return []
    
    async def process_store_replies(
        self, 
        store_code: str, 
        user_code: str, 
        max_replies: int = 10
    ) -> Dict[str, Any]:
        """
        특정 매장의 답글들을 일괄 처리
        
        Args:
            store_code: 매장 코드
            user_code: 처리하는 사용자 코드
            max_replies: 최대 처리할 답글 수
            
        Returns:
            Dict: 처리 결과 요약
        """
        try:
            # 대기 중인 답글 조회
            pending_reviews = await self.get_pending_replies(store_code, max_replies)
            
            if not pending_reviews:
                return {
                    'success': True,
                    'store_code': store_code,
                    'processed_count': 0,
                    'success_count': 0,
                    'failed_count': 0,
                    'message': '처리할 답글이 없습니다'
                }
            
            # 각 답글 순차 처리
            results = {
                'processed_count': 0,
                'success_count': 0,
                'failed_count': 0,
                'details': []
            }
            
            for review in pending_reviews:
                reply_content = review.get('ai_response') or review.get('manual_response')
                
                # 개별 답글 등록
                result = await self.post_single_reply(
                    review_id=review['review_id'],
                    reply_content=reply_content,
                    user_code=user_code
                )
                
                results['processed_count'] += 1
                
                if result['success']:
                    results['success_count'] += 1
                else:
                    results['failed_count'] += 1
                
                results['details'].append({
                    'review_id': review['review_id'],
                    'success': result['success'],
                    'error': result.get('error') if not result['success'] else None
                })
                
                # 답글 간 간격 (플랫폼 부하 방지)
                await asyncio.sleep(2)
            
            return {
                'success': True,
                'store_code': store_code,
                **results
            }
            
        except Exception as e:
            self.logger.error(f"매장 답글 일괄 처리 중 오류: {e}")
            return {
                'success': False,
                'store_code': store_code,
                'error': str(e)
            }
    
    async def process_all_stores_replies(
        self, 
        user_code: str, 
        max_per_store: int = 5
    ) -> Dict[str, Any]:
        """
        모든 활성 매장의 답글들을 일괄 처리
        
        Args:
            user_code: 처리하는 사용자 코드
            max_per_store: 매장당 최대 처리할 답글 수
            
        Returns:
            Dict: 전체 처리 결과 요약
        """
        try:
            # 활성 매장 목록 조회
            active_stores = await self.supabase.get_all_active_stores()
            
            if not active_stores:
                return {
                    'success': True,
                    'processed_stores': 0,
                    'total_processed': 0,
                    'message': '활성 매장이 없습니다'
                }
            
            # 전체 결과 집계
            total_results = {
                'processed_stores': 0,
                'total_processed': 0,
                'total_success': 0,
                'total_failed': 0,
                'store_results': []
            }
            
            # 각 매장별 순차 처리
            for store in active_stores:
                store_code = store['store_code']
                
                # 매장별 처리
                store_result = await self.process_store_replies(
                    store_code=store_code,
                    user_code=user_code,
                    max_replies=max_per_store
                )
                
                if store_result['success'] and store_result['processed_count'] > 0:
                    total_results['processed_stores'] += 1
                    total_results['total_processed'] += store_result['processed_count']
                    total_results['total_success'] += store_result['success_count']
                    total_results['total_failed'] += store_result['failed_count']
                
                total_results['store_results'].append({
                    'store_code': store_code,
                    'store_name': store.get('store_name', ''),
                    'platform': store.get('platform', ''),
                    'processed': store_result['processed_count'],
                    'success': store_result['success_count'],
                    'failed': store_result['failed_count']
                })
                
                # 매장 간 간격
                await asyncio.sleep(1)
            
            return {
                'success': True,
                **total_results
            }
            
        except Exception as e:
            self.logger.error(f"전체 매장 답글 처리 중 오류: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_reply_tracking_status(self, review_id: str) -> Dict[str, Any]:
        """
        답글 처리 상태 상세 정보 조회
        
        Args:
            review_id: 리뷰 ID
            
        Returns:
            Dict: 상태 추적 정보
        """
        try:
            # 기본 리뷰 정보
            review = await self.supabase.get_review_by_id(review_id)
            if not review:
                return {'error': '리뷰를 찾을 수 없습니다'}
            
            # 답글 생성 이력 조회
            generation_history = await self.supabase.get_reply_generation_history(review_id)
            
            # 처리 통계
            stats = {
                'total_attempts': len(generation_history),
                'last_attempt': generation_history[0] if generation_history else None,
                'processing_time_total': sum(h.get('processing_time_ms', 0) for h in generation_history),
                'token_usage_total': sum(h.get('token_usage', 0) for h in generation_history)
            }
            
            return {
                'review_id': review_id,
                'current_status': review.get('response_status'),
                'generation_history': generation_history,
                'statistics': stats,
                'can_retry': review.get('response_status') in ['failed', 'manual_required'],
                'last_updated': review.get('updated_at')
            }
            
        except Exception as e:
            self.logger.error(f"답글 상태 조회 중 오류: {e}")
            return {'error': str(e)}
    
    # ====== Private Methods ======
    
    async def _validate_reply_posting(
        self, 
        review: Dict[str, Any], 
        reply_content: str, 
        store_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        답글 등록 전 검증
        """
        try:
            # 1. 기본 검증
            if not reply_content or not reply_content.strip():
                return {'is_valid': False, 'error': '답글 내용이 비어있습니다'}
            
            # 2. 길이 검증
            max_length = store_info.get('max_length', 300)
            if len(reply_content) > max_length:
                return {'is_valid': False, 'error': f'답글이 최대 길이({max_length}자)를 초과했습니다'}
            
            # 3. 금지 단어 검증
            prohibited_words = store_info.get('prohibited_words', [])
            for word in prohibited_words:
                if word and word in reply_content:
                    return {'is_valid': False, 'error': f'금지된 단어가 포함되어 있습니다: {word}'}
            
            # 4. 매장 설정 검증
            if not store_info.get('auto_reply_enabled', True):
                return {'is_valid': False, 'error': '해당 매장은 자동 답글이 비활성화되어 있습니다'}
            
            # 5. 로그인 정보 검증
            if not store_info.get('platform_id') or not store_info.get('platform_pw'):
                return {'is_valid': False, 'error': '매장 로그인 정보가 설정되지 않았습니다'}
            
            return {'is_valid': True}
            
        except Exception as e:
            return {'is_valid': False, 'error': f'검증 중 오류: {str(e)}'}
    
    async def _execute_reply_posting(
        self, 
        review: Dict[str, Any], 
        reply_content: str, 
        store_info: Dict[str, Any], 
        platform: str
    ) -> Dict[str, Any]:
        """
        실제 플랫폼에 답글 등록 실행
        """
        try:
            # 플랫폼별 답글 매니저 선택
            reply_manager = self.reply_managers.get(platform)
            if not reply_manager:
                return {
                    'success': False,
                    'error': f'지원하지 않는 플랫폼입니다: {platform}',
                    'can_retry': False
                }
            
            # 답글 등록 시도 (재시도 로직 포함)
            for attempt in range(self.MAX_RETRY_COUNT):
                try:
                    # 실제 답글 등록 호출
                    result = await reply_manager.post_reply(
                        store_login_info={
                            'platform_id': store_info['platform_id'],
                            'platform_pw': store_info['platform_pw'],
                            'platform_code': store_info['platform_code']
                        },
                        review_data={
                            'review_id': review['review_id'],
                            'platform_review_id': review.get('platform_review_id', ''),
                            'review_content': review.get('review_content', ''),
                            'rating': review.get('rating', 0)
                        },
                        reply_content=reply_content
                    )
                    
                    if result.get('success'):
                        return {
                            'success': True,
                            'platform_response': result,
                            'attempt_number': attempt + 1
                        }
                    else:
                        # 재시도 가능한 오류인지 확인
                        if not result.get('can_retry', True) or attempt == self.MAX_RETRY_COUNT - 1:
                            return {
                                'success': False,
                                'error': result.get('error', '알 수 없는 오류'),
                                'retry_count': attempt + 1,
                                'can_retry': False,
                                'platform_response': result
                            }
                        
                        # 재시도 대기
                        await asyncio.sleep(self.RETRY_DELAY_SECONDS)
                        
                except Exception as attempt_error:
                    self.logger.warning(f"답글 등록 시도 {attempt + 1} 실패: {attempt_error}")
                    
                    if attempt == self.MAX_RETRY_COUNT - 1:
                        return {
                            'success': False,
                            'error': f'최대 재시도 횟수 초과: {str(attempt_error)}',
                            'retry_count': attempt + 1,
                            'can_retry': True
                        }
                    
                    await asyncio.sleep(self.RETRY_DELAY_SECONDS)
            
            return {
                'success': False,
                'error': '최대 재시도 횟수를 초과했습니다',
                'retry_count': self.MAX_RETRY_COUNT,
                'can_retry': True
            }
            
        except Exception as e:
            self.logger.error(f"답글 등록 실행 중 오류: {e}")
            return {
                'success': False,
                'error': f'시스템 오류: {str(e)}',
                'can_retry': True
            }
    
    async def _update_store_stats(self, store_code: str) -> None:
        """
        매장 통계 업데이트 (답글 등록 성공시)
        """
        try:
            # 매장의 마지막 답글 등록 시간 업데이트
            await self.supabase._execute_query(
                self.supabase.client.table('platform_reply_rules')
                .update({
                    'last_reply': datetime.now().isoformat(),
                    'total_reviews_processed': self.supabase.client.table('platform_reply_rules').select('total_reviews_processed').eq('store_code', store_code).single().data.get('total_reviews_processed', 0) + 1,
                    'updated_at': datetime.now().isoformat()
                })
                .eq('store_code', store_code)
            )
            
        except Exception as e:
            self.logger.warning(f"매장 통계 업데이트 실패: {e}")


# 싱글톤 패턴으로 서비스 인스턴스 관리
_reply_posting_service_instance = None

def get_reply_posting_service(supabase_service: SupabaseService) -> ReplyPostingService:
    """
    ReplyPostingService 싱글톤 인스턴스 반환
    """
    global _reply_posting_service_instance
    
    if _reply_posting_service_instance is None:
        _reply_posting_service_instance = ReplyPostingService(supabase_service)
    
    return _reply_posting_service_instance
