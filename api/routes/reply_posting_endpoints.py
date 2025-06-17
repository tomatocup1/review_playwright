"""
ReplyPostingService를 활용한 답글 등록 API 엔드포인트 (Step 4)
"""
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks, Body
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import logging

from api.dependencies import get_current_user, get_supabase_service
from api.services.supabase_service import SupabaseService
from api.services.reply_posting_service import ReplyPostingService
from api.schemas.auth import User

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/reply-posting",
    tags=["답글 등록"]
)


class ReplySubmitRequest(BaseModel):
    """답글 등록 요청 모델"""
    reply_content: Optional[str] = None
    auto_submit: bool = True


@router.post("/{review_id}/submit")
async def submit_reply_to_platform(
    review_id: str,
    request: ReplySubmitRequest,
    current_user: User = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    실제 플랫폼에 답글 등록
    """
    try:
        # 리뷰 정보 조회
        review = await supabase.get_review_by_id(review_id)
        if not review:
            logger.error(f"리뷰를 찾을 수 없습니다. review_id: {review_id}")
            raise HTTPException(
                status_code=404, 
                detail=f"리뷰 정보를 찾을 수 없습니다. (review_id: {review_id})"
            )
        
        # 이미 답글이 등록되었는지 확인
        if review.get('response_status') == 'posted':
            logger.warning(f"이미 답글이 등록된 리뷰입니다: review_id={review_id}")
            return {
                "success": True,
                "message": "이미 답글이 등록되었습니다",
                "review_id": review_id,
                "status": "already_posted"
            }
        
        # 처리 중인지 확인 (동시 요청 방지)
        if review.get('response_status') == 'processing':
            logger.warning(f"답글 등록이 진행 중입니다: review_id={review_id}")
            return {
                "success": False,
                "message": "답글 등록이 진행 중입니다",
                "review_id": review_id,
                "status": "processing"
            }
        
        # 권한 확인
        has_permission = await supabase.check_user_permission(
            current_user.user_code,
            review['store_code'],
            'reply'
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="답글 작성 권한이 없습니다")
        
        # 답글 상태 확인
        if review['response_status'] not in ['ready_to_post', 'generated', 'failed']:
            raise HTTPException(
                status_code=400, 
                detail=f"답글 등록이 불가능한 상태입니다. 현재 상태: {review['response_status']}"
            )
        
        # 상태를 processing으로 업데이트 (동시 요청 방지)
        try:
            await supabase.update_review_response(
                review_id,
                response_status='processing',
                response_by=current_user.user_code
            )
        except Exception as e:
            logger.error(f"상태 업데이트 실패: {e}")
        
        # 답글 내용 확인
        reply_content = (
            request.reply_content or 
            review.get('final_response') or 
            review.get('ai_response') or 
            review.get('response_text')
        )
        
        if not reply_content:
            # 상태를 원래대로 복구
            await supabase.update_review_response(
                review_id,
                response_status=review['response_status']
            )
            logger.warning(f"AI 답글을 찾을 수 없음. review keys: {list(review.keys())}")
            raise HTTPException(
                status_code=400,
                detail="AI 답글이 생성되지 않았습니다. 먼저 AI 답글을 생성해주세요."
            )
        
        # ReplyPostingService 초기화 및 실행
        reply_service = ReplyPostingService(supabase)
        
        # 단일 답글 등록
        result = await reply_service.post_single_reply(
            review_id=review_id,
            reply_content=reply_content,
            user_code=current_user.user_code
        )
        
        # 결과에 따라 상태 업데이트는 service에서 처리됨
        
        if result['success']:
            return {
                "success": True,
                "message": "답글이 성공적으로 등록되었습니다",
                "review_id": review_id,
                "reply_content": reply_content,
                "platform": result.get('platform', ''),
                "store_name": result.get('store_name', ''),
                "processing_time": result.get('processing_time', 0),
                "final_status": result.get('final_status', 'posted')
            }
        else:
            # 이미 등록된 경우
            if result.get('status') == 'already_posted' or '이미 답글이 등록' in result.get('error', ''):
                return {
                    "success": True,
                    "message": result.get('error', '이미 답글이 등록되었습니다'),
                    "review_id": review_id,
                    "status": "already_posted"
                }
            
            # 실패한 경우
            return {
                "success": False,
                "message": f"답글 등록 실패: {result.get('error', '알 수 없는 오류')}",
                "review_id": review_id,
                "error_details": result.get('error_details', {}),
                "retry_count": result.get('retry_count', 0),
                "can_retry": result.get('can_retry', True),
                "final_status": result.get('final_status', 'failed')
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"답글 등록 오류: {e}")
        # 에러 발생 시 상태 복구
        try:
            await supabase.update_review_response(
                review_id,
                response_status='failed',
                error_message=str(e)
            )
        except:
            pass
        raise HTTPException(status_code=500, detail=str(e))


# Section 2: Batch Reply Endpoints
class BatchSubmitRequest(BaseModel):
    """일괄 답글 등록 요청 모델"""
    filters: Optional[Dict[str, Any]] = None
    auto_submit: bool = True
    max_count: Optional[int] = None


@router.post("/batch/{store_code}/submit")
async def submit_batch_replies(
    store_code: str,
    request: BatchSubmitRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    매장의 여러 답글을 일괄 등록
    
    - store_code: 매장 코드
    - filters: 필터 조건 (status 등)
    - auto_submit: 자동 제출 여부
    - max_count: 최대 처리 개수
    """
    try:
        # 권한 확인
        has_permission = await supabase.check_user_permission(
            current_user.user_code,
            store_code,
            'reply'
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="답글 작성 권한이 없습니다")
        
        # ReplyPostingService 초기화
        reply_service = ReplyPostingService(supabase)
        
        # 백그라운드에서 일괄 처리 실행
        background_tasks.add_task(
            reply_service.post_batch_replies,
            store_code=store_code,
            filters=request.filters,
            user_code=current_user.user_code,
            max_count=request.max_count
        )
        
        return {
            "success": True,
            "message": "일괄 답글 등록이 시작되었습니다. 완료 후 알림을 받으실 수 있습니다.",
            "store_code": store_code
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"일괄 답글 등록 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch/{store_code}/status")
async def get_batch_status(
    store_code: str,
    current_user: User = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    일괄 답글 등록 진행 상태 조회
    
    - store_code: 매장 코드
    """
    try:
        # 권한 확인
        has_permission = await supabase.check_user_permission(
            current_user.user_code,
            store_code,
            'view'
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="조회 권한이 없습니다")
        
        # 최근 처리 상태 조회 (임시 구현)
        # 실제로는 별도의 작업 상태 추적 테이블이 필요합니다
        return {
            "store_code": store_code,
            "status": "processing",
            "total_count": 0,
            "processed_count": 0,
            "success_count": 0,
            "failed_count": 0,
            "message": "일괄 처리 상태 조회 기능은 추후 구현 예정입니다"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"일괄 상태 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Section 3: Reply History and Management
@router.get("/{review_id}/history")
async def get_reply_history(
    review_id: str,
    current_user: User = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    특정 리뷰의 답글 등록 이력 조회
    
    - review_id: 리뷰 ID
    """
    try:
        # 리뷰 정보 조회
        review = await supabase.get_review_by_id(review_id)
        if not review:
            logger.error(f"리뷰를 찾을 수 없습니다. review_id: {review_id}")
            raise HTTPException(
                status_code=404, 
                detail=f"리뷰 정보를 찾을 수 없습니다. (review_id: {review_id})"
            )
        
        # 권한 확인
        has_permission = await supabase.check_user_permission(
            current_user.user_code,
            review['store_code'],
            'view'
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="조회 권한이 없습니다")
        
        # 답글 생성 이력 조회
        history = await supabase.get_reply_generation_history(review_id)
        
        return {
            "review_id": review_id,
            "current_status": review.get('response_status'),
            "current_reply": review.get('final_response') or review.get('ai_response'),
            "history": history,
            "total_attempts": len(history)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"답글 이력 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{review_id}/retry")
async def retry_failed_reply(
    review_id: str,
    current_user: User = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    실패한 답글 재시도
    
    - review_id: 리뷰 ID
    """
    try:
        # 리뷰 정보 조회
        review = await supabase.get_review_by_id(review_id)
        if not review:
            logger.error(f"리뷰를 찾을 수 없습니다. review_id: {review_id}")
            raise HTTPException(
                status_code=404, 
                detail=f"리뷰 정보를 찾을 수 없습니다. (review_id: {review_id})"
            )
        
        # 권한 확인
        has_permission = await supabase.check_user_permission(
            current_user.user_code,
            review['store_code'],
            'reply'
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="답글 작성 권한이 없습니다")
        
        # 실패 상태인지 확인
        if review['response_status'] != 'failed':
            raise HTTPException(
                status_code=400, 
                detail=f"재시도할 수 없는 상태입니다. 현재 상태: {review['response_status']}"
            )
        
        # 답글 내용 확인 (여러 키 확인)
        reply_content = (
            review.get('final_response') or 
            review.get('ai_response') or 
            review.get('response_text')
        )
        
        if not reply_content:
            raise HTTPException(status_code=400, detail="재시도할 답글 내용이 없습니다")
        
        # ReplyPostingService 초기화 및 재시도
        reply_service = ReplyPostingService(supabase)
        
        # 상태를 ready_to_post로 변경하고 재시도
        await supabase.update_review_response(
            review_id,
            response_status='ready_to_post',
            retry_count=(review.get('retry_count', 0) + 1)
        )
        
        # 답글 등록 시도
        result = await reply_service.post_single_reply(
            review_id=review_id,
            reply_content=reply_content,
            user_code=current_user.user_code
        )
        
        return {
            "success": result['success'],
            "message": "재시도가 완료되었습니다" if result['success'] else "재시도가 실패했습니다",
            "result": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"답글 재시도 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))