"""
요기요 비동기 크롤러 테스트 실행 파일
Supabase 연동 버전
"""
import asyncio
import logging
import sys
import os
import json
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
from typing import Dict, List, Any, Optional

# .env 파일 로드
load_dotenv()

# 프로젝트 경로를 Python 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.insert(0, parent_dir)

# 절대 경로로 import
from api.crawlers.review_crawlers.yogiyo_async_review_crawler import YogiyoAsyncReviewCrawler

# 로깅 설정
log_dir = os.path.join(parent_dir, 'logs')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(log_dir, f'yogiyo_crawler_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'))
    ]
)

logger = logging.getLogger(__name__)

# Supabase 클라이언트 초기화
supabase: Client = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_ANON_KEY')
)

async def get_yogiyo_stores(store_code=None):
    """Supabase에서 요기요 매장 목록 가져오기"""
    try:
        query = supabase.table('platform_reply_rules').select(
            'store_code, store_name, platform_code, owner_user_code'
        ).eq('platform', 'yogiyo').eq('is_active', True)
        
        # 특정 매장만 조회
        if store_code:
            query = query.eq('store_code', store_code)
        
        response = query.execute()
        
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"매장 목록 조회 실패: {str(e)}")
        return []

async def save_reviews_to_db(reviews: List[Dict[str, Any]]) -> Dict[str, int]:
    """리뷰를 Supabase에 저장"""
    stats = {'saved': 0, 'duplicate': 0, 'failed': 0}
    
    for review in reviews:
        try:
            # 중복 확인
            existing = supabase.table('reviews').select('id').eq(
                'review_id', review['review_id']
            ).execute()
            
            if existing.data:
                stats['duplicate'] += 1
                logger.info(f"중복 리뷰 스킵: {review['review_id']}")
                continue
            
            # DB 스키마에 맞게 필드 조정
            review_data = {
                'review_id': review['review_id'],
                'platform': review['platform'],
                'platform_code': review['platform_code'],
                'store_code': review['store_code'],
                'review_name': review['review_name'],
                'rating': review['rating'],
                'review_content': review['review_content'],
                'review_date': review['review_date'],
                'ordered_menu': review['ordered_menu'],
                'review_images': review.get('review_images', []),
                'delivery_review': review.get('delivery_review', ''),
                'crawled_at': datetime.now().isoformat(),
                'is_deleted': False,
                'boss_reply_needed': False,
                'review_reason': None,
                'response_status': 'pending'
            }
            
            # 리뷰 저장
            response = supabase.table('reviews').insert(review_data).execute()
            if response.data:
                stats['saved'] += 1
                logger.info(f"리뷰 저장 성공: {review_data['review_id']}")
            else:
                stats['failed'] += 1
                logger.error(f"리뷰 저장 실패 (응답 없음): {review_data['review_id']}")
                
        except Exception as e:
            logger.error(f"리뷰 저장 실패: {str(e)}")
            if hasattr(e, 'response') and hasattr(e.response, 'json'):
                try:
                    error_detail = e.response.json()
                    logger.error(f"에러 상세: {error_detail}")
                except:
                    pass
            stats['failed'] += 1
    
    return stats

async def run_crawler_for_store(store: Dict[str, Any], headless: bool = True, debug: bool = False) -> Optional[Dict[str, Any]]:
    """특정 매장에 대해 크롤러 실행"""
    crawler = None
    try:
        store_code = store['store_code']
        platform_code = store['platform_code']
        store_name = store['store_name']
        
        if debug:
            print(f"\n크롤링 시작: {store_name}")
            print(f"Store Code: {store_code}")
            print(f"Platform Code: {platform_code}")
        
        # 크롤러 초기화
        crawler = YogiyoAsyncReviewCrawler(headless=headless)
        
        # 브라우저 시작
        await crawler.start_browser()
        
        # 로그인
        login_success = await crawler.login_with_store_code(store_code)
        if not login_success:
            logger.error(f"로그인 실패: {store_name}")
            return None
        
        # 매장 선택
        if not await crawler.select_store_by_platform_code(platform_code):
            logger.error(f"매장 선택 실패: {store_name}")
            return None
        
        # 리뷰 수집
        reviews = await crawler.get_reviews_with_pagination(
            platform_code=platform_code,
            store_code=store_code,
            limit=50
        )
        
        # DB 저장
        save_stats = await save_reviews_to_db(reviews)
        
        return {
            'store_name': store_name,
            'reviews': reviews,
            'save_stats': save_stats
        }
        
    except Exception as e:
        logger.error(f"크롤러 실행 오류 ({store.get('store_name', 'Unknown')}): {str(e)}")
        if debug:
            import traceback
            traceback.print_exc()
        return None
        
    finally:
        if crawler:
            await crawler.close_browser()

