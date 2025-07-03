"""
리뷰 자동화 SaaS 서비스 - FastAPI 백엔드 - Step 4 API 엔드포인트 추가
"""
import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from api.routes import reply_posting
from contextlib import asynccontextmanager
import logging
import nest_asyncio
import traceback

# Windows 전용 설정 - Playwright subprocess 지원을 위해 ProactorEventLoop 사용
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

nest_asyncio.apply()

BASE_DIR = Path(__file__).resolve().parent.parent

# 로그 설정
log_dir = os.path.join(BASE_DIR, 'logs')
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, f'app_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("리뷰 자동화 서비스 시작...")
    yield
    logger.info("리뷰 자동화 서비스 종료...")

app = FastAPI(
    title="리뷰 자동화 API",
    description="배민, 요기요, 쿠팡이츠 리뷰 자동 답글 서비스",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정 수정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발용 - 모든 출처 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {type(exc).__name__}: {str(exc)}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "type": type(exc).__name__,
            "path": str(request.url)
        }
    )

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "web" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

# 기존 라우터 임포트
from api.routes import auth, pages, stores, reviews

# Step 4: 새로운 답글 등록 관련 라우터 임포트
from api.routes import reply_posting_endpoints, reply_status

# 테스트용 라우터 임포트
from api.routes import test_reply_posting

# 기존 라우터 등록
app.include_router(auth.router)
app.include_router(stores.router)
app.include_router(pages.router)
app.include_router(reviews.router)

# 디버깅용 - 등록된 라우트 출력
@app.on_event("startup")
async def startup_event():
    routes = []
    for route in app.routes:
        if hasattr(route, "path"):
            routes.append(f"{route.methods} {route.path}")
    logger.info(f"Registered routes: {routes}")
    
# Step 4: 새로운 라우터 등록
app.include_router(reply_posting_endpoints.router)
app.include_router(reply_status.router)
app.include_router(reply_posting.router)

# 테스트용 라우터 등록
app.include_router(test_reply_posting.router)

@app.get("/api")
async def api_info():
    return {
        "message": "리뷰 자동화 API - Step 4 완료",
        "version": "1.0.0",
        "features": [
            "리뷰 수집",
            "AI 답글 생성",
            "답글 등록 (Step 4 추가)",
            "일괄 처리",
            "상태 조회"
        ],
        "docs": "/docs",
        "redoc": "/redoc"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "review-automation-api",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/test")
async def test_endpoint():
    return {
        "message": "API is working",
        "timestamp": datetime.now().isoformat()
    }

# Step 4: 새로운 API 엔드포인트 요약
@app.get("/api/endpoints")
async def list_endpoints():
    """
    사용 가능한 모든 API 엔드포인트 목록
    """
    return {
        "기존_엔드포인트": {
            "인증": "/api/auth/*",
            "매장_관리": "/api/stores/*",
            "리뷰_관리": "/api/reviews/*",
            "페이지": "/api/pages/*"
        },
        "Step4_새로운_엔드포인트": {
            "답글_등록": {
                "단일_답글_등록": "POST /api/reply-posting/{review_id}/submit",
                "매장별_일괄_등록": "POST /api/reply-posting/batch/{store_code}/submit",
                "전체_매장_일괄_등록": "POST /api/reply-posting/batch/all-stores/submit"
            },
            "상태_조회": {
                "대기_답글_조회": "GET /api/reply-status/{store_code}/pending",
                "답글_상태_조회": "GET /api/reply-status/{review_id}/status",
                "매장_요약_조회": "GET /api/reply-status/stores/{user_code}/summary",
                "답글_재시도": "POST /api/reply-status/{review_id}/retry"
            }
        },
        "테스트용_엔드포인트": {
            "테스트_답글_등록": "POST /api/test-reply-posting/{review_id}/submit",
            "리뷰_정보_조회": "GET /api/test-reply-posting/{review_id}/info",
            "매장_정보_조회": "GET /api/test-reply-posting/stores/{store_code}/info"
        },
        "문서": {
            "Swagger_UI": "/docs",
            "ReDoc": "/redoc"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )