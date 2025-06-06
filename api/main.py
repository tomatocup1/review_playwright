"""
리뷰 자동화 SaaS 서비스 - FastAPI 백엔드
"""
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 프로젝트 루트 경로
BASE_DIR = Path(__file__).resolve().parent.parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    # 시작 시
    logger.info("리뷰 자동화 서비스 시작...")
    yield
    # 종료 시
    logger.info("리뷰 자동화 서비스 종료...")

# FastAPI 앱 생성
app = FastAPI(
    title="리뷰 자동화 API",
    description="배민, 요기요, 쿠팡이츠 리뷰 자동 답글 서비스",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:8000",
        "http://localhost/playwright"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 마운트
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "web" / "static")), name="static")

# Jinja2 템플릿 설정
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

# 라우터 임포트
from api.routes import auth  # 인증 라우터
# from api.routes import stores, reviews, dashboard, pages, settings  # 나중에 추가

# 라우터 등록
app.include_router(auth.router)  # 인증 라우터 (태그와 prefix는 라우터 파일에서 정의)
# app.include_router(stores.router, prefix="/api/stores", tags=["매장"])
# app.include_router(reviews.router, prefix="/api/reviews", tags=["리뷰"])
# app.include_router(dashboard.router, prefix="/api/dashboard", tags=["대시보드"])
# app.include_router(settings.router, prefix="/api/settings", tags=["설정"])
# app.include_router(pages.router, tags=["페이지"])

# 루트 엔드포인트
@app.get("/")
async def root():
    """API 루트"""
    return {
        "message": "리뷰 자동화 API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }

# 헬스 체크
@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "service": "review-automation-api"
    }

if __name__ == "__main__":
    import uvicorn
    
    # 개발 서버 실행
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 개발 모드에서만 사용
        log_level="info"
    )
