"""
프로젝트 전역 설정 관리
모든 환경변수와 설정값을 중앙에서 관리합니다.
"""
import os
from typing import Optional, Dict, List
from datetime import timedelta
from pathlib import Path
from pydantic import BaseSettings, Field, validator
from functools import lru_cache


class Settings(BaseSettings):
    """
    애플리케이션 설정 클래스
    환경변수를 자동으로 로드하고 타입 검증을 수행합니다.
    """
    
    # ========================================
    # 앱 기본 설정
    # ========================================
    app_name: str = "리뷰 자동화 SaaS 서비스"
    app_version: str = "1.0.0"
    app_description: str = "배민/요기요/쿠팡이츠/네이버 리뷰 자동 답글 서비스"
    environment: str = Field("development", env="ENVIRONMENT")
    debug: bool = Field(False, env="DEBUG")
    
    # 프로젝트 경로
    project_root: Path = Path("C:/Review_playwright")
    logs_dir: Path = Path("C:/Review_playwright/logs")
    screenshots_dir: Path = Path("C:/Review_playwright/logs/screenshots")
    
    # ========================================
    # API 서버 설정
    # ========================================
    api_host: str = Field("0.0.0.0", env="API_HOST")
    api_port: int = Field(8000, env="API_PORT")
    api_prefix: str = "/api"
    api_version: str = "v1"
    
    # CORS 설정
    cors_origins: List[str] = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",  # React 개발 서버
    ]
    
    # ========================================
    # 보안 설정
    # ========================================
    # JWT 설정
    jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24시간
    refresh_token_expire_days: int = 7
    
    # 암호화 설정
    encryption_key: str = Field(..., env="ENCRYPTION_KEY")
    
    # ========================================
    # 데이터베이스 설정 (Supabase)
    # ========================================
    supabase_url: str = Field(..., env="SUPABASE_URL")
    supabase_anon_key: str = Field(..., env="SUPABASE_ANON_KEY")
    supabase_service_key: Optional[str] = Field(None, env="SUPABASE_SERVICE_KEY")
    
    # DB 연결 설정
    db_pool_size: int = 20
    db_max_overflow: int = 40
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600
    
    # ========================================
    # 외부 API 설정
    # ========================================
    # OpenAI
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o-mini", env="OPENAI_MODEL")
    openai_temperature: float = 0.7
    openai_max_tokens: int = 500
    openai_timeout: int = 30  # 초
    
    # ========================================
    # 크롤링 설정
    # ========================================
    # 브라우저 설정
    browser_headless: bool = Field(True, env="BROWSER_HEADLESS")
    browser_timeout: int = 60000  # 60초 (밀리초)
    browser_navigation_timeout: int = 30000  # 30초
    browser_user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    # 크롤링 설정
    crawl_retry_count: int = 3
    crawl_retry_delay: int = 5  # 초
    crawl_batch_size: int = 10  # 동시 크롤링 수
    
    # 플랫폼별 설정
    baemin_login_timeout: int = 45000
    coupang_login_timeout: int = 45000
    yogiyo_login_timeout: int = 45000
    naver_login_timeout: int = 60000
    
    # ========================================
    # 리뷰 처리 설정
    # ========================================
    # 답글 생성 설정
    reply_min_length: int = 50
    reply_max_length: int = 500
    reply_default_delay_minutes: int = 30
    reply_quality_threshold: float = 0.7
    
    # 자동 답글 운영 시간
    auto_reply_start_hour: int = 10
    auto_reply_end_hour: int = 20
    auto_reply_weekend: bool = True
    auto_reply_holiday: bool = False
    
    # ========================================
    # 사용량 제한 설정
    # ========================================
    # 요금제별 제한 (추후 DB로 이전)
    free_max_stores: int = 2
    free_max_reviews_per_month: int = 50
    basic_max_stores: int = 5
    basic_max_reviews_per_month: int = 500
    pro_max_stores: int = 20
    pro_max_reviews_per_month: int = 2000
    
    # API Rate Limiting
    api_rate_limit_per_hour: int = 1000
    api_rate_limit_per_day: int = 10000
    
    # ========================================
    # 로깅 설정
    # ========================================
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file_max_bytes: int = 10485760  # 10MB
    log_file_backup_count: int = 5
    
    # ========================================
    # 알림 설정
    # ========================================
    # 이메일 설정 (추후 구현)
    smtp_host: Optional[str] = Field(None, env="SMTP_HOST")
    smtp_port: Optional[int] = Field(587, env="SMTP_PORT")
    smtp_username: Optional[str] = Field(None, env="SMTP_USERNAME")
    smtp_password: Optional[str] = Field(None, env="SMTP_PASSWORD")
    smtp_from_email: Optional[str] = Field(None, env="SMTP_FROM_EMAIL")
    
    # 슬랙 웹훅 (추후 구현)
    slack_webhook_url: Optional[str] = Field(None, env="SLACK_WEBHOOK_URL")
    
    # ========================================
    # 기능 플래그
    # ========================================
    enable_auto_crawling: bool = Field(True, env="ENABLE_AUTO_CRAWLING")
    enable_ai_reply: bool = Field(True, env="ENABLE_AI_REPLY")
    enable_reply_posting: bool = Field(True, env="ENABLE_REPLY_POSTING")
    enable_analytics: bool = Field(False, env="ENABLE_ANALYTICS")
    enable_webhook: bool = Field(False, env="ENABLE_WEBHOOK")
    
    # 테스트 모드
    test_mode: bool = Field(False, env="TEST_MODE")
    test_store_prefix: str = "TEST_"
    
    # ========================================
    # 플랫폼별 URL
    # ========================================
    platform_urls: Dict[str, str] = {
        "baemin": "https://ceo.baemin.com",
        "coupang": "https://store.coupangeats.com",
        "yogiyo": "https://owner.yogiyo.co.kr",
        "naver": "https://new-m.pay.naver.com/pcmap"
    }
    
    class Config:
        """Pydantic 설정"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
        # 환경변수 접두사
        env_prefix = ""  # 접두사 없이 직접 매칭
    
    @validator("project_root", "logs_dir", "screenshots_dir")
    def validate_paths(cls, v):
        """경로 유효성 검증 및 생성"""
        path = Path(v)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        return path
    
    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        """CORS origins 파싱 (문자열 -> 리스트)"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("environment")
    def validate_environment(cls, v):
        """환경 검증"""
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v
    
    @property
    def is_development(self) -> bool:
        """개발 환경 여부"""
        return self.environment == "development"
    
    @property
    def is_production(self) -> bool:
        """프로덕션 환경 여부"""
        return self.environment == "production"
    
    @property
    def database_url(self) -> str:
        """데이터베이스 URL (Supabase)"""
        return self.supabase_url
    
    @property
    def access_token_expire_timedelta(self) -> timedelta:
        """액세스 토큰 만료 시간 (timedelta)"""
        return timedelta(minutes=self.access_token_expire_minutes)
    
    @property
    def refresh_token_expire_timedelta(self) -> timedelta:
        """리프레시 토큰 만료 시간 (timedelta)"""
        return timedelta(days=self.refresh_token_expire_days)
    
    def get_platform_url(self, platform: str) -> str:
        """플랫폼별 URL 반환"""
        return self.platform_urls.get(platform, "")
    
    def get_log_file_path(self, log_type: str = "app") -> Path:
        """로그 파일 경로 반환"""
        return self.logs_dir / f"{log_type}.log"
    
    def get_screenshot_dir(self, platform: str) -> Path:
        """플랫폼별 스크린샷 디렉토리 반환"""
        screenshot_dir = self.screenshots_dir / platform
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        return screenshot_dir


