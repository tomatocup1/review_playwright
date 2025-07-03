"""
추가 답글 등록 API 엔드포인트들 (일괄 처리)
"""
import asyncio
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks, Body
from api.schemas.auth import User
from api.auth.utils import get_current_user
from api.services.supabase_service import SupabaseService, get_supabase_service
from api.services.reply_posting_service import ReplyPostingService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/batch/{store_code}/submit")
async def submit_batch_replies(
    store_code: str,
    background_tasks: BackgroundTasks,
    request_body: dict = Body(...),  # Body로 받도록 수정
    current_user: User = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    매장의 대기 중인 답글들을 일괄 등록
    
    Request Body:
    - filters: 필터 조건 (status 배열 등)
    - auto_submit: 자동 제출 여부
    - limit: 한 번에 처리할 답글 수
    - use_optimized: 최적화된 일괄 처리 사용 여부
    """
    try:
        # 권한 확인
        has_permission = await supabase.check_user_permission(
            current_user.user_code,
            store_code,
            'reply'
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="해당 매장에 대한 답글 작성 권한이 없습니다")
        
        # 요청 파라미터 파싱
        filters = request_body.get('filters', {})
        auto_submit = request_body.get('auto_submit', True)
        limit = request_body.get('limit', 50)
        use_optimized = request_body.get('use_optimized', True)
        
        # ReplyPostingService 초기화
        reply_service = ReplyPostingService(supabase)
        
        # 필터 조건에 따른 리뷰 조회
        query = supabase.client.table('reviews').select('*').eq('store_code', store_code)
        
        # status 필터 적용
        if 'status' in filters and filters['status']:
            query = query.in_('response_status', filters['status'])
        else:
            # 기본값: generated와 ready_to_post 상태만
            query = query.in_('response_status', ['generated', 'ready_to_post'])
        
        # AI 답글이 있는 것만 조회
        query = query.neq('ai_response', None).neq('ai_response', '')
        
        # 제한 적용
        query = query.limit(limit)
        
        response = await supabase._execute_query(query)
        pending_reviews = response.data if response.data else []
        
        if not pending_reviews:
            return {
                "success": True,
                "message": "처리할 답글이 없습니다",
                "store_code": store_code,
                "pending_count": 0,
                "posted_count": 0,
                "failed_count": 0
            }
        
        # 플랫폼별로 그룹화
        reviews_by_platform = {}
        for review in pending_reviews:
            platform = review.get('platform', 'unknown')
            if platform not in reviews_by_platform:
                reviews_by_platform[platform] = []
            reviews_by_platform[platform].append(review)
        
        # 최적화된 일괄 처리 사용 여부 확인
        if use_optimized and len(pending_reviews) >= 3:  # 3개 이상일 때만 최적화 사용
            logger.info(f"최적화된 일괄 처리 사용: {len(pending_reviews)}개 리뷰")
            
            # 플랫폼별로 처리
            total_posted = 0
            total_failed = 0
            all_errors = []
            
            for platform, platform_reviews in reviews_by_platform.items():
                review_ids = [r['review_id'] for r in platform_reviews]
                
                # 최적화된 일괄 처리 호출
                result = await reply_service.post_batch_replies_optimized(
                    store_code=store_code,
                    review_ids=review_ids,
                    user_code=current_user.user_code
                )
                
                if result.get('success'):
                    total_posted += result.get('success_count', 0)
                    total_failed += result.get('failed_count', 0)
                    
                    # 실패한 리뷰의 에러 정보 수집
                    for review_result in result.get('results', []):
                        if not review_result.get('success'):
                            all_errors.append({
                                'review_id': review_result['review_id'],
                                'error': review_result.get('error', '알 수 없는 오류')
                            })
                else:
                    total_failed += len(review_ids)
                    all_errors.append({
                        'platform': platform,
                        'error': result.get('error', '플랫폼 처리 실패')
                    })
            
            return {
                "success": True,
                "message": f"{total_posted}개의 답글이 성공적으로 등록되었습니다",
                "store_code": store_code,
                "pending_count": len(pending_reviews),
                "posted_count": total_posted,
                "failed_count": total_failed,
                "errors": all_errors[:5]  # 최대 5개의 에러만 반환
            }
            
        else:
            # 기존 방식 (개별 처리)
            logger.info(f"개별 처리 방식 사용: {len(pending_reviews)}개 리뷰")
            
            posted_count = 0
            failed_count = 0
            errors = []
            
            for review in pending_reviews:
                try:
                    # 답글 내용 결정
                    reply_content = review.get('final_response') or review.get('ai_response') or review.get('manual_response')
                    
                    if not reply_content:
                        continue
                    
                    # 답글 등록 실행
                    result = await reply_service.post_single_reply(
                        review_id=review['review_id'],
                        reply_content=reply_content,
                        user_code=current_user.user_code
                    )
                    
                    if result.get('success'):
                        posted_count += 1
                    else:
                        failed_count += 1
                        errors.append({
                            'review_id': review['review_id'],
                            'error': result.get('error', '알 수 없는 오류')
                        })
                    
                    # 각 요청 사이에 지연 추가 (플랫폼 부하 방지)
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    failed_count += 1
                    errors.append({
                        'review_id': review['review_id'],
                        'error': str(e)
                    })
            
            return {
                "success": True,
                "message": f"{posted_count}개의 답글이 성공적으로 등록되었습니다",
                "store_code": store_code,
                "pending_count": len(pending_reviews),
                "posted_count": posted_count,
                "failed_count": failed_count,
                "errors": errors[:5]  # 최대 5개의 에러만 반환
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"일괄 답글 등록 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch/all-stores/submit")
async def submit_all_stores_replies(
    background_tasks: BackgroundTasks,
    request_body: dict = Body(...),  # Body로 받도록 수정
    current_user: User = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    모든 매장의 답글 일괄 등록 (관리자 전용)
    
    Request Body:
    - max_per_store: 매장당 최대 처리할 답글 수 (기본값: 5, 최대: 20)
    - use_optimized: 최적화된 일괄 처리 사용 여부
    """
    try:
        # 관리자 권한 확인
        if current_user.role not in ['admin', 'franchise']:
            raise HTTPException(status_code=403, detail="관리자 또는 프랜차이즈 권한이 필요합니다")
        
        # 요청 파라미터 파싱
        max_per_store = request_body.get('max_per_store', 5)
        use_optimized = request_body.get('use_optimized', True)
        
        # ReplyPostingService 초기화
        reply_service = ReplyPostingService(supabase)
        
        # 사용자가 접근 가능한 매장 목록 조회
        if current_user.role == 'admin':
            # 관리자는 모든 매장
            query = supabase.client.table('platform_reply_rules').select('*').eq('is_active', True)
            result = await supabase._execute_query(query)
            accessible_stores = result.data if result.data else []
        else:
            # 프랜차이즈는 권한이 있는 매장만
            query = supabase.client.table('user_store_permissions').select(
                'store_code, platform_reply_rules!inner(*)'
            ).eq('user_code', current_user.user_code).eq('is_active', True)
            result = await supabase._execute_query(query)
            accessible_stores = [item['platform_reply_rules'] for item in (result.data or [])]
        
        if not accessible_stores:
            return {
                "success": True,
                "message": "처리할 매장이 없습니다",
                "processed_stores": 0,
                "total_pending": 0
            }
        
        # 각 매장별 대기 답글 수 확인
        store_summary = []
        total_pending = 0
        
        for store in accessible_stores:
            # 대기 중인 리뷰 수 확인
            query = supabase.client.table('reviews').select('review_id').eq(
                'store_code', store['store_code']
            ).in_('response_status', ['generated', 'ready_to_post']).limit(max_per_store)
            
            result = await supabase._execute_query(query)
            pending_reviews = result.data if result.data else []
            pending_count = len(pending_reviews)
            
            if pending_count > 0:
                store_summary.append({
                    "store_code": store['store_code'],
                    "store_name": store.get('store_name', ''),
                    "platform": store.get('platform', ''),
                    "pending_replies": pending_count
                })
                total_pending += pending_count
        
        if total_pending == 0:
            return {
                "success": True,
                "message": "모든 매장에 처리할 답글이 없습니다",
                "processed_stores": len(accessible_stores),
                "total_pending": 0
            }
        
        # 백그라운드에서 전체 매장 처리 시작
        if use_optimized:
            # 최적화된 처리 방식
            background_tasks.add_task(
                process_all_stores_optimized,
                store_summary,
                current_user.user_code,
                reply_service,
                max_per_store
            )
        else:
            # 기존 처리 방식
            background_tasks.add_task(
                reply_service.process_all_stores_replies,
                current_user.user_code,
                max_per_store
            )
        
        return {
            "success": True,
            "message": f"{len(store_summary)}개 매장의 {total_pending}개 답글 일괄 등록이 시작되었습니다",
            "processed_stores": len(store_summary),
            "total_pending": total_pending,
            "store_summary": store_summary,
            "processing_mode": "background",
            "use_optimized": use_optimized,
            "estimated_time_minutes": total_pending * (0.5 if use_optimized else 2)  # 최적화 시 처리 시간 단축
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"전체 매장 답글 등록 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_all_stores_optimized(
    store_summary: List[Dict[str, Any]],
    user_code: str,
    reply_service: ReplyPostingService,
    max_per_store: int
):
    """
    최적화된 전체 매장 처리 (백그라운드 태스크)
    """
    try:
        logger.info(f"최적화된 전체 매장 처리 시작: {len(store_summary)}개 매장")
        
        for store_info in store_summary:
            store_code = store_info['store_code']
            
            try:
                # 해당 매장의 대기 중인 리뷰 조회
                supabase = reply_service.supabase
                query = supabase.client.table('reviews').select('review_id').eq(
                    'store_code', store_code
                ).in_('response_status', ['generated', 'ready_to_post']).limit(max_per_store)
                
                result = await supabase._execute_query(query)
                pending_reviews = result.data if result.data else []
                
                if pending_reviews:
                    review_ids = [r['review_id'] for r in pending_reviews]
                    
                    # 최적화된 일괄 처리 호출
                    result = await reply_service.post_batch_replies_optimized(
                        store_code=store_code,
                        review_ids=review_ids,
                        user_code=user_code
                    )
                    
                    logger.info(f"매장 {store_code} 처리 완료: {result.get('message', '')}")
                    
            except Exception as e:
                logger.error(f"매장 {store_code} 처리 중 오류: {e}")
                continue
            
            # 매장 간 처리 간격
            await asyncio.sleep(5)
        
        logger.info("최적화된 전체 매장 처리 완료")
        
    except Exception as e:
        logger.error(f"최적화된 전체 매장 처리 중 오류: {e}")


# 상태 확인 엔드포인트 추가
@router.get("/batch/{store_code}/status")
async def get_batch_status(
    store_code: str,
    current_user: User = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    매장의 일괄 처리 상태 확인
    """
    try:
        # 권한 확인
        has_permission = await supabase.check_user_permission(
            current_user.user_code,
            store_code,
            'view'
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="해당 매장에 대한 조회 권한이 없습니다")
        
        # 처리 상태별 리뷰 수 집계
        statuses = ['pending', 'generated', 'ready_to_post', 'processing', 'posted', 'failed']
        status_counts = {}
        
        for status in statuses:
            query = supabase.client.table('reviews').select('review_id', count='exact').eq(
                'store_code', store_code
            ).eq('response_status', status)
            
            result = await supabase._execute_query(query)
            status_counts[status] = result.count if hasattr(result, 'count') else 0
        
        # 오늘 처리된 답글 수
        from datetime import datetime, timedelta
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        query = supabase.client.table('reviews').select('review_id', count='exact').eq(
            'store_code', store_code
        ).eq('response_status', 'posted').gte('response_at', today.isoformat())
        
        result = await supabase._execute_query(query)
        today_posted = result.count if hasattr(result, 'count') else 0
        
        return {
            "success": True,
            "store_code": store_code,
            "status_counts": status_counts,
            "today_posted": today_posted,
            "ready_to_process": status_counts.get('generated', 0) + status_counts.get('ready_to_post', 0),
            "in_progress": status_counts.get('processing', 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"일괄 처리 상태 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))