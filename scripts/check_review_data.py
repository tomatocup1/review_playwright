"""
리뷰 데이터 확인 스크립트
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.services.supabase_service import SupabaseService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_review_data():
    """리뷰 데이터 확인"""
    supabase = SupabaseService()
    
    # 1. 특정 리뷰 ID로 조회
    review_ids = [
        "baemin_2025060800592092",
        "baemin_2025060900005927"
    ]
    
    for review_id in review_ids:
        logger.info(f"\n리뷰 조회 시작: {review_id}")
        review = await supabase.get_review_by_id(review_id)
        if review:
            logger.info(f"리뷰 찾음: {review}")
        else:
            logger.warning(f"리뷰를 찾을 수 없음: {review_id}")
    
    # 2. 모든 리뷰 조회 (최근 10개)
    logger.info("\n최근 리뷰 10개 조회...")
    try:
        response = await supabase._execute_query(
            supabase.client.table('reviews')
            .select('review_id, store_code, rating, response_status, created_at')
            .order('created_at', desc=True)
            .limit(10)
        )
        
        if response.data:
            logger.info("최근 리뷰 목록:")
            for r in response.data:
                logger.info(f"  - {r['review_id']} (store: {r.get('store_code', 'N/A')}, rating: {r.get('rating', 'N/A')}, status: {r.get('response_status', 'N/A')}, created: {r.get('created_at', 'N/A')})")
        else:
            logger.warning("리뷰 데이터가 없습니다.")
            
        # 3. 전체 리뷰 개수 확인
        response = await supabase._execute_query(
            supabase.client.table('reviews')
            .select('count', count='exact')
        )
        logger.info(f"\n전체 리뷰 개수: {response.count}")
        
    except Exception as e:
        logger.error(f"리뷰 조회 오류: {e}")

if __name__ == "__main__":
    asyncio.run(check_review_data())
