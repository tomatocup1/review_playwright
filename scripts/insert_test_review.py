"""
테스트 리뷰 데이터 삽입 스크립트
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.services.supabase_service import SupabaseService
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def insert_test_reviews():
    """테스트 리뷰 데이터 삽입"""
    supabase = SupabaseService()
    
    test_reviews = [
        {
            'review_id': 'baemin_2025060800592092',
            'store_code': 'TST_STORE001',
            'platform': 'baemin',
            'platform_code': 'shop_test_001',
            'review_name': '테스트고객1',
            'rating': 5,
            'review_content': '정말 맛있었어요! 배달도 빠르고 음식도 따뜻했습니다.',
            'ordered_menu': '치킨세트, 콜라',
            'delivery_review': '빠름',
            'review_date': datetime.now().date().isoformat(),
            'response_status': 'generated',
            'ai_response': '소중한 리뷰 감사합니다! 앞으로도 맛있는 음식으로 보답하겠습니다.',
            'boss_reply_needed': False,
            'is_deleted': False,
            'created_at': datetime.now().isoformat()
        },
        {
            'review_id': 'baemin_2025060900005927',
            'store_code': 'TST_STORE001',
            'platform': 'baemin',
            'platform_code': 'shop_test_001',
            'review_name': '보노보노',
            'rating': 5,
            'review_content': '닭다리살로 만든 닭강정이 정말 맛있어요! 양도 많고 배달도 빨라서 좋았습니다.',
            'ordered_menu': '닭강정, 치킨무',
            'delivery_review': '빠름',
            'review_date': datetime.now().date().isoformat(),
            'response_status': 'generated',
            'ai_response': '안녕하세요 보노보노님, 안녕하세요! 소중한 5점 리뷰 정말 감사드립니다. 닭다리살로 만든 닭강정을 맛있게 드셨다니 정말 기쁩니다. 앞으로도 더욱 맛있는 닭강정으로 보답할게요. 항상 건강하시고 행복한 하루 보내세요! 감사합니다!',
            'boss_reply_needed': False,
            'is_deleted': False,
            'created_at': datetime.now().isoformat()
        }
    ]
    
    for review in test_reviews:
        try:
            logger.info(f"테스트 리뷰 삽입 시작: {review['review_id']}")
            
            # 이미 존재하는지 확인
            existing = await supabase.get_review_by_id(review['review_id'])
            if existing:
                logger.info(f"리뷰가 이미 존재합니다: {review['review_id']}")
                # 상태만 업데이트
                await supabase.update_review_response(
                    review['review_id'],
                    response_status='generated',
                    ai_response=review['ai_response']
                )
                logger.info(f"리뷰 상태 업데이트 완료: {review['review_id']}")
            else:
                # 새로 삽입
                response = await supabase._execute_query(
                    supabase.client.table('reviews').insert(review)
                )
                
                if response.data:
                    logger.info(f"테스트 리뷰 삽입 성공: {review['review_id']}")
                else:
                    logger.error(f"테스트 리뷰 삽입 실패: {review['review_id']}")
        except Exception as e:
            logger.error(f"테스트 리뷰 삽입 오류 ({review['review_id']}): {e}")

if __name__ == "__main__":
    asyncio.run(insert_test_reviews())
