"""
배민 크롤러 테스트 스크립트
"""
import asyncio
import logging
from pathlib import Path
import sys
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from crawler.baemin import BaeminCrawler
from dotenv import load_dotenv
import os

# 환경변수 로드
load_dotenv()

# 로깅 설정
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(
            log_dir / f"baemin_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            encoding='utf-8'
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


async def test_baemin_crawler():
    """배민 크롤러 테스트"""
    
    # 테스트용 매장 설정
    store_config = {
        'store_code': 'TEST001',
        'platform_id': input("배민 로그인 ID: "),
        'platform_pw': input("배민 로그인 PW: "),
        'platform_code': input("플랫폼 매장 코드: "),
        'store_name': '테스트 매장'
    }
    
    crawler = BaeminCrawler(store_config)
    
    try:
        # 1. 브라우저 초기화
        logger.info("브라우저 초기화 중...")
        await crawler.initialize()
        
        # 2. 로그인
        logger.info("로그인 시도 중...")
        login_success = await crawler.login()
        
        if not login_success:
            logger.error("로그인 실패")
            return
        
        logger.info("로그인 성공")
        
        # 3. 리뷰 페이지로 이동
        logger.info("리뷰 페이지로 이동 중...")
        nav_success = await crawler.navigate_to_reviews(store_config['platform_code'])
        
        if not nav_success:
            logger.error("리뷰 페이지 이동 실패")
            return
        
        # 4. 리뷰 목록 가져오기
        logger.info("리뷰 목록 가져오는 중...")
        reviews = await crawler.get_reviews()
        
        logger.info(f"총 {len(reviews)}개 리뷰 발견")
        
        # 리뷰 정보 출력
        for i, review in enumerate(reviews[:5]):  # 처음 5개만 출력
            logger.info(f"\n리뷰 {i+1}:")
            logger.info(f"  작성자: {review['author']}")
            logger.info(f"  별점: {review['rating']}점")
            logger.info(f"  내용: {review['review_text'][:50]}...")
            logger.info(f"  날짜: {review['review_date']}")
            logger.info(f"  주문메뉴: {review['order_menu']}")
        
        # 5. 테스트 답글 등록 (실제로 등록하지 않음)
        if reviews:
            test_review = reviews[0]
            logger.info(f"\n첫 번째 리뷰에 답글 등록 테스트")
            logger.info(f"리뷰 작성자: {test_review['author']}")
            logger.info(f"리뷰 내용: {test_review['review_text'][:100]}...")
            
            # 실제 답글 등록은 주석 처리
            # test_reply = "테스트 답글입니다. 감사합니다!"
            # success, prohibited_words = await crawler.post_reply(test_review, test_reply)
            # logger.info(f"답글 등록 결과: {success}")
        
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {str(e)}")
        await crawler.save_screenshot("error")
    
    finally:
        # 브라우저 종료
        logger.info("브라우저 종료 중...")
        await crawler.close()
        logger.info("테스트 완료")


if __name__ == "__main__":
    asyncio.run(test_baemin_crawler())
