"""
Step 4: ReplyPostingService - 간단 테스트용 구현

실제 플랫폼 연동 대신 더미 응답을 제공하여 API 테스트가 가능하도록 합니다.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import time
import random

from api.services.supabase_service import SupabaseService

logger = logging.getLogger(__name__)


class ReplyPostingService:
    """
    답글 등록 서비스 클래스 (테스트용 간단 구현)
    
    실제 플랫폼 연동 대신 더미 데이터를 사용하여 API 테스트를 지원합니다.
    """
    
    def __init__(self, supabase_service: SupabaseService):
        """
        ReplyPostingService 초기화
        
        Args:
            supabase_service: Supabase 데이터베이스 서비스
        """
        self.supabase = supabase_service
        self.logger = logger
        
        # 테스트용 설정값들
        self.MAX_RETRY_COUNT = 3
        self.RETRY_DELAY_SECONDS = 1  # 테스트용으로 짧게
        self.PROCESSING_TIMEOUT = 30  # 테스트용으로 짧게
        
    async def post_single_reply(
        self, 
        review_id: str, 
        reply_content: str, 
        user_code: str
    ) -> Dict[str, Any]:
        """
        단일 답글을 실제 플랫폼에 등록 (테스트용 더미 구현)
        
        Args:
            review_id: 리뷰 ID
            reply_content: 등록할 답글 내용
            user_code: 답글 등록하는 사용자 코드
            
        Returns:
            Dict: 등록 결과 정보
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"답글 등록 시작: review_id={review_id}, user={user_code}")
            
            # 1. 기본 검증
            if not reply_content or not reply_content.strip():
                return {
                    'success': False,
                    'error': '답글 내용이 비어있습니다',
                    'review_id': review_id
                }
            
            # 2. 테스트용 가짜 처리 시간 (1-3초)
            processing_delay = random.uniform(1, 3)
            await asyncio.sleep(processing_delay)
            
            # 3. 테스트용 성공/실패 결정 (90% 성공률)
            success_rate = 0.9
            is_success = random.random() < success_rate
            
            processing_time = int((time.time() - start_time) * 1000)
            
            if is_success:
                # 성공 케이스
                self.logger.info(f"답글 등록 성공: review_id={review_id}")
                return {
                    'success': True,
                    'review_id': review_id,
                    'platform': 'test_platform',
                    'store_name': 'Test Store',
                    'processing_time': processing_time,
                    'final_status': 'posted',
                    'message': '테스트용 답글 등록 성공'
                }
            else:
                # 실패 케이스
                error_messages = [
                    '네트워크 연결 오류',
                    '플랫폼 서버 응답 없음',
                    '로그인 정보 오류',
                    '임시 서버 오류'
                ]
                error_msg = random.choice(error_messages)
                
                self.logger.warning(f"답글 등록 실패: review_id={review_id}, error={error_msg}")
                return {
                    'success': False,
                    'error': f'테스트용 실패: {error_msg}',
                    'review_id': review_id,
                    'error_details': {'test_mode': True, 'simulated_error': error_msg},
                    'retry_count': 1,
                    'can_retry': True,
                    'processing_time': processing_time
                }
                
        except Exception as e:
            self.logger.error(f"답글 등록 중 예외 발생: {e}")
            
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
        매장의 처리 대기 중인 답글 목록 조회 (테스트용 더미 데이터)
        
        Args:
            store_code: 매장 코드
            limit: 조회할 답글 수
            
        Returns:
            List[Dict]: 대기 중인 답글 목록
        """
        try:
            # 테스트용 더미 데이터 생성
            dummy_reviews = []
            
            for i in range(min(limit, 5)):  # 최대 5개의 더미 리뷰
                dummy_reviews.append({
                    'review_id': f'test_review_{store_code}_{i+1}',
                    'store_code': store_code,
                    'platform': 'test_platform',
                    'review_content': f'테스트 리뷰 내용 {i+1}',
                    'rating': random.randint(1, 5),
                    'review_date': datetime.now().strftime('%Y-%m-%d'),
                    'ai_response': f'테스트용 AI 답글 {i+1}: 안녕하세요! 소중한 리뷰 감사합니다.',
                    'manual_response': None,
                    'response_status': 'ready_to_post',
                    'created_at': datetime.now().isoformat()
                })
            
            self.logger.info(f"더미 대기 답글 {len(dummy_reviews)}개 반환: store_code={store_code}")
            return dummy_reviews
            
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
        특정 매장의 답글들을 일괄 처리 (테스트용)
        
        Args:
            store_code: 매장 코드
            user_code: 처리하는 사용자 코드
            max_replies: 최대 처리할 답글 수
            
        Returns:
            Dict: 처리 결과 요약
        """
        try:
            self.logger.info(f"매장 답글 일괄 처리 시작: store_code={store_code}, max={max_replies}")
            
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
                reply_content = review.get('ai_response') or review.get('manual_response', '')
                
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
                
                # 답글 간 간격 (테스트용으로 짧게)
                await asyncio.sleep(0.5)
            
            self.logger.info(f"매장 답글 일괄 처리 완료: store_code={store_code}, 성공={results['success_count']}, 실패={results['failed_count']}")
            
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
        모든 활성 매장의 답글들을 일괄 처리 (테스트용)
        
        Args:
            user_code: 처리하는 사용자 코드
            max_per_store: 매장당 최대 처리할 답글 수
            
        Returns:
            Dict: 전체 처리 결과 요약
        """
        try:
            self.logger.info(f"전체 매장 답글 일괄 처리 시작: user={user_code}, max_per_store={max_per_store}")
            
            # 테스트용 더미 매장 목록
            test_stores = [
                {'store_code': 'TEST_STORE_001', 'store_name': '테스트 맛집1', 'platform': 'baemin'},
                {'store_code': 'TEST_STORE_002', 'store_name': '테스트 치킨집', 'platform': 'yogiyo'},
                {'store_code': 'TEST_STORE_003', 'store_name': '테스트 피자집', 'platform': 'coupang'}
            ]
            
            # 전체 결과 집계
            total_results = {
                'processed_stores': 0,
                'total_processed': 0,
                'total_success': 0,
                'total_failed': 0,
                'store_results': []
            }
            
            # 각 매장별 순차 처리
            for store in test_stores:
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
                await asyncio.sleep(0.3)
            
            self.logger.info(f"전체 매장 답글 처리 완료: 총 {total_results['total_processed']}개 처리")
            
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
        답글 처리 상태 상세 정보 조회 (테스트용)
        
        Args:
            review_id: 리뷰 ID
            
        Returns:
            Dict: 상태 추적 정보
        """
        try:
            # 테스트용 더미 상태 정보
            dummy_history = [
                {
                    'id': 1,
                    'generation_type': 'ai_initial',
                    'generated_content': '테스트용 AI 답글입니다.',
                    'quality_score': 0.85,
                    'processing_time_ms': 1500,
                    'token_usage': 150,
                    'is_selected': True,
                    'created_at': datetime.now().isoformat()
                }
            ]
            
            stats = {
                'total_attempts': len(dummy_history),
                'last_attempt': dummy_history[0] if dummy_history else None,
                'processing_time_total': sum(h.get('processing_time_ms', 0) for h in dummy_history),
                'token_usage_total': sum(h.get('token_usage', 0) for h in dummy_history)
            }
            
            return {
                'review_id': review_id,
                'current_status': 'ready_to_post',
                'generation_history': dummy_history,
                'statistics': stats,
                'can_retry': True,
                'last_updated': datetime.now().isoformat(),
                'test_mode': True
            }
            
        except Exception as e:
            self.logger.error(f"답글 상태 조회 중 오류: {e}")
            return {'error': str(e), 'test_mode': True}


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
