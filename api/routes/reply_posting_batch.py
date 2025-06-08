"""
추가 답글 등록 API 엔드포인트들 (일괄 처리)
"""


@router.post("/batch/{store_code}/submit")
async def submit_batch_replies(
    store_code: str,
    background_tasks: BackgroundTasks,
    limit: int = Query(10, ge=1, le=50, description="한 번에 처리할 답글 수"),
    current_user: User = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    매장의 대기 중인 답글들을 일괄 등록
    
    - store_code: 매장 코드
    - limit: 한 번에 처리할 답글 수 (기본값: 10, 최대: 50)
    - 백그라운드에서 비동기로 처리됩니다
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
        
        # ReplyPostingService 초기화
        reply_service = ReplyPostingService(supabase)
        
        # 처리 대기 중인 답글 조회
        pending_reviews = await reply_service.get_pending_replies(
            store_code=store_code,
            limit=limit
        )
        
        if not pending_reviews:
            return {
                "success": True,
                "message": "처리할 답글이 없습니다",
                "store_code": store_code,
                "pending_count": 0
            }
        
        # 백그라운드에서 일괄 처리 시작
        background_tasks.add_task(
            reply_service.process_store_replies,
            store_code,
            current_user.user_code
        )
        
        return {
            "success": True,
            "message": f"{len(pending_reviews)}개의 답글 일괄 등록이 시작되었습니다",
            "store_code": store_code,
            "pending_count": len(pending_reviews),
            "processing_mode": "background",
            "estimated_time_minutes": len(pending_reviews) * 2  # 답글당 약 2분 예상
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"일괄 답글 등록 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch/all-stores/submit")
async def submit_all_stores_replies(
    background_tasks: BackgroundTasks,
    max_per_store: int = Query(5, ge=1, le=20, description="매장당 최대 처리 답글 수"),
    current_user: User = Depends(get_current_user),
    supabase: SupabaseService = Depends(get_supabase_service)
):
    """
    모든 매장의 답글 일괄 등록 (관리자 전용)
    
    - max_per_store: 매장당 최대 처리할 답글 수 (기본값: 5, 최대: 20)
    - 시스템 부하를 고려하여 매장당 처리량을 제한합니다
    """
    try:
        # 관리자 권한 확인
        if current_user.role not in ['admin', 'franchise']:
            raise HTTPException(status_code=403, detail="관리자 또는 프랜차이즈 권한이 필요합니다")
        
        # ReplyPostingService 초기화
        reply_service = ReplyPostingService(supabase)
        
        # 사용자가 접근 가능한 매장 목록 조회
        if current_user.role == 'admin':
            # 관리자는 모든 매장
            accessible_stores = await supabase.get_all_active_stores()
        else:
            # 프랜차이즈는 권한이 있는 매장만
            accessible_stores = await supabase.get_user_accessible_stores(current_user.user_code)
        
        if not accessible_stores:
            return {
                "success": True,
                "message": "처리할 매장이 없습니다",
                "processed_stores": 0
            }
        
        # 각 매장별 대기 답글 수 확인
        store_summary = []
        total_pending = 0
        
        for store in accessible_stores:
            pending_count = len(await reply_service.get_pending_replies(
                store_code=store['store_code'],
                limit=max_per_store
            ))
            
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
            "estimated_time_minutes": total_pending * 2  # 답글당 약 2분 예상
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"전체 매장 답글 등록 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
