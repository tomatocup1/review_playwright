"""
ReplyPostingService를 활용한 답글 등록 API 엔드포인트 (Step 4)
"""
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import Optional, List
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


@router.post("/{review_id}/submit")
async def submit_reply_to_platform(
    review_id: str,
    current_user: User = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    실제 플랫폼에 답글 등록
    
    - review_id: 리뷰 ID
    - ready_to_post 상태의 답글을 실제 플랫폼에 등록합니다
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
        
        # 답글 상태 확인 (ready_to_post 또는 generated 상태여야 함)
        if review['response_status'] not in ['ready_to_post', 'generated']:
            raise HTTPException(
                status_code=400, 
                detail=f"답글 등록이 불가능한 상태입니다. 현재 상태: {review['response_status']}"
            )
        
        # 답글 내용 확인
        reply_content = review.get('ai_response') or review.get('manual_response')
        if not reply_content:
            raise HTTPException(status_code=400, detail="등록할 답글 내용이 없습니다")
        
        # ReplyPostingService 초기화 및 실행
        reply_service = ReplyPostingService(supabase)
        
        # 단일 답글 등록
        result = await reply_service.post_single_reply(
            review_id=review_id,
            reply_content=reply_content,
            user_code=current_user.user_code
        )
        
        if result['success']:
            return {
                "success": True,
                "message": "답글이 성공적으로 등록되었습니다",
                "review_id": review_id,
                "reply_content": reply_content,
                "platform": result['platform'],
                "store_name": result.get('store_name', ''),
                "processing_time": result.get('processing_time', 0),
                "final_status": result['final_status']
            }
        else:
            # 실패한 경우에도 상세 정보 제공
            return {
                "success": False,
                "message": f"답글 등록 실패: {result.get('error', '알 수 없는 오류')}",
                "review_id": review_id,
                "error_details": result.get('error_details', {}),
                "retry_count": result.get('retry_count', 0),
                "can_retry": result.get('can_retry', False)
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"답글 등록 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
# Section 2: Batch Reply Endpoints 
