"""
에러 처리 통합 모듈
Supabase error_logs 테이블에 에러를 기록하고 관리
"""
import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import json
import asyncio
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로거 설정
logger = logging.getLogger(__name__)


class ErrorCategory:
    """에러 카테고리 상수"""
    SYSTEM_ERROR = '시스템오류'
    CRAWLING_FAILED = '크롤링실패'
    REPLY_FAILED = '답글등록실패'
    LOGIN_FAILED = '로그인실패'
    PAYMENT_ERROR = '결제오류'
    PERMISSION_ERROR = '권한오류'
    API_ERROR = 'API오류'
    DB_ERROR = 'DB오류'
    NETWORK_ERROR = '네트워크오류'


class ErrorSeverity:
    """에러 심각도 상수"""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


class ErrorType:
    """에러 타입 상수"""
    # 로그인 관련
    INVALID_CREDENTIALS = 'invalid_credentials'
    ACCOUNT_LOCKED = 'account_locked'
    CAPTCHA_REQUIRED = 'captcha_required'
    SESSION_EXPIRED = 'session_expired'
    
    # 크롤링 관련
    PAGE_LOAD_TIMEOUT = 'page_load_timeout'
    ELEMENT_NOT_FOUND = 'element_not_found'
    NETWORK_ERROR = 'network_error'
    UI_CHANGED = 'ui_changed'
    
    # AI API 관련
    API_RATE_LIMIT = 'api_rate_limit'
    TOKEN_LIMIT_EXCEEDED = 'token_limit_exceeded'
    API_TIMEOUT = 'api_timeout'
    INVALID_RESPONSE = 'invalid_response'
    
    # 답글 등록 관련
    REPLY_INPUT_NOT_FOUND = 'reply_input_not_found'
    REPLY_LENGTH_EXCEEDED = 'reply_length_exceeded'
    DUPLICATE_REPLY = 'duplicate_reply'
    NO_PERMISSION = 'no_permission'
    
    # DB 관련
    CONNECTION_FAILED = 'connection_failed'
    QUERY_TIMEOUT = 'query_timeout'
    DUPLICATE_KEY = 'duplicate_key'
    TRANSACTION_FAILED = 'transaction_failed'


