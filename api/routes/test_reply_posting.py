"""
테스트용 답글 등록 API 엔드포인트 (인증 없음)
실제 플랫폼 연동 테스트를 위한 임시 엔드포인트
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import logging

from api.dependencies import get_supabase_service
from api.services.supabase_service import SupabaseService
from api.services.reply_posting_service import ReplyPostingService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/test-reply-posting",
    tags=["테스트용 답글 등록"]
)


class TestReplyRequest(BaseModel):
    reply_content: str
    user_code: str


@router.post("/{review_id}/submit")
async def test_submit_reply_to_platform(
    review_id: str,
    request: TestReplyRequest,
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    테스트용 실제 플랫폼 답글 등록 (인증 우회)
    
    - review_id: 리뷰 ID
    - request.reply_content: 등록할 답글 내용
    - request.user_code: 사용자 코드
    """
    try:
        logger.info(f"테스트용 답글 등록 시작: review_id={review_id}, user_code={request.user_code}")
        
        # ReplyPostingService 초기화 및 실행
        reply_service = ReplyPostingService(supabase)
        
        # 단일 답글 등록
        result = await reply_service.post_single_reply(
            review_id=review_id,
            reply_content=request.reply_content,
            user_code=request.user_code
        )
        
        logger.info(f"테스트용 답글 등록 결과: success={result['success']}")
        
        if result['success']:
            return {
                "success": True,
                "message": "답글이 성공적으로 등록되었습니다",
                "review_id": review_id,
                "reply_content": request.reply_content,
                "platform": result.get('platform', ''),
                "store_name": result.get('store_name', ''),
                "processing_time": result.get('processing_time', 0),
                "final_status": result.get('final_status', ''),
                "action_taken": result.get('action_taken', ''),
                "test_mode": True
            }
        else:
            # 실패한 경우에도 상세 정보 제공
            return {
                "success": False,
                "message": f"답글 등록 실패: {result.get('error', '알 수 없는 오류')}",
                "review_id": review_id,
                "error_details": result.get('error_details', {}),
                "retry_count": result.get('retry_count', 0),
                "can_retry": result.get('can_retry', False),
                "platform": result.get('platform', ''),
                "test_mode": True
            }
            
    except Exception as e:
        error_msg = f"테스트용 답글 등록 오류: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "message": error_msg,
            "review_id": review_id,
            "test_mode": True,
            "error": str(e)
        }


@router.get("/{review_id}/info")
async def get_review_info_for_test(
    review_id: str,
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    테스트용 리뷰 정보 조회
    """
    try:
        result = await supabase.get_review_by_id(review_id)
        
        if not result or not result.get('data'):
            return {
                "found": False,
                "message": f"리뷰를 찾을 수 없습니다: {review_id}",
                "review_id": review_id
            }
        
        review_data = result['data']
        return {
            "found": True,
            "review_id": review_id,
            "store_code": review_data.get('store_code'),
            "platform": review_data.get('platform'),
            "review_content": review_data.get('review_content'),
            "rating": review_data.get('rating'),
            "response_status": review_data.get('response_status'),
            "ai_response": review_data.get('ai_response'),
            "manual_response": review_data.get('manual_response'),
            "final_response": review_data.get('final_response')
        }
        
    except Exception as e:
        return {
            "found": False,
            "message": f"리뷰 조회 오류: {str(e)}",
            "review_id": review_id,
            "error": str(e)
        }


@router.get("/stores/{store_code}/info")
async def get_store_info_for_test(
    store_code: str,
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    테스트용 매장 정보 조회
    """
    try:
        result = await supabase.get_store_by_code(store_code)
        
        if not result or not result.get('data'):
            return {
                "found": False,
                "message": f"매장을 찾을 수 없습니다: {store_code}",
                "store_code": store_code
            }
        
        store_data = result['data']
        return {
            "found": True,
            "store_code": store_code,
            "store_name": store_data.get('store_name'),
            "platform": store_data.get('platform'),
            "platform_id": store_data.get('platform_id'),
            "platform_code": store_data.get('platform_code'),
            "is_active": store_data.get('is_active'),
            "owner_user_code": store_data.get('owner_user_code'),
            "has_password": bool(store_data.get('platform_pw'))  # 비밀번호 존재 여부만
        }
        
    except Exception as e:
        return {
            "found": False,
            "message": f"매장 조회 오류: {str(e)}",
            "store_code": store_code,
            "error": str(e)
        }
