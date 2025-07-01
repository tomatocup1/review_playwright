"""
매장 관련 Pydantic 스키마
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class PlatformEnum(str, Enum):
    """지원 플랫폼"""
    BAEMIN = "baemin"
    YOGIYO = "yogiyo"
    COUPANG = "coupang"
    NAVER = "naver"

class StoreStatus(str, Enum):
    """매장 상태"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"

class StoreType(str, Enum):
    """매장 유형"""
    DELIVERY_ONLY = "delivery_only"
    DINE_IN = "dine_in"

# 매장 등록 요청
class StoreRegisterRequest(BaseModel):
    """매장 등록 요청"""
    platform: PlatformEnum
    platform_id: str = Field(..., description="플랫폼 로그인 ID")
    platform_pw: str = Field(..., description="플랫폼 로그인 비밀번호")
    store_name: Optional[str] = Field(None, description="매장명 (자동 조회 가능)")
    platform_code: Optional[str] = Field(None, description="플랫폼 매장 코드 (자동 조회 가능)")
    
    # 답글 정책 설정
    greeting_start: str = Field("안녕하세요", description="답글 시작 인사말")
    greeting_end: Optional[str] = Field("감사합니다", description="답글 마무리 인사말")
    role: Optional[str] = Field("친절한 사장님", description="AI 역할 설정")
    tone: Optional[str] = Field("친근하고 정중한", description="답글 톤앤매너")
    prohibited_words: List[str] = Field(default_factory=list, description="사용 금지 단어")
    max_length: int = Field(300, ge=50, le=500, description="답글 최대 길이")
    
    # 별점별 자동 답글 설정
    rating_5_reply: bool = Field(True, description="5점 리뷰 자동 답글")
    rating_4_reply: bool = Field(True, description="4점 리뷰 자동 답글")
    rating_3_reply: bool = Field(True, description="3점 리뷰 자동 답글")
    rating_2_reply: bool = Field(True, description="2점 리뷰 자동 답글")
    rating_1_reply: bool = Field(True, description="1점 리뷰 자동 답글")
    
    # 운영 설정
    auto_reply_enabled: bool = Field(True, description="자동 답글 활성화")
    auto_reply_hours: str = Field("10:00-20:00", description="자동 답글 운영 시간")
    reply_delay_minutes: int = Field(30, ge=0, le=180, description="답글 등록 지연 시간(분)")
    weekend_enabled: bool = Field(True, description="주말 운영 여부")
    holiday_enabled: bool = Field(False, description="공휴일 운영 여부")

# 매장 정보 조회 응답
class StoreInfo(BaseModel):
    """매장 정보"""
    store_code: str
    store_name: str
    platform: PlatformEnum
    platform_code: str
    platform_id: str
    owner_user_code: str
    store_type: StoreType
    business_hours: Optional[Dict[str, str]] = None
    store_address: Optional[str] = None
    store_phone: Optional[str] = None
    
    # 답글 정책
    greeting_start: str
    greeting_end: Optional[str]
    role: Optional[str]
    tone: Optional[str]
    prohibited_words: List[str]
    max_length: int
    
    # 별점별 설정
    rating_5_reply: bool
    rating_4_reply: bool
    rating_3_reply: bool
    rating_2_reply: bool
    rating_1_reply: bool
    
    # 운영 설정
    auto_reply_enabled: bool
    auto_reply_hours: str
    reply_delay_minutes: int
    weekend_enabled: bool
    holiday_enabled: bool
    
    # 통계
    total_reviews_processed: int
    avg_rating: Optional[float]
    is_active: bool
    last_crawled: Optional[datetime]
    last_reply: Optional[datetime]
    created_at: datetime
    updated_at: datetime

# 플랫폼 매장 조회 응답
class PlatformStore(BaseModel):
    """플랫폼에서 조회한 매장 정보"""
    platform: PlatformEnum
    platform_code: str
    store_name: str
    store_type: Optional[str] = None
    category: Optional[str] = None
    brand_name: Optional[str] = None
    status: Optional[str] = None

class PlatformStoresResponse(BaseModel):
    """플랫폼 매장 목록 응답"""
    platform: PlatformEnum
    stores: List[PlatformStore]
    count: int

# 매장 등록 응답
class StoreRegisterResponse(BaseModel):
    """매장 등록 응답"""
    success: bool
    message: str
    store_code: Optional[str] = None
    store_info: Optional[StoreInfo] = None

# 매장 목록 응답
class StoreListResponse(BaseModel):
    """매장 목록 응답"""
    stores: List[StoreInfo]
    total: int
    page: int
    page_size: int

# 매장 업데이트 요청
class StoreUpdateRequest(BaseModel):
    """매장 설정 업데이트 요청"""
    # 답글 정책 설정 (Optional로 변경)
    greeting_start: Optional[str] = None
    greeting_end: Optional[str] = None
    role: Optional[str] = None
    tone: Optional[str] = None
    prohibited_words: Optional[List[str]] = None
    max_length: Optional[int] = Field(None, ge=50, le=500)
    
    # 별점별 자동 답글 설정
    rating_5_reply: Optional[bool] = None
    rating_4_reply: Optional[bool] = None
    rating_3_reply: Optional[bool] = None
    rating_2_reply: Optional[bool] = None
    rating_1_reply: Optional[bool] = None
    
    # 운영 설정
    auto_reply_enabled: Optional[bool] = None
    auto_reply_hours: Optional[str] = None
    reply_delay_minutes: Optional[int] = Field(None, ge=0, le=180)
    weekend_enabled: Optional[bool] = None
    holiday_enabled: Optional[bool] = None
    
    # 매장 정보
    business_hours: Optional[Dict[str, str]] = None
    store_address: Optional[str] = None
    store_phone: Optional[str] = None

# 매장 크롤링 요청
class StoreCrawlRequest(BaseModel):
    """매장 정보 크롤링 요청"""
    platform: PlatformEnum
    platform_id: str
    platform_pw: str
    platform_code: Optional[str] = None  # 특정 매장만 선택하려는 경우
    headless: bool = True  # 추가 - 브라우저 숨김 모드 설정 (기본값 True)