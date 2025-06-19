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

logger = logging.getLogger(__name__)

class ErrorLogger:
    """에러 로그 관리 클래스"""
    
    def __init__(self, db: Client):
        self.db = db
        
    async def log_error(
        self,
        category: str,
        severity: str,
        error_type: str,
        error_message: str,
        user_code: Optional[str] = None,
        store_code: Optional[str] = None,
        platform: Optional[str] = None,
        platform_code: Optional[str] = None,
        store_name: Optional[str] = None,
        request_data: Optional[Dict[str, Any]] = None,
        response_data: Optional[Dict[str, Any]] = None,
        stack_trace: Optional[str] = None
    ):
        """에러를 DB에 기록"""
        try:
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
            
            # NULL 값 제거
            error_data = {k: v for k, v in error_data.items() if v is not None}
            
            # DB에 삽입
            response = self.db.table('error_logs').insert(error_data).execute()
            
            if response.data:
                logger.info(f"에러 로그 저장 성공: {error_type} - {error_message}")
                return response.data[0]
            else:
                logger.error("에러 로그 저장 실패")
                return None
                
        except Exception as e:
            logger.error(f"에러 로그 저장 중 오류: {str(e)}")
            return None
    
    async def log_crawler_error(
        self,
        platform: str,
        error_type: str,
        error_message: str,
        store_info: Optional[Dict[str, Any]] = None,
        **kwargs  # 추가 파라미터를 받을 수 있도록
    ):
        """크롤러 관련 에러 로그"""
        # kwargs에서 severity가 있으면 사용, 없으면 기본값 설정
        severity = kwargs.pop('severity', 'high' if error_type in ["LOGIN_FAILED", "BROWSER_CRASH"] else 'medium')
        
        return await self.log_error(
            category="크롤링실패",
            severity=severity,  # 여기서 한 번만 severity 지정
            error_type=f"CRAWLER_{error_type}",
            error_message=error_message,
            platform=platform,
            store_code=store_info.get('store_code') if store_info else None,
            platform_code=store_info.get('platform_code') if store_info else None,
            store_name=store_info.get('store_name') if store_info else None,
            **kwargs  # 나머지 kwargs 전달
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