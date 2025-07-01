from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Optional, List
from datetime import datetime
import logging
import sys
from pathlib import Path

# Import 설정
try:
    from ..dependencies import get_current_user, get_database_service, get_reply_posting_service
    from ..schemas.auth import User
    from ..schemas.review_schemas import ReplyRequest, ReplyResponse
    from ..services.reply_posting_service import ReplyPostingService
    from ..services.supabase_service import SupabaseService
except ImportError:
    # 절대 경로로 대체
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    
    from api.dependencies import get_current_user, get_database_service, get_reply_posting_service
    from api.schemas.auth import User
    from api.schemas.review_schemas import ReplyRequest, ReplyResponse
    from api.services.reply_posting_service import ReplyPostingService
    from api.services.supabase_service import SupabaseService
router = APIRouter(
    prefix="/api",
    tags=["reply-posting"]
)
logger = logging.getLogger(__name__)

@router.post("/reviews/{review_id}/post-reply", response_model=ReplyResponse)
async def post_review_reply(
    review_id: str,
    request: ReplyRequest,
    current_user: User = Depends(get_current_user),
    database_service: SupabaseService = Depends(get_database_service),
    reply_posting_service: ReplyPostingService = Depends(get_reply_posting_service)
):
    """리뷰에 답글 등록"""
    try:
        logger.info(f"답글 등록 요청: review_id={review_id}, user={current_user.email}")
        
        # 리뷰 정보 조회
        review = await database_service.get_review_by_id(review_id)
        if not review:
            raise HTTPException(status_code=404, detail="리뷰를 찾을 수 없습니다")
        
        # 매장 정보 조회
        store = await database_service.get_store_by_code(review['store_code'])
        if not store:
            raise HTTPException(status_code=404, detail="매장 정보를 찾을 수 없습니다")
        
        # 권한 확인
        if store['owner_user_code'] != current_user.user_code:
            # 권한 테이블에서 추가 권한 확인
            has_permission = await database_service.check_user_store_permission(
                current_user.user_code, 
                store['store_code'],
                'reply'
            )
            if not has_permission:
                raise HTTPException(status_code=403, detail="이 매장에 대한 답글 권한이 없습니다")
        
        # 플랫폼 확인
        platform = store.get('platform', '').lower()
        if platform not in ['baemin', 'coupang', 'coupangeats', 'yogiyo']:
            raise HTTPException(
                status_code=400, 
                detail=f"지원하지 않는 플랫폼입니다: {platform}"
            )
        
        # 답글 내용 확인
        reply_content = request.reply_content.strip()
        if not reply_content:
            raise HTTPException(status_code=400, detail="답글 내용을 입력해주세요")
        
        # 답글 길이 제한 확인 (플랫폼별로 다를 수 있음)
        max_length = 300 if platform in ['coupang', 'coupangeats'] else 500
        if len(reply_content) > max_length:
            raise HTTPException(
                status_code=400, 
                detail=f"답글은 {max_length}자를 초과할 수 없습니다"
            )
        
        # 이미 답글이 등록된 리뷰인지 확인
        if review.get('response_status') == 'posted':
            raise HTTPException(status_code=400, detail="이미 답글이 등록된 리뷰입니다")
        
        # 답글 등록 시작 - DB 상태 업데이트
        await database_service.update_review_status(
            review_id, 
            response_status='posting',
            final_response=reply_content
        )
        
        # 매장 설정 정보 준비
        store_config = {
            'platform': store['platform'],  # platform 정보 추가
            'platform_id': store['platform_id'],
            'platform_pw': store['platform_pw'],
            'platform_code': store['platform_code'],
            'store_code': store['store_code'],
            'store_name': store['store_name']
        }
        
        # 플랫폼별 답글 등록 실행
        result = await reply_posting_service.post_reply_to_platform(
            platform=platform,
            review_id=review_id,
            response_text=reply_content,
            store_config=store_config
        )
        
        # 결과에 따른 DB 업데이트
        if result['success']:
            await database_service.update_review_status(
                review_id,
                response_status='posted',
                response_at=datetime.now(),
                response_by=current_user.user_code,
                response_method='manual'
            )
            
            # 답글 생성 이력 저장
            await database_service.save_reply_generation_history(
                review_id=review_id,
                user_code=current_user.user_code,
                generation_type='manual_post',
                generated_content=reply_content,
                is_selected=True
            )
            
            logger.info(f"답글 등록 성공: review_id={review_id}")
            
            return ReplyResponse(
                success=True,
                message=result.get('message', '답글이 성공적으로 등록되었습니다'),
                review_id=review_id,
                posted_at=datetime.now()
            )
        else:
            # 실패 시 상태 롤백
            await database_service.update_review_status(
                review_id,
                response_status='failed',
                error_message=result.get('error', '알 수 없는 오류')
            )
            
            # 에러 로그 저장
            await database_service.log_error(
                category='답글등록실패',
                platform=platform,
                store_code=store['store_code'],
                error_message=result.get('error', ''),
                user_code=current_user.user_code
            )
            
            error_message = result.get('error', '답글 등록에 실패했습니다')
            logger.error(f"답글 등록 실패: review_id={review_id}, error={error_message}")
            
            raise HTTPException(status_code=500, detail=error_message)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"답글 등록 중 예외 발생: {str(e)}", exc_info=True)
        
        # DB 상태 롤백
        try:
            await database_service.update_review_status(
                review_id,
                response_status='failed',
                error_message=str(e)
            )
        except:
            pass
            
        raise HTTPException(status_code=500, detail=f"답글 등록 중 오류가 발생했습니다: {str(e)}")

