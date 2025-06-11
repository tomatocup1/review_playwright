"""
리뷰 ?�동??SaaS ?�비??- FastAPI 백엔??- Step 4 API ?�드?�인??추�?
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
from contextlib import asynccontextmanager
import logging
import nest_asyncio
import traceback

# Windows ?�용 ?�정
if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())  # Playwright subprocess ����

nest_asyncio.apply()

BASE_DIR = Path(__file__).resolve().parent.parent

# 로그 ?�정
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
    logger.info("리뷰 ?�동???�비???�작...")
    yield
    logger.info("리뷰 ?�동???�비??종료...")

app = FastAPI(
    title="리뷰 ?�동??API",
    description="배�?, ?�기?? 쿠팡?�츠 리뷰 ?�동 ?��? ?�비??,
    version="1.0.0",
    lifespan=lifespan
)

# CORS ?�정 ?�정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발??- 모든 출처 ?�용
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

# 기존 ?�우???�포??from api.routes import auth, pages, stores, reviews

# Step 4: ?�로???��? ?�록 관???�우???�포??from api.routes import reply_posting_endpoints, reply_status

# ?�스?�용 ?�우???�포??from api.routes import test_reply_posting

# 기존 ?�우???�록
app.include_router(auth.router)
app.include_router(stores.router)
app.include_router(pages.router)
app.include_router(reviews.router)

# Step 4: ?�로???�우???�록
app.include_router(reply_posting_endpoints.router)
app.include_router(reply_status.router)

# ?�스?�용 ?�우???�록
app.include_router(test_reply_posting.router)

@app.get("/api")
async def api_info():
    return {
        "message": "리뷰 ?�동??API - Step 4 ?�료",
        "version": "1.0.0",
        "features": [
            "리뷰 ?�집",
            "AI ?��? ?�성",
            "?��? ?�록 (Step 4 추�?)",
            "?�괄 처리",
            "?�태 조회"
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

# Step 4: ?�로??API ?�드?�인???�약
@app.get("/api/endpoints")
async def list_endpoints():
    """
    ?�용 가?�한 모든 API ?�드?�인??목록
    """
    return {
        "기존_?�드?�인??: {
            "?�증": "/api/auth/*",
            "매장_관�?: "/api/stores/*",
            "리뷰_관�?: "/api/reviews/*",
            "?�이지": "/api/pages/*"
        },
        "Step4_?�로???�드?�인??: {
            "?��?_?�록": {
                "?�일_?��?_?�록": "POST /api/reply-posting/{review_id}/submit",
                "매장�??�괄_?�록": "POST /api/reply-posting/batch/{store_code}/submit",
                "?�체_매장_?�괄_?�록": "POST /api/reply-posting/batch/all-stores/submit"
            },
            "?�태_조회": {
                "?��??��?_조회": "GET /api/reply-status/{store_code}/pending",
                "?��?_?�태_조회": "GET /api/reply-status/{review_id}/status",
                "매장_?�약_조회": "GET /api/reply-status/stores/{user_code}/summary",
                "?��?_?�시??: "POST /api/reply-status/{review_id}/retry"
            }
        },
        "?�스?�용_?�드?�인??: {
            "?�스???��?_?�록": "POST /api/test-reply-posting/{review_id}/submit",
            "리뷰_?�보_조회": "GET /api/test-reply-posting/{review_id}/info",
            "매장_?�보_조회": "GET /api/test-reply-posting/stores/{store_code}/info"
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
