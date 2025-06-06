"""
인증 관련 유틸리티 함수
"""
from typing import Optional, Dict
from datetime import datetime
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from config.supabase_client import get_supabase_client
from .jwt import verify_token, SECRET_KEY, ALGORITHM
import logging

# 로거 설정
logger = logging.getLogger(__name__)

# OAuth2 설정
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict:
    """
    현재 인증된 사용자 정보 가져오기
    
    Args:
        token: JWT 토큰
    
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
    
    # 토큰 검증
    payload = verify_token(token)
    if payload is None:
        raise credentials_exception
    
    user_code: str = payload.get("sub")
    if user_code is None:
        raise credentials_exception
    
    # 사용자 정보 조회
    supabase = get_supabase_client()
    try:
        response = supabase.table('users').select("*").eq('user_code', user_code).single().execute()
        user = response.data
        
        if user is None:
            raise credentials_exception
        
        # 활성 사용자 확인
        if not user.get('is_active', False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="비활성화된 계정입니다"
            )
        
        return user
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
    current_user: Dict = Depends(get_current_user),
    required_permission: str = "view"
) -> bool:
    """
    매장 접근 권한 확인
    
    Args:
        store_code: 매장 코드
        current_user: 현재 사용자
        required_permission: 필요한 권한 (view, edit, admin)
    
    Returns:
        권한 여부
    """
    supabase = get_supabase_client()
    user_code = current_user['user_code']
    user_role = current_user['role']
    
    # 관리자는 모든 권한
    if user_role == 'admin':
        return True
    
    try:
        # 매장 소유자 확인
        store_response = supabase.table('platform_reply_rules').select('owner_user_code').eq('store_code', store_code).single().execute()
        
        if store_response.data and store_response.data['owner_user_code'] == user_code:
            return True
        
        # 권한 테이블 확인
        permission_map = {
            'view': 'can_view',
            'edit': 'can_edit_settings',
            'reply': 'can_reply',
            'admin': 'can_manage_users'
        }
        
        permission_field = permission_map.get(required_permission, 'can_view')
        
        perm_response = supabase.table('user_store_permissions').select(permission_field).eq('user_code', user_code).eq('store_code', store_code).eq('is_active', True).single().execute()
        
        if perm_response.data:
            return perm_response.data.get(permission_field, False)
        
        return False
    except Exception as e:
        logger.error(f"권한 확인 실패: {e}")
        return False
