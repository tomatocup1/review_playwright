"""
리뷰 관련 API 라우터
"""
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import Optional, List
import logging

from api.dependencies import get_current_user, get_supabase_service
from api.services.supabase_service import SupabaseService
from api.services.review_collector_service import ReviewCollectorService
from api.schemas.review_schemas import (
    ReviewResponse,
    ReviewCollectRequest,
    ReviewCollectResponse,
    ReplyRequest,
    ReplyResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/reviews",
    tags=["리뷰"]
)


@router.post("/collect", response_model=ReviewCollectResponse)
async def collect_reviews(
    request: ReviewCollectRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    리뷰 수집 API
    
    - store_code: 매장 코드
    - async_mode: 비동기 실행 여부 (기본값: False)
    """
    try:
        # 권한 확인
        has_permission = await supabase.check_user_permission(
            current_user['user_code'],
            request.store_code,
            'view'
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="해당 매장에 대한 권한이 없습니다")
        
        # 리뷰 수집 서비스 초기화
        collector = ReviewCollectorService(supabase)
        
        # 비동기 모드
        if request.async_mode:
            background_tasks.add_task(
                collector.collect_reviews_for_store,
                request.store_code
            )
            return ReviewCollectResponse(
                success=True,
                message="리뷰 수집이 백그라운드에서 시작되었습니다",
                collected=0,
                store_code=request.store_code
            )
        
        # 동기 모드
        result = await collector.collect_reviews_for_store(request.store_code)
        
        return ReviewCollectResponse(
            success=result['success'],
            message="리뷰 수집 완료" if result['success'] else "리뷰 수집 실패",
            collected=result['collected'],
            store_code=request.store_code,
            platform=result.get('platform', ''),
            errors=result.get('errors', [])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"리뷰 수집 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{store_code}", response_model=List[ReviewResponse])
async def get_reviews(
    store_code: str,
    status: Optional[str] = Query(None, description="리뷰 상태 필터"),
    rating: Optional[int] = Query(None, ge=1, le=5, description="별점 필터"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    매장별 리뷰 조회
    
    - store_code: 매장 코드
    - status: pending, posted, failed
    - rating: 1-5
    - limit: 조회 개수
    - offset: 시작 위치
    """
    try:
        # 권한 확인
        has_permission = await supabase.check_user_permission(
            current_user['user_code'],
            store_code,
            'view'
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="해당 매장에 대한 권한이 없습니다")
        
        # 리뷰 조회
        reviews = await supabase.get_reviews_by_store(
            store_code=store_code,
            status=status,
            rating=rating,
            limit=limit,
            offset=offset
        )
        
        return [ReviewResponse(**review) for review in reviews]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"리뷰 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{review_id}/reply", response_model=ReplyResponse)
async def post_reply(
    review_id: str,
    request: ReplyRequest,
    current_user: dict = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    답글 등록
    
    - review_id: 리뷰 ID
    - reply_content: 답글 내용
    - reply_type: ai_auto, ai_manual, full_manual
    """
    try:
        # 리뷰 정보 조회
        review = await supabase.get_review_by_id(review_id)
        if not review:
            raise HTTPException(status_code=404, detail="리뷰를 찾을 수 없습니다")
        
        # 권한 확인
        has_permission = await supabase.check_user_permission(
            current_user['user_code'],
            review['store_code'],
            'reply'
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="답글 작성 권한이 없습니다")
        
        # 이미 답글이 있는지 확인
        if review['response_status'] == 'posted':
            raise HTTPException(status_code=400, detail="이미 답글이 등록된 리뷰입니다")
        
        # 크롤러를 통해 실제 답글 등록
        # TODO: 실제 플랫폼에 답글 등록하는 로직 구현
        
        # DB 업데이트
        update_result = await supabase.update_review_status(
            review_id=review_id,
            status='posted',
            reply_content=request.reply_content,
            reply_type=request.reply_type,
            reply_by=current_user['user_code']
        )
        
        if update_result:
            return ReplyResponse(
                success=True,
                message="답글이 성공적으로 등록되었습니다",
                review_id=review_id,
                reply_content=request.reply_content
            )
        else:
            raise HTTPException(status_code=500, detail="답글 등록 실패")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"답글 등록 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/{store_code}")
async def get_review_stats(
    store_code: str,
    current_user: dict = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    매장 리뷰 통계
    """
    try:
        # 권한 확인
        has_permission = await supabase.check_user_permission(
            current_user['user_code'],
            store_code,
            'view'
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="해당 매장에 대한 권한이 없습니다")
        
        # 통계 조회
        stats = await supabase.get_review_stats(store_code)
        
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"리뷰 통계 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collect/all")
async def collect_all_stores_reviews(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    모든 매장 리뷰 수집 (관리자 전용)
    """
    try:
        # 관리자 권한 확인
        if current_user['role'] != 'admin':
            raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
        
        # 백그라운드에서 실행
        collector = ReviewCollectorService(supabase)
        background_tasks.add_task(collector.collect_all_stores_reviews)
        
        return {
            "message": "전체 매장 리뷰 수집이 시작되었습니다",
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"전체 리뷰 수집 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))