async def run_subprocess_mode(store_code: str):
    """subprocess 모드로 실행 (자동화용)"""
    try:
        # 매장 정보 가져오기
        stores = await get_yogiyo_stores(store_code)
        
        if not stores:
            result = {"success": False, "error": f"매장을 찾을 수 없음: {store_code}"}
            print(json.dumps(result))
            return
        
        store = stores[0]
        
        # 크롤러 실행
        result = await run_crawler_for_store(store, headless=True, debug=False)
        
        if result and result.get('save_stats'):
            stats = result['save_stats']
            output = {
                "success": True,
                "collected": len(result.get('reviews', [])),
                "saved": stats['saved']
            }
        else:
            output = {"success": False, "error": "크롤링 실패"}
        
        # JSON 결과 출력 (마지막 줄에)
        print(json.dumps(output))
        
    except Exception as e:
        output = {"success": False, "error": str(e)}
        print(json.dumps(output))

async def main():
    """메인 함수"""
    
    # subprocess 모드 확인
    if '--subprocess' in sys.argv:
        # store-code 파라미터 찾기
        try:
            idx = sys.argv.index('--store-code')
            store_code = sys.argv[idx + 1]
            await run_subprocess_mode(store_code)
            return
        except (ValueError, IndexError):
            print(json.dumps({"success": False, "error": "store-code 파라미터 없음"}))
            return
    
    # 기존 대화형 모드
    print("=== 요기요 리뷰 수집 시작 ===\n")
    
    try:
        # Supabase에서 요기요 매장 목록 가져오기
        stores = await get_yogiyo_stores()
        
        if not stores:
            print("Supabase에 등록된 요기요 매장이 없습니다.")
            return
        
        print(f"총 {len(stores)}개의 요기요 매장 발견\n")
        
        # 실행 모드 선택
        print("어떤 모드로 실행하시겠습니까?")
        print("1. 전체 매장 자동 실행 (headless)")
        print("2. 첫 번째 매장만 브라우저 표시하며 테스트")
        print("3. 특정 매장 선택하여 테스트")
        
        choice = input("\n선택 (1/2/3): ").strip()
        
        if choice == "2":
            # 첫 번째 매장만 테스트
            store = stores[0]
            print(f"\n테스트 매장: {store['store_name']}")
            
            result = await run_crawler_for_store(store, headless=False, debug=True)
            
            if result:
                print(f"\n크롤링 성공: {len(result.get('reviews', []))}개 리뷰 수집")
                if 'save_stats' in result:
                    stats = result['save_stats']
                    print(f"DB 저장 결과: 성공 {stats['saved']}개, 중복 {stats['duplicate']}개, 실패 {stats['failed']}개")
            else:
                print("\n크롤링 실패")
                
        elif choice == "3":
            # 매장 목록 표시
            print("\n=== 매장 목록 ===")
            for idx, store in enumerate(stores, 1):
                print(f"{idx}. {store['store_name']} (Platform Code: {store['platform_code']})")
            
            try:
                store_idx = int(input("\n테스트할 매장 번호: ")) - 1
                
                if 0 <= store_idx < len(stores):
                    store = stores[store_idx]
                    print(f"\n선택한 매장: {store['store_name']}")
                    
                    result = await run_crawler_for_store(store, headless=False, debug=True)
                    
                    if result:
                        print(f"\n크롤링 성공: {len(result.get('reviews', []))}개 리뷰 수집")
                        if 'save_stats' in result:
                            stats = result['save_stats']
                            print(f"DB 저장 결과: 성공 {stats['saved']}개, 중복 {stats['duplicate']}개, 실패 {stats['failed']}개")
                    else:
                        print("\n크롤링 실패")
                else:
                    print("잘못된 번호입니다.")
            except ValueError:
                print("올바른 숫자를 입력해주세요.")
                
        else:  # choice == "1" 또는 기타
            # 전체 실행
            print("\n전체 매장 자동 실행을 시작합니다...\n")
            
            total_reviews = 0
            total_saved = 0
            successful_stores = 0
            failed_stores = []
            
            for idx, store in enumerate(stores, 1):
                print(f"\n[{idx}/{len(stores)}] {store['store_name']} 처리 중...")
                
                result = await run_crawler_for_store(store, headless=True, debug=False)
                
                if result:
                    review_count = len(result.get('reviews', []))
                    print(f"  ✓ 크롤링 성공: {review_count}개 리뷰 수집")
                    
                    if 'save_stats' in result:
                        stats = result['save_stats']
                        print(f"  ✓ DB 저장: 성공 {stats['saved']}개, 중복 {stats['duplicate']}개, 실패 {stats['failed']}개")
                        total_saved += stats['saved']
                    
                    total_reviews += review_count
                    successful_stores += 1
                else:
                    print(f"  ✗ 크롤링 실패")
                    failed_stores.append(store['store_name'])
                
                # 매장 간 대기 시간 (서버 부하 방지)
                if idx < len(stores):
                    await asyncio.sleep(3)
            
            # 최종 결과 출력
            print("\n" + "=" * 50)
            print("=== 전체 수집 완료 ===")
            print("=" * 50)
            print(f"✓ 성공: {successful_stores}/{len(stores)} 매장")
            print(f"✓ 총 수집 리뷰: {total_reviews}개")
            print(f"✓ 총 저장 리뷰: {total_saved}개")
            
            if failed_stores:
                print(f"\n✗ 실패한 매장 ({len(failed_stores)}개):")
                for store_name in failed_stores:
                    print(f"  - {store_name}")
                    
    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n예기치 않은 오류: {e}")
        import traceback
        traceback.print_exc()

