"""
인증 관련 스키마 정의
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserBase(BaseModel):
    """사용자 기본 정보"""
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, pattern=r'^\d{3}-\d{4}-\d{4}$')
    role: str = Field(..., pattern='^(admin|franchise|sales|owner)$')
    company_name: Optional[str] = Field(None, max_length=100)


class UserCreate(UserBase):
    """사용자 생성"""
    password: str = Field(..., min_length=8, max_length=100)
    marketing_consent: bool = False


class UserUpdate(BaseModel):
    """사용자 정보 수정"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, pattern=r'^\d{3}-\d{4}-\d{4}$')
    company_name: Optional[str] = Field(None, max_length=100)
    password: Optional[str] = Field(None, min_length=8, max_length=100)
    marketing_consent: Optional[bool] = None


class User(BaseModel):
    """사용자 응답"""
    model_config = ConfigDict(from_attributes=True)
    
    user_code: str
    email: EmailStr
    name: str
    phone: Optional[str] = None
    role: str
    company_name: Optional[str] = None
    email_verified: bool
    phone_verified: bool = False
    is_active: bool
    signup_date: Optional[datetime] = None
    last_login: Optional[datetime] = None
    login_count: int = 0
    created_at: datetime


class UserInDB(User):
    """DB의 사용자 정보 (비밀번호 포함)"""
    password_hash: str


class Token(BaseModel):
    """JWT 토큰"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class TokenData(BaseModel):
    """토큰 데이터"""
    user_code: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None


class LoginRequest(BaseModel):
    """로그인 요청"""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """로그인 응답"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: User


class PasswordChange(BaseModel):
    """비밀번호 변경"""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)


class PasswordReset(BaseModel):
    """비밀번호 재설정"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """비밀번호 재설정 확인"""
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)


class EmailVerification(BaseModel):
    """이메일 인증"""
    token: str


class UserStats(BaseModel):
    """사용자 통계"""
    total_stores: int = 0
    active_stores: int = 0
    total_reviews: int = 0
    replied_reviews: int = 0
    reply_rate: float = 0.0
    avg_rating: float = 0.0
    subscription_status: str = "no_subscription"
    days_until_expiry: Optional[int] = None
