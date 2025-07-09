"""
배민 리뷰 수집을 위한 subprocess 전용 크롤러
asyncio 루프 외부에서 실행되어야 하는 동기식 크롤러
"""
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from api.crawlers.review_crawlers.baemin_sync_review_crawler import BaeminSyncReviewCrawler

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """메인 실행 함수"""
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "No data provided"}))
        sys.exit(1)
    
    try:
        # 인자로 받은 데이터 파싱
        crawler_data = json.loads(sys.argv[1])
        
        platform = crawler_data.get('platform')
        if platform != 'baemin':
            print(json.dumps({"success": False, "error": f"Unsupported platform: {platform}"}))
            sys.exit(1)
        
        # 크롤러 실행
        crawler = BaeminSyncReviewCrawler(headless=True)
        
        try:
            # 브라우저 시작
            crawler.start_browser()
            
            # 로그인
            login_success = crawler.login(
                crawler_data['platform_id'],
                crawler_data['platform_pw']
            )
            
            if not login_success:
                print(json.dumps({"success": False, "error": "Login failed"}))
                sys.exit(1)
            
            # 리뷰 수집
            reviews = crawler.get_reviews(
                crawler_data['platform_code'],
                crawler_data['store_code'],
                limit=50
            )
            
            # 결과 반환
            result = {
                "success": True,
                "reviews": reviews,
                "collected": len(reviews),
                "store_name": crawler_data['store_name']
            }
            
            print(json.dumps(result, ensure_ascii=False))
            
        finally:
            # 브라우저 종료
            crawler.close_browser()
            
    except Exception as e:
        logger.error(f"크롤러 실행 오류: {str(e)}")
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
