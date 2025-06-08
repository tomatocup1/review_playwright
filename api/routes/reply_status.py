"""
답글 등록 상태 조회 및 유틸리티 API 엔드포인트들
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
import logging

from api.dependencies import get_current_user, get_supabase_service
from api.services.supabase_service import SupabaseService
from api.services.reply_posting_service import ReplyPostingService
from api.schemas.auth import User

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/reply-status",
    tags=["답글 상태 조회"]
)


@router.get("/{store_code}/pending")
async def get_pending_replies(
    store_code: str,
    limit: int = Query(20, ge=1, le=100, description="조회할 답글 수"),
    current_user: User = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    매장의 처리 대기 중인 답글 목록 조회
    
    - store_code: 매장 코드
    - limit: 조회할 답글 수 (기본값: 20, 최대: 100)
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
        
        # ReplyPostingService 초기화
        reply_service = ReplyPostingService(supabase)
        
        # 대기 중인 답글 조회
        pending_reviews = await reply_service.get_pending_replies(
            store_code=store_code,
            limit=limit
        )
        
        # 매장 정보 조회
        store_info = await supabase.get_store_by_code(store_code)
        
        return {
            "store_code": store_code,
            "store_name": store_info.get('store_name', '') if store_info else '',
            "platform": store_info.get('platform', '') if store_info else '',
            "pending_count": len(pending_reviews),
            "pending_reviews": [
                {
                    "review_id": review['review_id'],
                    "review_content": review.get('review_content', ''),
                    "rating": review.get('rating', 0),
                    "review_date": review.get('review_date', ''),
                    "reply_content": review.get('ai_response') or review.get('manual_response', ''),
                    "response_status": review.get('response_status', ''),
                    "created_at": review.get('created_at', '')
                }
                for review in pending_reviews
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"대기 답글 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{review_id}/status")
async def get_reply_status(
    review_id: str,
    current_user: User = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    특정 리뷰의 답글 처리 상태 상세 조회
    
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
            raise HTTPException(status_code=403, detail="해당 매장에 대한 조회 권한이 없습니다")
        
        # ReplyPostingService 초기화
        reply_service = ReplyPostingService(supabase)
        
        # 상태 추적 정보 조회
        status_info = await reply_service.get_reply_tracking_status(review_id)
        
        return {
            "review_id": review_id,
            "store_code": review['store_code'],
            "platform": review.get('platform', ''),
            "review_content": review.get('review_content', ''),
            "rating": review.get('rating', 0),
            "review_date": review.get('review_date', ''),
            "current_status": review.get('response_status', ''),
            "reply_content": review.get('ai_response') or review.get('manual_response', ''),
            "final_response": review.get('final_response', ''),
            "response_at": review.get('response_at', ''),
            "response_by": review.get('response_by', ''),
            "response_method": review.get('response_method', ''),
            "processing_info": status_info,
            "error_message": review.get('error_message', ''),
            "retry_count": review.get('retry_count', 0),
            "last_retry_at": review.get('last_retry_at', ''),
            "boss_reply_needed": review.get('boss_reply_needed', False),
            "review_reason": review.get('review_reason', '')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"답글 상태 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stores/{user_code}/summary")
async def get_user_stores_summary(
    user_code: str = None,
    current_user: User = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    사용자의 모든 매장별 답글 처리 현황 요약
    
    - user_code: 조회할 사용자 코드 (없으면 현재 사용자)
    """
    try:
        # 조회 대상 사용자 결정
        target_user_code = user_code or current_user.user_code
        
        # 권한 확인 (본인 또는 관리자만 조회 가능)
        if target_user_code != current_user.user_code and current_user.role not in ['admin', 'franchise']:
            raise HTTPException(status_code=403, detail="다른 사용자의 정보는 관리자만 조회할 수 있습니다")
        
        # ReplyPostingService 초기화
        reply_service = ReplyPostingService(supabase)
        
        # 사용자가 접근 가능한 매장 목록 조회
        accessible_stores = await supabase.get_user_accessible_stores(target_user_code)
        
        if not accessible_stores:
            return {
                "user_code": target_user_code,
                "total_stores": 0,
                "stores_summary": []
            }
        
        # 각 매장별 상태 요약
        stores_summary = []
        total_pending = 0
        total_posted = 0
        total_failed = 0
        
        for store in accessible_stores:
            store_code = store['store_code']
            
            # 각 상태별 개수 조회
            pending_count = len(await reply_service.get_pending_replies(store_code, limit=100))
            posted_count = await supabase.get_store_reply_count(store_code, 'posted')
            failed_count = await supabase.get_store_reply_count(store_code, 'failed')
            
            store_summary = {
                "store_code": store_code,
                "store_name": store.get('store_name', ''),
                "platform": store.get('platform', ''),
                "is_active": store.get('is_active', False),
                "pending_replies": pending_count,
                "posted_replies": posted_count,
                "failed_replies": failed_count,
                "last_crawled": store.get('last_crawled', ''),
                "last_reply": store.get('last_reply', ''),
                "auto_reply_enabled": store.get('auto_reply_enabled', False)
            }
            
            stores_summary.append(store_summary)
            total_pending += pending_count
            total_posted += posted_count
            total_failed += failed_count
        
        return {
            "user_code": target_user_code,
            "total_stores": len(accessible_stores),
            "summary": {
                "total_pending": total_pending,
                "total_posted": total_posted,
                "total_failed": total_failed
            },
            "stores_summary": stores_summary
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"매장 요약 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{review_id}/retry")
async def retry_reply_posting(
    review_id: str,
    current_user: User = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    실패한 답글 등록 재시도
    
    - review_id: 리뷰 ID
    - 실패 상태인 답글만 재시도 가능합니다
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
        
        # 재시도 가능한 상태인지 확인
        if review['response_status'] not in ['failed', 'manual_required']:
            raise HTTPException(
                status_code=400,
                detail=f"재시도할 수 없는 상태입니다. 현재 상태: {review['response_status']}"
            )
        
        # 답글 내용 확인
        reply_content = review.get('ai_response') or review.get('manual_response')
        if not reply_content:
            raise HTTPException(status_code=400, detail="재시도할 답글 내용이 없습니다")
        
        # ReplyPostingService 초기화 및 재시도
        reply_service = ReplyPostingService(supabase)
        
        result = await reply_service.post_single_reply(
            review_id=review_id,
            reply_content=reply_content,
            user_code=current_user.user_code
        )
        
        if result['success']:
            return {
                "success": True,
                "message": "답글 등록 재시도가 성공했습니다",
                "review_id": review_id,
                "platform": result['platform'],
                "final_status": result['final_status'],
                "retry_count": result.get('retry_count', 0)
            }
        else:
            return {
                "success": False,
                "message": f"답글 등록 재시도가 실패했습니다: {result.get('error', '알 수 없는 오류')}",
                "review_id": review_id,
                "error_details": result.get('error_details', {}),
                "retry_count": result.get('retry_count', 0),
                "can_retry": result.get('can_retry', False)
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"답글 재시도 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
