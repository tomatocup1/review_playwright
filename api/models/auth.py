"""
인증 관련 Pydantic 모델
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime


class UserLogin(BaseModel):
    """로그인 요청 모델"""
    email: EmailStr
    password: str = Field(..., min_length=6)
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "password123"
            }
        }


class UserRegister(BaseModel):
    """회원가입 요청 모델"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    name: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = Field(None, regex=r"^01\d-?\d{3,4}-?\d{4}$")
    company_name: Optional[str] = Field(None, max_length=100)
    marketing_consent: bool = False
    
    @validator('password')
    def validate_password(cls, v):
        """비밀번호 복잡도 검증"""
        if not any(char.isdigit() for char in v):
            raise ValueError('비밀번호는 최소 하나의 숫자를 포함해야 합니다')
        if not any(char.isalpha() for char in v):
            raise ValueError('비밀번호는 최소 하나의 문자를 포함해야 합니다')
        return v
    
    @validator('phone')
    def format_phone(cls, v):
        """전화번호 포맷팅"""
        if v:
            # 하이픈 제거
            v = v.replace('-', '')
            # 포맷팅
            if len(v) == 10:
                return f"{v[:3]}-{v[3:6]}-{v[6:]}"
            elif len(v) == 11:
                return f"{v[:3]}-{v[3:7]}-{v[7:]}"
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "password123",
                "name": "홍길동",
                "phone": "010-1234-5678",
                "company_name": "테스트 회사",
                "marketing_consent": True
            }
        }


class Token(BaseModel):
    """토큰 응답 모델"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(default=86400, description="토큰 만료 시간(초)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 86400
            }
        }


class TokenData(BaseModel):
    """토큰 데이터 모델"""
    user_code: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None


class UserResponse(BaseModel):
    """사용자 응답 모델"""
    user_code: str
    email: str
    name: str
    phone: Optional[str]
    role: str
    company_name: Optional[str]
    email_verified: bool
    phone_verified: bool
    signup_date: datetime
    last_login: Optional[datetime]
    is_active: bool
    created_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_code": "USR001",
                "email": "user@example.com",
                "name": "홍길동",
                "phone": "010-1234-5678",
                "role": "owner",
                "company_name": "테스트 회사",
                "email_verified": True,
                "phone_verified": False,
                "signup_date": "2024-01-01T00:00:00",
                "last_login": "2024-01-15T10:30:00",
                "is_active": True,
                "created_at": "2024-01-01T00:00:00"
            }
        }


class PasswordChange(BaseModel):
    """비밀번호 변경 모델"""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)
    
    @validator('new_password')
    def validate_new_password(cls, v, values):
        """새 비밀번호 검증"""
        if 'current_password' in values and v == values['current_password']:
            raise ValueError('새 비밀번호는 현재 비밀번호와 달라야 합니다')
        if not any(char.isdigit() for char in v):
            raise ValueError('비밀번호는 최소 하나의 숫자를 포함해야 합니다')
        if not any(char.isalpha() for char in v):
            raise ValueError('비밀번호는 최소 하나의 문자를 포함해야 합니다')
        return v


class PasswordReset(BaseModel):
    """비밀번호 재설정 모델"""
    email: EmailStr
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com"
            }
        }


class EmailVerification(BaseModel):
    """이메일 인증 모델"""
    token: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "token": "verification-token-string"
            }
        }
