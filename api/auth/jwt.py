"""
JWT 토큰 관리 모듈
"""
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv
import logging

# 환경변수 로드
load_dotenv()

# 로거 설정
logger = logging.getLogger(__name__)

# JWT 설정
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60  # 24시간

# 비밀번호 해싱 설정
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호 검증"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """비밀번호 해싱"""
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    JWT 액세스 토큰 생성
    
    Args:
        data: 토큰에 포함할 데이터
        expires_delta: 만료 시간 (기본값: 24시간)
    
    Returns:
        JWT 토큰 문자열
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    
    try:
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    except Exception as e:
        logger.error(f"토큰 생성 실패: {e}")
        raise


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    JWT 토큰 검증
    
    Args:
        token: 검증할 JWT 토큰
    
    Returns:
        토큰 페이로드 또는 None
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.error(f"토큰 검증 실패: {e}")
        return None
    except Exception as e:
        logger.error(f"예상치 못한 토큰 검증 오류: {e}")
        return None


def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    리프레시 토큰 생성 (7일 유효)
    
    Args:
        data: 토큰에 포함할 데이터
    
    Returns:
        리프레시 토큰 문자열
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire, "type": "refresh"})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_refresh_token(token: str) -> Optional[Dict[str, Any]]:
    """
    리프레시 토큰 검증
    
    Args:
        token: 검증할 리프레시 토큰
    
    Returns:
        토큰 페이로드 또는 None
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError:
        return None
