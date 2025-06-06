"""
인증 관련 유틸리티 함수
"""
from typing import Optional, Dict
from datetime import datetime
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
import logging

from .jwt import verify_token, SECRET_KEY, ALGORITHM
from ..dependencies import get_db
from ..services.database import Database

# 로거 설정
logger = logging.getLogger(__name__)

# 패스워드 암호화 설정
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 설정
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호 검증"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """비밀번호 해시 생성"""
    return pwd_context.hash(password)


async def get_current_user(token: str = Depends(oauth2_scheme), db: Database = Depends(get_db)) -> Dict:
    """
    현재 인증된 사용자 정보 가져오기
    
    Args:
        token: JWT 토큰
        db: 데이터베이스 세션
    
    Returns:
        사용자 정보 딕셔너리
    
    Raises:
        HTTPException: 인증 실패시
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 정보를 확인할 수 없습니다",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 토큰 검증
        payload = verify_token(token)
        if payload is None:
            raise credentials_exception
        
        user_code: str = payload.get("user_code")
        if user_code is None:
            raise credentials_exception
        
        # 사용자 정보 조회
        user = await db.fetch_one(
            "SELECT * FROM users WHERE user_code = ? AND is_active = true",
            (user_code,)
        )
        
        if user is None:
            raise credentials_exception
        
        return user
    except JWTError:
        raise credentials_exception
    except Exception as e:
        logger.error(f"사용자 조회 실패: {e}")
        raise credentials_exception


async def get_current_active_user(current_user: Dict = Depends(get_current_user)) -> Dict:
    """활성 사용자만 필터링"""
    if not current_user.get("is_active"):
        raise HTTPException(status_code=400, detail="비활성 사용자")
    return current_user


async def get_admin_user(current_user: Dict = Depends(get_current_user)) -> Dict:
    """관리자 권한 확인"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다"
        )
    return current_user


def generate_user_code(last_code: Optional[str] = None) -> str:
    """
    사용자 코드 생성 (USR001 형식)
    
    Args:
        last_code: 마지막 사용자 코드
    
    Returns:
        새로운 사용자 코드
    """
    if not last_code:
        return "USR001"
    
    try:
        # USR 접두사 제거하고 숫자 추출
        number = int(last_code[3:])
        return f"USR{number + 1:03d}"
    except (ValueError, IndexError):
        # 파싱 실패시 기본값
        return "USR001"


def generate_subscription_code(user_code: str) -> str:
    """
    구독 코드 생성
    
    Args:
        user_code: 사용자 코드
    
    Returns:
        구독 코드 (SUB_USR001_YYYYMMDD 형식)
    """
    date_str = datetime.now().strftime("%Y%m%d")
    return f"SUB_{user_code}_{date_str}"


async def check_store_permission(
    store_code: str,
    current_user: Dict,
    required_permission: str = "view",
    db: Database = Depends(get_db)
) -> bool:
    """
    매장 접근 권한 확인
    
    Args:
        store_code: 매장 코드
        current_user: 현재 사용자
        required_permission: 필요한 권한 (view, edit, admin)
        db: 데이터베이스 세션
    
    Returns:
        권한 여부
    """
    user_code = current_user.get("user_code")
    user_role = current_user.get("role")
    
    # 관리자는 모든 권한
    if user_role == 'admin':
        return True
    
    try:
        # 매장 소유자 확인
        store_result = await db.fetch_one(
            "SELECT owner_user_code FROM platform_reply_rules WHERE store_code = ?",
            (store_code,)
        )
        
        if store_result and store_result['owner_user_code'] == user_code:
            return True
        
        # 권한 테이블 확인
        permission_map = {
            'view': 'can_view',
            'edit': 'can_edit_settings',
            'reply': 'can_reply',
            'admin': 'can_manage_users'
        }
        
        permission_field = permission_map.get(required_permission, 'can_view')
        
        perm_result = await db.fetch_one(
            f"SELECT {permission_field} FROM user_store_permissions WHERE user_code = ? AND store_code = ? AND is_active = true",
            (user_code, store_code)
        )
        
        if perm_result:
            return perm_result.get(permission_field, False)
        
        return False
    except Exception as e:
        logger.error(f"권한 확인 실패: {e}")
        return False
