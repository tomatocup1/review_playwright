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

from api.schemas.auth import User, TokenData
from config.supabase_client import get_supabase_client
from api.services.supabase_service import SupabaseService

load_dotenv()

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
    
    # Supabase에서 사용자 정보 조회
    supabase = get_db()
    
    @async_wrapper
    def fetch_user():
        response = supabase.table('users').select('*').eq('user_code', token_data.user_code).eq('is_active', True).execute()
        return response
    
    response = await fetch_user()
    
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
    except:
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
