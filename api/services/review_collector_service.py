"""
리뷰 수집 서비스
각 플랫폼의 크롤러를 활용하여 리뷰를 수집하고 DB에 저장
"""
import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
import sys
import os

# 프로젝트 루트 경로를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from api.services.supabase_service import SupabaseService
from api.crawlers.review_crawlers.baemin_review_crawler import BaeminReviewCrawler  # 파일명 확인
from api.crawlers.review_parsers.baemin_review_parser import BaeminReviewParser

logger = logging.getLogger(__name__)


class ReviewCollectorService:
    def __init__(self, supabase_service: SupabaseService):
        """
        서비스 초기화
        
        Args:
            supabase_service: Supabase 서비스 인스턴스
        """
        self.supabase = supabase_service
        self.baemin_crawler = None
        self.coupang_crawler = None
        self.yogiyo_crawler = None
        self.baemin_parser = BaeminReviewParser()
        
    async def collect_reviews_for_store(self, store_code: str) -> Dict:
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
            store_info = await self.supabase.get_store_by_code(store_code)
            if not store_info:
                result['errors'].append(f"매장을 찾을 수 없습니다: {store_code}")
                return result
            
            result['platform'] = store_info['platform']
            result['store_name'] = store_info['store_name']
            
            # 플랫폼별 크롤러 선택
            if store_info['platform'] == 'baemin':
                reviews = await self._collect_baemin_reviews(store_info)
            elif store_info['platform'] == 'coupang':
                reviews = await self._collect_coupang_reviews(store_info)
            elif store_info['platform'] == 'yogiyo':
                reviews = await self._collect_yogiyo_reviews(store_info)
            else:
                result['errors'].append(f"지원하지 않는 플랫폼: {store_info['platform']}")
                return result
            
            # 리뷰 저장
            save_result = await self.save_reviews_to_db(reviews)
            
            result['success'] = True
            result['collected'] = save_result['saved']
            result['duplicates'] = save_result['duplicates']
            
            # 사용량 업데이트
            await self.supabase.update_usage_tracking(
                store_info['owner_user_code'],
                reviews_increment=save_result['saved']
            )
            
            logger.info(f"리뷰 수집 완료 - store: {store_code}, collected: {save_result['saved']}")
            
        except Exception as e:
            logger.error(f"리뷰 수집 실패 - store: {store_code}, error: {e}")
            result['errors'].append(str(e))
            
        return result
    
    async def _collect_baemin_reviews(self, store_info: Dict) -> List[Dict]:
        """
        배민 리뷰 수집
        
        Args:
            store_info: 매장 정보
            
        Returns:
            list: 수집된 리뷰 리스트
        """
        try:
            # 크롤러 초기화
            if not self.baemin_crawler:
                self.baemin_crawler = BaeminReviewCrawler()  # 클래스명 확인
                await self.baemin_crawler.start()
            
            # 로그인
            login_success = await self.baemin_crawler.login(
                store_info['platform_id'],
                store_info['platform_pw']
            )
            
            if not login_success:
                raise Exception("배민 로그인 실패")
            
            # 리뷰 수집 - get_reviews 메서드 사용
            reviews = await self.baemin_crawler.get_reviews(
                store_info['platform_code'],
                store_info['store_code']
            )
            
            return reviews
            
        except Exception as e:
            logger.error(f"배민 리뷰 수집 실패: {e}")
            raise
        finally:
            # 크롤러 정리
            if self.baemin_crawler:
                await self.baemin_crawler.close()
                self.baemin_crawler = None
    
    async def _collect_coupang_reviews(self, store_info: Dict) -> List[Dict]:
        """
        쿠팡이츠 리뷰 수집 (추후 구현)
        """
        # TODO: 쿠팡이츠 리뷰 수집 구현
        return []
    
    async def _collect_yogiyo_reviews(self, store_info: Dict) -> List[Dict]:
        """
        요기요 리뷰 수집 (추후 구현)
        """
        # TODO: 요기요 리뷰 수집 구현
        return []
    
    async def save_reviews_to_db(self, reviews: List[Dict]) -> Dict:
        """
        수집한 리뷰를 DB에 저장
        
        Args:
            reviews: 리뷰 데이터 리스트
            
        Returns:
            dict: {saved: int, duplicates: int, errors: []}
        """
        result = {
            'saved': 0,
            'duplicates': 0,
            'errors': []
        }
        
        for review in reviews:
            try:
                # 중복 체크
                exists = await self.check_duplicate_review(review['review_id'])
                if exists:
                    result['duplicates'] += 1
                    continue
                
                # DB 저장
                save_result = await self.supabase.insert_review(review)
                if save_result:
                    result['saved'] += 1
                else:
                    result['errors'].append(f"리뷰 저장 실패: {review['review_id']}")
                    
            except Exception as e:
                logger.error(f"리뷰 저장 중 오류 - review_id: {review.get('review_id')}, error: {e}")
                result['errors'].append(str(e))
        
        return result
    
    async def check_duplicate_review(self, review_id: str) -> bool:
        """
        중복 리뷰 체크
        
        Args:
            review_id: 리뷰 ID
            
        Returns:
            bool: 존재 여부
        """
        try:
            return await self.supabase.check_review_exists(review_id)
        except Exception as e:
            logger.error(f"중복 체크 실패 - review_id: {review_id}, error: {e}")
            return False
    
    async def collect_all_stores_reviews(self) -> Dict:
        """
        모든 활성 매장의 리뷰 수집 (배치 작업용)
        
        Returns:
            dict: 수집 결과 요약
        """
        total_result = {
            'total_stores': 0,
            'successful_stores': 0,
            'failed_stores': 0,
            'total_collected': 0,
            'errors': []
        }
        
        try:
            # 활성 매장 목록 조회
            active_stores = await self.supabase.get_active_stores()
            total_result['total_stores'] = len(active_stores)
            
            # 각 매장별로 수집
            for store in active_stores:
                try:
                    result = await self.collect_reviews_for_store(store['store_code'])
                    
                    if result['success']:
                        total_result['successful_stores'] += 1
                        total_result['total_collected'] += result['collected']
                    else:
                        total_result['failed_stores'] += 1
                        total_result['errors'].extend(result['errors'])
                    
                    # 매장 간 딜레이
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    logger.error(f"매장 리뷰 수집 실패 - store: {store['store_code']}, error: {e}")
                    total_result['failed_stores'] += 1
                    total_result['errors'].append(f"{store['store_code']}: {str(e)}")
            
        except Exception as e:
            logger.error(f"전체 리뷰 수집 실패: {e}")
            total_result['errors'].append(str(e))
        
        return total_result