"""
SupabaseService 확장 메서드들 (Step 4용)

ReplyPostingService에서 필요한 추가 메서드들을 구현합니다.
실제 프로젝트에서는 이들을 SupabaseService 클래스에 직접 추가해야 합니다.
"""

# 다음 메서드들을 api/services/supabase_service.py의 SupabaseService 클래스에 추가하세요:

async def get_all_active_stores(self):
    """모든 활성 매장 목록 조회"""
    try:
        response = await self._execute_query(
            self.client.table('platform_reply_rules')
            .select('store_code, store_name, platform, platform_code, is_active')
            .eq('is_active', True)
        )
        return response.data or []
    except Exception as e:
        self.logger.error(f"활성 매장 조회 오류: {e}")
        return []

async def get_user_accessible_stores(self, user_code: str):
    """사용자가 접근 가능한 매장 목록 조회"""
    try:
        # 소유한 매장들
        owned_stores = await self._execute_query(
            self.client.table('platform_reply_rules')
            .select('store_code, store_name, platform, platform_code, is_active')
            .eq('owner_user_code', user_code)
            .eq('is_active', True)
        )
        
        # 권한이 부여된 매장들
        permitted_stores = await self._execute_query(
            self.client.table('user_store_permissions')
            .select('store_code, platform_reply_rules(store_name, platform, platform_code, is_active)')
            .eq('user_code', user_code)
            .eq('is_active', True)
        )
        
        # 결합하여 반환
        all_stores = (owned_stores.data or []) + [p['platform_reply_rules'] for p in (permitted_stores.data or [])]
        return [store for store in all_stores if store.get('is_active')]
        
    except Exception as e:
        self.logger.error(f"사용자 접근 가능 매장 조회 오류: {e}")
        return []

async def get_store_reply_count(self, store_code: str, status: str):
    """매장별 답글 상태별 개수 조회"""
    try:
        response = await self._execute_query(
            self.client.table('reviews')
            .select('id', count='exact')
            .eq('store_code', store_code)
            .eq('response_status', status)
        )
        return response.count or 0
    except Exception as e:
        self.logger.error(f"매장 답글 개수 조회 오류: {e}")
        return 0

async def get_reply_generation_history(self, review_id: str):
    """답글 생성 이력 조회"""
    try:
        response = await self._execute_query(
            self.client.table('reply_generation_history')
            .select('*')
            .eq('review_id', review_id)
            .order('created_at', desc=True)
        )
        return response.data or []
    except Exception as e:
        self.logger.error(f"답글 생성 이력 조회 오류: {e}")
        return []

async def get_store_by_code(self, store_code: str):
    """매장 코드로 매장 정보 조회"""
    try:
        response = await self._execute_query(
            self.client.table('platform_reply_rules')
            .select('*')
            .eq('store_code', store_code)
            .single()
        )
        return response.data
    except Exception as e:
        self.logger.error(f"매장 정보 조회 오류: {e}")
        return None

async def get_reviews_by_store(self, store_code: str, status=None, rating=None, limit=20, offset=0):
    """매장별 리뷰 조회 (다중 상태 지원)"""
    try:
        query = self.client.table('reviews').select('*').eq('store_code', store_code)
        
        if status:
            if isinstance(status, list):
                query = query.in_('response_status', status)
            else:
                query = query.eq('response_status', status)
        
        if rating:
            query = query.eq('rating', rating)
            
        query = query.order('created_at', desc=True).limit(limit).offset(offset)
        
        response = await self._execute_query(query)
        return response.data or []
    except Exception as e:
        self.logger.error(f"매장별 리뷰 조회 오류: {e}")
        return []

async def save_reply_generation_history(self, review_id: str, user_code: str, generation_type: str, 
                                      prompt_used: str, model_version: str, generated_content: str,
                                      quality_score: float, processing_time_ms: int, token_usage: int,
                                      is_selected: bool):
    """답글 생성 이력 저장"""
    try:
        response = await self._execute_query(
            self.client.table('reply_generation_history')
            .insert({
                'review_id': review_id,
                'user_code': user_code,
                'generation_type': generation_type,
                'prompt_used': prompt_used,
                'model_version': model_version,
                'generated_content': generated_content,
                'quality_score': quality_score,
                'processing_time_ms': processing_time_ms,
                'token_usage': token_usage,
                'is_selected': is_selected
            })
        )
        return response.data[0] if response.data else None
    except Exception as e:
        self.logger.error(f"답글 생성 이력 저장 오류: {e}")
        return None

# 추가로 필요한 업데이트된 메서드들

async def update_review_status(self, review_id: str, status: str, reply_content: str = None, 
                             reply_type: str = None, reply_by: str = None, 
                             final_response: str = None, error_message: str = None):
    """리뷰 상태 업데이트 (확장 버전)"""
    try:
        update_data = {
            'response_status': status,
            'updated_at': 'now()'
        }
        
        if reply_content:
            update_data['ai_response'] = reply_content
        if reply_type:
            update_data['response_method'] = reply_type
        if reply_by:
            update_data['response_by'] = reply_by
        if final_response:
            update_data['final_response'] = final_response
        if error_message:
            update_data['error_message'] = error_message
        if status == 'posted':
            update_data['response_at'] = 'now()'
            
        response = await self._execute_query(
            self.client.table('reviews')
            .update(update_data)
            .eq('review_id', review_id)
        )
        return response.data[0] if response.data else None
    except Exception as e:
        self.logger.error(f"리뷰 상태 업데이트 오류: {e}")
        return None
