"""
에러 로깅 서비스
모든 에러를 Supabase error_logs 테이블에 저장
"""
import traceback
import json
from datetime import datetime
from typing import Optional, Dict, Any
from supabase import Client
import logging
from playwright.async_api import Page
import os

logger = logging.getLogger(__name__)

class ErrorLogger:
    """에러 로그 관리 클래스"""
    
    def __init__(self, db: Client = None):
        self.db = db
        self._initialized = False
        
    def initialize(self, db: Client):
        """DB 클라이언트 초기화"""
        self.db = db
        self._initialized = True
        
    async def log_error(
        self,
        error_type: str,
        error_message: str,
        category: str = "시스템오류",
        severity: str = "medium",
        user_code: Optional[str] = None,
        store_code: Optional[str] = None,
        platform: Optional[str] = None,
        platform_code: Optional[str] = None,
        store_name: Optional[str] = None,
        store_info: Optional[Dict[str, Any]] = None,
        review_info: Optional[Dict[str, Any]] = None,
        request_data: Optional[Dict[str, Any]] = None,
        response_data: Optional[Dict[str, Any]] = None,
        stack_trace: Optional[str] = None
    ):
        """에러를 DB에 기록"""
        try:
            # store_info가 있으면 그 정보를 사용
            if store_info:
                store_code = store_code or store_info.get('store_code')
                platform = platform or store_info.get('platform')
                platform_code = platform_code or store_info.get('platform_code')
                store_name = store_name or store_info.get('store_name')
            
            # 스택 트레이스가 없으면 현재 스택 트레이스 가져오기
            if stack_trace is None and severity in ['high', 'critical']:
                stack_trace = traceback.format_exc()
            
            error_data = {
                "category": category,
                "severity": severity,
                "error_type": error_type,
                "error_message": error_message,
                "user_code": user_code,
                "store_code": store_code,
                "platform": platform,
                "platform_code": platform_code,
                "store_name": store_name,
                "request_data": json.dumps(request_data) if request_data else None,
                "response_data": json.dumps(response_data) if response_data else None,
                "stack_trace": stack_trace,
                "status": "new",
                "occurred_at": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat()
            }
            
            # review_info가 있으면 request_data에 추가
            if review_info:
                existing_request_data = request_data or {}
                existing_request_data['review_info'] = review_info
                error_data['request_data'] = json.dumps(existing_request_data)
            
            # NULL 값 제거
            error_data = {k: v for k, v in error_data.items() if v is not None}
            
            # DB에 삽입 (DB가 초기화되어 있을 때만)
            if self._initialized and self.db:
                response = self.db.table('error_logs').insert(error_data).execute()
                
                if response.data:
                    logger.info(f"에러 로그 저장 성공: {error_type} - {error_message}")
                    return response.data[0]
                else:
                    logger.error("에러 로그 저장 실패")
            else:
                # DB가 초기화되지 않았으면 파일로만 로깅
                logger.warning("ErrorLogger DB가 초기화되지 않음. 파일 로깅만 수행")
                await self._log_to_file(platform or "system", error_type, error_message)
                
            return None
                
        except Exception as e:
            logger.error(f"에러 로그 저장 중 오류: {str(e)}")
            # 에러 로그 저장 실패시 파일로 로깅
            await self._log_to_file(platform or "system", error_type, error_message)
            return None
    
    async def _log_to_file(self, platform: str, error_type: str, error_message: str):
        """파일로 에러 로깅"""
        try:
            log_dir = os.path.join("logs")
            os.makedirs(log_dir, exist_ok=True)
            
            error_log_file = os.path.join(log_dir, f"{platform}_errors.log")
            with open(error_log_file, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat()} - [{error_type}] {error_message}\n")
        except Exception as e:
            logger.error(f"파일 로깅 중 오류: {str(e)}")
    
    async def log_crawler_error(
        self,
        platform: str,
        error_type: str,
        error_message: str,
        store_info: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """크롤러 관련 에러 로그"""
        severity = kwargs.pop('severity', 'high' if error_type in ["LOGIN_FAILED", "BROWSER_CRASH"] else 'medium')
        
        return await self.log_error(
            category="크롤링실패",
            severity=severity,
            error_type=f"CRAWLER_{error_type}",
            error_message=error_message,
            platform=platform,
            store_info=store_info,
            **kwargs
        )
    
    async def log_api_error(
        self,
        error_type: str,
        error_message: str,
        endpoint: str,
        user_code: Optional[str] = None,
        **kwargs
    ):
        """API 관련 에러 로그"""
        return await self.log_error(
            category="시스템오류",
            severity="medium",
            error_type=f"API_{error_type}",
            error_message=error_message,
            user_code=user_code,
            request_data={"endpoint": endpoint},
            **kwargs
        )


# 싱글톤 인스턴스 생성
error_logger = ErrorLogger()


# 단독 함수 버전 (이전 버전과의 호환성을 위해)
async def log_error(
    error_type: str,
    error_message: str,
    store_code: Optional[str] = None,
    platform: Optional[str] = None,
    page: Optional[Page] = None,
    severity: str = "medium",
    **kwargs
):
    """
    에러 로깅 함수 (이전 버전과의 호환성)
    크롤러에서 직접 호출할 수 있는 단순화된 버전
    """
    try:
        # 스크린샷 저장 (page 객체가 있을 경우)
        screenshot_path = None
        if page:
            try:
                screenshot_dir = os.path.join("logs", "screenshots", platform or "unknown", "errors")
                os.makedirs(screenshot_dir, exist_ok=True)
                screenshot_path = os.path.join(
                    screenshot_dir, 
                    f"{error_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                )
                await page.screenshot(path=screenshot_path)
                logger.info(f"에러 스크린샷 저장: {screenshot_path}")
            except Exception as e:
                logger.warning(f"스크린샷 저장 실패: {str(e)}")
        
        # 콘솔에 에러 로그
        logger.error(f"[{platform or 'SYSTEM'}] {error_type}: {error_message}")
        
        # 싱글톤 error_logger를 통해 DB에 저장
        await error_logger.log_error(
            error_type=error_type,
            error_message=error_message,
            store_code=store_code,
            platform=platform,
            severity=severity,
            **kwargs
        )
        
    except Exception as e:
        logger.error(f"에러 로깅 중 오류 발생: {str(e)}")


# DB 초기화 함수 (앱 시작시 호출 필요)
def initialize_error_logger(db_client: Client):
    """ErrorLogger DB 클라이언트 초기화"""
    error_logger.initialize(db_client)
    logger.info("ErrorLogger 초기화 완료")