@router.get("/reviews/{review_id}/reply-status")
async def get_reply_status(
    review_id: str,
    current_user: User = Depends(get_current_user),
    database_service: SupabaseService = Depends(get_database_service)
):
    """답글 등록 상태 조회"""
    try:
        review = await database_service.get_review_by_id(review_id)
        if not review:
            raise HTTPException(status_code=404, detail="리뷰를 찾을 수 없습니다")
        
        # 권한 확인
        store = await database_service.get_store_by_code(review['store_code'])
        if not store:
            raise HTTPException(status_code=404, detail="매장 정보를 찾을 수 없습니다")
            
        if store['owner_user_code'] != current_user.user_code:
            has_permission = await database_service.check_user_store_permission(
                current_user.user_code,
                store['store_code'],
                'view'
            )
            if not has_permission:
                raise HTTPException(status_code=403, detail="이 리뷰를 볼 권한이 없습니다")
        
        return {
            'review_id': review_id,
            'response_status': review.get('response_status'),
            'response_at': review.get('response_at'),
            'final_response': review.get('final_response'),
            'error_message': review.get('error_message')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"답글 상태 조회 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail="답글 상태 조회 중 오류가 발생했습니다")

@router.post("/reviews/batch-post-replies")
async def batch_post_replies(
    request: Dict[str, List[str]],  # {"review_ids": ["id1", "id2", ...]}
    current_user: User = Depends(get_current_user),
    database_service: SupabaseService = Depends(get_database_service),
    reply_posting_service: ReplyPostingService = Depends(get_reply_posting_service)
):
    """여러 리뷰에 일괄 답글 등록"""
    try:
        review_ids = request.get('review_ids', [])
        if not review_ids:
            raise HTTPException(status_code=400, detail="review_ids가 필요합니다")
            
        results = []
        
        for review_id in review_ids:
            try:
                # 각 리뷰에 대해 개별 처리
                review = await database_service.get_review_by_id(review_id)
                if not review:
                    results.append({
                        'review_id': review_id,
                        'success': False,
                        'error': '리뷰를 찾을 수 없습니다'
                    })
                    continue
                    
                # final_response가 없으면 ai_response 사용
                reply_content = review.get('final_response') or review.get('ai_response')
                if not reply_content:
                    results.append({
                        'review_id': review_id,
                        'success': False,
                        'error': '답글이 준비되지 않았습니다'
                    })
                    continue
                
                # 개별 답글 등록 API 호출
                reply_request = ReplyRequest(reply_content=reply_content)
                response = await post_review_reply(
                    review_id=review_id,
                    request=reply_request,
                    current_user=current_user,
                    database_service=database_service,
                    reply_posting_service=reply_posting_service
                )
                
                results.append({
                    'review_id': review_id,
                    'success': True,
                    'message': response.message
                })
                
            except HTTPException as e:
                results.append({
                    'review_id': review_id,
                    'success': False,
                    'error': e.detail
                })
            except Exception as e:
                results.append({
                    'review_id': review_id,
                    'success': False,
                    'error': str(e)
                })
        
        # 결과 요약
        success_count = sum(1 for r in results if r['success'])
        failed_count = len(results) - success_count
        
        return {
            'total': len(results),
            'success': success_count,
            'failed': failed_count,
            'results': results
        }
        
    except Exception as e:
        logger.error(f"일괄 답글 등록 중 오류: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="일괄 답글 등록 중 오류가 발생했습니다")

# 추가 엔드포인트: 매장별 답글 대기 목록 조회
@router.get("/stores/{store_code}/pending-replies")
async def get_pending_replies(
    store_code: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    database_service: SupabaseService = Depends(get_database_service)
):
    """매장의 답글 대기 리뷰 목록 조회"""
    try:
        # 권한 확인
        store = await database_service.get_store_by_code(store_code)
        if not store:
            raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다")
            
        if store['owner_user_code'] != current_user.user_code:
            has_permission = await database_service.check_user_store_permission(
                current_user.user_code,
                store_code,
                'view'
            )
            if not has_permission:
                raise HTTPException(status_code=403, detail="이 매장의 정보를 볼 권한이 없습니다")
        
        # 답글 대기 리뷰 조회
        pending_reviews = await database_service.get_pending_reviews(
            store_code=store_code,
            limit=limit
        )
        
        return {
            'store_code': store_code,
            'store_name': store['store_name'],
            'platform': store['platform'],
            'total_count': len(pending_reviews),
            'reviews': pending_reviews
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"답글 대기 목록 조회 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail="답글 대기 목록 조회 중 오류가 발생했습니다")