@lru_cache()
def get_settings() -> Settings:
    """
    설정 인스턴스 반환 (싱글톤)
    
    Returns:
        Settings: 애플리케이션 설정 인스턴스
    """
    return Settings()


# 전역 설정 인스턴스
settings = get_settings()


# 설정 검증 함수
def validate_settings():
    """
    애플리케이션 시작 시 설정 검증
    필수 환경변수가 설정되었는지 확인합니다.
    """
    try:
        settings = get_settings()
        print(f"✅ 설정 로드 완료: {settings.app_name} v{settings.app_version}")
        print(f"✅ 환경: {settings.environment}")
        print(f"✅ API 서버: {settings.api_host}:{settings.api_port}")
        print(f"✅ 로그 디렉토리: {settings.logs_dir}")
        return True
    except Exception as e:
        print(f"❌ 설정 검증 실패: {str(e)}")
        print("필수 환경변수를 .env 파일에 설정해주세요.")
        return False


if __name__ == "__main__":
    # 설정 테스트
    if validate_settings():
        print("\n[설정 정보]")
        print(f"- JWT Secret: {'*' * 10}...")
        print(f"- OpenAI Model: {settings.openai_model}")
        print(f"- Browser Headless: {settings.browser_headless}")
        print(f"- Auto Reply Hours: {settings.auto_reply_start_hour}:00 - {settings.auto_reply_end_hour}:00")
        print(f"- Platform URLs:")
        for platform, url in settings.platform_urls.items():
            print(f"  - {platform}: {url}")
