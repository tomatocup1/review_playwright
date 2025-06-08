"""
리뷰 수집 테스트 - subprocess 방식
"""
import sys
import os
import json
import subprocess
from datetime import datetime
from dotenv import load_dotenv
import logging

# 프로젝트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.supabase_client import get_supabase_client

# 환경변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_crawler_subprocess(store_info):
    """subprocess로 크롤러 실행"""
    
    # 크롤러 스크립트 생성
    crawler_script = f"""
import asyncio
import sys
import os
import json

sys.path.append(r'{os.path.dirname(os.path.abspath(__file__))}')

from api.crawlers.baemin_review_crawler import BaeminReviewCrawler

async def main():
    crawler = BaeminReviewCrawler(headless=False)
    try:
        await crawler.start()
        
        # 로그인
        login_success = await crawler.login(
            '{store_info['platform_id']}',
            '{store_info['platform_pw']}'
        )
        
        if not login_success:
            print(json.dumps({{'success': False, 'error': '로그인 실패'}}))
            return
        
        # 리뷰 수집
        reviews = await crawler.get_reviews(
            '{store_info['platform_code']}',
            '{store_info['store_code']}',
            limit=10
        )
        
        result = {{
            'success': True,
            'reviews': reviews
        }}
        
        print(json.dumps(result, ensure_ascii=False))
        
    except Exception as e:
        print(json.dumps({{'success': False, 'error': str(e)}}))
    finally:
        await crawler.close()

if __name__ == '__main__':
    asyncio.run(main())
"""
    
    # 임시 파일에 스크립트 저장
    script_path = os.path.join(os.path.dirname(__file__), 'temp_crawler.py')
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(crawler_script)
    
    try:
        # subprocess로 실행
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        if result.stdout:
            return json.loads(result.stdout)
        else:
            return {'success': False, 'error': result.stderr}
            
    finally:
        # 임시 파일 삭제
        if os.path.exists(script_path):
            os.remove(script_path)


def main():
    """메인 실행 함수"""
    
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
    
    if store_info['platform'] == 'baemin':
        print("\n크롤러 실행 중...")
        result = run_crawler_subprocess(store_info)
        
        if result['success']:
            reviews = result.get('reviews', [])
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
                    if isinstance(review.get('ordered_menu'), str):
                        review['ordered_menu'] = review['ordered_menu']
                    
                    supabase.table('reviews').insert(review).execute()
                    saved_count += 1
                except Exception as e:
                    logger.error(f"리뷰 저장 실패: {e}")
            
            print(f"\n=== 저장 결과 ===")
            print(f"새로 저장: {saved_count}개")
            print(f"중복: {duplicate_count}개")
        else:
            print(f"크롤링 실패: {result.get('error')}")
    else:
        print(f"{store_info['platform']} 플랫폼은 아직 지원하지 않습니다.")


if __name__ == "__main__":
    main()
