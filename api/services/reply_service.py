"""
답글 관리 서비스 클래스
- 비즈니스 로직 처리
- DB 연동 및 상태 관리
- 다양한 플랫폼 지원 (확장성)
"""
import logging
import traceback
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

# Supabase 연결
from ..dependencies import get_supabase_client

# 플랫폼별 답글 관리자
from api.crawlers.reply_managers.baemin_reply_manager import BaeminReplyManager

class ReplyPostingService:
    """
    답글 등록/수정 서비스
    - 플랫폼별 답글 관리자 통합
    - DB 상태 관리
    - 비즈니스 로직 처리
    """
    
    def __init__(self):
        self.supabase = get_supabase_client()
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """로깅 설정"""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    async def post_reply_to_platform(
        self, 
        review_id: str, 
        reply_text: str, 
        action: str = "auto"
    ) -> Dict[str, Any]:
        """
        메인 함수: 답글을 플랫폼에 등록/수정
        
        Args:
            review_id: 리뷰 고유 ID
            reply_text: 답글 내용
            action: "auto" (자동판단), "post" (강제등록), "edit" (강제수정)
            
        Returns:
            Dict: {
                "success": bool,
                "action_taken": str,  # "posted", "edited", "no_action"
                "message": str,
                "error": str,
                "review_info": dict
            }
        """
        try:
            self.logger.info(f"답글 등록/수정 요청 - Review ID: {review_id}, Action: {action}")
            
            # 1. 입력 검증
            validation_result = await self._validate_inputs(review_id, reply_text)
            if not validation_result[0]:
                return {
                    "success": False,
                    "action_taken": "no_action",
                    "message": validation_result[1],
                    "error": "Validation failed",
                    "review_info": {}
                }
            
            # 2. 리뷰 정보 조회 (매장 정보 포함)
            review_info = await self._get_review_with_store_info(review_id)
            if not review_info:
                return {
                    "success": False,
                    "action_taken": "no_action",
                    "message": "리뷰 정보를 찾을 수 없습니다",
                    "error": "Review not found",
                    "review_info": {}
                }
            
            # 3. 매장 설정 조회 (로그인 정보)
            store_config = await self._get_store_config(review_info["store_code"])
            if not store_config:
                return {
                    "success": False,
                    "action_taken": "no_action",
                    "message": "매장 설정을 찾을 수 없습니다",
                    "error": "Store config not found",
                    "review_info": review_info
                }
            
            # 4. DB 상태 업데이트 (처리 시작)
            await self._update_review_status(review_id, "processing", "답글 등록/수정 처리 중")
            
            # 5. 플랫폼별 답글 관리자 생성 및 실행
            try:
                platform_manager = self._get_platform_manager(
                    review_info["platform"], 
                    store_config
                )
                
                if not platform_manager:
                    return {
                        "success": False,
                        "action_taken": "no_action",
                        "message": f"플랫폼 '{review_info['platform']}' 지원되지 않습니다",
                        "error": "Unsupported platform",
                        "review_info": review_info
                    }
                
                # 6. 실제 답글 등록/수정 실행
                result = await self._execute_reply_management(
                    platform_manager, 
                    review_id, 
                    reply_text, 
                    action
                )
                
                # 7. 결과에 따른 DB 상태 업데이트
                if result["success"]:
                    await self._update_review_status(
                        review_id, 
                        "posted", 
                        f"답글 {result['action_taken']} 성공",
                        reply_text
                    )
                    
                    # 성공 로그 기록
                    await self._log_reply_attempt(
                        review_id, 
                        True, 
                        f"{result['action_taken']} 성공: {result['message']}"
                    )
                    
                    self.logger.info(f"답글 처리 성공 - Review ID: {review_id}, Action: {result['action_taken']}")
                else:
                    await self._update_review_status(
                        review_id, 
                        "failed", 
                        f"답글 처리 실패: {result['message']}"
                    )
                    
                    # 실패 로그 기록
                    await self._log_reply_attempt(
                        review_id, 
                        False, 
                        f"실패: {result['message']}"
                    )
                
                result["review_info"] = review_info
                return result
                
            except Exception as e:
                error_msg = f"답글 처리 실행 중 오류: {str(e)}"
                self.logger.error(f"{error_msg}\n{traceback.format_exc()}")
                
                await self._update_review_status(review_id, "failed", error_msg)
                await self._log_reply_attempt(review_id, False, error_msg)
                
                return {
                    "success": False,
                    "action_taken": "no_action",
                    "message": error_msg,
                    "error": str(e),
                    "review_info": review_info
                }
                
        except Exception as e:
            error_msg = f"답글 서비스 처리 중 오류: {str(e)}"
            self.logger.error(f"{error_msg}\n{traceback.format_exc()}")
            
            return {
                "success": False,
                "action_taken": "no_action",
                "message": error_msg,
                "error": str(e),
                "review_info": {}
            }
    
    async def _validate_inputs(self, review_id: str, reply_text: str) -> Tuple[bool, str]:
        """입력값 검증"""
        try:
            # 1. 리뷰 ID 검증
            if not review_id or not review_id.strip():
                return False, "리뷰 ID가 필요합니다"
            
            # 2. 답글 텍스트 검증
            if not reply_text or not reply_text.strip():
                return False, "답글 내용이 필요합니다"
            
            # 3. 답글 길이 검증 (일반적으로 500자 제한)
            if len(reply_text.strip()) > 500:
                return False, "답글이 너무 깁니다 (최대 500자)"
            
            # 4. 금지 단어 검증 (추후 확장 가능)
            forbidden_words = ["스팸", "광고", "욕설"]  # 실제로는 DB에서 가져오기
            reply_lower = reply_text.lower()
            for word in forbidden_words:
                if word in reply_lower:
                    return False, f"금지된 단어가 포함되어 있습니다: {word}"
            
            return True, "검증 성공"
            
        except Exception as e:
            return False, f"입력 검증 중 오류: {str(e)}"
    
    async def _get_review_with_store_info(self, review_id: str) -> Optional[Dict[str, Any]]:
        """리뷰 정보와 매장 정보를 함께 조회"""
        try:
            # reviews 테이블과 platform_reply_rules 테이블 조인
            response = self.supabase.table("reviews").select(
                "id, review_id, store_code, platform, platform_code, "
                "review_content, rating, review_date, "
                "ai_response, manual_response, final_response, "
                "response_status, response_method, "
                "platform_reply_rules(store_name, platform_id, platform_pw)"
            ).eq("review_id", review_id).execute()
            
            if response.data and len(response.data) > 0:
                review_data = response.data[0]
                
                # 매장 정보 추가
                if review_data.get("platform_reply_rules"):
                    store_info = review_data["platform_reply_rules"]
                    review_data.update({
                        "store_name": store_info.get("store_name"),
                        "platform_id": store_info.get("platform_id"),
                        "platform_pw": store_info.get("platform_pw")
                    })
                
                return review_data
            
            return None
            
        except Exception as e:
            self.logger.error(f"리뷰 정보 조회 실패: {str(e)}")
            return None
    
    async def _get_store_config(self, store_code: str) -> Optional[Dict[str, Any]]:
        """매장 설정 조회 (로그인 정보 등)"""
        try:
            response = self.supabase.table("platform_reply_rules").select(
                "store_code, store_name, platform, platform_code, "
                "platform_id, platform_pw, "
                "greeting_start, greeting_end, role, tone, "
                "max_length, auto_reply_enabled"
            ).eq("store_code", store_code).eq("is_active", True).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            
            return None
            
        except Exception as e:
            self.logger.error(f"매장 설정 조회 실패: {str(e)}")
            return None
    
    def _get_platform_manager(self, platform: str, store_config: Dict[str, Any]):
        """플랫폼별 답글 관리자 생성"""
        try:
            if platform.lower() == "baemin":
                manager = BaeminReplyManager(store_config)
                # 브라우저 설정
                if manager.setup_browser(headless=True):
                    return manager
                else:
                    self.logger.error("배민 답글 관리자 브라우저 설정 실패")
                    return None
            
            elif platform.lower() == "coupang":
                # 쿠팡이츠 지원 (추후 구현)
                self.logger.warning("쿠팡이츠 답글 관리자는 아직 구현되지 않았습니다")
                return None
            
            elif platform.lower() == "yogiyo":
                # 요기요 지원 (추후 구현)
                self.logger.warning("요기요 답글 관리자는 아직 구현되지 않았습니다")
                return None
            
            else:
                self.logger.error(f"지원되지 않는 플랫폼: {platform}")
                return None
                
        except Exception as e:
            self.logger.error(f"플랫폼 관리자 생성 실패: {str(e)}")
            return None
    
    async def _execute_reply_management(
        self, 
        platform_manager, 
        review_id: str, 
        reply_text: str, 
        action: str
    ) -> Dict[str, Any]:
        """실제 답글 등록/수정 실행"""
        try:
            with platform_manager:  # 컨텍스트 매니저로 안전한 브라우저 관리
                # 1. 플랫폼 로그인
                login_success, login_message = platform_manager.login_to_platform()
                if not login_success:
                    return {
                        "success": False,
                        "action_taken": "no_action",
                        "message": f"플랫폼 로그인 실패: {login_message}",
                        "error": "Login failed"
                    }
                
                # 2. 리뷰 페이지로 이동
                nav_success, nav_message = platform_manager.navigate_to_reviews_page()
                if not nav_success:
                    return {
                        "success": False,
                        "action_taken": "no_action",
                        "message": f"리뷰 페이지 이동 실패: {nav_message}",
                        "error": "Navigation failed"
                    }
                
                # 3. 답글 관리 실행 (등록/수정 자동 판단)
                result = platform_manager.manage_reply(review_id, reply_text, action)
                
                # 4. 로그아웃
                platform_manager.logout()
                
                return result
                
        except Exception as e:
            error_msg = f"답글 관리 실행 중 오류: {str(e)}"
            self.logger.error(f"{error_msg}\n{traceback.format_exc()}")
            return {
                "success": False,
                "action_taken": "no_action",
                "message": error_msg,
                "error": str(e)
            }
    
    async def _update_review_status(
        self, 
        review_id: str, 
        status: str, 
        message: str = None, 
        final_response: str = None
    ) -> bool:
        """리뷰 답글 상태 업데이트"""
        try:
            update_data = {
                "response_status": status,
                "updated_at": datetime.now().isoformat()
            }
            
            if message:
                update_data["error_message"] = message
            
            if final_response:
                update_data["final_response"] = final_response
                update_data["response_at"] = datetime.now().isoformat()
            
            if status == "processing":
                update_data["processing_started_at"] = datetime.now().isoformat()
            
            response = self.supabase.table("reviews").update(
                update_data
            ).eq("review_id", review_id).execute()
            
            if response.data:
                self.logger.info(f"리뷰 상태 업데이트 성공: {review_id} -> {status}")
                return True
            else:
                self.logger.error(f"리뷰 상태 업데이트 실패: {review_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"리뷰 상태 업데이트 중 오류: {str(e)}")
            return False
    
    async def _log_reply_attempt(
        self, 
        review_id: str, 
        success: bool, 
        message: str = None
    ) -> None:
        """답글 시도 로그 기록"""
        try:
            log_data = {
                "review_id": review_id,
                "success": success,
                "message": message or "",
                "attempted_at": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat()
            }
            
            # 답글 처리 이력 테이블이 있다면 기록
            # (선택사항: reply_processing_logs 테이블 생성 후 사용)
            # response = self.supabase.table("reply_processing_logs").insert(log_data).execute()
            
            self.logger.info(f"답글 시도 로그: {review_id} - {'성공' if success else '실패'}: {message}")
            
        except Exception as e:
            self.logger.error(f"답글 시도 로그 기록 실패: {str(e)}")
    
    # ===========================================
    # 유틸리티 및 헬퍼 메서드들
    # ===========================================
    
    async def get_review_status(self, review_id: str) -> Dict[str, Any]:
        """리뷰 답글 상태 조회"""
        try:
            response = self.supabase.table("reviews").select(
                "review_id, response_status, final_response, "
                "response_at, error_message, updated_at"
            ).eq("review_id", review_id).execute()
            
            if response.data and len(response.data) > 0:
                return {
                    "success": True,
                    "data": response.data[0],
                    "error": ""
                }
            else:
                return {
                    "success": False,
                    "data": {},
                    "error": "리뷰를 찾을 수 없습니다"
                }
                
        except Exception as e:
            return {
                "success": False,
                "data": {},
                "error": f"상태 조회 실패: {str(e)}"
            }
    
    async def get_pending_reviews(self, store_code: str = None) -> Dict[str, Any]:
        """처리 대기 중인 리뷰 목록 조회"""
        try:
            query = self.supabase.table("reviews").select(
                "review_id, store_code, platform, review_content, "
                "rating, ai_response, response_status, created_at"
            ).in_("response_status", ["generated", "pending", "failed"])
            
            if store_code:
                query = query.eq("store_code", store_code)
            
            response = query.order("created_at", desc=False).execute()
            
            return {
                "success": True,
                "data": response.data,
                "count": len(response.data),
                "error": ""
            }
            
        except Exception as e:
            return {
                "success": False,
                "data": [],
                "count": 0,
                "error": f"대기 리뷰 조회 실패: {str(e)}"
            }

# ===========================================
# 싱글톤 서비스 인스턴스
# ===========================================

_reply_service_instance = None

def get_reply_service() -> ReplyPostingService:
    """답글 서비스 싱글톤 인스턴스 반환"""
    global _reply_service_instance
    if _reply_service_instance is None:
        _reply_service_instance = ReplyPostingService()
    return _reply_service_instance
