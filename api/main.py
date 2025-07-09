"""
리뷰 자동화 SaaS 서비스 - FastAPI 백엔드 - 24시간 자동화 구현
"""
import os
import sys
import asyncio
import time
from pathlib import Path
from datetime import datetime, timedelta
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
from api.services.encryption import decrypt_password
from config.openai_client import get_openai_client

# Windows에서 Playwright 호환성을 위해 SelectorEventLoopPolicy 사용
# nest_asyncio 적용 전에 설정해야 함
if sys.platform == 'win32':
    # Playwright async API를 위한 필수 설정
    from asyncio import WindowsSelectorEventLoopPolicy
    asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())

# nest_asyncio는 이벤트루프 정책 설정 후에 적용
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
    
    # ⭐ 조건부 실행 로직 추가
    enable_auto_start = os.getenv("AUTO_START_JOBS", "false").lower() == "true"
    
    if enable_auto_start:
        logger.info("🚀 자동화 모드: 즉시 실행 + 스케줄러 시작")
        # 기존 코드 그대로 - 즉시 실행 포함
        await startup_scheduler()
    else:
        logger.info("🌐 웹서버 모드: 스케줄러만 등록 (즉시 실행 없음)")
        # 스케줄러만 등록, 즉시 실행 안함
        await setup_scheduler_only()
    
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
        
        # 먼저 리뷰 수집 (직접 실행)
        logger.info("1. 리뷰 수집 시작...")
        try:
            result = await review_service.collect_all_stores_reviews()
            logger.info(f"초기 리뷰 수집 완료: {result}")
        except Exception as e:
            logger.error(f"초기 리뷰 수집 실패: {str(e)}")
        
        # 10초 후 AI 답글 생성
        await asyncio.sleep(10)
        logger.info("2. AI 답글 생성 시작...")
        try:
            await generate_ai_replies_job(ai_service, supabase_service)
        except Exception as e:
            logger.error(f"초기 AI 답글 생성 실패: {str(e)}")
        
        # 20초 후 답글 등록
        await asyncio.sleep(10)
        logger.info("3. 답글 등록 시작...")
        try:
            await post_replies_batch_job(reply_service)
        except Exception as e:
            logger.error(f"초기 답글 등록 실패: {str(e)}")
        
        # 2. 정기 스케줄 설정 (AI 답글 생성이 답글 등록보다 우선)
        # 3분마다 리뷰 수집
        scheduler.add_job(
            collect_all_reviews_job,
            trigger=CronTrigger(minute="*/3"),
            id="review_collection",
            args=[review_service],
            name="리뷰 수집 작업"
        )
        
        # 30초마다 AI 답글 생성 (우선순위 높임)
        scheduler.add_job(
            generate_ai_replies_job,
            trigger=CronTrigger(second="*/30"),
            id="ai_reply_generation",
            args=[ai_service, supabase_service],
            name="AI 답글 생성 작업"
        )
        
        # 2분마다 답글 등록 (AI 생성 후 실행)
        scheduler.add_job(
            post_replies_batch_job,
            trigger=CronTrigger(minute="*/2"),
            id="reply_posting",
            args=[reply_service],
            name="답글 등록 작업"
        )
        
        scheduler.start()
        logger.info("=== 스케줄러가 시작되었습니다 ===")
        logger.info("자동화 모드: 리뷰 수집(3분), AI 생성(30초), 답글 등록(2분) 간격")
        
    except Exception as e:
        logger.error(f"스케줄러 시작 실패: {str(e)}")
        logger.error(traceback.format_exc())