class ErrorHandler:
    """통합 에러 처리 클래스"""
    
    def __init__(self):
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        self.supabase: Optional[Client] = None
        
        # 로컬 로그 디렉토리
        self.log_dir = Path("C:/Review_playwright/logs/errors")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Supabase 클라이언트 초기화
        if self.supabase_url and self.supabase_key:
            try:
                self.supabase = create_client(self.supabase_url, self.supabase_key)
            except Exception as e:
                logger.error(f"Supabase 초기화 실패: {str(e)}")
    
    async def log_error(
        self,
        error_code: str,
        category: str,
        severity: str,
        error_type: str,
        error_message: str,
        platform: Optional[str] = None,
        store_code: Optional[str] = None,
        store_name: Optional[str] = None,
        user_code: Optional[str] = None,
        request_data: Optional[Dict] = None,
        response_data: Optional[Dict] = None,
        stack_trace: Optional[str] = None,
        screenshot_path: Optional[str] = None,
        current_url: Optional[str] = None,
        additional_data: Optional[Dict] = None
    ) -> bool:
        """
        에러를 Supabase error_logs 테이블에 기록
        
        Args:
            error_code: 에러 코드 (ERR001, ERR002 등)
            category: 에러 카테고리 (ErrorCategory 상수 사용)
            severity: 심각도 (ErrorSeverity 상수 사용)
            error_type: 구체적 에러 유형 (ErrorType 상수 사용)
            error_message: 에러 메시지
            platform: 플랫폼명 (baemin, coupang, yogiyo)
            store_code: 매장 코드
            store_name: 매장 이름
            user_code: 사용자 코드
            request_data: 요청 데이터
            response_data: 응답 데이터
            stack_trace: 스택 트레이스
            screenshot_path: 스크린샷 경로
            current_url: 현재 URL
            additional_data: 추가 데이터
        
        Returns:
            bool: 로깅 성공 여부
        """
        try:
            # 에러 데이터 구성
            error_data = {
                'error_code': error_code,
                'category': category,
                'severity': severity,
                'error_type': error_type,
                'error_message': error_message,
                'platform': platform,
                'store_code': store_code,
                'store_name': store_name,
                'user_code': user_code,
                'request_data': request_data,
                'response_data': response_data,
                'stack_trace': stack_trace or traceback.format_exc(),
                'occurred_at': datetime.now().isoformat(),
                'status': 'new',
                'environment': 'production',
                'version': '1.0.0'
            }
            
            # 추가 데이터 병합
            if additional_data:
                error_data.update(additional_data)
            
            # 스크린샷 경로 추가
            if screenshot_path:
                error_data['response_data'] = error_data.get('response_data', {})
                error_data['response_data']['screenshot_path'] = screenshot_path
            
            # 현재 URL 추가
            if current_url:
                error_data['request_data'] = error_data.get('request_data', {})
                error_data['request_data']['current_url'] = current_url
            
            # 로컬 파일에 먼저 저장
            await self._save_to_local_file(error_data)
            
            # Supabase에 저장
            if self.supabase:
                try:
                    result = self.supabase.table('error_logs').insert(error_data).execute()
                    logger.info(f"에러 로그 DB 저장 완료: {error_code}")
                    return True
                except Exception as e:
                    logger.error(f"에러 로그 DB 저장 실패: {str(e)}")
                    # DB 저장 실패해도 로컬 저장은 성공
                    return True
            
            return True
            
        except Exception as e:
            logger.error(f"에러 로깅 중 예외 발생: {str(e)}")
            return False
    
    async def _save_to_local_file(self, error_data: Dict[str, Any]):
        """로컬 파일에 에러 로그 저장"""
        try:
            # 날짜별 파일 생성
            date_str = datetime.now().strftime("%Y%m%d")
            log_file = self.log_dir / f"error_log_{date_str}.json"
            
            # 기존 로그 읽기
            logs = []
            if log_file.exists():
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        logs = json.load(f)
                except:
                    logs = []
            
            # 새 로그 추가
            logs.append(error_data)
            
            # 파일에 저장
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f"에러 로그 로컬 저장 완료: {log_file}")
            
        except Exception as e:
            logger.error(f"로컬 파일 저장 실패: {str(e)}")
    
    async def log_login_error(
        self,
        platform: str,
        username: str,
        error_type: str,
        error_message: str,
        screenshot_path: Optional[str] = None,
        **kwargs
    ):
        """로그인 에러 전용 로깅"""
        error_code = f"LOGIN_{platform.upper()}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        await self.log_error(
            error_code=error_code,
            category=ErrorCategory.LOGIN_FAILED,
            severity=ErrorSeverity.HIGH if error_type == ErrorType.ACCOUNT_LOCKED else ErrorSeverity.MEDIUM,
            error_type=error_type,
            error_message=error_message,
            platform=platform,
            request_data={'username': username},
            screenshot_path=screenshot_path,
            **kwargs
        )
    
    async def log_crawling_error(
        self,
        platform: str,
        store_code: str,
        store_name: str,
        error_type: str,
        error_message: str,
        current_url: Optional[str] = None,
        screenshot_path: Optional[str] = None,
        **kwargs
    ):
        """크롤링 에러 전용 로깅"""
        error_code = f"CRAWL_{platform.upper()}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        await self.log_error(
            error_code=error_code,
            category=ErrorCategory.CRAWLING_FAILED,
            severity=ErrorSeverity.MEDIUM,
            error_type=error_type,
            error_message=error_message,
            platform=platform,
            store_code=store_code,
            store_name=store_name,
            current_url=current_url,
            screenshot_path=screenshot_path,
            **kwargs
        )
    
    async def log_reply_error(
        self,
        platform: str,
        store_code: str,
        store_name: str,
        review_id: str,
        error_type: str,
        error_message: str,
        reply_text: Optional[str] = None,
        screenshot_path: Optional[str] = None,
        **kwargs
    ):
        """답글 등록 에러 전용 로깅"""
        error_code = f"REPLY_{platform.upper()}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        await self.log_error(
            error_code=error_code,
            category=ErrorCategory.REPLY_FAILED,
            severity=ErrorSeverity.HIGH,
            error_type=error_type,
            error_message=error_message,
            platform=platform,
            store_code=store_code,
            store_name=store_name,
            request_data={
                'review_id': review_id,
                'reply_text': reply_text[:100] if reply_text else None  # 처음 100자만
            },
            screenshot_path=screenshot_path,
            **kwargs
        )
    
    async def log_api_error(
        self,
        api_type: str,  # 'openai', 'supabase' 등
        error_type: str,
        error_message: str,
        request_data: Optional[Dict] = None,
        response_data: Optional[Dict] = None,
        **kwargs
    ):
        """API 에러 전용 로깅"""
        error_code = f"API_{api_type.upper()}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        severity = ErrorSeverity.CRITICAL if error_type == ErrorType.API_RATE_LIMIT else ErrorSeverity.MEDIUM
        
        await self.log_error(
            error_code=error_code,
            category=ErrorCategory.API_ERROR,
            severity=severity,
            error_type=error_type,
            error_message=error_message,
            request_data=request_data,
            response_data=response_data,
            **kwargs
        )


# 싱글톤 인스턴스
error_handler = ErrorHandler()


# 편의 함수들
async def log_login_error(*args, **kwargs):
    """로그인 에러 로깅 편의 함수"""
    return await error_handler.log_login_error(*args, **kwargs)


async def log_crawling_error(*args, **kwargs):
    """크롤링 에러 로깅 편의 함수"""
    return await error_handler.log_crawling_error(*args, **kwargs)


async def log_reply_error(*args, **kwargs):
    """답글 에러 로깅 편의 함수"""
    return await error_handler.log_reply_error(*args, **kwargs)


async def log_api_error(*args, **kwargs):
    """API 에러 로깅 편의 함수"""
    return await error_handler.log_api_error(*args, **kwargs)
