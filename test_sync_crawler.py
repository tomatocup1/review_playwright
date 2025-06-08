"""
리뷰 수집 테스트 - 동기 방식
"""
import sys
import os
from datetime import datetime
from dotenv import load_dotenv
import logging

# 프로젝트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.supabase_client import get_supabase_client
from api.crawlers.baemin_sync_crawler import BaeminSyncCrawler

# 환경변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_sync_crawler():
    """동기 방식으로 크롤러 테스트"""
    
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
    
    # 크롤러 실행
    if store_info['platform'] == 'baemin':
        crawler = BaeminSyncCrawler(headless=False)  # 브라우저 보이게
        
        try:
            # 브라우저 시작
            crawler.start_browser()
            
            # 로그인
            print("\n로그인 시도 중...")
            login_success = crawler.login(
                store_info['platform_id'],
                store_info['platform_pw']
            )
            
            if not login_success:
                print("로그인 실패!")
                return
            
            print("로그인 성공!")
            
            # 리뷰 수집
            print("\n리뷰 수집 중...")
            reviews = crawler.get_reviews(
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
                
            # DB에 저장 (중복 체크)
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
                    # 날짜 형식 변환
                    review['review_date'] = datetime.now().strftime('%Y-%m-%d')
                    review['crawled_at'] = datetime.now().isoformat()
                    review['response_status'] = 'pending'
                    review['boss_reply_needed'] = True
                    
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
            crawler.close_browser()
    else:
        print(f"{store_info['platform']} 플랫폼은 아직 지원하지 않습니다.")


if __name__ == "__main__":
    test_sync_crawler()
