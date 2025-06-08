"""
리뷰 수집 직접 실행 테스트
asyncio 이벤트 루프를 올바르게 처리
"""
import asyncio
import sys
import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv

# Windows 이벤트 루프 정책 설정을 가장 먼저
if sys.platform == 'win32':
    # Windows에서는 ProactorEventLoop가 subprocess를 지원함
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# 프로젝트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.supabase_client import get_supabase_client
from api.crawlers.baemin_review_crawler import BaeminReviewCrawler

# 환경변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def test_review_crawler():
    """리뷰 크롤러 테스트"""
    
    # Supabase에서 매장 정보 가져오기
    supabase = get_supabase_client()
    
    # 활성 매장 조회
    response = supabase.table('platform_reply_rules')\
        .select('*')\
        .eq('is_active', True)\
        .eq('auto_reply_enabled', True)\
        .limit(1)\
        .execute()
    
    if not response.data:
        print("활성 매장이 없습니다.")
        return
    
    store_info = response.data[0]
    
    print(f"\n=== 매장 정보 ===")
    print(f"매장명: {store_info['store_name']}")
    print(f"플랫폼: {store_info['platform']}")
    print(f"매장 코드: {store_info['store_code']}")
    print(f"플랫폼 코드: {store_info['platform_code']}")
    
    if store_info['platform'] != 'baemin':
        print(f"{store_info['platform']} 플랫폼은 아직 지원하지 않습니다.")
        return
    
    # 크롤러 실행
    crawler = BaeminReviewCrawler(headless=False)  # 브라우저 보이게
    
    try:
        print("\n브라우저 시작 중...")
        await crawler.start()
        
        print("로그인 시도 중...")
        login_success = await crawler.login(
            store_info['platform_id'],
            store_info['platform_pw']
        )
        
        if not login_success:
            print("로그인 실패!")
            return
        
        print("로그인 성공!")
        
        print("\n리뷰 수집 중...")
        reviews = await crawler.get_reviews(
            store_info['platform_code'],
            store_info['store_code'],
            limit=10
        )
        
        print(f"\n수집된 리뷰: {len(reviews)}개")
        
        # 첫 3개 리뷰만 출력
        for i, review in enumerate(reviews[:3], 1):
            print(f"\n--- 리뷰 {i} ---")
            print(f"작성자: {review['review_name']}")
            print(f"별점: {review['rating']}점")
            print(f"내용: {review['review_content'][:50]}...")
            print(f"날짜: {review['review_date']}")
        
        # DB에 저장
        saved_count = 0
        duplicate_count = 0
        
        for review in reviews:
            # 중복 체크
            existing = supabase.table('reviews')\
                .select('review_id')\
                .eq('review_id', review['review_id'])\
                .execute()
            
            if existing.data:
                duplicate_count += 1
                continue
            
            # 저장
            try:
                # 필수 필드 추가
                review['crawled_at'] = datetime.now().isoformat()
                review['response_status'] = 'pending'
                review['boss_reply_needed'] = True
                
                # JSON 필드 변환
                if isinstance(review.get('review_images'), list):
                    review['review_images'] = json.dumps(review['review_images'], ensure_ascii=False)
                
                supabase.table('reviews').insert(review).execute()
                saved_count += 1
                
            except Exception as e:
                logger.error(f"리뷰 저장 실패: {e}")
        
        print(f"\n=== 저장 결과 ===")
        print(f"새로 저장: {saved_count}개")
        print(f"중복: {duplicate_count}개")
        
    except Exception as e:
        logger.error(f"크롤링 실패: {e}", exc_info=True)
        
    finally:
        print("\n브라우저 종료 중...")
        await crawler.close()
        print("완료!")


def main():
    """메인 함수"""
    # 새로운 이벤트 루프 생성 및 실행
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(test_review_crawler())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