async def setup_scheduler_only():
    """스케줄러만 등록, 즉시 실행 안함 - 웹서버 모드용"""
    try:
        # 서비스 인스턴스 준비 (기존과 동일)
        supabase_service = get_supabase_service()
        review_service = ReviewCollectorService(supabase_service)
        reply_service = ReplyPostingService(supabase_service)
        ai_service = AIService()
        
        logger.info("=== 스케줄러만 등록 시작 (즉시 실행 없음) ===")
        
        # 1. 리뷰 수집 작업 - 4시간마다 (운영 환경)
        scheduler.add_job(
            collect_all_reviews_job,
            CronTrigger(hour="*/4"),  # 4시간마다
            args=[review_service],
            id="review_collection",
            name="리뷰 수집 작업",
            replace_existing=True
        )
        
        # 2. AI 답글 생성 작업 - 30분마다
        scheduler.add_job(
            generate_ai_replies_job,
            CronTrigger(minute="*/30"),  # 30분마다
            args=[ai_service, supabase_service],
            id="ai_reply_generation",
            name="AI 답글 생성 작업",
            replace_existing=True
        )
        
        # 3. 답글 등록 작업 - 4시간마다 (1일/2일 지연 로직 포함)
        scheduler.add_job(
            post_replies_batch_job,
            CronTrigger(hour="*/4"),  # 4시간마다
            args=[reply_service],
            id="reply_posting",
            name="답글 등록 작업 (1일/2일 지연)",
            replace_existing=True
        )
        
        scheduler.start()
        logger.info("=== 스케줄러 등록 완료 (웹서버 모드) ===")
        logger.info("운영 모드: 리뷰 수집(4시간), AI 생성(30분), 답글 등록(4시간) 간격")
        logger.info("답글 지연: 일반 1일, 사장님확인 2일")
        
    except Exception as e:
        logger.error(f"스케줄러 등록 실패: {str(e)}")
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
    """새 리뷰에 대한 AI 답글 자동 생성"""
    try:
        logger.info("=== AI 답글 자동 생성 시작 ===")
        
        # 답글이 없는 리뷰 조회
        new_reviews = await supabase_service.get_reviews_without_reply()
        
        if not new_reviews:
            logger.info("AI 답글 생성할 새 리뷰가 없습니다")
            return
            
        logger.info(f"{len(new_reviews)}개 리뷰에 대한 AI 답글 생성 시작")
        
        # 병렬 처리를 위한 세마포어 (동시 5개)
        semaphore = asyncio.Semaphore(5)
        
        async def generate_with_limit(review):
            async with semaphore:
                try:
                    # 매장 정책 조회
                    policy = await supabase_service.get_store_reply_rules(review['store_code'])
                    
                    # AI 답글 생성
                    reply_result = await ai_service.generate_reply(
                        review_data=review,
                        store_rules=policy
                    )
                    
                    # DB에 저장
                    if reply_result['success']:
                        # 답글 저장 및 상태 업데이트 (수동 시스템과 동일)
                        await supabase_service.save_ai_reply(
                            review['review_id'],
                            reply_result['reply'],
                            reply_result.get('quality_score', 0.8)
                        )
                        
                        # 생성 이력 저장 (수동 시스템과 동일)
                        await supabase_service.save_reply_generation_history(
                            review_id=review['review_id'],
                            user_code='SYSTEM',  # 자동화 시스템
                            generation_type='ai_auto',  # 자동 생성
                            prompt_used=reply_result.get('prompt_used', ''),
                            model_version=reply_result.get('model_used', 'gpt-4o-mini'),
                            generated_content=reply_result['reply'],
                            quality_score=reply_result['quality_score'],
                            processing_time_ms=reply_result.get('processing_time_ms', 0),
                            token_usage=reply_result.get('token_usage', 0),
                            is_selected=True  # 자동화에서는 바로 선택됨
                        )
                        
                        # boss_review_needed, review_reason, urgency_score 처리
                        boss_review_needed = reply_result.get('boss_review_needed', False)
                        review_reason = reply_result.get('review_reason', '')
                        urgency_score = reply_result.get('urgency_score', 0.3)
                        quality_score = reply_result.get('quality_score', 0.8)
                        rating = review.get('rating', 5)
                        
                        # 자동 등록 여부 결정 (스마트 자동화)
                        auto_post_status = 'generated'  # 기본값: 수동 검토 필요
                        
                        # 높은 별점 + 높은 품질 + 사장님 검토 불필요 → 자동 등록 대기
                        if (rating >= 4 and 
                            quality_score >= 0.7 and 
                            not boss_review_needed and
                            urgency_score < 0.5):
                            auto_post_status = 'ready_to_post'  # 자동 등록 대기
                            logger.info(f"리뷰 {review['review_id']} 자동 등록 대기 상태로 설정 (별점: {rating}, 품질: {quality_score:.2f})")
                        else:
                            logger.info(f"리뷰 {review['review_id']} 수동 검토 필요 (별점: {rating}, 품질: {quality_score:.2f}, 사장님검토: {boss_review_needed})")
                        
                        # 상태 업데이트 (수동 시스템과 동일한 방식)
                        await supabase_service.update_review_status(
                            review_id=review['review_id'],
                            status=auto_post_status,
                            reply_content=reply_result['reply'],
                            reply_type='ai_auto',
                            reply_by='AI_AUTO',
                            boss_review_needed=boss_review_needed,  # 파라미터명은 그대로 유지 (메서드에서 boss_reply_needed로 변환)
                            review_reason=review_reason,
                            urgency_score=urgency_score
                        )
                    else:
                        # 답글 생성 실패시 로그 기록
                        logger.error(f"답글 생성 실패: {reply_result.get('error', 'Unknown error')}")
                        return {"success": False, "review_id": review['review_id'], "error": reply_result.get('error')}
                    
                    return {"success": True, "review_id": review['review_id']}
                    
                except Exception as e:
                    logger.error(f"AI 답글 생성 실패 - review_id: {review['review_id']}, error: {str(e)}")
                    return {"success": False, "review_id": review['review_id'], "error": str(e)}
        
        # 모든 리뷰 병렬 처리
        tasks = [generate_with_limit(review) for review in new_reviews]
        results = await asyncio.gather(*tasks)
        
        # 결과 집계
        success_count = sum(1 for r in results if r and r.get('success', False))
        logger.info(f"AI 답글 생성 완료: {success_count}/{len(new_reviews)} 성공")
        
    except Exception as e:
        logger.error(f"AI 답글 생성 작업 실패: {str(e)}")

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

