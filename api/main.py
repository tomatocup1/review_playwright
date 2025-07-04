"""
리뷰 자동화 SaaS 서비스 - FastAPI 백엔드 - 24시간 자동화 구현
"""
import os
import sys
import asyncio
import time
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from api.routes import reply_posting
from contextlib import asynccontextmanager
import logging
import nest_asyncio
import traceback

# 24시간 자동화를 위한 스케줄러 추가
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# 서비스 임포트
from api.services.review_collector_service import ReviewCollectorService
from api.services.reply_posting_service import ReplyPostingService
from api.services.ai_service import AIService
from api.services.supabase_service import SupabaseService, get_supabase_service
from config.openai_client import get_openai_client

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

# 스케줄러 생성
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("리뷰 자동화 서비스 시작...")
    
    # 24시간 자동화 스케줄러 시작
    await startup_scheduler()
    
    yield
    
    # 스케줄러 종료
    if scheduler.running:
        scheduler.shutdown()
    
    logger.info("리뷰 자동화 서비스 종료...")

app = FastAPI(
    title="리뷰 자동화 API",
    description="배민, 요기요, 쿠팡이츠 리뷰 자동 답글 서비스 - 24시간 자동화",
    version="2.0.0",
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

# Step 4: 새로운 라우터 등록
app.include_router(reply_posting_endpoints.router)
app.include_router(reply_status.router)
app.include_router(reply_posting.router)

# 테스트용 라우터 등록
app.include_router(test_reply_posting.router)

async def startup_scheduler():
    """24시간 자동화 스케줄러 설정"""
    try:
        # 서비스 인스턴스 준비
        supabase_service = get_supabase_service()
        review_service = ReviewCollectorService(supabase_service)
        reply_service = ReplyPostingService(supabase_service)
        ai_service = AIService()
        
        # 1. 즉시 한 번 실행 (서버 시작 시)
        logger.info("=== 서버 시작 시 초기 작업 실행 ===")
        
        # 먼저 리뷰 수집
        logger.info("1. 리뷰 수집 시작...")
        asyncio.create_task(collect_all_reviews_job(review_service))
        
        # 10초 후 AI 답글 생성
        await asyncio.sleep(10)
        logger.info("2. AI 답글 생성 시작...")
        asyncio.create_task(generate_ai_replies_job(ai_service, supabase_service))
        
        # 20초 후 답글 등록
        await asyncio.sleep(10)
        logger.info("3. 답글 등록 시작...")
        asyncio.create_task(post_replies_batch_job(reply_service))
        
        # 2. 정기 스케줄 설정 (테스트용 짧은 간격)
        # 3분마다 리뷰 수집
        scheduler.add_job(
            collect_all_reviews_job,
            trigger=CronTrigger(minute="*/3"),
            id="review_collection",
            args=[review_service]
        )
        
        # 1분마다 AI 답글 생성
        scheduler.add_job(
            generate_ai_replies_job,
            trigger=CronTrigger(minute="*/1"),
            id="ai_reply_generation",
            args=[ai_service, supabase_service]
        )
        
        # 2분마다 답글 등록
        scheduler.add_job(
            post_replies_batch_job,
            trigger=CronTrigger(minute="*/2"),
            id="reply_posting",
            args=[reply_service]
        )
        
        scheduler.start()
        logger.info("=== 스케줄러가 시작되었습니다 ===")
        logger.info("테스트 모드: 리뷰 수집(3분), AI 생성(1분), 답글 등록(2분) 간격")
        
    except Exception as e:
        logger.error(f"스케줄러 시작 실패: {str(e)}")
        logger.error(traceback.format_exc())

# 리뷰 수집 작업
async def collect_all_reviews_job(review_service: ReviewCollectorService):
    """모든 활성 매장의 리뷰를 수집하는 스케줄 작업"""
    try:
        logger.info("=== 리뷰 자동 수집 시작 ===")
        start_time = time.time()
        
        result = await review_service.collect_all_stores_reviews()
        
        elapsed_time = time.time() - start_time
        logger.info(f"리뷰 수집 완료: {result} (소요시간: {elapsed_time:.2f}초)")
        
    except Exception as e:
        logger.error(f"리뷰 수집 중 오류: {str(e)}")
        logger.error(traceback.format_exc())

# AI 답글 생성 작업
async def generate_ai_replies_job(ai_service: AIService, supabase_service: SupabaseService):
    """답글이 없는 리뷰에 대해 AI 답글을 생성하는 스케줄 작업"""
    try:
        logger.info("=== AI 답글 자동 생성 시작 ===")
        
        # 답글이 없는 리뷰 조회
        new_reviews = await supabase_service.get_reviews_without_reply()
        
        if not new_reviews:
            logger.info("새로운 리뷰가 없습니다.")
            return
        
        logger.info(f"{len(new_reviews)}개의 새 리뷰에 대해 AI 답글 생성 시작")
        
        # 병렬로 AI 답글 생성 (최대 10개씩)
        semaphore = asyncio.Semaphore(10)
        
        async def generate_with_limit(review):
            async with semaphore:
                return await generate_single_reply(ai_service, supabase_service, review)
        
        tasks = []
        for review in new_reviews:
            task = asyncio.create_task(generate_with_limit(review))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for r in results if r is True)
        error_count = sum(1 for r in results if isinstance(r, Exception))
        
        logger.info(f"AI 답글 생성 완료: {success_count}/{len(new_reviews)} 성공, {error_count} 실패")
        
    except Exception as e:
        logger.error(f"AI 답글 생성 중 오류: {str(e)}")
        logger.error(traceback.format_exc())

