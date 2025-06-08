"""
리뷰 관련 스키마 정의 - ordered_menu 필드 수정
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Union
from datetime import datetime


class ReviewCollectRequest(BaseModel):
    """리뷰 수집 요청"""
    store_code: str = Field(..., description="매장 코드")
    async_mode: bool = Field(False, description="비동기 실행 여부")


class ReviewCollectResponse(BaseModel):
    """리뷰 수집 응답"""
    success: bool
    message: str
    collected: int = Field(0, description="수집된 리뷰 수")
    store_code: str
    platform: Optional[str] = None
    errors: List[str] = []


class ReviewResponse(BaseModel):
    """리뷰 조회 응답"""
    review_id: str
    store_code: str
    platform: str
    platform_code: str
    review_name: str
    rating: int
    review_content: str
    ordered_menu: Optional[Union[str, List[str]]] = None  # str 또는 List[str] 허용
    delivery_review: Optional[str] = None
    review_date: str
    review_images: Optional[List[str]] = []
    response_status: str
    final_response: Optional[str] = None
    response_at: Optional[datetime] = None
    boss_reply_needed: bool
    created_at: datetime
    
    @field_validator('ordered_menu', mode='before')
    @classmethod
    def validate_ordered_menu(cls, v):
        """ordered_menu 필드를 문자열로 변환"""
        if v is None:
            return None
        if isinstance(v, list):
            # 리스트인 경우 쉼표로 구분된 문자열로 변환
            return ', '.join(str(item) for item in v if item)
        return str(v)
    
    class Config:
        from_attributes = True


class ReplyRequest(BaseModel):
    """답글 등록 요청"""
    reply_content: str = Field(..., min_length=1, max_length=1000)
    reply_type: str = Field('manual', pattern="^(ai_auto|ai_manual|full_manual)$")


class ReplyResponse(BaseModel):
    """답글 등록 응답"""
    success: bool
    message: str
    review_id: str
    reply_content: str
