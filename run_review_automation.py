"""
리뷰 수집 직접 실행 스크립트
실제 Supabase 데이터를 사용하여 리뷰 수집
"""
import asyncio
import logging
import sys
import os
from datetime import datetime
from dotenv import load_dotenv
import nest_asyncio

# Windows asyncio 이벤트 루프 문제 해결
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# asyncio 중첩 실행 허용
nest_asyncio.apply()

# 프로젝트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.services.supabase_service import SupabaseService
from api.services.review_collector_service import ReviewCollectorService

# 환경변수 로드
load_dotenv()

# 로깅 설정
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, f'review_collector_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


async def collect_single_store(store_code: str):
    """특정 매장의 리뷰 수집"""
    logger.info(f"=== 리뷰 수집 시작: {store_code} ===")
    
    try:
        # 서비스 초기화
        supabase_service = SupabaseService()
        collector = ReviewCollectorService(supabase_service)
        
        # 리뷰 수집 실행
        result = await collector.collect_reviews_for_store(store_code)
        
        # 결과 출력
        logger.info("=== 리뷰 수집 결과 ===")
        logger.info(f"성공 여부: {result['success']}")
        logger.info(f"플랫폼: {result['platform']}")
        logger.info(f"매장명: {result['store_name']}")
        logger.info(f"수집된 리뷰: {result['collected']}개")
        
        if 'duplicates' in result:
            logger.info(f"중복 리뷰: {result['duplicates']}개")
        
        if result['errors']:
            logger.error(f"오류 발생: {result['errors']}")
            
        return result
        
    except Exception as e:
        logger.error(f"리뷰 수집 중 오류 발생: {e}", exc_info=True)
        return None


async def collect_all_active_stores():
    """모든 활성 매장의 리뷰 수집"""
    logger.info("=== 전체 매장 리뷰 수집 시작 ===")
    
    try:
        # 서비스 초기화
        supabase_service = SupabaseService()
        collector = ReviewCollectorService(supabase_service)
        
        # 전체 수집 실행
        result = await collector.collect_all_stores_reviews()
        
        # 결과 출력
        logger.info("=== 전체 리뷰 수집 결과 ===")
        logger.info(f"전체 매장 수: {result['total_stores']}")
        logger.info(f"성공한 매장: {result['successful_stores']}")
        logger.info(f"실패한 매장: {result['failed_stores']}")
        logger.info(f"총 수집된 리뷰: {result['total_collected']}")
        
        if result['errors']:
            logger.error("오류 목록:")
            for error in result['errors']:
                logger.error(f"  - {error}")
                
        return result
        
    except Exception as e:
        logger.error(f"전체 수집 중 오류 발생: {e}", exc_info=True)
        return None


async def list_available_stores():
    """수집 가능한 매장 목록 표시"""
    try:
        supabase_service = SupabaseService()
        
        # 활성 매장 조회
        stores = await supabase_service.get_active_stores()
        
        print("\n=== 수집 가능한 매장 목록 ===")
        for i, store in enumerate(stores, 1):
            print(f"{i}. {store['store_name']} ({store['platform']}) - 코드: {store['store_code']}")
            
        return stores
        
    except Exception as e:
        logger.error(f"매장 목록 조회 실패: {e}")
        return []


def main():
    """메인 실행 함수"""
    print("\n리뷰 수집 프로그램")
    print("=" * 50)
    
    while True:
        print("\n1. 특정 매장 리뷰 수집")
        print("2. 전체 활성 매장 리뷰 수집")
        print("3. 수집 가능한 매장 목록 보기")
        print("4. 종료")
        
        choice = input("\n선택하세요 (1-4): ")
        
        if choice == '1':
            # 특정 매장 수집
            store_code = input("매장 코드를 입력하세요: ").strip()
            if store_code:
                asyncio.run(collect_single_store(store_code))
            else:
                print("매장 코드를 입력해주세요.")
                
        elif choice == '2':
            # 전체 매장 수집
            confirm = input("전체 매장 리뷰를 수집하시겠습니까? (y/n): ")
            if confirm.lower() == 'y':
                asyncio.run(collect_all_active_stores())
                
        elif choice == '3':
            # 매장 목록 표시
            asyncio.run(list_available_stores())
            
        elif choice == '4':
            print("프로그램을 종료합니다.")
            break
            
        else:
            print("잘못된 선택입니다.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n프로그램이 중단되었습니다.")
    except Exception as e:
        logger.error(f"프로그램 오류: {e}", exc_info=True)