"""
인증 관련 API 엔드포인트
- 회원가입
- 로그인
- 현재 사용자 정보 조회
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from ..models.auth import LoginRequest, TokenResponse
from ..models.user import UserCreate, UserResponse, UserInDB
from ..auth.jwt import create_access_token, create_refresh_token
from ..auth.utils import verify_password, get_password_hash, get_current_user
from ..services.user_service import UserService
from config.database import get_db

router = APIRouter(prefix="/api/auth", tags=["authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """
    새로운 사용자 등록
    
    - **email**: 이메일 주소 (중복 불가)
    - **password**: 비밀번호 (8자 이상)
    - **name**: 사용자 이름
    - **phone**: 전화번호 (선택)
    - **company_name**: 회사명 (선택)
    """
    user_service = UserService(db)
    
    # 이메일 중복 확인
    if user_service.get_user_by_email(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 등록된 이메일입니다."
        )
    
    # 사용자 생성
    user = user_service.create_user(user_data)
    return user

@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    사용자 로그인
    
    - **email**: 이메일 주소
    - **password**: 비밀번호
    """
    user_service = UserService(db)
    
    # 사용자 확인
    user = user_service.get_user_by_email(login_data.email)
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 계정 활성화 확인
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다."
        )
    
    # 토큰 생성
    access_token = create_access_token(data={"sub": user.email, "user_code": user.user_code})
    refresh_token = create_refresh_token(data={"sub": user.email, "user_code": user.user_code})
    
    # 로그인 정보 업데이트
    user_service.update_last_login(user.user_code)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: UserInDB = Depends(get_current_user)
):
    """
    현재 로그인한 사용자 정보 조회
    
    Authorization 헤더에 Bearer 토큰 필요
    """
    return current_user

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_db)
):
    """
    리프레시 토큰으로 새로운 액세스 토큰 발급
    
    - **refresh_token**: 리프레시 토큰
    """
    # TODO: 리프레시 토큰 검증 및 새 토큰 발급 로직 구현
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="리프레시 토큰 기능은 아직 구현되지 않았습니다."
    )
