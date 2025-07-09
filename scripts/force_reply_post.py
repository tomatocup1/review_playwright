"""
지연 없이 강제로 답글 등록하는 스크립트
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.supabase_service import get_supabase_service
from api.services.reply_posting_service import ReplyPostingService
from api.services.encryption import decrypt_password

async def force_post_replies():
    """지연 무시하고 강제 답글 등록"""
    print("=== 강제 답글 등록 시작 (지연 무시) ===")
    
    supabase = get_supabase_service()
    reply_service = ReplyPostingService(supabase)
    
    # 모든 ready_to_post 상태 리뷰 조회 (날짜 제한 없음)
    result = await supabase._execute_query(
        supabase.client.table('reviews')
        .select('*')
        .in_('response_status', ['ready_to_post', 'generated'])
        .order('review_date', desc=True)
        .limit(20)  # 최대 20개만
    )
    
    if not result.data:
        print("답글 등록 가능한 리뷰가 없습니다.")
        return
    
    print(f"\n답글 등록 가능한 리뷰 {len(result.data)}개 발견")
    
    # 플랫폼별 그룹핑
    platform_groups = {}
    for review in result.data:
        key = f"{review['platform']}_{review['platform_code']}"
        if key not in platform_groups:
            platform_groups[key] = []
        platform_groups[key].append(review)
    
    # 각 그룹별로 처리
    total_success = 0
    total_fail = 0
    
    for group_key, reviews in platform_groups.items():
        platform, platform_code = group_key.split('_', 1)
        print(f"\n{platform} ({platform_code}): {len(reviews)}개 리뷰 처리")
        
        # 매장 정보 조회
        store_code = reviews[0]['store_code']
        store_result = await supabase._execute_query(
            supabase.client.table('platform_reply_rules')
            .select('*')
            .eq('store_code', store_code)
            .single()
        )
        
        if store_result.data:
            store_info = store_result.data
            if store_info.get('platform_pw'):
                store_info['platform_pw'] = decrypt_password(store_info['platform_pw'])
            
            # 답글 등록 실행
            result = await reply_service.post_batch_replies_by_platform(
                platform=platform,
                platform_code=platform_code,
                user_code='FORCE_TEST',
                reviews=reviews,
                store_info=store_info
            )
            
            total_success += result.get('success_count', 0)
            total_fail += result.get('fail_count', 0)
    
    print(f"\n=== 전체 결과 ===")
    print(f"성공: {total_success}개")
    print(f"실패: {total_fail}개")

if __name__ == "__main__":
    asyncio.run(force_post_replies())