"""
리뷰 수집 서비스
각 플랫폼의 크롤러를 활용하여 리뷰를 수집하고 DB에 저장
"""
import logging
import asyncio
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import sys
import os

# 프로젝트 루트 경로를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from api.services.supabase_service import SupabaseService
from api.services.encryption import get_encryption_service

logger = logging.getLogger(__name__)


class ReviewCollectorService:
    def __init__(self, supabase_service: SupabaseService):
        """
        서비스 초기화
        
        Args:
            supabase_service: Supabase 서비스 인스턴스
        """
        self.supabase = supabase_service
        self.encryption = get_encryption_service()
        
    async def collect_reviews_for_store(self, store_code: str) -> Dict[str, Any]:
        """
        특정 매장의 리뷰 수집
        
        Args:
            store_code: 매장 코드
            
        Returns:
            dict: {success: bool, collected: int, errors: [], platform: str}
        """
        result = {
            'success': False,
            'collected': 0,
            'errors': [],
            'platform': '',
            'store_name': ''
        }
        
        try:
            # 매장 정보 조회
            store_info = await self._get_store_info(store_code)
            if not store_info:
                result['errors'].append(f"매장을 찾을 수 없습니다: {store_code}")
                return result
            
            result['platform'] = store_info['platform']
            result['store_name'] = store_info['store_name']
            
            # 날짜 범위 설정 (최근 30일)
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            # 플랫폼별 크롤러 선택
            platform = store_info['platform'].lower()
            if platform == 'baemin':
                collect_result = await self.collect_baemin_reviews(store_info, start_date, end_date)
            elif platform == 'coupang':
                collect_result = await self.collect_coupang_reviews(store_info, start_date, end_date)
            elif platform == 'yogiyo':
                collect_result = await self.collect_yogiyo_reviews(store_info, start_date, end_date)
            elif platform == 'naver':
                collect_result = await self.collect_naver_reviews(store_info, start_date, end_date)
            else:
                result['errors'].append(f"지원하지 않는 플랫폼: {store_info['platform']}")
                return result
            
            if collect_result.get('success'):
                result['success'] = True
                result['collected'] = collect_result.get('saved', 0)
                
                # 사용량 업데이트
                if result['collected'] > 0:
                    await self.supabase.update_usage_tracking(
                        store_info['owner_user_code'],
                        reviews_increment=result['collected']
                    )
            else:
                result['errors'].append(collect_result.get('error', '알 수 없는 오류'))
            
            logger.info(f"리뷰 수집 완료 - store: {store_code}, collected: {result['collected']}")
            
        except Exception as e:
            logger.error(f"리뷰 수집 실패 - store: {store_code}, error: {str(e)}")
            result['errors'].append(str(e))
            
        return result
    
    async def _get_store_info(self, store_code: str) -> Optional[Dict]:
        """매장 정보 조회"""
        try:
            # get_stores_by_user 대신 get_active_stores 사용
            stores = await self.supabase.get_active_stores()  # 모든 활성 매장 조회
            for store in stores:
                if store['store_code'] == store_code:
                    return store
            return None
        except Exception as e:
            logger.error(f"매장 정보 조회 실패: {str(e)}")
            return None
    
    async def collect_baemin_reviews(self, store_info: dict, start_date: str, end_date: str) -> dict:
        """배민 리뷰 수집"""
        try:
            logger.info(f"배민 리뷰 수집 시작 - 매장: {store_info['store_name']}")
            
            # BaeminSyncReviewCrawler 사용
            from api.crawlers.review_crawlers.baemin_sync_review_crawler import BaeminSyncReviewCrawler
            
            # 크롤러 초기화
            crawler = BaeminSyncReviewCrawler(headless=True)
            
            try:
                # 브라우저 시작
                crawler.start_browser()
                
                # 로그인
                decrypted_id = self.encryption.decrypt(store_info['platform_id'])
                decrypted_pw = self.encryption.decrypt(store_info['platform_pw'])
                
                login_success = crawler.login(decrypted_id, decrypted_pw)
                if not login_success:
                    logger.error("배민 로그인 실패")
                    return {"success": False, "error": "로그인 실패"}
                
                # 리뷰 수집
                reviews = crawler.get_reviews(
                    platform_code=store_info['platform_code'],
                    store_code=store_info['store_code'],
                    limit=50
                )
                
                # 리뷰 저장
                saved_count = 0
                for review in reviews:
                    # 이미 존재하는 리뷰인지 확인
                    existing = await self.supabase.check_review_exists(review['review_id'])
                    if not existing:
                        # 새 리뷰 저장
                        saved = await self.supabase.insert_review(review)
                        if saved:
                            saved_count += 1
                
                logger.info(f"배민 리뷰 수집 완료 - 수집: {len(reviews)}개, 저장: {saved_count}개")
                
                return {
                    "success": True,
                    "collected": len(reviews),
                    "saved": saved_count
                }
                
            finally:
                # 브라우저 종료
                crawler.close_browser()
                
        except Exception as e:
            logger.error(f"배민 리뷰 수집 실패: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def collect_coupang_reviews(self, store_info: dict, start_date: str, end_date: str) -> dict:
        """쿠팡이츠 리뷰 수집"""
        try:
            logger.info(f"쿠팡이츠 리뷰 수집 시작 - 매장: {store_info['store_name']}")
            
            from api.crawlers.review_crawlers.coupang_async_review_crawler import CoupangAsyncReviewCrawler
            
            crawler = CoupangAsyncReviewCrawler(headless=True)
            
            try:
                await crawler.start()
                
                # 로그인
                decrypted_id = self.encryption.decrypt(store_info['platform_id'])
                decrypted_pw = self.encryption.decrypt(store_info['platform_pw'])
                
                login_success = await crawler.login(decrypted_id, decrypted_pw)
                if not login_success:
                    return {"success": False, "error": "로그인 실패"}
                
                # 리뷰 수집
                reviews = await crawler.get_reviews(
                    store_id=store_info['platform_code'],
                    store_code=store_info['store_code']
                )
                
                # 리뷰 저장
                saved_count = 0
                for review in reviews:
                    existing = await self.supabase.check_review_exists(review['review_id'])
                    if not existing:
                        saved = await self.supabase.insert_review(review)
                        if saved:
                            saved_count += 1
                
                return {
                    "success": True,
                    "collected": len(reviews),
                    "saved": saved_count
                }
                
            finally:
                await crawler.close()
                
        except Exception as e:
            logger.error(f"쿠팡이츠 리뷰 수집 실패: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def collect_yogiyo_reviews(self, store_info: dict, start_date: str, end_date: str) -> dict:
        """요기요 리뷰 수집"""
        try:
            logger.info(f"요기요 리뷰 수집 시작 - 매장: {store_info['store_name']}")
            
            from api.crawlers.review_crawlers.yogiyo_async_review_crawler import YogiyoAsyncReviewCrawler
            
            crawler = YogiyoAsyncReviewCrawler(headless=True)
            
            try:
                await crawler.start()
                
                # 로그인
                decrypted_id = self.encryption.decrypt(store_info['platform_id'])
                decrypted_pw = self.encryption.decrypt(store_info['platform_pw'])
                
                login_success = await crawler.login(decrypted_id, decrypted_pw)
                if not login_success:
                    return {"success": False, "error": "로그인 실패"}
                
                # 리뷰 수집
                reviews = await crawler.get_reviews(
                    store_id=store_info['platform_code'],
                    store_code=store_info['store_code']
                )
                
                # 리뷰 저장
                saved_count = 0
                for review in reviews:
                    existing = await self.supabase.check_review_exists(review['review_id'])
                    if not existing:
                        saved = await self.supabase.insert_review(review)
                        if saved:
                            saved_count += 1
                
                return {
                    "success": True,
                    "collected": len(reviews),
                    "saved": saved_count
                }
                
            finally:
                await crawler.close()
                
        except Exception as e:
            logger.error(f"요기요 리뷰 수집 실패: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def collect_naver_reviews(self, store_info: dict, start_date: str, end_date: str) -> dict:
        """네이버 리뷰 수집"""
        logger.info(f"네이버 리뷰 수집은 아직 구현되지 않았습니다 - 매장: {store_info['store_name']}")
        return {"success": True, "collected": 0, "saved": 0}
    
    async def collect_all_stores_reviews(self) -> Dict[str, Any]:
        """모든 활성 매장의 리뷰를 병렬로 수집"""
        start_time = time.time()
        
        try:
            # 활성 매장 목록 조회
            active_stores = await self.supabase.get_active_stores()
            
            if not active_stores:
                logger.info("활성 매장이 없습니다.")
                return {"success": True, "message": "No active stores", "total": 0}
            
            logger.info(f"총 {len(active_stores)}개 매장 리뷰 수집 시작")
            
            # 동시 실행 제한 (10개)
            semaphore = asyncio.Semaphore(10)
            
            async def collect_with_limit(store):
                """세마포어로 동시 실행 제한"""
                async with semaphore:
                    return await self.collect_reviews_for_store(store['store_code'])
            
            # 모든 매장 병렬 처리
            tasks = [
                asyncio.create_task(collect_with_limit(store)) 
                for store in active_stores
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 집계
            success_count = 0
            fail_count = 0
            total_reviews = 0
            
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    fail_count += 1
                    logger.error(f"매장 {active_stores[idx]['store_code']} 수집 실패: {result}")
                elif isinstance(result, dict) and result.get('success'):
                    success_count += 1
                    total_reviews += result.get('collected', 0)
                else:
                    fail_count += 1
            
            elapsed_time = time.time() - start_time
            
            return {
                "success": True,
                "total_stores": len(active_stores),
                "success_count": success_count,
                "fail_count": fail_count,
                "total_new_reviews": total_reviews,
                "elapsed_time": f"{elapsed_time:.2f}초"
            }
            
        except Exception as e:
            logger.error(f"전체 리뷰 수집 중 오류: {str(e)}")
            return {"success": False, "error": str(e)}