async def run_automated():
    """24시간 자동 실행용 함수"""
    while True:
        try:
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 자동 리뷰 수집 시작")
            
            # 매장 목록 가져오기
            stores = await get_yogiyo_stores()
            
            if stores:
                total_saved = 0
                
                for store in stores:
                    result = await run_crawler_for_store(store, headless=True, debug=False)
                    
                    if result and 'save_stats' in result:
                        total_saved += result['save_stats']['saved']
                    
                    # 매장 간 대기
                    await asyncio.sleep(5)
                
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 수집 완료: {total_saved}개 새 리뷰 저장")
            
            # 다음 실행까지 대기 (1시간)
            print("다음 실행까지 1시간 대기...")
            await asyncio.sleep(3600)
            
        except Exception as e:
            logger.error(f"자동 실행 오류: {str(e)}")
            await asyncio.sleep(300)  # 오류 시 5분 후 재시도

def print_usage():
    """사용법 출력"""
    print("""
요기요 리뷰 크롤러 사용법 (Supabase 연동):

1. .env 파일에 다음 환경변수가 설정되어 있어야 합니다:
   - SUPABASE_URL
   - SUPABASE_ANON_KEY
   - ENCRYPTION_KEY (선택사항)

2. Supabase의 platform_reply_rules 테이블에 요기요 매장 정보가 등록되어 있어야 합니다:
   - platform: 'yogiyo'
   - platform_id: 요기요 로그인 아이디
   - platform_pw: 요기요 로그인 비밀번호 (암호화 권장)
   - platform_code: 요기요 매장 ID

3. 실행 방법:
   python run_yogiyo_async_crawler.py          # 대화형 모드
   python run_yogiyo_async_crawler.py --auto   # 24시간 자동 모드
   python run_yogiyo_async_crawler.py --help   # 도움말

실행 모드:
   1. 전체 매장 자동 실행 (headless) - 모든 매장을 순차적으로 처리
   2. 첫 번째 매장만 테스트 - 브라우저를 표시하며 디버깅
   3. 특정 매장 선택 - 원하는 매장만 선택하여 테스트

주의사항:
- 네트워크 상태에 따라 시간이 걸릴 수 있습니다
- 브라우저가 자동으로 제어되므로 마우스나 키보드를 건드리지 마세요
- 24시간 모드는 매시간 자동으로 실행됩니다
""")

if __name__ == "__main__":
    # Windows 환경 설정
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # 명령줄 인자 확인
    if len(sys.argv) > 1:
        if sys.argv[1] == '--help':
            print_usage()
        elif sys.argv[1] == '--auto':
            # 24시간 자동 실행 모드
            print("24시간 자동 실행 모드를 시작합니다...")
            asyncio.run(run_automated())
        elif sys.argv[1] == '--subprocess':
            # subprocess 모드 (자동화용)
            asyncio.run(main())
        else:
            print("알 수 없는 옵션입니다. --help를 사용하세요.")
    else:
        # 대화형 모드
        asyncio.run(main())