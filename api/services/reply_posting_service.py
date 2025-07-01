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
import subprocess
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path

from api.services.supabase_service import SupabaseService
from api.services.encryption import decrypt_password

logger = logging.getLogger(__name__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
        self.PROCESSING_TIMEOUT = 180  # 3분으로 증가
        self.BROWSER_TIMEOUT = 60  # 브라우저 작업 타임아웃 증가
        
        # 지원하는 플랫폼 목록
        self.SUPPORTED_PLATFORMS = ['baemin', 'yogiyo', 'coupang', 'naver']
        
        # 로그 디렉토리 생성
        self.log_dir = Path("C:/Review_playwright/logs")
        self.log_dir.mkdir(exist_ok=True)
    
    async def post_reply(self, review_id: str, reply_type: str = "ai") -> dict:
        """
        답글 등록 (API 호환성을 위한 메인 함수)
        
        Args:
            review_id: 리뷰 ID
            reply_type: 답글 유형 (ai/manual)
            
        Returns:
            Dict: 등록 결과
        """
        try:
            self.logger.info(f"답글 등록 요청: review_id={review_id}, type={reply_type}")
            
            # 리뷰 정보 조회
            review = await self._get_review_data(review_id)
            if not review:
                return {
                    'success': False,
                    'error': '리뷰를 찾을 수 없습니다',
                    'review_id': review_id
                }
            
            # 매장 정보 조회
            store = await self._get_store_config(review['store_code'])
            if not store:
                return {
                    'success': False,
                    'error': '매장 정보를 찾을 수 없습니다',
                    'review_id': review_id
                }
            
            # 답글 내용 결정
            if reply_type == "ai":
                reply_content = review.get('ai_response', '')
            else:
                reply_content = review.get('manual_response', '')
            
            if not reply_content:
                reply_content = review.get('final_response', '')
            
            if not reply_content:
                return {
                    'success': False,
                    'error': '답글 내용이 없습니다',
                    'review_id': review_id
                }
            
            # 실제 답글 등록
            result = await self._perform_reply_posting(
                review, 
                store, 
                reply_content,
                review.get('response_by', 'system')
            )
            
            # 상태 업데이트
            await self._update_review_status(
                review_id, 
                result,
                review.get('response_by', 'system')
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"답글 등록 중 오류: {str(e)}\n{traceback.format_exc()}")
            return {
                'success': False,
                'error': str(e),
                'review_id': review_id
            }
        
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
            
            # 리뷰 상태 먼저 확인 (중복 체크 추가)
            review_data = await self._get_review_data(review_id)
            if review_data:
                current_status = review_data.get('response_status')
                self.logger.info(f"현재 리뷰 상태: {current_status}")
                
                if current_status == 'posted':
                    self.logger.warning(f"이미 답글이 등록된 리뷰입니다: review_id={review_id}")
                    return {
                        'success': False,
                        'error': '이미 답글이 등록된 리뷰입니다.',
                        'review_id': review_id,
                        'status': 'already_posted'
                    }
                
                # processing 상태 체크를 제거하거나 수정
                # 옵션 1: processing 상태여도 본인이 처리 중인 경우 계속 진행
                if current_status == 'processing':
                    # response_by가 현재 사용자와 다른 경우만 차단
                    processing_by = review_data.get('response_by')
                    if processing_by and processing_by != user_code:
                        self.logger.warning(f"다른 사용자가 답글 등록 중입니다: review_id={review_id}, processing_by={processing_by}")
                        return {
                            'success': False,
                            'error': '다른 사용자가 답글 등록을 진행 중입니다.',
                            'review_id': review_id,
                            'status': 'processing'
                        }
                    # 본인이 처리 중이면 계속 진행
                    self.logger.info(f"본인이 처리 중인 답글 등록 계속 진행: review_id={review_id}")
            
            # 상태를 processing으로 업데이트 (user_code 포함)
            try:
                await self._update_review_status_simple(review_id, 'processing', user_code)
                self.logger.info(f"상태를 processing으로 변경: review_id={review_id}, user={user_code}")
            except Exception as e:
                self.logger.error(f"processing 상태 업데이트 실패: {e}")
            
            # 1. 기본 검증
            validation_result = self._validate_reply_request(review_id, reply_content, user_code)
            if not validation_result['valid']:
                # 실패시 상태 복구
                await self._update_review_status_simple(review_id, 'generated', user_code)
                return {
                    'success': False,
                    'error': validation_result['error'],
                    'review_id': review_id
                }
            
            # 2. 리뷰 정보 재조회 (processing 상태 업데이트 후)
            review_data = await self._get_review_data(review_id)
            if not review_data:
                await self._update_review_status_simple(review_id, 'failed', user_code)
                return {
                    'success': False,
                    'error': '리뷰 정보를 찾을 수 없습니다',
                    'review_id': review_id
                }
            
            # 3. 매장 로그인 정보 조회
            store_config = await self._get_store_config(review_data['store_code'])
            if not store_config:
                await self._update_review_status_simple(review_id, 'failed', user_code)
                return {
                    'success': False,
                    'error': '매장 정보를 찾을 수 없습니다',
                    'review_id': review_id
                }
            
            # 4. 플랫폼 지원 여부 확인
            platform = review_data.get('platform', '').lower()
            if platform not in self.SUPPORTED_PLATFORMS:
                await self._update_review_status_simple(review_id, 'failed', user_code)
                return {
                    'success': False,
                    'error': f'지원하지 않는 플랫폼입니다: {platform}',
                    'review_id': review_id,
                    'platform': platform
                }
            
            # 5. 실제 답글 등록 수행 (재시도 로직 포함)
            posting_result = None
            for attempt in range(self.MAX_RETRY_COUNT):
                try:
                    posting_result = await self._perform_reply_posting(
                        review_data, 
                        store_config, 
                        reply_content,
                        user_code
                    )
                    
                    if posting_result['success']:
                        break
                    
                    # 특정 에러는 재시도하지 않음
                    if '이미 답글이 등록' in posting_result.get('error', ''):
                        break
                        
                except Exception as e:
                    self.logger.error(f"답글 등록 시도 {attempt + 1} 실패: {str(e)}")
                    posting_result = {
                        'success': False,
                        'error': str(e),
                        'review_id': review_id
                    }
                
                if attempt < self.MAX_RETRY_COUNT - 1:
                    await asyncio.sleep(self.RETRY_DELAY_SECONDS)
            
            # 6. 결과 DB 업데이트
            await self._update_review_status(review_id, posting_result, user_code)
            
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
                await self._update_review_status(review_id, {
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

    async def _update_review_status_simple(self, review_id: str, status: str, user_code: str):
        """간단한 리뷰 상태 업데이트 (processing 상태 설정용)"""
        try:
            update_data = {
                "response_status": status,
                "response_by": user_code,
                "updated_at": datetime.now().isoformat()
            }
            
            query = self.supabase.client.table('reviews').update(update_data).eq(
                'review_id', review_id
            )
            await self.supabase._execute_query(query)
            
            self.logger.info(f"리뷰 상태 간단 업데이트 완료: review_id={review_id}, status={status}, user={user_code}")
            
        except Exception as e:
            self.logger.error(f"리뷰 상태 간단 업데이트 실패: {str(e)}")


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
            # platform_reply_rules에서 직접 조회
            query = self.supabase.client.table('platform_reply_rules').select('*').eq('store_code', store_code)
            response = await self.supabase._execute_query(query)
            
            if not response.data:
                self.logger.warning(f"매장 조회 실패: store_code={store_code}")
                return None
            
            store_data = response.data[0]
            
            # 디버깅: 조회된 데이터 확인
            self.logger.info(f"platform_reply_rules 데이터: {list(store_data.keys())}")
            
            # 필수 필드 확인
            if not store_data.get('platform_id'):
                self.logger.error(f"platform_id가 없음: store_code={store_code}")
                return None
                
            if not store_data.get('platform_pw'):
                self.logger.error(f"platform_pw가 없음: store_code={store_code}")
                return None
            
            self.logger.info(f"platform_id 존재: {store_data['platform_id']}")
            self.logger.info(f"platform_pw 존재: {store_data['platform_pw'][:20]}...")
            
            # 로그인 비밀번호 복호화
            try:
                decrypted_password = decrypt_password(store_data['platform_pw'])
                store_data['platform_pw'] = decrypted_password
                self.logger.info("비밀번호 복호화 성공")
            except Exception as e:
                self.logger.error(f"비밀번호 복호화 실패: {e}")
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
                return await self._post_yogiyo_reply(review_data, store_config, reply_content)
            elif platform == 'coupang':
                # 쿠팡이츠 답글 등록 구현 호출로 변경
                return await self._post_coupang_reply(review_data, store_config, reply_content)
            elif platform == 'naver':  # 네이버 추가
                return await self._post_naver_reply(review_data, store_config, reply_content)
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

    async def _run_subprocess_manager(self, review_id: str, store_data: dict) -> dict:
        """서브프로세스 실행 (매니저 모드)"""
        try:
            self.logger.info(f"{'='*50}")
            self.logger.info(f"=== 서브프로세스 시작: {review_id} ===")
            self.logger.info(f"=== 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
            self.logger.info(f"{'='*50}")
            
            script_path = Path(__file__).parent / "platforms" / "baemin_subprocess.py"
            
            # store_data에서 필요한 정보 추출
            platform_id = store_data.get('platform_id', '')
            platform_pw = store_data.get('platform_pw', '')  
            platform_code = store_data.get('platform_code', '')
            
            # AI 응답 텍스트 가져오기 (여러 키 확인)
            response_text = (
                store_data.get('final_response') or 
                store_data.get('ai_response') or 
                store_data.get('response_text') or 
                ''
            )
            
            # 리뷰 정보 조회
            review_info = {}
            try:
                review_data = await self._get_review_data(review_id)
                if review_data:
                    review_info = {
                        'review_id': review_id,
                        'review_name': review_data.get('review_name', ''),
                        'rating': review_data.get('rating', 0),
                        'review_content': review_data.get('review_content', ''),
                        'review_date': review_data.get('review_date', ''),
                        'ordered_menu': review_data.get('ordered_menu', '')
                    }
                    self.logger.info(f"리뷰 정보 조회 성공: {review_info}")
            except Exception as e:
                self.logger.error(f"리뷰 정보 조회 실패: {e}")
            
            # 답글 내용이 없는 경우 경고
            if not response_text:
                self.logger.warning(f"AI 응답을 찾을 수 없음. store_data keys: {list(store_data.keys())}")
                response_text = "소중한 리뷰 감사합니다! 더 나은 서비스로 보답하겠습니다."
            
            # 인자 검증
            if not all([platform_id, platform_pw, platform_code]):
                missing = []
                if not platform_id: missing.append('platform_id')
                if not platform_pw: missing.append('platform_pw')
                if not platform_code: missing.append('platform_code')
                raise ValueError(f"필수 정보 누락: {', '.join(missing)}")
            
            # subprocess 실행 인자
            import json
            review_info_json = json.dumps(review_info, ensure_ascii=False)
            
            cmd = [
                sys.executable,
                str(script_path),
                review_id,
                platform_id,
                platform_pw,
                platform_code,
                response_text or "소중한 리뷰 감사합니다! 더 나은 서비스로 보답하겠습니다.",
                review_info_json
            ]
            
            # subprocess 실행 전 상세 로그
            self.logger.info(f"서브프로세스 실행 정보:")
            self.logger.info(f"  - Review ID: {review_id}")
            self.logger.info(f"  - Platform Code: {platform_code}")
            self.logger.info(f"  - Platform ID: {platform_id[:4]}***")
            self.logger.info(f"  - Reply Length: {len(response_text)}자")
            self.logger.info(f"  - Review Info: {review_info}")
            self.logger.info(f"  - Script Path: {script_path}")
            self.logger.info(f"  - Python Executable: {sys.executable}")
            
            # Windows에서 subprocess 실행 옵션
            creation_flags = 0
            
            # subprocess 실행
            self.logger.info("subprocess.run() 호출 시작...")
            start_time = time.time()
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,
                creationflags=creation_flags
            )
            
            execution_time = time.time() - start_time
            self.logger.info(f"subprocess.run() 완료 - 실행 시간: {execution_time:.2f}초")
            self.logger.info(f"subprocess 종료 코드: {result.returncode}")
            
            # 로그 파일 확인
            log_file = self.log_dir / f"subprocess_{review_id}.log"
            subprocess_logs = ""
            if log_file.exists():
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        subprocess_logs = f.read()
                        self.logger.info(f"서브프로세스 로그 파일 크기: {len(subprocess_logs)}바이트")
                        if subprocess_logs:
                            self.logger.info(f"서브프로세스 로그 내용:\n{'='*40}\n{subprocess_logs}\n{'='*40}")
                except Exception as e:
                    self.logger.error(f"로그 파일 읽기 실패: {e}")
            else:
                self.logger.warning(f"서브프로세스 로그 파일이 존재하지 않음: {log_file}")
            
            # stdout/stderr 로그
            if result.stdout:
                self.logger.info(f"subprocess stdout:\n{result.stdout}")
            if result.stderr:
                self.logger.error(f"subprocess stderr:\n{result.stderr}")
            
            # 결과 처리 - 수정된 부분
            if result.returncode == 0:
                # SUCCESS 키워드 확인
                if "SUCCESS" in result.stdout:
                    self.logger.info("✅ 서브프로세스 성공 - SUCCESS 키워드 발견")
                    return {
                        'success': True,
                        'message': '답글이 성공적으로 등록되었습니다.',
                        'execution_time': execution_time,
                        'final_status': 'posted'
                    }
                # ERROR 키워드 확인 - 수정된 부분
                elif "ERROR:" in result.stdout:
                    error_msg = result.stdout.split("ERROR:", 1)[1].strip()
                    
                    # "리뷰를 찾을 수 없거나" 에러는 이미 답글이 등록된 경우일 수 있음
                    if "리뷰를 찾을 수 없거나" in error_msg:
                        # DB에서 현재 상태 확인
                        try:
                            current_review = await self._get_review_data(review_id)
                            if current_review and current_review.get('response_status') == 'posted':
                                self.logger.info(f"이미 답글이 등록된 리뷰입니다: {review_id}")
                                return {
                                    'success': True,
                                    'message': '이미 답글이 등록되었습니다.',
                                    'execution_time': execution_time,
                                    'final_status': 'posted'
                                }
                        except Exception as e:
                            self.logger.error(f"리뷰 상태 확인 실패: {e}")
                    
                    self.logger.error(f"❌ 서브프로세스 에러: {error_msg}")
                    return {
                        'success': False,
                        'error': error_msg,
                        'logs': subprocess_logs,
                        'execution_time': execution_time,
                        'final_status': 'failed'
                    }
                else:
                    # JSON 응답 파싱 시도
                    try:
                        response = json.loads(result.stdout)
                        self.logger.info(f"JSON 응답 파싱 성공: {response}")
                        if 'final_status' not in response:
                            response['final_status'] = 'posted' if response.get('success') else 'failed'
                        return response
                    except:
                        self.logger.warning("JSON 파싱 실패, 기본 성공 응답 반환")
                        return {
                            'success': True,
                            'message': '답글이 등록되었습니다.',
                            'execution_time': execution_time,
                            'final_status': 'posted'
                        }
            else:
                # 종료 코드가 0이 아닌 경우
                error_msg = result.stderr or result.stdout or "알 수 없는 오류"
                
                self.logger.error(f"❌ 서브프로세스 에러 (exit code: {result.returncode}): {error_msg}")
                
                if subprocess_logs:
                    self.logger.error(f"서브프로세스 상세 로그:\n{subprocess_logs}")
                
                return {
                    'success': False,
                    'error': error_msg,
                    'logs': subprocess_logs,
                    'execution_time': execution_time,
                    'final_status': 'failed'
                }
                
        except subprocess.TimeoutExpired:
            self.logger.error("⏱️ 서브프로세스 타임아웃 (180초 초과)")
            return {
                'success': False,
                'error': '처리 시간이 초과되었습니다. 다시 시도해주세요.',
                'final_status': 'failed'
            }
        except Exception as e:
            self.logger.error(f"💥 서브프로세스 실행 오류: {str(e)}")
            self.logger.error(f"상세 에러:\n{traceback.format_exc()}")
            return {
                'success': False,
                'error': str(e),
                'final_status': 'failed'
            }
        finally:
            self.logger.info(f"{'='*50}")
            self.logger.info(f"=== 서브프로세스 종료: {review_id} ===")
            self.logger.info(f"{'='*50}")

    async def _run_coupang_subprocess_manager(self, review_id: str, store_config: dict) -> dict:
        """쿠팡이츠 답글 등록을 위한 subprocess 실행"""
        try:
            self.logger.info(f"{'='*50}")
            self.logger.info(f"=== 쿠팡 서브프로세스 시작: {review_id} ===")
            self.logger.info(f"=== 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
            self.logger.info(f"{'='*50}")
            
            # 실행할 Python 스크립트 경로
            script_path = Path(__file__).parent / "platforms" / "coupang_subprocess.py"
            
            # 스크립트 파일 존재 확인
            if not script_path.exists():
                error_msg = f"쿠팡 subprocess 스크립트를 찾을 수 없습니다: {script_path}"
                self.logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'final_status': 'failed'
                }
            
            # 리뷰 정보 조회
            review = await self._get_review_data(review_id)
            if not review:
                return {
                    'success': False,
                    'error': f'리뷰를 찾을 수 없습니다: {review_id}',
                    'final_status': 'failed'
                }
            
            # subprocess에 전달할 데이터
            subprocess_data = {
                'store_info': {
                    'platform_id': store_config['platform_id'],
                    'platform_pw': store_config['platform_pw'],
                    'store_code': store_config['store_code'],
                    'platform_code': store_config['platform_code']  # 쿠팡 매장 ID
                },
                'review_data': {
                    'review_id': review_id,
                    'review_content': review.get('review_content', ''),
                    'ordered_menu': review.get('ordered_menu', ''),
                    'reply_content': store_config.get('final_response', '') or store_config.get('reply_content', '')
                }
            }
            
            # 답글 내용 확인
            if not subprocess_data['review_data']['reply_content']:
                error_msg = "답글 내용이 없습니다"
                self.logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'final_status': 'failed'
                }
            
            # subprocess 실행 (동기식으로 변경)
            cmd = [
                sys.executable,
                str(script_path),
                json.dumps(subprocess_data, ensure_ascii=False)
            ]
            
            # Windows 환경 변수 설정 추가
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            
            self.logger.info(f"쿠팡 서브프로세스 실행 정보:")
            self.logger.info(f"  - Review ID: {review_id}")
            self.logger.info(f"  - Platform Code: {store_config['platform_code']}")
            self.logger.info(f"  - Platform ID: {store_config['platform_id'][:4]}***")
            self.logger.info(f"  - Script Path: {script_path}")
            self.logger.info(f"  - Reply Content Length: {len(subprocess_data['review_data']['reply_content'])} chars")
            
            # Windows에서 subprocess 실행
            start_time = time.time()
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',  # UTF-8 인코딩 명시
                timeout=180,
                creationflags=0 if sys.platform != 'win32' else subprocess.CREATE_NO_WINDOW,
                env=env  # 환경 변수 전달 추가
            )
            
            execution_time = time.time() - start_time
            self.logger.info(f"subprocess 실행 완료 - 실행 시간: {execution_time:.2f}초")
            self.logger.info(f"subprocess 종료 코드: {result.returncode}")
            
            # stdout/stderr 로그
            if result.stdout:
                self.logger.info(f"subprocess stdout: {result.stdout}")
            if result.stderr:
                self.logger.error(f"subprocess stderr: {result.stderr}")
            
            # 결과 파싱
            if result.returncode == 0:
                try:
                    response = json.loads(result.stdout)
                    self.logger.info(f"쿠팡 서브프로세스 응답: {response}")
                    
                    if response.get('success'):
                        return {
                            'success': True,
                            'message': response.get('message', '답글이 성공적으로 등록되었습니다'),
                            'final_status': 'posted'
                        }
                    else:
                        return {
                            'success': False,
                            'error': response.get('error', response.get('message', '알 수 없는 오류')),
                            'final_status': 'failed'
                        }
                except json.JSONDecodeError as e:
                    self.logger.error(f"JSON 파싱 오류: {result.stdout}")
                    return {
                        'success': False,
                        'error': f'subprocess 결과 파싱 오류: {str(e)}',
                        'final_status': 'failed'
                    }
            else:
                error_msg = result.stderr or result.stdout or '알 수 없는 오류'
                self.logger.error(f"쿠팡 서브프로세스 실패: {error_msg}")
                return {
                    'success': False,
                    'error': f'subprocess 실행 실패: {error_msg}',
                    'final_status': 'failed'
                }
                
        except subprocess.TimeoutExpired:
            self.logger.error("쿠팡 subprocess 타임아웃 (180초 초과)")
            return {
                'success': False,
                'error': '처리 시간이 초과되었습니다',
                'final_status': 'timeout'
            }
        except Exception as e:
            error_msg = f"쿠팡 subprocess 실행 중 오류: {str(e)}"
            self.logger.error(f"{error_msg}\n{traceback.format_exc()}")
            return {
                'success': False,
                'error': error_msg,
                'final_status': 'failed'
            }
        finally:
            self.logger.info(f"{'='*50}")
            self.logger.info(f"=== 쿠팡 서브프로세스 종료: {review_id} ===")
            self.logger.info(f"{'='*50}")
    
    async def _run_yogiyo_subprocess_manager(self, review_id: str, store_config: dict) -> dict:
        """요기요 답글 등록을 위한 subprocess 실행"""
        try:
            self.logger.info(f"{'='*50}")
            self.logger.info(f"=== 요기요 서브프로세스 시작: {review_id} ===")
            self.logger.info(f"=== 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
            self.logger.info(f"{'='*50}")
            
            script_path = Path(__file__).parent / "platforms" / "yogiyo_subprocess.py"
            
            # 스크립트 파일 존재 확인
            if not script_path.exists():
                error_msg = f"요기요 subprocess 스크립트를 찾을 수 없습니다: {script_path}"
                self.logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'final_status': 'failed'
                }
            
            # store_config에서 필요한 정보 추출
            platform_id = store_config.get('platform_id', '')
            platform_pw = store_config.get('platform_pw', '')  
            platform_code = store_config.get('platform_code', '')
            
            # AI 응답 텍스트 가져오기
            response_text = (
                store_config.get('final_response') or 
                store_config.get('ai_response') or 
                store_config.get('response_text') or 
                store_config.get('reply_content') or
                ''
            )
            
            # 리뷰 정보 조회
            review_info = {}
            try:
                review_data = await self._get_review_data(review_id)
                if review_data:
                    review_info = {
                        'review_id': review_id,
                        'review_name': review_data.get('review_name', ''),
                        'rating': review_data.get('rating', 0),
                        'review_content': review_data.get('review_content', ''),
                        'review_date': review_data.get('review_date', ''),
                        'ordered_menu': review_data.get('ordered_menu', '')
                    }
                    self.logger.info(f"리뷰 정보 조회 성공: {review_info}")
            except Exception as e:
                self.logger.error(f"리뷰 정보 조회 실패: {e}")
            
            # 답글 내용이 없는 경우 경고
            if not response_text:
                self.logger.warning(f"AI 응답을 찾을 수 없음. store_config keys: {list(store_config.keys())}")
                response_text = "소중한 리뷰 감사합니다! 더 나은 서비스로 보답하겠습니다."
            
            # 인자 검증
            if not all([platform_id, platform_pw, platform_code]):
                missing = []
                if not platform_id: missing.append('platform_id')
                if not platform_pw: missing.append('platform_pw')
                if not platform_code: missing.append('platform_code')
                raise ValueError(f"필수 정보 누락: {', '.join(missing)}")
            
            # subprocess 실행 인자
            import json
            review_info_json = json.dumps(review_info, ensure_ascii=False)
            
            cmd = [
                sys.executable,
                str(script_path),
                review_id,
                platform_id,
                platform_pw,
                platform_code,
                response_text or "소중한 리뷰 감사합니다! 더 나은 서비스로 보답하겠습니다.",
                review_info_json
            ]
            
            self.logger.info(f"요기요 서브프로세스 실행 정보:")
            self.logger.info(f"  - Review ID: {review_id}")
            self.logger.info(f"  - Platform Code: {platform_code}")
            self.logger.info(f"  - Platform ID: {platform_id[:4]}***")
            self.logger.info(f"  - Reply Length: {len(response_text)}자")
            self.logger.info(f"  - Review Info: {review_info}")
            self.logger.info(f"  - Script Path: {script_path}")
            
            # Windows에서 subprocess 실행 옵션
            creation_flags = 0
            
            # subprocess 실행
            self.logger.info("subprocess.run() 호출 시작...")
            start_time = time.time()
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,
                creationflags=creation_flags
            )
            
            execution_time = time.time() - start_time
            self.logger.info(f"subprocess.run() 완료 - 실행 시간: {execution_time:.2f}초")
            self.logger.info(f"subprocess 종료 코드: {result.returncode}")
            
            # 로그 파일 확인
            log_file = self.log_dir / f"yogiyo_subprocess_{review_id}.log"
            subprocess_logs = ""
            if log_file.exists():
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        subprocess_logs = f.read()
                        self.logger.info(f"서브프로세스 로그 파일 크기: {len(subprocess_logs)}바이트")
                except Exception as e:
                    self.logger.error(f"로그 파일 읽기 실패: {e}")
            
            # stdout/stderr 로그
            if result.stdout:
                self.logger.info(f"subprocess stdout:\n{result.stdout}")
            if result.stderr:
                self.logger.error(f"subprocess stderr:\n{result.stderr}")
            
            # 결과 처리
            if result.returncode == 0:
                if "SUCCESS" in result.stdout:
                    self.logger.info("✅ 요기요 서브프로세스 성공")
                    return {
                        'success': True,
                        'message': '답글이 성공적으로 등록되었습니다.',
                        'execution_time': execution_time,
                        'final_status': 'posted'
                    }
                elif "ERROR:" in result.stdout:
                    error_msg = result.stdout.split("ERROR:", 1)[1].strip()
                    
                    # "리뷰를 찾을 수 없거나" 에러 처리
                    if "리뷰를 찾을 수 없거나" in error_msg:
                        try:
                            current_review = await self._get_review_data(review_id)
                            if current_review and current_review.get('response_status') == 'posted':
                                self.logger.info(f"이미 답글이 등록된 리뷰입니다: {review_id}")
                                return {
                                    'success': True,
                                    'message': '이미 답글이 등록되었습니다.',
                                    'execution_time': execution_time,
                                    'final_status': 'posted'
                                }
                        except Exception as e:
                            self.logger.error(f"리뷰 상태 확인 실패: {e}")
                    
                    self.logger.error(f"❌ 요기요 서브프로세스 에러: {error_msg}")
                    return {
                        'success': False,
                        'error': error_msg,
                        'logs': subprocess_logs,
                        'execution_time': execution_time,
                        'final_status': 'failed'
                    }
                else:
                    try:
                        response = json.loads(result.stdout)
                        self.logger.info(f"JSON 응답 파싱 성공: {response}")
                        if 'final_status' not in response:
                            response['final_status'] = 'posted' if response.get('success') else 'failed'
                        return response
                    except:
                        self.logger.warning("JSON 파싱 실패, 기본 성공 응답 반환")
                        return {
                            'success': True,
                            'message': '답글이 등록되었습니다.',
                            'execution_time': execution_time,
                            'final_status': 'posted'
                        }
            else:
                error_msg = result.stderr or result.stdout or "알 수 없는 오류"
                self.logger.error(f"❌ 요기요 서브프로세스 에러 (exit code: {result.returncode}): {error_msg}")
                
                return {
                    'success': False,
                    'error': error_msg,
                    'logs': subprocess_logs,
                    'execution_time': execution_time,
                    'final_status': 'failed'
                }
                
        except subprocess.TimeoutExpired:
            self.logger.error("⏱️ 요기요 서브프로세스 타임아웃 (180초 초과)")
            return {
                'success': False,
                'error': '처리 시간이 초과되었습니다. 다시 시도해주세요.',
                'final_status': 'failed'
            }
        except Exception as e:
            self.logger.error(f"💥 요기요 서브프로세스 실행 오류: {str(e)}")
            self.logger.error(f"상세 에러:\n{traceback.format_exc()}")
            return {
                'success': False,
                'error': str(e),
                'final_status': 'failed'
            }
        finally:
            self.logger.info(f"{'='*50}")
            self.logger.info(f"=== 요기요 서브프로세스 종료: {review_id} ===")
            self.logger.info(f"{'='*50}")

    async def _run_naver_subprocess_manager(self, review_id: str, store_config: dict) -> dict:
        """네이버 플레이스 답글 등록을 위한 subprocess 실행"""
        try:
            self.logger.info(f"{'='*50}")
            self.logger.info(f"=== 네이버 서브프로세스 시작: {review_id} ===")
            self.logger.info(f"=== 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
            self.logger.info(f"{'='*50}")
            
            script_path = Path(__file__).parent / "platforms" / "naver_subprocess.py"
            
            # 스크립트 파일 존재 확인
            if not script_path.exists():
                error_msg = f"네이버 subprocess 스크립트를 찾을 수 없습니다: {script_path}"
                self.logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'final_status': 'failed'
                }
            
            # store_config에서 필요한 정보 추출
            platform_id = store_config.get('platform_id', '')
            platform_pw = store_config.get('platform_pw', '')  
            platform_code = store_config.get('platform_code', '')
            
            # AI 응답 텍스트 가져오기
            response_text = (
                store_config.get('final_response') or 
                store_config.get('ai_response') or 
                store_config.get('response_text') or 
                store_config.get('reply_content') or
                ''
            )
            
            # 리뷰 정보 조회
            review_info = {}
            try:
                review_data = await self._get_review_data(review_id)
                if review_data:
                    review_info = {
                        'review_id': review_id,
                        'review_name': review_data.get('review_name', ''),
                        'rating': review_data.get('rating', 0),
                        'review_content': review_data.get('review_content', ''),
                        'review_date': review_data.get('review_date', ''),
                        'ordered_menu': review_data.get('ordered_menu', '')
                    }
                    self.logger.info(f"리뷰 정보 조회 성공: {review_info}")
            except Exception as e:
                self.logger.error(f"리뷰 정보 조회 실패: {e}")
            
            # 답글 내용이 없는 경우 경고
            if not response_text:
                self.logger.warning(f"AI 응답을 찾을 수 없음. store_config keys: {list(store_config.keys())}")
                response_text = "소중한 리뷰 감사합니다! 더 나은 서비스로 보답하겠습니다."
            
            # 인자 검증
            if not all([platform_id, platform_pw, platform_code]):
                missing = []
                if not platform_id: missing.append('platform_id')
                if not platform_pw: missing.append('platform_pw')
                if not platform_code: missing.append('platform_code')
                raise ValueError(f"필수 정보 누락: {', '.join(missing)}")
            
            # subprocess에 전달할 데이터 (쿠팡 방식과 동일하게)
            import json
            subprocess_data = {
                'store_info': {
                    'platform_id': platform_id,
                    'platform_pw': platform_pw,
                    'platform_code': platform_code,
                    'store_code': store_config.get('store_code', '')
                },
                'review_ids': [review_id],  # 리스트 형태로 전달
                'reply_contents': {review_id: response_text}  # 답글 내용 추가
            }

            cmd = [
                sys.executable,
                str(script_path),
                json.dumps(subprocess_data['review_ids'], ensure_ascii=False),      # 첫 번째 인자: review_ids
                json.dumps(subprocess_data['store_info'], ensure_ascii=False),      # 두 번째 인자: store_info
                json.dumps(subprocess_data['reply_contents'], ensure_ascii=False)   # 세 번째 인자: reply_contents
            ]
            
            self.logger.info(f"네이버 서브프로세스 실행 정보:")
            self.logger.info(f"  - Review ID: {review_id}")
            self.logger.info(f"  - Platform Code: {platform_code}")
            self.logger.info(f"  - Platform ID: {platform_id[:4]}***")
            self.logger.info(f"  - Reply Length: {len(response_text)}자")
            self.logger.info(f"  - Review Info: {review_info}")
            self.logger.info(f"  - Script Path: {script_path}")
            
            # Windows에서 subprocess 실행 옵션
            creation_flags = 0
            
            # subprocess 실행
            self.logger.info("subprocess.run() 호출 시작...")
            start_time = time.time()
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,
                creationflags=creation_flags
            )
            
            execution_time = time.time() - start_time
            self.logger.info(f"subprocess.run() 완료 - 실행 시간: {execution_time:.2f}초")
            self.logger.info(f"subprocess 종료 코드: {result.returncode}")
            
            # 로그 파일 확인
            log_file = self.log_dir / f"naver_subprocess_{review_id}.log"
            subprocess_logs = ""
            if log_file.exists():
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        subprocess_logs = f.read()
                        self.logger.info(f"서브프로세스 로그 파일 크기: {len(subprocess_logs)}바이트")
                except Exception as e:
                    self.logger.error(f"로그 파일 읽기 실패: {e}")
            
            # stdout/stderr 로그
            if result.stdout:
                self.logger.info(f"subprocess stdout:\n{result.stdout}")
            if result.stderr:
                self.logger.error(f"subprocess stderr:\n{result.stderr}")
            
            # 결과 처리
            if result.returncode == 0:
                # JSON 응답 파싱 시도
                try:
                    response = json.loads(result.stdout)
                    self.logger.info(f"JSON 응답 파싱 성공: {response}")
                    if 'final_status' not in response:
                        response['final_status'] = 'posted' if response.get('success') else 'failed'
                    return response
                except:
                    # SUCCESS 키워드 확인
                    if "SUCCESS" in result.stdout:
                        self.logger.info("✅ 네이버 서브프로세스 성공")
                        return {
                            'success': True,
                            'message': '답글이 성공적으로 등록되었습니다.',
                            'execution_time': execution_time,
                            'final_status': 'posted'
                        }
                    else:
                        self.logger.warning("JSON 파싱 실패, 기본 실패 응답 반환")
                        return {
                            'success': False,
                            'error': '응답 파싱 실패',
                            'execution_time': execution_time,
                            'final_status': 'failed'
                        }
            else:
                error_msg = result.stderr or result.stdout or "알 수 없는 오류"
                self.logger.error(f"❌ 네이버 서브프로세스 에러 (exit code: {result.returncode}): {error_msg}")
                
                return {
                    'success': False,
                    'error': error_msg,
                    'logs': subprocess_logs,
                    'execution_time': execution_time,
                    'final_status': 'failed'
                }
                
        except subprocess.TimeoutExpired:
            self.logger.error("⏱️ 네이버 서브프로세스 타임아웃 (180초 초과)")
            return {
                'success': False,
                'error': '처리 시간이 초과되었습니다. 다시 시도해주세요.',
                'final_status': 'failed'
            }
        except Exception as e:
            self.logger.error(f"💥 네이버 서브프로세스 실행 오류: {str(e)}")
            self.logger.error(f"상세 에러:\n{traceback.format_exc()}")
            return {
                'success': False,
                'error': str(e),
                'final_status': 'failed'
            }
        finally:
            self.logger.info(f"{'='*50}")
            self.logger.info(f"=== 네이버 서브프로세스 종료: {review_id} ===")
            self.logger.info(f"{'='*50}")

    def _parse_error_message(self, error_output: str, log_content: str) -> str:
        """에러 메시지 파싱 및 사용자 친화적 메시지 변환"""
        error_output_lower = error_output.lower()
        log_content_lower = log_content.lower()
        combined = error_output_lower + " " + log_content_lower
        
        # 일반적인 에러 패턴 매칭
        if "target page, context or browser has been closed" in combined:
            return "브라우저 연결이 끊어졌습니다. 다시 시도해주세요."
        elif "답글 입력 필드를 찾을 수 없습니다" in error_output:
            return "답글 입력 필드를 찾을 수 없습니다. 페이지 구조가 변경되었을 수 있습니다."
        elif "로그인 실패" in error_output:
            return "플랫폼 로그인에 실패했습니다. 로그인 정보를 확인해주세요."
        elif "timeout" in combined:
            return "작업 시간이 초과되었습니다. 네트워크 상태를 확인해주세요."
        elif "리뷰를 찾을 수 없음" in error_output:
            return "해당 리뷰를 찾을 수 없습니다. 이미 답글이 등록되었거나 삭제되었을 수 있습니다."
        else:
            # 기본 에러 메시지
            if error_output:
                # 깨진 문자 제거
                clean_error = re.sub(r'[^\x00-\x7F\uAC00-\uD7AF]+', '', error_output)
                return f"답글 등록 실패: {clean_error[:100]}"
            return "알 수 없는 오류가 발생했습니다."

    async def _post_baemin_reply(
        self,
        review_data: Dict[str, Any],
        store_config: Dict[str, Any],
        reply_content: str
    ) -> Dict[str, Any]:
        """
        배민 답글 등록 - subprocess를 사용한 구현
        
        Args:
            review_data: 리뷰 데이터
            store_config: 매장 설정
            reply_content: 답글 내용
            
        Returns:
            Dict: 등록 결과
        """
        review_id = review_data.get('review_id', 'unknown')
        
        try:
            self.logger.info(f"배민 답글 등록 시작 (subprocess): review_id={review_id}")
            
            # store_config에 reply_content 추가
            store_config['reply_content'] = reply_content
            store_config['final_response'] = reply_content  # AI 답글로 추가
            store_config['ai_response'] = reply_content  # 호환성을 위해 추가
            
            # review_data를 store_config에 병합 (새로 추가)
            store_config.update({
                'review_name': review_data.get('review_name', ''),
                'rating': review_data.get('rating', 0),
                'review_content': review_data.get('review_content', ''),
                'review_date': review_data.get('review_date', ''),
                'ordered_menu': review_data.get('ordered_menu', '')
            })
            
            # subprocess 실행
            result = await self._run_subprocess_manager(review_id, store_config)
            
            if result['success']:
                self.logger.info(f"배민 답글 등록 성공: review_id={review_id}")
                return {
                    'success': True,
                    'message': '답글이 성공적으로 등록되었습니다',
                    'review_id': review_id,
                    'platform': 'baemin',
                    'final_status': result.get('final_status', 'posted')
                }
            else:
                self.logger.warning(f"배민 답글 등록 실패: review_id={review_id}, error={result.get('error')}")
                return {
                    'success': False,
                    'error': result.get('error', '알 수 없는 오류'),
                    'review_id': review_id,
                    'platform': 'baemin',
                    'final_status': result.get('final_status', 'failed')
                }
                
        except Exception as e:
            error_msg = f"배민 답글 등록 중 예외: {str(e)}"
            self.logger.error(f"{error_msg}\n{traceback.format_exc()}")
            return {
                'success': False,
                'error': error_msg,
                'review_id': review_id,
                'platform': 'baemin',
                'final_status': 'failed'
            }
        
    async def _post_yogiyo_reply(
        self,
        review_data: Dict[str, Any],
        store_config: Dict[str, Any],
        reply_content: str
    ) -> Dict[str, Any]:
        """
        요기요 답글 등록 - subprocess를 사용한 구현
        
        Args:
            review_data: 리뷰 데이터
            store_config: 매장 설정
            reply_content: 답글 내용
            
        Returns:
            Dict: 등록 결과
        """
        review_id = review_data.get('review_id', 'unknown')
        
        try:
            self.logger.info(f"요기요 답글 등록 시작 (subprocess): review_id={review_id}")
            
            # store_config에 reply_content 추가
            store_config['reply_content'] = reply_content
            store_config['final_response'] = reply_content
            store_config['ai_response'] = reply_content
            
            # review_data를 store_config에 병합
            store_config.update({
                'review_name': review_data.get('review_name', ''),
                'rating': review_data.get('rating', 0),
                'review_content': review_data.get('review_content', ''),
                'review_date': review_data.get('review_date', ''),
                'ordered_menu': review_data.get('ordered_menu', '')
            })
            
            # subprocess 실행 (요기요 전용)
            result = await self._run_yogiyo_subprocess_manager(review_id, store_config)
            
            if result['success']:
                self.logger.info(f"요기요 답글 등록 성공: review_id={review_id}")
                return {
                    'success': True,
                    'message': '답글이 성공적으로 등록되었습니다',
                    'review_id': review_id,
                    'platform': 'yogiyo',
                    'final_status': result.get('final_status', 'posted')
                }
            else:
                self.logger.warning(f"요기요 답글 등록 실패: review_id={review_id}, error={result.get('error')}")
                return {
                    'success': False,
                    'error': result.get('error', '알 수 없는 오류'),
                    'review_id': review_id,
                    'platform': 'yogiyo',
                    'final_status': result.get('final_status', 'failed')
                }
                
        except Exception as e:
            error_msg = f"요기요 답글 등록 중 예외: {str(e)}"
            self.logger.error(f"{error_msg}\n{traceback.format_exc()}")
            return {
                'success': False,
                'error': error_msg,
                'review_id': review_id,
                'platform': 'yogiyo',
                'final_status': 'failed'
            }
        
    async def _post_coupang_reply(
        self,
        review_data: Dict[str, Any],
        store_config: Dict[str, Any],
        reply_content: str
    ) -> Dict[str, Any]:
        """
        쿠팡이츠 답글 등록 - subprocess를 사용한 구현
        
        Args:
            review_data: 리뷰 데이터
            store_config: 매장 설정
            reply_content: 답글 내용
            
        Returns:
            Dict: 등록 결과
        """
        review_id = review_data.get('review_id', 'unknown')
        
        try:
            self.logger.info(f"쿠팡이츠 답글 등록 시작 (subprocess): review_id={review_id}")
            
            # store_config에 reply_content 추가
            store_config['reply_content'] = reply_content
            store_config['final_response'] = reply_content
            store_config['ai_response'] = reply_content
            
            # review_data를 store_config에 병합
            store_config.update({
                'review_name': review_data.get('review_name', ''),
                'rating': review_data.get('rating', 0),
                'review_content': review_data.get('review_content', ''),
                'review_date': review_data.get('review_date', ''),
                'ordered_menu': review_data.get('ordered_menu', '')
            })
            
            # subprocess 실행 (쿠팡 전용)
            result = await self._run_coupang_subprocess_manager(review_id, store_config)
            
            if result['success']:
                self.logger.info(f"쿠팡이츠 답글 등록 성공: review_id={review_id}")
                return {
                    'success': True,
                    'message': '답글이 성공적으로 등록되었습니다',
                    'review_id': review_id,
                    'platform': 'coupang',
                    'final_status': result.get('final_status', 'posted')
                }
            else:
                self.logger.warning(f"쿠팡이츠 답글 등록 실패: review_id={review_id}, error={result.get('error')}")
                return {
                    'success': False,
                    'error': result.get('error', '알 수 없는 오류'),
                    'review_id': review_id,
                    'platform': 'coupang',
                    'final_status': result.get('final_status', 'failed')
                }
                
        except Exception as e:
            error_msg = f"쿠팡이츠 답글 등록 중 예외: {str(e)}"
            self.logger.error(f"{error_msg}\n{traceback.format_exc()}")
            return {
                'success': False,
                'error': error_msg,
                'review_id': review_id,
                'platform': 'coupang',
                'final_status': 'failed'
            }
        
    async def _post_naver_reply(
        self,
        review_data: Dict[str, Any],
        store_config: Dict[str, Any],
        reply_content: str
    ) -> Dict[str, Any]:
        """
        네이버 플레이스 답글 등록 - subprocess를 사용한 구현
        
        Args:
            review_data: 리뷰 데이터
            store_config: 매장 설정
            reply_content: 답글 내용
            
        Returns:
            Dict: 등록 결과
        """
        review_id = review_data.get('review_id', 'unknown')
        
        try:
            self.logger.info(f"네이버 답글 등록 시작 (subprocess): review_id={review_id}")
            
            # store_config에 reply_content 추가
            store_config['reply_content'] = reply_content
            store_config['final_response'] = reply_content
            store_config['ai_response'] = reply_content
            
            # review_data를 store_config에 병합
            store_config.update({
                'review_name': review_data.get('review_name', ''),
                'rating': review_data.get('rating', 0),
                'review_content': review_data.get('review_content', ''),
                'review_date': review_data.get('review_date', ''),
                'ordered_menu': review_data.get('ordered_menu', '')
            })
            
            # subprocess 실행 (네이버 전용)
            result = await self._run_naver_subprocess_manager(review_id, store_config)
            
            if result['success']:
                self.logger.info(f"네이버 답글 등록 성공: review_id={review_id}")
                return {
                    'success': True,
                    'message': '답글이 성공적으로 등록되었습니다',
                    'review_id': review_id,
                    'platform': 'naver',
                    'final_status': result.get('final_status', 'posted')
                }
            else:
                self.logger.warning(f"네이버 답글 등록 실패: review_id={review_id}, error={result.get('error')}")
                return {
                    'success': False,
                    'error': result.get('error', '알 수 없는 오류'),
                    'review_id': review_id,
                    'platform': 'naver',
                    'final_status': result.get('final_status', 'failed')
                }
                
        except Exception as e:
            error_msg = f"네이버 답글 등록 중 예외: {str(e)}"
            self.logger.error(f"{error_msg}\n{traceback.format_exc()}")
            return {
                'success': False,
                'error': error_msg,
                'review_id': review_id,
                'platform': 'naver',
                'final_status': 'failed'
            }
    
    async def post_reply_to_platform(self, platform: str, review_id: str, 
                                    response_text: str, store_config: dict) -> dict:
        """플랫폼별 답글 등록"""
        self.logger.info(f"플랫폼 답글 등록 시작: platform={platform}, review_id={review_id}")
        
        try:
            if platform == "baemin":
                # store_config에 response_text 추가 (여러 키로 저장)
                store_config['final_response'] = response_text
                store_config['ai_response'] = response_text  # 호환성을 위해 추가
                store_config['response_text'] = response_text  # 호환성을 위해 추가
                
                self.logger.info(f"배민 답글 등록 시작 (subprocess): review_id={review_id}")
                
                # platform_id, platform_pw, platform_code 확인
                required_fields = ['platform_id', 'platform_pw', 'platform_code']
                for field in required_fields:
                    if field not in store_config:
                        raise ValueError(f"필수 필드 누락: {field}")
                
                # subprocess 실행
                result = await self._run_subprocess_manager(review_id, store_config)
                
                if result['success']:
                    self.logger.info(f"배민 답글 등록 성공: {result.get('message', '')}")
                    return {
                        'success': True,
                        'message': result.get('message', '답글이 성공적으로 등록되었습니다.'),
                        'final_status': result.get('final_status', 'posted')
                    }
                else:
                    error_msg = result.get('error', '알 수 없는 오류가 발생했습니다.')
                    self.logger.warning(f"배민 답글 등록 실패: review_id={review_id}, error={error_msg}")
                    
                    # 브라우저 관련 에러인 경우 재시도 가능 메시지 추가
                    if 'browser' in error_msg.lower() or 'closed' in error_msg.lower():
                        error_msg = "브라우저 연결이 끊어졌습니다. 다시 시도해주세요."
                    
                    return {
                        'success': False,
                        'error': error_msg,
                        'final_status': result.get('final_status', 'failed')
                    }
                    
            elif platform == "coupang" or platform == "coupangeats":
                # store_config에 response_text 추가 (쿠팡도 동일한 방식)
                store_config['final_response'] = response_text
                store_config['ai_response'] = response_text
                store_config['response_text'] = response_text
                
                self.logger.info(f"쿠팡이츠 답글 등록 시작 (subprocess): review_id={review_id}")
                
                # platform_id, platform_pw, platform_code 확인
                required_fields = ['platform_id', 'platform_pw', 'platform_code']
                for field in required_fields:
                    if field not in store_config:
                        raise ValueError(f"필수 필드 누락: {field}")
                
                # subprocess 실행 (쿠팡 전용)
                result = await self._run_coupang_subprocess_manager(review_id, store_config)
                
                if result['success']:
                    self.logger.info(f"쿠팡이츠 답글 등록 성공: {result.get('message', '')}")
                    return {
                        'success': True,
                        'message': result.get('message', '답글이 성공적으로 등록되었습니다.'),
                        'final_status': result.get('final_status', 'posted')
                    }
                else:
                    error_msg = result.get('error', '알 수 없는 오류가 발생했습니다.')
                    self.logger.warning(f"쿠팡이츠 답글 등록 실패: review_id={review_id}, error={error_msg}")
                    
                    # 브라우저 관련 에러인 경우 재시도 가능 메시지 추가
                    if 'browser' in error_msg.lower() or 'closed' in error_msg.lower():
                        error_msg = "브라우저 연결이 끊어졌습니다. 다시 시도해주세요."
                    
                    return {
                        'success': False,
                        'error': error_msg,
                        'final_status': result.get('final_status', 'failed')
                    }
                    
            elif platform == "yogiyo":
                # store_config에 response_text 추가
                store_config['final_response'] = response_text
                store_config['ai_response'] = response_text
                store_config['response_text'] = response_text
                store_config['reply_content'] = response_text
                
                self.logger.info(f"요기요 답글 등록 시작 (subprocess): review_id={review_id}")
                
                # platform_id, platform_pw, platform_code 확인
                required_fields = ['platform_id', 'platform_pw', 'platform_code']
                for field in required_fields:
                    if field not in store_config:
                        raise ValueError(f"필수 필드 누락: {field}")
                
                # subprocess 실행 (요기요 전용)
                result = await self._run_yogiyo_subprocess_manager(review_id, store_config)
                
                if result['success']:
                    self.logger.info(f"요기요 답글 등록 성공: {result.get('message', '')}")
                    return {
                        'success': True,
                        'message': result.get('message', '답글이 성공적으로 등록되었습니다.'),
                        'final_status': result.get('final_status', 'posted')
                    }
                else:
                    error_msg = result.get('error', '알 수 없는 오류가 발생했습니다.')
                    self.logger.warning(f"요기요 답글 등록 실패: review_id={review_id}, error={error_msg}")
                    
                    # 브라우저 관련 에러인 경우 재시도 가능 메시지 추가
                    if 'browser' in error_msg.lower() or 'closed' in error_msg.lower():
                        error_msg = "브라우저 연결이 끊어졌습니다. 다시 시도해주세요."
                    
                    return {
                        'success': False,
                        'error': error_msg,
                        'final_status': result.get('final_status', 'failed')
                    }

            elif platform == "naver":
                # store_config에 response_text 추가
                store_config['final_response'] = response_text
                store_config['ai_response'] = response_text
                store_config['response_text'] = response_text
                store_config['reply_content'] = response_text
                
                self.logger.info(f"네이버 답글 등록 시작 (subprocess): review_id={review_id}")
                
                # platform_id, platform_pw, platform_code 확인
                required_fields = ['platform_id', 'platform_pw', 'platform_code']
                for field in required_fields:
                    if field not in store_config:
                        raise ValueError(f"필수 필드 누락: {field}")
                
                # subprocess 실행 (네이버 전용)
                result = await self._run_naver_subprocess_manager(review_id, store_config)
                
                if result['success']:
                    self.logger.info(f"네이버 답글 등록 성공: {result.get('message', '')}")
                    return {
                        'success': True,
                        'message': result.get('message', '답글이 성공적으로 등록되었습니다.'),
                        'final_status': result.get('final_status', 'posted')
                    }
                else:
                    error_msg = result.get('error', '알 수 없는 오류가 발생했습니다.')
                    self.logger.warning(f"네이버 답글 등록 실패: review_id={review_id}, error={error_msg}")
                    
                    # 브라우저 관련 에러인 경우 재시도 가능 메시지 추가
                    if 'browser' in error_msg.lower() or 'closed' in error_msg.lower():
                        error_msg = "브라우저 연결이 끊어졌습니다. 다시 시도해주세요."
                    
                    return {
                        'success': False,
                        'error': error_msg,
                        'final_status': result.get('final_status', 'failed')
                    }
            
            else:
                return {
                    'success': False,
                    'error': f"지원하지 않는 플랫폼입니다: {platform}",
                    'final_status': 'failed'
                }
        except Exception as e:
            self.logger.error(f"플랫폼 답글 등록 중 오류: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'final_status': 'failed'
            }

    async def _check_user_permission(self, user_code: str, store_code: str) -> bool:
        """사용자 권한 확인"""
        try:
            # store_code의 소유자 확인
            query = self.supabase.client.table('platform_reply_rules')\
                .select('owner_user_code')\
                .eq('store_code', store_code)
            response = await self.supabase._execute_query(query)
            
            if response.data:
                owner_code = response.data[0].get('owner_user_code')
                return owner_code == user_code
            
            return False
        except Exception as e:
            logger.error(f"권한 확인 실패: {str(e)}")
            return False

    async def _update_review_status(
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
            if isinstance(posting_result, dict):
                status = posting_result.get('final_status', 'failed' if not posting_result.get('success') else 'posted')
                error_message = posting_result.get('error') if not posting_result.get('success') else None
            else:
                # posting_result가 dict가 아닌 경우 처리
                status = posting_result
                error_message = None
            
            update_data = {
                'response_status': status,
                'response_by': user_code,
                'updated_at': datetime.now().isoformat()
            }
            
            if status == 'posted':
                update_data['response_at'] = datetime.now().isoformat()
                update_data['response_method'] = 'manual'
            
            if error_message:
                update_data['error_message'] = error_message
            
            query = self.supabase.client.table('reviews')\
                .update(update_data)\
                .eq('review_id', review_id)
            
            await self.supabase._execute_query(query)
            
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