"""
API 엔드포인트 테스트 스크립트
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.services.supabase_service import SupabaseService
from api.services.reply_posting_service import ReplyPostingService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_api_endpoints():
    """API 엔드포인트 테스트"""
    supabase = SupabaseService()
    
    # 테스트할 리뷰 ID
    review_id = "baemin_2025060900005927"
    
    logger.info(f"\n=== API 엔드포인트 테스트 시작 ===")
    logger.info(f"테스트 리뷰 ID: {review_id}")
    
    # 1. 리뷰 조회 테스트
    logger.info("\n1. 리뷰 조회 테스트")
    review = await supabase.get_review_by_id(review_id)
    if review:
        logger.info(f"✓ 리뷰 찾음")
        logger.info(f"  - store_code: {review.get('store_code')}")
        logger.info(f"  - platform: {review.get('platform')}")
        logger.info(f"  - rating: {review.get('rating')}")
        logger.info(f"  - response_status: {review.get('response_status')}")
        logger.info(f"  - ai_response 길이: {len(review.get('ai_response') or '')}")
        logger.info(f"  - final_response 길이: {len(review.get('final_response') or '')}")
    else:
        logger.error(f"✗ 리뷰를 찾을 수 없음: {review_id}")
        return
    
    # 2. 매장 정보 조회 테스트
    logger.info("\n2. 매장 정보 조회 테스트")
    store_code = review.get('store_code')
    if store_code:
        store_rules = await supabase.get_store_reply_rules(store_code)
        logger.info(f"✓ 매장 정보 찾음")
        logger.info(f"  - store_name: {store_rules.get('store_name')}")
        logger.info(f"  - platform: {store_rules.get('platform')}")
        logger.info(f"  - platform_code: {store_rules.get('platform_code')}")
    else:
        logger.error(f"✗ store_code가 없음")
    
    # 3. 답글 내용 확인
    logger.info("\n3. 답글 내용 확인")
    reply_content = review.get('final_response') or review.get('ai_response')
    if reply_content:
        logger.info(f"✓ 답글 내용 있음: {reply_content[:50]}...")
    else:
        logger.error(f"✗ 답글 내용이 없음")
    
    # 4. 답글 등록 서비스 테스트 (실제 등록은 하지 않음)
    logger.info("\n4. 답글 등록 서비스 확인")
    reply_service = ReplyPostingService(supabase)
    logger.info(f"✓ ReplyPostingService 생성 완료")
    
    # 5. 사용자 권한 확인 (TST001 사용자로 테스트)
    logger.info("\n5. 사용자 권한 확인")
    test_user_code = "TST001"  # 테스트 사용자
    if store_code:
        has_permission = await supabase.check_user_permission(
            test_user_code,
            store_code,
            'reply'
        )
        if has_permission:
            logger.info(f"✓ 사용자 {test_user_code}는 답글 작성 권한이 있음")
        else:
            logger.warning(f"✗ 사용자 {test_user_code}는 답글 작성 권한이 없음")
    
    logger.info("\n=== 테스트 완료 ===")

if __name__ == "__main__":
    asyncio.run(test_api_endpoints())
