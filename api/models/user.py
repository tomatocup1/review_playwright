"""
사용자 관련 Pydantic 모델
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from .auth import UserResponse


class UserCreate(BaseModel):
    """사용자 생성 모델 (내부용)"""
    user_code: str
    email: str
    password_hash: str
    name: str
    phone: Optional[str] = None
    role: str = "owner"
    company_name: Optional[str] = None
    marketing_consent: bool = False


class UserUpdate(BaseModel):
    """사용자 정보 수정 모델"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, regex=r"^01\d-?\d{3,4}-?\d{4}$")
    company_name: Optional[str] = Field(None, max_length=100)
    marketing_consent: Optional[bool] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "홍길동",
                "phone": "010-1234-5678",
                "company_name": "새로운 회사",
                "marketing_consent": True
            }
        }


class UserStats(BaseModel):
    """사용자 통계 모델"""
    user_code: str
    total_stores: int = 0
    active_stores: int = 0
    total_reviews: int = 0
    replied_reviews: int = 0
    reply_rate: float = 0.0
    avg_response_time_hours: float = 0.0
    subscription_status: str
    subscription_end_date: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_code": "USR001",
                "total_stores": 5,
                "active_stores": 3,
                "total_reviews": 150,
                "replied_reviews": 120,
                "reply_rate": 80.0,
                "avg_response_time_hours": 2.5,
                "subscription_status": "active",
                "subscription_end_date": "2024-12-31T23:59:59"
            }
        }


class UserList(BaseModel):
    """사용자 목록 응답 모델"""
    users: List[UserResponse]
    total: int
    page: int
    per_page: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "users": [UserResponse.Config.json_schema_extra["example"]],
                "total": 100,
                "page": 1,
                "per_page": 20
            }
        }


class UserSubscription(BaseModel):
    """사용자 구독 정보 모델"""
    subscription_code: str
    plan_code: str
    plan_name: str
    status: str
    billing_cycle: str
    start_date: datetime
    end_date: datetime
    auto_renewal: bool
    payment_amount: float
    next_billing_date: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "subscription_code": "SUB_USR001_20240101",
                "plan_code": "BASIC",
                "plan_name": "베이직",
                "status": "active",
                "billing_cycle": "monthly",
                "start_date": "2024-01-01T00:00:00",
                "end_date": "2024-01-31T23:59:59",
                "auto_renewal": True,
                "payment_amount": 29000.0,
                "next_billing_date": "2024-02-01T00:00:00"
            }
        }


class UserUsage(BaseModel):
    """사용자 사용량 모델"""
    user_code: str
    tracking_month: str
    stores_count: int = 0
    reviews_processed: int = 0
    manual_replies: int = 0
    ai_api_calls: int = 0
    web_api_calls: int = 0
    error_count: int = 0
    success_rate: float = 0.0
    
    # 요금제 한도
    max_stores: int
    max_reviews_per_month: int
    
    # 남은 한도
    remaining_stores: int
    remaining_reviews: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_code": "USR001",
                "tracking_month": "2024-01",
                "stores_count": 3,
                "reviews_processed": 250,
                "manual_replies": 10,
                "ai_api_calls": 300,
                "web_api_calls": 1000,
                "error_count": 5,
                "success_rate": 98.0,
                "max_stores": 5,
                "max_reviews_per_month": 500,
                "remaining_stores": 2,
                "remaining_reviews": 250
            }
        }
