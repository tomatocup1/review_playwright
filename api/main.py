"""
ë¦¬ë·° ?ë™??SaaS ?œë¹„??- FastAPI ë°±ì—”??- Step 4 API ?”ë“œ?¬ì¸??ì¶”ê?
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

# Windows ?„ìš© ?¤ì •
if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())  # Playwright subprocess Áö¿ø

nest_asyncio.apply()

BASE_DIR = Path(__file__).resolve().parent.parent

# ë¡œê·¸ ?¤ì •
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
    logger.info("ë¦¬ë·° ?ë™???œë¹„???œì‘...")
    yield
    logger.info("ë¦¬ë·° ?ë™???œë¹„??ì¢…ë£Œ...")

app = FastAPI(
    title="ë¦¬ë·° ?ë™??API",
    description="ë°°ë?, ?”ê¸°?? ì¿ íŒ¡?´ì¸  ë¦¬ë·° ?ë™ ?µê? ?œë¹„??,
    version="1.0.0",
    lifespan=lifespan
)

# CORS ?¤ì • ?˜ì •
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ê°œë°œ??- ëª¨ë“  ì¶œì²˜ ?ˆìš©
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

# ê¸°ì¡´ ?¼ìš°???„í¬??from api.routes import auth, pages, stores, reviews

# Step 4: ?ˆë¡œ???µê? ?±ë¡ ê´€???¼ìš°???„í¬??from api.routes import reply_posting_endpoints, reply_status

# ?ŒìŠ¤?¸ìš© ?¼ìš°???„í¬??from api.routes import test_reply_posting

# ê¸°ì¡´ ?¼ìš°???±ë¡
app.include_router(auth.router)
app.include_router(stores.router)
app.include_router(pages.router)
app.include_router(reviews.router)

# Step 4: ?ˆë¡œ???¼ìš°???±ë¡
app.include_router(reply_posting_endpoints.router)
app.include_router(reply_status.router)

# ?ŒìŠ¤?¸ìš© ?¼ìš°???±ë¡
app.include_router(test_reply_posting.router)

@app.get("/api")
async def api_info():
    return {
        "message": "ë¦¬ë·° ?ë™??API - Step 4 ?„ë£Œ",
        "version": "1.0.0",
        "features": [
            "ë¦¬ë·° ?˜ì§‘",
            "AI ?µê? ?ì„±",
            "?µê? ?±ë¡ (Step 4 ì¶”ê?)",
            "?¼ê´„ ì²˜ë¦¬",
            "?íƒœ ì¡°íšŒ"
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

# Step 4: ?ˆë¡œ??API ?”ë“œ?¬ì¸???”ì•½
@app.get("/api/endpoints")
async def list_endpoints():
    """
    ?¬ìš© ê°€?¥í•œ ëª¨ë“  API ?”ë“œ?¬ì¸??ëª©ë¡
    """
    return {
        "ê¸°ì¡´_?”ë“œ?¬ì¸??: {
            "?¸ì¦": "/api/auth/*",
            "ë§¤ì¥_ê´€ë¦?: "/api/stores/*",
            "ë¦¬ë·°_ê´€ë¦?: "/api/reviews/*",
            "?˜ì´ì§€": "/api/pages/*"
        },
        "Step4_?ˆë¡œ???”ë“œ?¬ì¸??: {
            "?µê?_?±ë¡": {
                "?¨ì¼_?µê?_?±ë¡": "POST /api/reply-posting/{review_id}/submit",
                "ë§¤ì¥ë³??¼ê´„_?±ë¡": "POST /api/reply-posting/batch/{store_code}/submit",
                "?„ì²´_ë§¤ì¥_?¼ê´„_?±ë¡": "POST /api/reply-posting/batch/all-stores/submit"
            },
            "?íƒœ_ì¡°íšŒ": {
                "?€ê¸??µê?_ì¡°íšŒ": "GET /api/reply-status/{store_code}/pending",
                "?µê?_?íƒœ_ì¡°íšŒ": "GET /api/reply-status/{review_id}/status",
                "ë§¤ì¥_?”ì•½_ì¡°íšŒ": "GET /api/reply-status/stores/{user_code}/summary",
                "?µê?_?¬ì‹œ??: "POST /api/reply-status/{review_id}/retry"
            }
        },
        "?ŒìŠ¤?¸ìš©_?”ë“œ?¬ì¸??: {
            "?ŒìŠ¤???µê?_?±ë¡": "POST /api/test-reply-posting/{review_id}/submit",
            "ë¦¬ë·°_?•ë³´_ì¡°íšŒ": "GET /api/test-reply-posting/{review_id}/info",
            "ë§¤ì¥_?•ë³´_ì¡°íšŒ": "GET /api/test-reply-posting/stores/{store_code}/info"
        },
        "ë¬¸ì„œ": {
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
