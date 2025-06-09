"""
리뷰 데이터 업데이트 스크립트
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.services.supabase_service import SupabaseService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def update_review_data():
    """리뷰 데이터 업데이트"""
    supabase = SupabaseService()
    
    review_id = "baemin_2025060900005927"
    
    logger.info(f"리뷰 업데이트 시작: {review_id}")
    
    # 현재 리뷰 상태 확인
    review = await supabase.get_review_by_id(review_id)
    if not review:
        logger.error(f"리뷰를 찾을 수 없음: {review_id}")
        return
    
    logger.info(f"현재 상태:")
    logger.info(f"  - response_status: {review.get('response_status')}")
    logger.info(f"  - ai_response: {review.get('ai_response')}")
    logger.info(f"  - final_response: {review.get('final_response')}")
    
    # final_response 업데이트
    if not review.get('final_response') and not review.get('ai_response'):
        # 샘플 답글 설정
        sample_reply = "안녕하세요 보노보노님, 안녕하세요! 소중한 5점 리뷰 정말 감사드립니다. 닭다리살로 만든 저희 만족100% 완전닭강정을 맛있게 드셨다니 정말 기쁩니다. 고객님의 긍정적인 반응 덕분에 더욱 힘이 나네요! 앞으로도 맛있고 만족스러운 메뉴로 보답할 수 있도록 최선을 다하겠습니다. 다음에도 또 찾아주시면 더욱 맛있는 닭강정으로 보답할게요. 항상 건강하시고 행복한 하루 보내세요! 감사합니다!"
        
        success = await supabase.update_review_response(
            review_id,
            response_status='generated',
            final_response=sample_reply,
            response_method='ai_auto'
        )
        
        if success:
            logger.info("✓ 리뷰 업데이트 성공")
            logger.info(f"  - final_response 설정됨")
        else:
            logger.error("✗ 리뷰 업데이트 실패")
    else:
        logger.info("리뷰에 이미 답글이 있습니다")

if __name__ == "__main__":
    asyncio.run(update_review_data())
