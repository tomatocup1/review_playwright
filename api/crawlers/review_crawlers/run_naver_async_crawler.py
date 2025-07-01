import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime
import logging
import subprocess
import threading

# 프로젝트 루트 경로를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from api.crawlers.naver_crawler import NaverCrawler
from config.supabase_client import get_supabase_client
from api.services.encryption import encrypt_password, decrypt_password

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(project_root / 'logs' / f'naver_review_crawler_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def crawl_naver_reviews():
    """네이버 스마트플레이스 리뷰 크롤링"""
    supabase = get_supabase_client()
    
    try:
        # 활성화된 네이버 매장 목록 조회
        response = supabase.table('platform_reply_rules')\
            .select('*')\
            .eq('platform', 'naver')\
            .eq('is_active', True)\
            .eq('auto_reply_enabled', True)\
            .execute()
        
        stores = response.data if response.data else []
        
        if not stores:
            logger.info("활성화된 네이버 매장이 없습니다.")
            return
        
        logger.info(f"총 {len(stores)}개의 네이버 매장에서 리뷰를 수집합니다.")
        
        # NaverCrawler를 컨텍스트 매니저로 사용
        async with NaverCrawler(headless=False) as crawler:
            # 첫 번째 매장으로 로그인
            first_store = stores[0]
            platform_id = first_store['platform_id']
            platform_pw = decrypt_password(first_store['platform_pw'])
            
            # 로그인 - page 인자 추가
            login_success = await crawler.login(crawler.page, platform_id, platform_pw)
            if not login_success:
                logger.error(f"네이버 로그인 실패: {platform_id}")
                return
            
            # 각 매장별로 리뷰 크롤링
            for store in stores:
                try:
                    store_code = store['store_code']
                    platform_code = store['platform_code']
                    
                    # 다른 계정인 경우 재로그인
                    if store['platform_id'] != platform_id:
                        platform_id = store['platform_id']
                        platform_pw = decrypt_password(store['platform_pw'])
                        
                        # 로그아웃 후 재로그인
                        await crawler.logout()
                        login_success = await crawler.login(crawler.page, platform_id, platform_pw)
                        if not login_success:
                            logger.error(f"네이버 로그인 실패: {platform_id}")
                            continue
                    
                    logger.info(f"\n{'='*50}")
                    logger.info(f"매장: {store['store_name']} (코드: {store_code})")
                    logger.info(f"플랫폼 코드: {platform_code}")
                    
                    # 리뷰 크롤링
                    reviews = await crawler.crawl_reviews(crawler.page, platform_code, store_code)
                    logger.info(f"{len(reviews)}개의 리뷰를 크롤링했습니다.")
                    
                    # DB 저장
                    saved_count = 0
                    for review in reviews:
                        try:
                            # 중복 확인
                            existing = supabase.table('reviews').select('id').eq('review_id', review['review_id']).execute()

                            if existing.data:
                                logger.info(f"이미 존재하는 리뷰: {review['review_id']}")
                                continue

                            # store_code 추가 부분 삭제 (이미 파서에서 처리됨)
                            # review['store_code'] = store_code  # 이 줄 삭제

                            # 리뷰 저장
                            supabase.table('reviews').insert(review).execute()
                            saved_count += 1
                            
                        except Exception as e:
                            logger.error(f"리뷰 저장 중 오류: {str(e)}")
                            continue
                    
                    logger.info(f"{saved_count}개의 새로운 리뷰를 저장했습니다.")
                    
                    # 매장별 크롤링 간격
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    logger.error(f"매장 {store['store_name']} 크롤링 중 오류: {str(e)}")
                    continue
        
    except Exception as e:
        logger.error(f"네이버 리뷰 크롤링 중 오류: {str(e)}")
    
    finally:
        logger.info("네이버 리뷰 크롤링 완료")

def run_crawler_in_thread():
    """별도 스레드에서 크롤러 실행"""
    # 새로운 이벤트 루프 생성
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(crawl_naver_reviews())
    finally:
        loop.close()

if __name__ == "__main__":
    if sys.platform == 'win32':
        # Windows에서는 ProactorEventLoop 사용 (기본값)
        # SelectorEventLoop를 설정하지 않음
        asyncio.run(crawl_naver_reviews())
    else:
        # Unix/Linux/Mac에서는 기본 방식 사용
        asyncio.run(crawl_naver_reviews())