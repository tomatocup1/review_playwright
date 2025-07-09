"""
쿠팡이츠 비동기 크롤러 실행 스크립트
Supabase 연동 및 리뷰 수집
"""
import asyncio
import sys
import os
import json
from typing import Dict, List
from dotenv import load_dotenv
from datetime import datetime

# Windows 이벤트 루프 설정
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# 환경변수 로드
load_dotenv()

# Supabase 클라이언트 가져오기
sys.path.append(r"C:\Review_playwright")
from config.supabase_client import get_supabase_client
from api.services.encryption import decrypt_password
from api.crawlers.review_crawlers.coupang_async_review_crawler import CoupangAsyncReviewCrawler

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_coupang_stores(store_code=None):
    """Supabase에서 쿠팡이츠 매장 정보 가져오기"""
    logger.info("[DB] Supabase에서 쿠팡이츠 매장 정보 조회 중...")
    supabase = get_supabase_client()
    
    # 쿼리 빌드
    query = supabase.table('platform_reply_rules')\
        .select('*')\
        .eq('platform', 'coupang')\
        .eq('is_active', True)
    
    # 특정 매장만 조회
    if store_code:
        query = query.eq('store_code', store_code)
    
    response = query.execute()
    
    logger.info(f"[DB] {len(response.data)}개의 쿠팡이츠 매장 발견")
    
    # 비밀번호 복호화
    stores = response.data
    for store in stores:
        try:
            # 암호화된 비밀번호 복호화
            store['platform_pw_decrypted'] = decrypt_password(store['platform_pw'])
            logger.info(f"[복호화] 성공: {store['store_name']}")
        except Exception as e:
            logger.error(f"[복호화] 실패: {store['store_name']} - {e}")
            store['platform_pw_decrypted'] = None
    
    return stores


def save_reviews_to_supabase(store_info: Dict, reviews: List[Dict]) -> Dict[str, int]:
    """수집한 리뷰를 Supabase에 저장"""
    logger.info(f"\n[DB] {len(reviews)}개 리뷰 저장 시작...")
    
    supabase = get_supabase_client()
    
    # 저장 통계
    saved_count = 0
    failed_count = 0
    duplicate_count = 0
    
    for review in reviews:
        try:
            # 중복 체크
            existing = supabase.table('reviews').select('review_id').eq('review_id', review['review_id']).execute()
            
            if existing.data:
                logger.info(f"[DB] 중복 리뷰 스킵: {review['review_id']} - {review['review_name']}")
                duplicate_count += 1
                continue
            
            # DB에 맞게 데이터 정제
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
                'delivery_review': review['delivery_review'],
                'response_status': 'pending',
                'crawled_at': datetime.now().isoformat()
            }
            
            # review_images 처리
            if isinstance(review.get('review_images'), list):
                if review['review_images']:
                    review_data['review_images'] = review['review_images']
                else:
                    review_data['review_images'] = []
            else:
                review_data['review_images'] = []
            
            # 리뷰 저장
            result = supabase.table('reviews').insert(review_data).execute()
            
            if result.data:
                logger.info(f"[DB] 저장 성공: {review['review_id']} - {review['review_name']}")
                saved_count += 1
            else:
                logger.error(f"[DB] 저장 실패: {review['review_id']} - {review['review_name']}")
                failed_count += 1
                
        except Exception as e:
            logger.error(f"[DB] 저장 중 오류: {review['review_id']} - {str(e)}")
            failed_count += 1
    
    # 사용량 업데이트
    if saved_count > 0:
        try:
            supabase.rpc('update_usage', {
                'p_user_code': store_info['owner_user_code'],
                'p_reviews_increment': saved_count,
                'p_ai_api_calls_increment': 0,
                'p_web_api_calls_increment': 0,
                'p_manual_replies_increment': 0,
                'p_error_increment': 0
            }).execute()
        except Exception as e:
            logger.error(f"[DB] 사용량 업데이트 실패: {str(e)}")
    
    logger.info(f"\n[DB] 저장 완료:")
    logger.info(f"  - 성공: {saved_count}개")
    logger.info(f"  - 중복: {duplicate_count}개")
    logger.info(f"  - 실패: {failed_count}개")
    
    return {
        'saved': saved_count,
        'duplicate': duplicate_count,
        'failed': failed_count
    }