# 단일 리뷰 AI 답글 생성 헬퍼 함수
async def generate_single_reply(ai_service: AIService, supabase_service: SupabaseService, review: dict):
    """단일 리뷰에 대한 AI 답글 생성"""
    try:
        # 매장 정보 조회
        stores = await supabase_service.get_stores_by_user('all')
        store_info = None
        for store in stores:
            if store['store_code'] == review['store_code']:
                store_info = store
                break
                
        if not store_info:
            logger.error(f"매장 정보를 찾을 수 없습니다: {review['store_code']}")
            return False

        # AI 답글 생성
        reply = await ai_service.generate_reply(
            review_data={
                'review_content': review['review_content'],
                'rating': review.get('rating', 5),
                'review_name': review.get('review_name', '고객')
            },
            store_rules={
                'greeting_start': store_info.get('greeting_start', '안녕하세요'),
                'greeting_end': store_info.get('greeting_end', '감사합니다'),
                'role': store_info.get('role', ''),
                'tone': store_info.get('tone', ''),
                'prohibited_words': store_info.get('prohibited_words', []),
                'max_length': store_info.get('max_length', 300)
            }
        )
        
        if not reply.get('success'):
            logger.error(f"AI 답글 생성 실패: {reply.get('error')}")
            return False
        
        # DB에 저장
        saved = await supabase_service.save_ai_reply(
            review_id=review['review_id'],
            ai_response=reply.get('reply', ''),
            quality_score=reply.get('quality_score', 0.8)
        )
        
        if saved:
            logger.info(f"리뷰 {review['review_id']} AI 답글 생성 및 저장 성공")
            return True
        else:
            logger.error(f"리뷰 {review['review_id']} AI 답글 저장 실패")
            return False
            
    except Exception as e:
        logger.error(f"리뷰 {review['review_id']} 답글 생성 실패: {str(e)}")
        raise

# 답글 일괄 등록 작업
async def post_replies_batch_job(reply_service: ReplyPostingService):
    """대기 중인 답글을 일괄로 등록하는 스케줄 작업"""
    try:
        logger.info("=== 답글 자동 등록 시작 ===")
        start_time = time.time()
        
        # 플랫폼별로 그룹화하여 처리
        result = await reply_service.post_all_pending_replies()
        
        elapsed_time = time.time() - start_time
        logger.info(f"답글 등록 완료: {result} (소요시간: {elapsed_time:.2f}초)")
        
    except Exception as e:
        logger.error(f"답글 등록 중 오류: {str(e)}")
        logger.error(traceback.format_exc())

# 일일 통계 리포트 생성 (선택사항)
async def generate_daily_report(supabase_service: SupabaseService):
    """매일 자정 통계 리포트 생성"""
    try:
        logger.info("=== 일일 통계 리포트 생성 시작 ===")
        
        # 오늘 날짜
        today = datetime.now().date()
        
        # 통계 데이터 수집 (예시)
        stats = {
            "date": today.isoformat(),
            "total_reviews_collected": 0,
            "total_replies_generated": 0,
            "total_replies_posted": 0,
            "success_rate": 0.0
        }
        
        # TODO: 실제 통계 로직 구현
        logger.info(f"일일 통계: {stats}")
        
    except Exception as e:
        logger.error(f"일일 리포트 생성 중 오류: {str(e)}")

# 디버깅용 - 등록된 라우트 출력
@app.on_event("startup")
async def startup_event():
    routes = []
    for route in app.routes:
        if hasattr(route, "path"):
            routes.append(f"{route.methods} {route.path}")
    logger.info(f"Registered routes: {routes}")

# 스케줄러 상태 확인 API
@app.get("/api/scheduler/status")
async def scheduler_status():
    """스케줄러 상태 확인"""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger)
        })
    
    return {
        "scheduler_running": scheduler.running,
        "jobs": jobs,
        "current_time": datetime.now().isoformat()
    }

# 스케줄러 작업 수동 실행 API
@app.post("/api/scheduler/run/{job_id}")
async def run_scheduler_job(job_id: str):
    """특정 스케줄 작업을 수동으로 실행"""
    try:
        job = scheduler.get_job(job_id)
        if not job:
            return {"success": False, "error": f"Job {job_id} not found"}
        
        # 작업 즉시 실행
        job.modify(next_run_time=datetime.now())
        
        return {
            "success": True,
            "message": f"Job {job_id} scheduled for immediate execution"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api")
async def api_info():
    return {
        "message": "리뷰 자동화 API - 24시간 자동화 구현 완료",
        "version": "2.0.0",
        "features": [
            "리뷰 수집 (30분마다 자동)",
            "AI 답글 생성 (5분마다 자동)",
            "답글 등록 (10분마다 자동, 08-22시)",
            "일괄 처리",
            "상태 조회",
            "24시간 자동화"
        ],
        "scheduler": {
            "status": "running" if scheduler.running else "stopped",
            "jobs_count": len(scheduler.get_jobs())
        },
        "docs": "/docs",
        "redoc": "/redoc"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "review-automation-api",
        "version": "2.0.0",
        "scheduler_running": scheduler.running,
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
        "24시간_자동화_엔드포인트": {
            "스케줄러_상태": "GET /api/scheduler/status",
            "작업_수동_실행": "POST /api/scheduler/run/{job_id}"
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
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )