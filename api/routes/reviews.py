"""
리뷰 관련 API 라우터
"""
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import Optional, List
import logging

from api.dependencies import get_current_user, get_supabase_service
from api.services.supabase_service import SupabaseService
from api.services.review_collector_service import ReviewCollectorService
from api.schemas.auth import User  # User 스키마 임포트 추가
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
    current_user: User = Depends(get_current_user),  # dict -> User로 변경
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
            current_user.user_code,  # 딕셔너리 접근 대신 속성 접근
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


@router.get("/{store_code}/debug")
async def debug_store_reviews(
    store_code: str,
    current_user: User = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """매장 리뷰 디버깅 정보 조회"""
    try:
        debug_info = {}
        
        # 1. 사용자 권한 정보
        has_view_permission = await supabase.check_user_permission(
            current_user.user_code,
            store_code,
            'view'
        )
        debug_info['user_permission'] = {
            'user_code': current_user.user_code,
            'has_view_permission': has_view_permission
        }
        
        # 2. 매장 정보 확인
        store_query = supabase.client.table('platform_reply_rules').select('*').eq('store_code', store_code)
        store_response = await supabase._execute_query(store_query)
        debug_info['store_exists'] = bool(store_response.data)
        debug_info['store_owner'] = store_response.data[0].get('owner_user_code') if store_response.data else None
        
        # 3. 전체 리뷰 수 (조건 없이)
        all_reviews_query = supabase.client.table('reviews').select('*', count='exact').eq('store_code', store_code)
        all_reviews_response = await supabase._execute_query(all_reviews_query)
        debug_info['total_reviews'] = all_reviews_response.count
        
        # 4. 플랫폼별 리뷰 수
        platforms = ['naver', 'baemin', 'coupang', 'yogiyo']
        platform_counts = {}
        for platform in platforms:
            platform_query = supabase.client.table('reviews').select('*', count='exact').eq('store_code', store_code).eq('platform', platform)
            platform_response = await supabase._execute_query(platform_query)
            platform_counts[platform] = platform_response.count
        debug_info['platform_counts'] = platform_counts
        
        # 5. is_deleted 상태별 수
        deleted_true_query = supabase.client.table('reviews').select('*', count='exact').eq('store_code', store_code).eq('is_deleted', True)
        deleted_true_response = await supabase._execute_query(deleted_true_query)
        
        deleted_false_query = supabase.client.table('reviews').select('*', count='exact').eq('store_code', store_code).eq('is_deleted', False)
        deleted_false_response = await supabase._execute_query(deleted_false_query)
        
        deleted_null_query = supabase.client.table('reviews').select('*', count='exact').eq('store_code', store_code).is_('is_deleted', 'null')
        deleted_null_response = await supabase._execute_query(deleted_null_query)
        
        debug_info['is_deleted_stats'] = {
            'true': deleted_true_response.count,
            'false': deleted_false_response.count,
            'null': deleted_null_response.count
        }
        
        # 6. 최근 네이버 리뷰 샘플 (5개)
        naver_sample_query = supabase.client.table('reviews').select('review_id, platform, rating, review_date, is_deleted, created_at, review_name').eq('store_code', store_code).eq('platform', 'naver').order('created_at', desc=True).limit(5)
        naver_sample_response = await supabase._execute_query(naver_sample_query)
        debug_info['naver_samples'] = naver_sample_response.data
        
        # 7. API 호출과 동일한 조건으로 조회
        api_query = supabase.client.table('reviews').select('*').eq('store_code', store_code).or_('is_deleted.is.null,is_deleted.eq.false').order('review_date', desc=True).limit(20)
        api_response = await supabase._execute_query(api_query)
        debug_info['api_query_result'] = {
            'count': len(api_response.data or []),
            'platforms': {}
        }
        
        if api_response.data:
            for review in api_response.data:
                platform = review.get('platform', 'unknown')
                debug_info['api_query_result']['platforms'][platform] = debug_info['api_query_result']['platforms'].get(platform, 0) + 1
        
        return debug_info
        
    except Exception as e:
        logger.error(f"디버그 조회 오류: {e}")
        logger.exception("상세 오류:")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{store_code}", response_model=List[ReviewResponse])
async def get_reviews(
    store_code: str,
    status: Optional[str] = Query(None, description="리뷰 상태 필터"),
    rating: Optional[int] = Query(None, ge=1, le=5, description="별점 필터"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),  # dict -> User로 변경
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
        logger.info(f"리뷰 조회 요청 - store_code: {store_code}, user: {current_user.user_code}")
        
        # 권한 확인
        has_permission = await supabase.check_user_permission(
            current_user.user_code,  # 딕셔너리 접근 대신 속성 접근
            store_code,
            'view'
        )
        
        logger.info(f"권한 확인 결과: {has_permission}")
        
        if not has_permission:
            # 권한이 없을 때 더 자세한 정보 로깅
            logger.warning(f"권한 없음 - user: {current_user.user_code}, store: {store_code}")
            
            # 매장 정보 확인
            store_check = await supabase._execute_query(
                supabase.client.table('platform_reply_rules')
                .select('store_code, owner_user_code')
                .eq('store_code', store_code)
            )
            logger.debug(f"매장 정보: {store_check.data}")
            
            raise HTTPException(status_code=403, detail="해당 매장에 대한 권한이 없습니다")
        
        # 리뷰 조회
        reviews = await supabase.get_reviews_by_store(
            store_code=store_code,
            status=status,
            rating=rating,
            limit=limit,
            offset=offset
        )
        
        logger.info(f"조회된 리뷰 수: {len(reviews)}")
        
        # 네이버 리뷰만 별도로 확인
        naver_reviews = [r for r in reviews if r.get('platform') == 'naver']
        logger.info(f"네이버 리뷰 수: {len(naver_reviews)}")
        
        return [ReviewResponse(**review) for review in reviews]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"리뷰 조회 오류: {e}")
        logger.exception("상세 오류:")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{review_id}/reply", response_model=ReplyResponse)
async def post_reply(
    review_id: str,
    request: ReplyRequest,
    current_user: User = Depends(get_current_user),  # dict -> User로 변경
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
            current_user.user_code,  # 딕셔너리 접근 대신 속성 접근
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
            reply_by=current_user.user_code  # 딕셔너리 접근 대신 속성 접근
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
    current_user: User = Depends(get_current_user),  # dict -> User로 변경
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    매장 리뷰 통계
    """
    try:
        # 권한 확인
        has_permission = await supabase.check_user_permission(
            current_user.user_code,  # 딕셔너리 접근 대신 속성 접근
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
    current_user: User = Depends(get_current_user),  # dict -> User로 변경
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    모든 매장 리뷰 수집 (관리자 전용)
    """
    try:
        # 관리자 권한 확인
        if current_user.role != 'admin':  # 딕셔너리 접근 대신 속성 접근
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

# =============================================
# AI 답글 생성 관련 엔드포인트 추가
# =============================================

from api.services.ai_service import AIService

@router.post("/{review_id}/generate-reply")
async def generate_reply(
    review_id: str,
    current_user: User = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    AI 답글 생성
    
    - review_id: 리뷰 ID
    """
    try:
        # 리뷰 정보 조회
        review = await supabase.get_review_by_id(review_id)
        if not review:
            raise HTTPException(status_code=404, detail="리뷰를 찾을 수 없습니다")
        
        # 권한 확인
        has_permission = await supabase.check_user_permission(
            current_user.user_code,
            review['store_code'],
            'reply'
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="답글 작성 권한이 없습니다")
        
        # 이미 답글이 있는지 확인
        if review['response_status'] == 'posted':
            raise HTTPException(status_code=400, detail="이미 답글이 등록된 리뷰입니다")
        
        # 매장 답글 정책 조회
        store_rules = await supabase.get_store_reply_rules(review['store_code'])
        
        # AI 서비스로 답글 생성
        ai_service = AIService()
        result = await ai_service.generate_reply(review, store_rules)
        
        if result['success']:
            # 생성 이력 저장
            await supabase.save_reply_generation_history(
                review_id=review_id,
                user_code=current_user.user_code,
                generation_type='ai_initial',
                prompt_used=result.get('prompt_used', ''),
                model_version=result.get('model_used', 'gpt-4o-mini'),
                generated_content=result['reply'],
                quality_score=result['quality_score'],
                processing_time_ms=result['processing_time_ms'],
                token_usage=result['token_usage'],
                is_selected=False
            )
            
            # boss_review_needed, review_reason, urgency_score 추가
            boss_review_needed = result.get('boss_review_needed', False)
            review_reason = result.get('review_reason', '')
            urgency_score = result.get('urgency_score', 0.3)
            
            # 리뷰에 AI 답글 저장 (아직 등록하지는 않음)
            await supabase.update_review_status(
                review_id=review_id,
                status='generated',
                reply_content=result['reply'],
                reply_type='ai_auto',
                reply_by='AI',
                boss_review_needed=boss_review_needed,
                review_reason=review_reason,
                urgency_score=urgency_score
            )
            
            return {
                "success": True,
                "message": "AI 답글이 성공적으로 생성되었습니다",
                "review_id": review_id,
                "generated_reply": result['reply'],
                "quality_score": result['quality_score'],
                "is_valid": result['is_valid'],
                "processing_time_ms": result['processing_time_ms'],
                "token_usage": result['token_usage'],
                "store_name": store_rules.get('store_name', ''),
                "platform": store_rules.get('platform', ''),
                "boss_review_needed": boss_review_needed,
                "review_reason": review_reason,
                "urgency_score": urgency_score,
                "total_attempts": result.get('total_attempts', 1),
                "retry_count": result.get('retry_count', 0)
            }
        else:
            # 실패한 경우도 이력 저장
            await supabase.save_reply_generation_history(
                review_id=review_id,
                user_code=current_user.user_code,
                generation_type='ai_initial',
                prompt_used='',
                model_version='gpt-4o-mini',
                generated_content='',
                quality_score=0.0,
                processing_time_ms=result['processing_time_ms'],
                token_usage=0,
                is_selected=False
            )
            
            raise HTTPException(
                status_code=500, 
                detail=f"답글 생성 실패: {result.get('error', '알 수 없는 오류')}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"답글 생성 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{review_id}/regenerate-reply")
async def regenerate_reply(
    review_id: str,
    current_user: User = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    AI 답글 재생성
    
    - review_id: 리뷰 ID
    """
    try:
        # 리뷰 정보 조회
        review = await supabase.get_review_by_id(review_id)
        if not review:
            raise HTTPException(status_code=404, detail="리뷰를 찾을 수 없습니다")
        
        # 권한 확인
        has_permission = await supabase.check_user_permission(
            current_user.user_code,
            review['store_code'],
            'reply'
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="답글 작성 권한이 없습니다")
        
        # 매장 답글 정책 조회
        store_rules = await supabase.get_store_reply_rules(review['store_code'])
        
        # 이전 시도 횟수 확인 (간단히 1로 설정)
        previous_attempts = 1
        
        # AI 서비스로 답글 재생성
        ai_service = AIService()
        result = await ai_service.regenerate_reply(review, store_rules, previous_attempts)
        
        if result['success']:
            # 생성 이력 저장
            await supabase.save_reply_generation_history(
                review_id=review_id,
                user_code=current_user.user_code,
                generation_type='ai_retry',
                prompt_used=result.get('prompt_used', ''),
                model_version=result.get('model_used', 'gpt-4o-mini'),
                generated_content=result['reply'],
                quality_score=result['quality_score'],
                processing_time_ms=result['processing_time_ms'],
                token_usage=result['token_usage'],
                is_selected=False
            )
            
            # boss_review_needed, review_reason, urgency_score 추가
            boss_review_needed = result.get('boss_review_needed', False)
            review_reason = result.get('review_reason', '')
            urgency_score = result.get('urgency_score', 0.3)
            
            # 리뷰에 새로운 AI 답글 저장
            await supabase.update_review_status(
                review_id=review_id,
                status='generated',
                reply_content=result['reply'],
                reply_type='ai_retry',
                reply_by='AI',
                boss_review_needed=boss_review_needed,
                review_reason=review_reason,
                urgency_score=urgency_score
            )
            
            return {
                "success": True,
                "message": "AI 답글이 재생성되었습니다",
                "review_id": review_id,
                "generated_reply": result['reply'],
                "quality_score": result['quality_score'],
                "is_valid": result['is_valid'],
                "processing_time_ms": result['processing_time_ms'],
                "token_usage": result['token_usage'],
                "attempt_number": result.get('attempt_number', 1),
                "boss_review_needed": boss_review_needed,
                "review_reason": review_reason,
                "urgency_score": urgency_score
            }
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"답글 재생성 실패: {result.get('error', '알 수 없는 오류')}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"답글 재생성 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{review_id}/generation-history")
async def get_generation_history(
    review_id: str,
    current_user: User = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    답글 생성 이력 조회
    
    - review_id: 리뷰 ID
    """
    try:
        # 리뷰 정보 조회
        review = await supabase.get_review_by_id(review_id)
        if not review:
            raise HTTPException(status_code=404, detail="리뷰를 찾을 수 없습니다")
        
        # 권한 확인
        has_permission = await supabase.check_user_permission(
            current_user.user_code,
            review['store_code'],
            'view'
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="해당 매장에 대한 권한이 없습니다")
        
        # 생성 이력 조회
        response = await supabase._execute_query(
            supabase.client.table('reply_generation_history')
            .select('*')
            .eq('review_id', review_id)
            .order('created_at', desc=True)
        )
        
        history = response.data or []
        
        return {
            "review_id": review_id,
            "history": history,
            "total_attempts": len(history)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"생성 이력 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{review_id}/select-reply")
async def select_reply(
    review_id: str,
    selected_reply: dict,  # {"reply_content": "선택된 답글", "generation_id": 123}
    current_user: User = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    생성된 답글 중 하나를 선택
    
    - review_id: 리뷰 ID
    - selected_reply: 선택된 답글 정보
    """
    try:
        # 리뷰 정보 조회
        review = await supabase.get_review_by_id(review_id)
        if not review:
            raise HTTPException(status_code=404, detail="리뷰를 찾을 수 없습니다")
        
        # 권한 확인
        has_permission = await supabase.check_user_permission(
            current_user.user_code,
            review['store_code'],
            'reply'
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="답글 작성 권한이 없습니다")
        
        reply_content = selected_reply.get('reply_content', '')
        generation_id = selected_reply.get('generation_id')
        
        if not reply_content:
            raise HTTPException(status_code=400, detail="답글 내용이 필요합니다")
        
        # 선택된 답글로 업데이트
        await supabase.update_review_status(
            review_id=review_id,
            status='ready_to_post',  # 등록 준비 완료
            reply_content=reply_content,
            reply_type='ai_manual',  # 사용자가 선택한 AI 답글
            reply_by=current_user.user_code
        )
        
        # 생성 이력에서 선택된 것으로 표시
        if generation_id:
            await supabase._execute_query(
                supabase.client.table('reply_generation_history')
                .update({'is_selected': True})
                .eq('id', generation_id)
            )
        
        return {
            "success": True,
            "message": "답글이 선택되었습니다. 이제 등록할 수 있습니다.",
            "review_id": review_id,
            "selected_reply": reply_content,
            "status": "ready_to_post"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"답글 선택 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 사장님 확인 필요 리뷰 조회 엔드포인트 추가
@router.get("/boss-review-needed/{store_code}")
async def get_boss_review_needed(
    store_code: str,
    urgency_level: Optional[str] = Query(None, description="긴급도 필터 (low, medium, high, critical)"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    사장님 확인 필요 리뷰 조회
    
    - store_code: 매장 코드
    - urgency_level: 긴급도 필터
    - limit: 조회 개수
    - offset: 시작 위치
    """
    try:
        # 권한 확인
        has_permission = await supabase.check_user_permission(
            current_user.user_code,
            store_code,
            'view'
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="해당 매장에 대한 권한이 없습니다")
        
        # 사장님 확인 필요 리뷰 조회
        query = supabase.client.table('reviews').select('*').eq('store_code', store_code).eq('boss_reply_needed', True)
        
        if urgency_level:
            query = query.eq('urgency_level', urgency_level)
        
        # 긴급도 순으로 정렬 (critical > high > medium > low)
        query = query.order('urgency_level', desc=False).order('created_at', desc=True)
        
        # 페이징
        query = query.limit(limit).offset(offset)
        
        response = await supabase._execute_query(query)
        reviews = response.data or []
        
        return [ReviewResponse(**review) for review in reviews]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"사장님 확인 필요 리뷰 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))