async def post_replies_batch_job(reply_service: ReplyPostingService):
    """생성된 AI 답글을 일괄 등록 - 1일/2일 지연 로직 적용"""
    try:
        logger.info("=== 답글 일괄 등록 시작 ===")
        
        supabase = reply_service.supabase
        now = datetime.now()
        one_day_ago = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)
        
        # 1. 일반 답글: 1일 지난 것만 (사장님 확인 불필요)
        # 30일 이내 리뷰만 선택 (배민 등의 답글 등록 제한 고려)
        thirty_days_ago = now - timedelta(days=30)
        
        logger.info(f"지연 조건 확인: 현재시간={now.strftime('%Y-%m-%d %H:%M')}, 1일전={one_day_ago.date()}, 2일전={two_days_ago.date()}")
        
        normal_replies = await supabase._execute_query(
            supabase.client.table('reviews')
            .select('*')
            .in_('response_status', ['ready_to_post', 'generated'])
            .or_('boss_reply_needed.is.null,boss_reply_needed.eq.false')  # null이거나 false
            .lte('review_date', one_day_ago.date().isoformat())  # 1일 이전 (lte로 변경)
            .gte('review_date', thirty_days_ago.date().isoformat())  # 30일 이내만 (gte로 변경)
            .order('review_date', desc=False)
            .limit(15)
        )
        
        # 2. 사장님 확인 필요: 2일 지난 것만 (30일 이내)
        boss_review_replies = await supabase._execute_query(
            supabase.client.table('reviews')
            .select('*')
            .in_('response_status', ['ready_to_post', 'generated'])
            .eq('boss_reply_needed', True)  # 사장님 확인 필요
            .lte('review_date', two_days_ago.date().isoformat())  # 2일 이전 (lte로 변경)
            .gte('review_date', thirty_days_ago.date().isoformat())  # 30일 이내만 (gte로 변경)
            .order('review_date', desc=False)
            .limit(5)
        )
        
        # 두 그룹 합치기
        all_reviews = []
        if normal_replies.data:
            all_reviews.extend(normal_replies.data)
        if boss_review_replies.data:
            all_reviews.extend(boss_review_replies.data)
        
        if not all_reviews:
            logger.info("등록할 답글이 없습니다 (1일/2일 지연 조건 미충족)")
            return
        
        logger.info(f"답글 등록 대상: 일반 {len(normal_replies.data if normal_replies.data else [])}개, "
                   f"사장님확인 {len(boss_review_replies.data if boss_review_replies.data else [])}개")
        
        # 플랫폼별 그룹핑으로 효율적 처리
        success_count = 0
        fail_count = 0
        
        # 매장 정보 한 번만 조회 (platform_reply_rules에서)
        try:
            # platform_reply_rules 테이블에서 직접 조회
            stores_query = supabase.client.table('platform_reply_rules').select('*').eq('is_active', True)
            stores_response = await supabase._execute_query(stores_query)
            
            if not stores_response.data:
                logger.warning("활성화된 매장이 없습니다")
                return
            
            store_map = {store['store_code']: store for store in stores_response.data}
            logger.info(f"매장 정보 조회 성공: {len(store_map)}개 매장")
            
        except Exception as e:
            logger.error(f"매장 정보 조회 실패: {str(e)}")
            return
        
        # 플랫폼별로 그룹핑
        platform_groups = {}
        for review in all_reviews:
            platform = review.get('platform')
            platform_code = review.get('platform_code')
            store_code = review.get('store_code')
            
            if not all([platform, platform_code, store_code]):
                logger.error(f"필수 정보 누락: {review['review_id']}")
                fail_count += 1
                continue
                
            # 매장 정보 확인
            store_info = store_map.get(store_code)
            if not store_info:
                logger.error(f"매장 정보 없음: {store_code}")
                fail_count += 1
                continue
            
            # 플랫폼+계정별로 그룹핑 (매장 정보 포함)
            group_key = f"{platform}_{platform_code}"
            if group_key not in platform_groups:
                # 비밀번호 복호화
                encrypted_pw = store_info.get('platform_pw', '')
                decrypted_pw = decrypt_password(encrypted_pw) if encrypted_pw else ''
                
                # 복호화된 매장 정보 생성
                decrypted_store_info = store_info.copy()
                decrypted_store_info['platform_pw'] = decrypted_pw
                
                platform_groups[group_key] = {
                    'platform': platform,
                    'platform_code': platform_code,
                    'store_info': decrypted_store_info,  # 복호화된 매장 정보 포함
                    'platform_id': store_info.get('platform_id'),
                    'platform_pw': decrypted_pw,  # 복호화된 비밀번호
                    'store_name': store_info.get('store_name'),
                    'user_code': store_info.get('owner_user_code'),  # 올바른 필드명
                    'reviews': []
                }
                
                logger.info(f"비밀번호 복호화 완료: {platform_code} (암호화: {len(encrypted_pw)}자 -> 복호화: {len(decrypted_pw)}자)")
            platform_groups[group_key]['reviews'].append(review)
        
        logger.info(f"플랫폼별 그룹핑 완료: {len(platform_groups)}개 그룹")
        
        # 각 플랫폼별로 일괄 처리
        for group_key, group_data in platform_groups.items():
            try:
                platform = group_data['platform']
                platform_code = group_data['platform_code']
                user_code = group_data['user_code']
                reviews = group_data['reviews']
                
                logger.info(f"=== {platform} ({platform_code}) 일괄 처리 시작: {len(reviews)}개 리뷰 ===")
                
                # 플랫폼별 일괄 처리 (매장 정보 포함)
                result = await reply_service.post_batch_replies_by_platform(
                    platform=platform,
                    platform_code=platform_code,
                    user_code=user_code,
                    reviews=reviews,
                    store_info=group_data['store_info']  # 매장 정보 직접 전달
                )
                
                batch_success = result.get('success_count', 0)
                batch_fail = result.get('fail_count', 0)
                
                success_count += batch_success
                fail_count += batch_fail
                
                logger.info(f"{platform} ({platform_code}) 완료: {batch_success}개 성공, {batch_fail}개 실패")
                
            except Exception as e:
                logger.error(f"플랫폼 일괄 처리 실패 - {group_key}: {str(e)}")
                fail_count += len(group_data['reviews'])
        
        logger.info(f"전체 답글 일괄 등록 완료: {success_count}개 성공, {fail_count}개 실패")
            
    except Exception as e:
        logger.error(f"답글 일괄 등록 작업 실패: {str(e)}")
        
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