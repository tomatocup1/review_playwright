"""
테스트용 답글 등록 API 엔드포인트 (인증 없음)
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
import logging

from api.dependencies import get_supabase_service
from api.services.supabase_service import SupabaseService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/test-reply-posting",
    tags=["테스트 답글 등록"]
)


@router.get("/{review_id}/info")
async def get_review_info(
    review_id: str,
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    리뷰 정보 조회 (테스트용 - 인증 불필요)
    """
    try:
        # 리뷰 정보 조회 (인증 없이)
        review = await supabase.get_review_by_id(review_id)
        if not review:
            raise HTTPException(status_code=404, detail="리뷰를 찾을 수 없습니다")
        
        return {
            "success": True,
            "review": {
                "review_id": review['review_id'],
                "store_code": review['store_code'],
                "platform": review['platform'],
                "rating": review['rating'],
                "review_content": review['review_content'],
                "ai_response": review.get('ai_response', ''),
                "manual_response": review.get('manual_response', ''),
                "response_status": review['response_status'],
                "review_date": review['review_date'],
                "created_at": review.get('created_at', ''),
                "updated_at": review.get('updated_at', '')
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"리뷰 정보 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stores/{store_code}/info")
async def get_store_info(
    store_code: str,
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    매장 정보 조회 (테스트용 - 인증 불필요)
    """
    try:
        # 매장 정보 조회 (인증 없이)
        store = await supabase.get_store_by_code(store_code)
        if not store:
            raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다")
        
        return {
            "success": True,
            "store": {
                "store_code": store['store_code'],
                "store_name": store['store_name'],
                "platform": store['platform'],
                "platform_code": store['platform_code'],
                "is_active": store.get('is_active', True),
                "auto_reply_enabled": store.get('auto_reply_enabled', False),
                "greeting_start": store.get('greeting_start', ''),
                "greeting_end": store.get('greeting_end', ''),
                "created_at": store.get('created_at', ''),
                "updated_at": store.get('updated_at', '')
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"매장 정보 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{review_id}/submit")
async def test_submit_reply(
    review_id: str,
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    테스트용 답글 등록 (실제 플랫폼에는 등록하지 않음, 인증 불필요)
    """
    try:
        # 리뷰 정보 조회
        review = await supabase.get_review_by_id(review_id)
        if not review:
            raise HTTPException(status_code=404, detail="리뷰를 찾을 수 없습니다")
        
        # 답글 내용 확인
        reply_content = review.get('ai_response') or review.get('manual_response')
        if not reply_content:
            raise HTTPException(status_code=400, detail="등록할 답글 내용이 없습니다")
        
        # 테스트용 - 상태만 업데이트 (실제 플랫폼에는 등록하지 않음)
        await supabase.update_review_status(
            review_id=review_id,
            status='posted',
            final_response=reply_content,
            response_by='test_user'
        )
        
        return {
            "success": True,
            "message": "테스트 답글 등록 완료 (실제 플랫폼에는 등록되지 않음)",
            "review_id": review_id,
            "reply_content": reply_content,
            "platform": review['platform'],
            "store_code": review['store_code'],
            "test_mode": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"테스트 답글 등록 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test")
async def test_endpoint():
    """
    간단한 테스트 엔드포인트
    """
    return {
        "success": True,
        "message": "테스트 답글 등록 API가 정상 작동 중입니다",
        "endpoints": [
            "GET /{review_id}/info - 리뷰 정보 조회",
            "GET /stores/{store_code}/info - 매장 정보 조회", 
            "POST /{review_id}/submit - 테스트 답글 등록"
        ]
    }
