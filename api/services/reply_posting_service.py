"""
Step 5: ReplyPostingService - 실제 플랫폼 연동 구현

배달의민족, 요기요, 쿠팡이츠 플랫폼에 실제 답글을 등록하는 서비스
Playwright를 활용한 브라우저 자동화로 실제 플랫폼과 연동
"""
import asyncio
import logging
import traceback
import time
import json
import sys
import os
import threading
import queue
from typing import Dict, List, Optional, Any
from datetime import datetime

from api.services.supabase_service import SupabaseService
from api.services.encryption import decrypt_password

logger = logging.getLogger(__name__)


class ReplyPostingService:
    """
    실제 플랫폼 연동 답글 등록 서비스 클래스
    
    Step 4에서 구현된 API와 호환되며, 실제 브라우저 자동화를 통해
    배민, 요기요, 쿠팡이츠에 답글을 등록합니다.
    """
    
    def __init__(self, supabase_service: SupabaseService):
        """
        ReplyPostingService 초기화
        
        Args:
            supabase_service: Supabase 데이터베이스 서비스
        """
        self.supabase = supabase_service
        self.logger = logger
        
        # 실제 운영 설정값들
        self.MAX_RETRY_COUNT = 3
        self.RETRY_DELAY_SECONDS = 5
        self.PROCESSING_TIMEOUT = 120  # 2분
        self.BROWSER_TIMEOUT = 30  # 브라우저 작업 타임아웃
        
        # 지원하는 플랫폼 목록
        self.SUPPORTED_PLATFORMS = ['baemin', 'yogiyo', 'coupang']
        
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
            self.logger.info(f"실제 답글 등록 시작: review_id={review_id}, user={user_code}")
            
            # 1. 기본 검증
            validation_result = self._validate_reply_request(review_id, reply_content, user_code)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': validation_result['error'],
                    'review_id': review_id
                }
            
            # 2. 리뷰 정보 및 매장 정보 조회
            review_data = await self._get_review_data(review_id)
            if not review_data:
                return {
                    'success': False,
                    'error': '리뷰 정보를 찾을 수 없습니다',
                    'review_id': review_id
                }
            
            # 3. 매장 로그인 정보 조회
            store_config = await self._get_store_config(review_data['store_code'])
            if not store_config:
                return {
                    'success': False,
                    'error': '매장 정보를 찾을 수 없습니다',
                    'review_id': review_id
                }
            
            # 4. 플랫폼 지원 여부 확인
            platform = review_data.get('platform', '').lower()
            if platform not in self.SUPPORTED_PLATFORMS:
                return {
                    'success': False,
                    'error': f'지원하지 않는 플랫폼입니다: {platform}',
                    'review_id': review_id,
                    'platform': platform
                }
            
            # 5. 실제 답글 등록 수행
            posting_result = await self._perform_reply_posting(
                review_data, 
                store_config, 
                reply_content,
                user_code
            )
            
            # 6. 결과 DB 업데이트
            await self._update_reply_status(review_id, posting_result, user_code)
            
            processing_time = int((time.time() - start_time) * 1000)
            posting_result['processing_time'] = processing_time
            
            if posting_result['success']:
                self.logger.info(f"실제 답글 등록 성공: review_id={review_id}, platform={platform}")
            else:
                self.logger.warning(f"답글 등록 실패: review_id={review_id}, error={posting_result.get('error')}")
            
            return posting_result
            
        except Exception as e:
            error_msg = f"답글 등록 중 예외 발생: {str(e)}"
            self.logger.error(f"{error_msg}\n{traceback.format_exc()}")
            
            # 예외 발생시 DB 상태 업데이트
            try:
                await self._update_reply_status(review_id, {
                    'success': False,
                    'error': error_msg,
                    'final_status': 'failed'
                }, user_code)
            except:
                pass  # DB 업데이트 실패는 무시
            
            return {
                'success': False,
                'error': error_msg,
                'review_id': review_id,
                'processing_time': int((time.time() - start_time) * 1000)
            }

    def _validate_reply_request(self, review_id: str, reply_content: str, user_code: str) -> Dict[str, Any]:
        """
        답글 등록 요청 유효성 검증
        
        Args:
            review_id: 리뷰 ID
            reply_content: 답글 내용
            user_code: 사용자 코드
            
        Returns:
            Dict: {'valid': bool, 'error': str}
        """
        try:
            # 필수 파라미터 검증
            if not review_id or not review_id.strip():
                return {'valid': False, 'error': '리뷰 ID가 없습니다'}
            
            if not reply_content or not reply_content.strip():
                return {'valid': False, 'error': '답글 내용이 비어있습니다'}
                
            if not user_code or not user_code.strip():
                return {'valid': False, 'error': '사용자 코드가 없습니다'}
            
            # 답글 길이 검증
            if len(reply_content.strip()) > 1000:
                return {'valid': False, 'error': '답글 내용이 너무 깁니다 (최대 1000자)'}
                
            if len(reply_content.strip()) < 2:
                return {'valid': False, 'error': '답글 내용이 너무 짧습니다 (최소 2자)'}
            
            return {'valid': True, 'error': ''}
            
        except Exception as e:
            return {'valid': False, 'error': f'검증 중 오류: {str(e)}'}
    
    async def _get_review_data(self, review_id: str) -> Optional[Dict[str, Any]]:
        """
        리뷰 데이터 조회
        
        Args:
            review_id: 리뷰 ID
            
        Returns:
            Dict: 리뷰 데이터 (store_code, platform, review_content 등)
        """
        try:
            # Supabase에서 리뷰 정보 조회
            review_data = await self.supabase.get_review_by_id(review_id)
            
            if not review_data:
                self.logger.warning(f"리뷰 조회 실패: review_id={review_id}")
                return None
            
            # 필수 필드 확인
            required_fields = ['store_code', 'platform']
            for field in required_fields:
                if not review_data.get(field):
                    self.logger.warning(f"리뷰 데이터 누락 필드: {field}, review_id={review_id}")
                    return None
            
            self.logger.info(f"리뷰 데이터 조회 성공: review_id={review_id}, platform={review_data.get('platform')}")
            return review_data
            
        except Exception as e:
            self.logger.error(f"리뷰 데이터 조회 중 오류: {e}")
            return None
    
    async def _get_store_config(self, store_code: str) -> Optional[Dict[str, Any]]:
        """
        매장 설정 정보 조회 (로그인 정보 포함)
        
        Args:
            store_code: 매장 코드
            
        Returns:
            Dict: 매장 설정 정보
        """
        try:
            # Supabase에서 매장 정보 조회 - get_store_reply_rules 사용
            store_data = await self.supabase.get_store_reply_rules(store_code)
            
            if not store_data:
                self.logger.warning(f"매장 조회 실패: store_code={store_code}")
                return None
            
            # 필수 필드 확인
            required_fields = ['platform_id', 'platform_pw', 'platform', 'store_name']
            for field in required_fields:
                if field not in store_data or not store_data.get(field):
                    # platform_id, platform_pw는 platform_reply_rules 테이블에 있을 것이므로
                    # 추가로 조회가 필요할 수 있습니다.
                    self.logger.warning(f"매장 데이터 누락 필드: {field}, store_code={store_code}")
                    
            # 로그인 정보 조회를 위해 platform_reply_rules에서 직접 조회
            try:
                query = self.supabase.client.table('platform_reply_rules').select('*').eq('store_code', store_code)
                response = await self.supabase._execute_query(query)
                
                if response.data:
                    platform_data = response.data[0]
                    store_data['platform_id'] = platform_data.get('platform_id')
                    store_data['platform_pw'] = platform_data.get('platform_pw')
                    store_data['platform_code'] = platform_data.get('platform_code')
                    
                    # 로그인 비밀번호 복호화
                    if store_data['platform_pw']:
                        try:
                            decrypted_password = decrypt_password(store_data['platform_pw'])
                            store_data['platform_pw'] = decrypted_password
                        except Exception as e:
                            self.logger.error(f"비밀번호 복호화 실패: {e}")
                            return None
                
            except Exception as e:
                self.logger.error(f"플랫폼 정보 조회 오류: {e}")
                return None
            
            self.logger.info(f"매장 설정 조회 성공: store_code={store_code}, platform={store_data.get('platform')}")
            return store_data
            
        except Exception as e:
            self.logger.error(f"매장 설정 조회 중 오류: {e}")
            return None

    async def _perform_reply_posting(
        self,
        review_data: Dict[str, Any],
        store_config: Dict[str, Any],
        reply_content: str,
        user_code: str
    ) -> Dict[str, Any]:
        """
        실제 답글 등록 수행
        
        Args:
            review_data: 리뷰 데이터
            store_config: 매장 설정 정보
            reply_content: 답글 내용
            user_code: 사용자 코드
            
        Returns:
            Dict: 등록 결과
        """
        platform = store_config['platform'].lower()
        
        try:
            self.logger.info(f"플랫폼 답글 등록 시작: platform={platform}, review_id={review_data.get('review_id')}")
            
            # 현재는 배민만 지원
            if platform == 'baemin':
                return await self._post_baemin_reply(review_data, store_config, reply_content)
            elif platform == 'yogiyo':
                return {
                    'success': False,
                    'error': '요기요 답글 등록은 아직 구현되지 않았습니다',
                    'review_id': review_data.get('review_id'),
                    'platform': platform
                }
            elif platform == 'coupang':
                return {
                    'success': False,
                    'error': '쿠팡이츠 답글 등록은 아직 구현되지 않았습니다',
                    'review_id': review_data.get('review_id'),
                    'platform': platform
                }
            else:
                return {
                    'success': False,
                    'error': f'지원하지 않는 플랫폼: {platform}',
                    'review_id': review_data.get('review_id'),
                    'platform': platform
                }
                
        except Exception as e:
            error_msg = f"답글 등록 수행 중 오류: {str(e)}"
            self.logger.error(f"{error_msg}\n{traceback.format_exc()}")
            return {
                'success': False,
                'error': error_msg,
                'review_id': review_data.get('review_id'),
                'platform': platform
            }

    async def _post_baemin_reply(
        self,
        review_data: Dict[str, Any],
        store_config: Dict[str, Any],
        reply_content: str
    ) -> Dict[str, Any]:
        """
        배민 답글 등록
        
        Args:
            review_data: 리뷰 데이터
            store_config: 매장 설정
            reply_content: 답글 내용
            
        Returns:
            Dict: 등록 결과
        """
        review_id = review_data.get('review_id', 'unknown')
        
        try:
            self.logger.info(f"배민 답글 등록 시작: review_id={review_id}")
            
            # threading을 사용한 간단한 해결책
            import threading
            import queue
            
            result_queue = queue.Queue()
            
            def run_browser_task():
                """별도 스레드에서 실행할 브라우저 작업"""
                reply_manager = None
                try:
                    # 동기 import를 여기서 수행
                    from api.crawlers.baemin_reply_manager import BaeminReplyManager
                    
                    # BaeminReplyManager 인스턴스 생성
                    reply_manager = BaeminReplyManager(store_config)
                    
                    # 브라우저 설정 및 초기화
                    browser_setup = reply_manager.setup_browser(headless=False)  # 디버깅을 위해 headless=False
                    if not browser_setup:
                        result_queue.put({
                            'success': False,
                            'error': '브라우저 초기화 실패 - Playwright가 설치되지 않았거나 Chromium이 없습니다',
                            'review_id': review_id,
                            'platform': 'baemin',
                            'error_details': {
                                'message': 'playwright install chromium 명령을 실행해주세요'
                            }
                        })
                        return
                    
                    # 로그인
                    login_success, login_message = reply_manager.login_to_platform()
                    if not login_success:
                        result_queue.put({
                            'success': False,
                            'error': f'로그인 실패: {login_message}',
                            'review_id': review_id,
                            'platform': 'baemin'
                        })
                        return
                    
                    # 리뷰 관리 페이지로 이동
                    nav_success, nav_message = reply_manager.navigate_to_reviews_page()
                    if not nav_success:
                        result_queue.put({
                            'success': False,
                            'error': f'리뷰 페이지 이동 실패: {nav_message}',
                            'review_id': review_id,
                            'platform': 'baemin'
                        })
                        return
                    
                    # 답글 등록 수행
                    reply_result = reply_manager.manage_reply(
                        review_id=review_id,
                        reply_text=reply_content,
                        action="auto"
                    )
                    
                    if reply_result['success']:
                        result_queue.put({
                            'success': True,
                            'review_id': review_id,
                            'platform': 'baemin',
                            'store_name': store_config.get('store_name', ''),
                            'final_status': 'posted',
                            'action_taken': reply_result.get('action_taken', 'posted'),
                            'message': reply_result.get('message', '답글 등록 성공')
                        })
                    else:
                        result_queue.put({
                            'success': False,
                            'error': reply_result.get('message', '답글 등록 실패'),
                            'review_id': review_id,
                            'platform': 'baemin',
                            'error_details': reply_result
                        })
                        
                except Exception as e:
                    result_queue.put({
                        'success': False,
                        'error': f'브라우저 작업 중 오류: {str(e)}',
                        'review_id': review_id,
                        'platform': 'baemin',
                        'error_details': {
                            'exception': str(e),
                            'type': type(e).__name__
                        }
                    })
                finally:
                    # 브라우저 정리
                    if reply_manager:
                        try:
                            reply_manager.close_browser()
                        except:
                            pass
            
            # 스레드 시작
            thread = threading.Thread(target=run_browser_task)
            thread.start()
            
            # 스레드 완료 대기 (타임아웃 설정)
            thread.join(timeout=self.PROCESSING_TIMEOUT)
            
            if thread.is_alive():
                # 타임아웃 발생
                self.logger.error("브라우저 작업 타임아웃")
                return {
                    'success': False,
                    'error': '브라우저 작업 타임아웃',
                    'review_id': review_id,
                    'platform': 'baemin'
                }
            
            # 결과 가져오기
            try:
                result = result_queue.get_nowait()
            except queue.Empty:
                result = {
                    'success': False,
                    'error': '결과를 가져올 수 없습니다',
                    'review_id': review_id,
                    'platform': 'baemin'
                }
            
            # 로깅
            if result['success']:
                self.logger.info(f"배민 답글 등록 성공: review_id={review_id}, action={result.get('action_taken')}")
            else:
                self.logger.warning(f"배민 답글 등록 실패: review_id={review_id}, error={result.get('error')}")
            
            return result
            
        except Exception as e:
            error_msg = f"배민 답글 등록 중 예외: {str(e)}"
            self.logger.error(f"{error_msg}\n{traceback.format_exc()}")
            return {
                'success': False,
                'error': error_msg,
                'review_id': review_id,
                'platform': 'baemin',
                'error_details': {
                    'exception': str(e),
                    'traceback': traceback.format_exc()
                }
            }
            
    async def _update_reply_status(
        self,
        review_id: str,
        posting_result: Dict[str, Any],
        user_code: str
    ) -> None:
        """
        답글 등록 결과를 DB에 업데이트
        
        Args:
            review_id: 리뷰 ID
            posting_result: 답글 등록 결과
            user_code: 사용자 코드
        """
        try:
            status = posting_result.get('final_status', 'failed' if not posting_result['success'] else 'posted')
            
            await self.supabase.update_review_response(
                review_id,
                response_status=status,
                response_by=user_code,
                error_message=posting_result.get('error') if not posting_result['success'] else None,
                response_method='manual' if posting_result['success'] else None
            )
            
            self.logger.info(f"리뷰 상태 업데이트 완료: review_id={review_id}, status={status}")
            
        except Exception as e:
            self.logger.error(f"리뷰 상태 업데이트 실패: review_id={review_id}, error={e}")

    # Step 4 호환성을 위한 기존 메서드들 (간소화된 구현)
    async def get_pending_replies(self, store_code: str, limit: int = 10) -> List[Dict[str, Any]]:
        """매장의 처리 대기 중인 답글 목록 조회"""
        try:
            result = await self.supabase.get_pending_reviews(store_code, limit)
            return result.get('data', []) if result else []
        except Exception as e:
            self.logger.error(f"대기 답글 조회 중 오류: {e}")
            return []

    async def process_store_replies(self, store_code: str, user_code: str, max_replies: int = 10) -> Dict[str, Any]:
        """특정 매장의 답글들을 일괄 처리"""
        try:
            pending_reviews = await self.get_pending_replies(store_code, max_replies)
            results = {'processed_count': 0, 'success_count': 0, 'failed_count': 0, 'details': []}
            
            for review in pending_reviews:
                reply_content = review.get('ai_response') or review.get('manual_response', '')
                if not reply_content:
                    continue
                    
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
                
                await asyncio.sleep(2)  # 답글 간 간격
            
            return {'success': True, 'store_code': store_code, **results}
            
        except Exception as e:
            self.logger.error(f"매장 답글 일괄 처리 중 오류: {e}")
            return {'success': False, 'store_code': store_code, 'error': str(e)}

    async def process_all_stores_replies(self, user_code: str, max_per_store: int = 5) -> Dict[str, Any]:
        """모든 활성 매장의 답글들을 일괄 처리"""
        try:
            # 사용자의 활성 매장 목록 조회
            stores_result = await self.supabase.get_user_stores(user_code)
            stores = stores_result.get('data', []) if stores_result else []
            
            total_results = {'processed_stores': 0, 'total_processed': 0, 'total_success': 0, 'total_failed': 0, 'store_results': []}
            
            for store in stores:
                store_code = store.get('store_code')
                if not store_code:
                    continue
                    
                store_result = await self.process_store_replies(store_code, user_code, max_per_store)
                
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
            
            return {'success': True, **total_results}
            
        except Exception as e:
            self.logger.error(f"전체 매장 답글 처리 중 오류: {e}")
            return {'success': False, 'error': str(e)}

    async def get_reply_tracking_status(self, review_id: str) -> Dict[str, Any]:
        """답글 처리 상태 상세 정보 조회"""
        try:
            result = await self.supabase.get_review_status(review_id)
            return result.get('data', {}) if result else {}
        except Exception as e:
            self.logger.error(f"답글 상태 조회 중 오류: {e}")
            return {'error': str(e)}


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