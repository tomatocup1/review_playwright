"""
의존성 주입을 위한 모듈
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime
import os
from dotenv import load_dotenv
from supabase import Client
import asyncio
from functools import wraps
import time
import logging
from httpx import RemoteProtocolError, ConnectError, TimeoutException

from api.schemas.auth import User, TokenData
from config.supabase_client import get_supabase_client
from api.services.supabase_service import SupabaseService
from api.services.reply_posting_service import ReplyPostingService
from api.services.reply_posting_service import ReplyPostingService

load_dotenv()

# 로깅 설정
logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Supabase 클라이언트 인스턴스
_supabase_client = None

def get_db() -> Client:
    """Supabase 클라이언트 의존성"""
    global _supabase_client
    if not _supabase_client:
        _supabase_client = get_supabase_client()
    return _supabase_client


def async_wrapper(func):
    """동기 함수를 비동기로 래핑"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)
    return wrapper


def retry_on_connection_error(max_retries=3, delay=1):
    """연결 오류 시 재시도 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (RemoteProtocolError, ConnectError, TimeoutException) as e:
                    last_exception = e
                    logger.warning(f"연결 오류 발생 (시도 {attempt + 1}/{max_retries}): {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))  # 지수적 백오프
                        # 새로운 클라이언트 인스턴스 생성
                        global _supabase_client
                        _supabase_client = None
                    continue
                except Exception as e:
                    logger.error(f"예상치 못한 오류: {str(e)}")
                    raise e
            
            # 모든 재시도 실패
            logger.error(f"모든 재시도 실패: {str(last_exception)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection failed. Please try again later."
            )
        return wrapper
    return decorator


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """현재 로그인한 사용자 정보 가져오기"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_code: str = payload.get("user_code")
        if user_code is None:
            raise credentials_exception
        token_data = TokenData(user_code=user_code)
    except JWTError:
        raise credentials_exception
    
    # Supabase에서 사용자 정보 조회 (재시도 로직 포함)
    @retry_on_connection_error(max_retries=3, delay=1)
    def fetch_user():
        supabase = get_db()
        response = supabase.table('users').select('*').eq('user_code', token_data.user_code).eq('is_active', True).execute()
        return response
    
    @async_wrapper
    def fetch_user_async():
        return fetch_user()
    
    try:
        response = await fetch_user_async()
    except HTTPException:
        # 이미 HTTPException인 경우 그대로 raise
        raise
    except Exception as e:
        logger.error(f"사용자 조회 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable"
        )
    
    if not response.data:
        raise credentials_exception
    
    user_dict = response.data[0]
    
    # User 객체로 변환
    user = User(
        user_code=user_dict["user_code"],
        email=user_dict["email"],
        name=user_dict["name"],
        phone=user_dict.get("phone"),
        role=user_dict["role"],
        company_name=user_dict.get("company_name"),
        is_active=user_dict["is_active"],
        email_verified=user_dict.get("email_verified", False),
        phone_verified=user_dict.get("phone_verified", False),
        signup_date=user_dict.get("signup_date"),
        last_login=user_dict.get("last_login"),
        login_count=user_dict.get("login_count", 0),
        created_at=user_dict["created_at"]
    )
    
    return user


async def get_current_user_optional(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[User]:
    """현재 로그인한 사용자 정보 가져오기 (선택적)"""
    if not token:
        return None
    
    try:
        return await get_current_user(token)
    except HTTPException as e:
        if e.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            # 서비스 불가 상태는 재발생
            raise e
        # 인증 오류는 무시하고 None 반환
        return None
    except Exception:
        return None


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """활성 사용자만 허용"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """관리자만 허용"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


def get_supabase_service() -> SupabaseService:
    """Supabase 서비스 의존성"""
    return SupabaseService()


def get_database_service() -> SupabaseService:
    """데이터베이스 서비스 의존성 (SupabaseService를 사용)"""
    return SupabaseService()


def get_reply_posting_service(supabase_service: SupabaseService = Depends(get_supabase_service)) -> ReplyPostingService:
    """답글 등록 서비스 의존성"""
    return ReplyPostingService(supabase_service)