async def run_crawler_for_store(store_info: Dict, headless: bool = True):
    """특정 매장에 대해 크롤러 실행"""
    
    # 복호화된 비밀번호 확인
    if not store_info.get('platform_pw_decrypted'):
        logger.error(f"[오류] 비밀번호 복호화 실패: {store_info['store_name']}")
        return None
    
    logger.info(f"\n[크롤러] {store_info['store_name']} 크롤링 시작...")
    logger.info(f"[크롤러] 플랫폼 ID: {store_info['platform_id']}")
    logger.info(f"[크롤러] 플랫폼 코드: {store_info['platform_code']}")
    
    crawler = CoupangAsyncReviewCrawler(headless=headless)
    
    try:
        # 브라우저 시작
        await crawler.start_browser()
        logger.info("[크롤러] 브라우저 시작 완료")
        
        # 로그인
        login_result = await crawler.login(
            store_info['platform_id'],
            store_info['platform_pw_decrypted']
        )
        
        if not login_result:
            logger.error("[크롤러] 로그인 실패")
            return None
        
        logger.info("[크롤러] 로그인 성공")
        
        # 매장 선택
        if not await crawler.select_store(store_info['platform_code']):
            logger.error(f"[크롤러] 매장 선택 실패: {store_info['platform_code']}")
            return None
        
        # 리뷰 수집
        reviews = await crawler.get_reviews_with_pagination(
            platform_code=store_info['platform_code'],
            store_code=store_info['store_code'],
            store_name=store_info['store_name'],
            limit=50
        )
        
        logger.info(f"[크롤러] 수집된 리뷰 수: {len(reviews)}")
        
        # 리뷰 저장
        if reviews:
            save_stats = save_reviews_to_supabase(store_info, reviews)
            return {
                'store_name': store_info['store_name'],
                'platform_code': store_info['platform_code'],
                'reviews': reviews,
                'save_stats': save_stats
            }
        
        return None
        
    except Exception as e:
        logger.error(f"[크롤러] 오류 발생: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None
        
    finally:
        if not headless:
            input("\n브라우저를 닫으려면 Enter를 누르세요...")
        await crawler.close_browser()


async def run_subprocess_mode(store_code: str):
    """subprocess 모드로 실행 (자동화용)"""
    try:
        # 매장 정보 가져오기
        stores = get_coupang_stores(store_code)
        
        if not stores:
            result = {"success": False, "error": f"매장을 찾을 수 없음: {store_code}"}
            print(json.dumps(result))
            return
        
        store = stores[0]
        
        # 크롤러 실행
        result = await run_crawler_for_store(store, headless=True)
        
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
    print("=== 쿠팡이츠 리뷰 수집 시작 ===\n")
    
    try:
        # Supabase에서 쿠팡이츠 매장 목록 가져오기
        stores = get_coupang_stores()
        
        # 복호화 성공한 매장만 필터링
        valid_stores = [s for s in stores if s.get('platform_pw_decrypted')]
        
        print(f"\n총 {len(stores)}개의 쿠팡이츠 매장 중 {len(valid_stores)}개 사용 가능\n")
        
        if not valid_stores:
            print("사용 가능한 매장이 없습니다. 비밀번호 복호화를 확인하세요.")
            return
        
        # 테스트할 매장 선택
        print("어떤 모드로 실행하시겠습니까?")
        print("1. 전체 매장 자동 실행 (headless)")
        print("2. 첫 번째 매장만 브라우저 표시하며 테스트")
        print("3. 특정 매장 선택하여 테스트")
        
        choice = input("\n선택 (1/2/3): ").strip()
        
        if choice == "2":
            # 첫 번째 매장만 테스트
            store = valid_stores[0]
            print(f"\n테스트 매장: {store['store_name']}")
            
            result = await run_crawler_for_store(store, headless=False)
            
            if result:
                print(f"\n크롤링 성공: {len(result.get('reviews', []))}개 리뷰 수집")
                if 'save_stats' in result:
                    stats = result['save_stats']
                    print(f"DB 저장 결과: 성공 {stats['saved']}개, 중복 {stats['duplicate']}개, 실패 {stats['failed']}개")
            else:
                print("\n실패")
                
        elif choice == "3":
            # 매장 목록 표시
            print("\n=== 매장 목록 ===")
            for idx, store in enumerate(valid_stores, 1):
                print(f"{idx}. {store['store_name']} (코드: {store['platform_code']})")
            
            store_idx = int(input("\n테스트할 매장 번호: ")) - 1
            
            if 0 <= store_idx < len(valid_stores):
                store = valid_stores[store_idx]
                print(f"\n선택한 매장: {store['store_name']}")
                
                result = await run_crawler_for_store(store, headless=False)
                
                if result:
                    print(f"\n크롤링 성공: {len(result.get('reviews', []))}개 리뷰 수집")
                    if 'save_stats' in result:
                        stats = result['save_stats']
                        print(f"DB 저장 결과: 성공 {stats['saved']}개, 중복 {stats['duplicate']}개, 실패 {stats['failed']}개")
                else:
                    print("\n실패")
                    
        else:
            # 전체 실행
            total_reviews = 0
            total_saved = 0
            successful_stores = 0
            
            for idx, store in enumerate(valid_stores, 1):
                print(f"\n[{idx}/{len(valid_stores)}] {store['store_name']} 처리 중...")
                
                result = await run_crawler_for_store(store, headless=True)
                
                if result:
                    review_count = len(result.get('reviews', []))
                    print(f"  크롤링 성공: {review_count}개 리뷰 수집")
                    
                    if 'save_stats' in result:
                        stats = result['save_stats']
                        print(f"  DB 저장: 성공 {stats['saved']}개, 중복 {stats['duplicate']}개, 실패 {stats['failed']}개")
                        total_saved += stats['saved']
                    
                    total_reviews += review_count
                    successful_stores += 1
                else:
                    print(f"  실패")
            
            print("\n=== 수집 완료 ===")
            print(f"성공: {successful_stores}/{len(valid_stores)} 매장")
            print(f"총 수집 리뷰: {total_reviews}개")
            print(f"총 저장 리뷰: {total_saved}개")
            
    except Exception as e:
        print(f"\n예기치 않은 오류: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())