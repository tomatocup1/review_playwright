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
from pathlib import Path  # 추가
import json              # 추가
import re
# 프로젝트 루트 경로를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from .review_collector_service_sync import SyncReviewCollector
import threading
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
                    await self.supabase.update_usage(
                        store_info['owner_user_code'],
                        reviews_processed=result['collected']
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
        """배민 리뷰 수집 - 스레드 방식으로 동기 실행"""
        try:
            logger.info(f"배민 리뷰 수집 시작 - 매장: {store_info['store_name']}")
            
            # 암호화된 비밀번호 복호화
            try:
                decrypted_id = self.encryption.decrypt(store_info['platform_id'])
                decrypted_pw = self.encryption.decrypt(store_info['platform_pw'])
                
                if not decrypted_id:
                    decrypted_id = store_info['platform_id']
                if not decrypted_pw:
                    decrypted_pw = store_info['platform_pw']
                    
            except Exception as e:
                logger.warning(f"복호화 실패, 평문 사용: {str(e)}")
                decrypted_id = store_info['platform_id']
                decrypted_pw = store_info['platform_pw']
            
            # ID와 PW가 없으면 스킵
            if not decrypted_id or not decrypted_pw:
                logger.warning(f"로그인 정보 없음: {store_info['store_name']}")
                return {"success": True, "collected": 0, "saved": 0}
            
            # 복호화된 정보로 store_info 업데이트
            store_info_copy = store_info.copy()
            store_info_copy['platform_id'] = decrypted_id
            store_info_copy['platform_pw'] = decrypted_pw
            
            # 동기 수집기 생성
            sync_collector = SyncReviewCollector()
            
            # 스레드에서 실행
            thread = threading.Thread(
                target=sync_collector.run_in_thread,
                args=(store_info_copy, start_date, end_date)
            )
            thread.start()
            
            # 스레드 완료 대기 (최대 60초)
            thread.join(timeout=60)
            
            if thread.is_alive():
                logger.error("리뷰 수집 시간 초과")
                return {"success": False, "error": "시간 초과"}
            
            # 결과 가져오기
            try:
                result = sync_collector.result_queue.get_nowait()
                return result
            except:
                logger.error("결과를 가져올 수 없음")
                return {"success": False, "error": "결과 없음"}
                
        except Exception as e:
            logger.error(f"배민 리뷰 수집 실패: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}

    async def collect_coupang_reviews(self, store_info: dict, start_date: str, end_date: str) -> dict:
        """쿠팡이츠 리뷰 수집 - 스레드 방식으로 동기 실행"""
        try:
            logger.info(f"쿠팡이츠 리뷰 수집 시작 - 매장: {store_info['store_name']}")
            
            # 암호화된 비밀번호 복호화
            try:
                decrypted_id = self.encryption.decrypt(store_info['platform_id'])
                decrypted_pw = self.encryption.decrypt(store_info['platform_pw'])
                
                if not decrypted_id:
                    decrypted_id = store_info['platform_id']
                if not decrypted_pw:
                    decrypted_pw = store_info['platform_pw']
                    
            except Exception as e:
                logger.warning(f"복호화 실패, 평문 사용: {str(e)}")
                decrypted_id = store_info['platform_id']
                decrypted_pw = store_info['platform_pw']
            
            # ID와 PW가 없으면 스킵
            if not decrypted_id or not decrypted_pw:
                logger.warning(f"로그인 정보 없음: {store_info['store_name']}")
                return {"success": True, "collected": 0, "saved": 0}
            
            # 복호화된 정보로 store_info 업데이트
            store_info_copy = store_info.copy()
            store_info_copy['platform_id'] = decrypted_id
            store_info_copy['platform_pw'] = decrypted_pw
            
            # 동기 수집기에서 쿠팡 크롤러 사용
            from .review_collector_service_sync import SyncReviewCollector
            sync_collector = SyncReviewCollector()
            
            # 스레드에서 실행
            thread = threading.Thread(
                target=sync_collector.run_coupang_in_thread,
                args=(store_info_copy, start_date, end_date)
            )
            thread.start()
            
            # 스레드 완료 대기 (최대 60초)
            thread.join(timeout=60)
            
            if thread.is_alive():
                logger.error("쿠팡 리뷰 수집 시간 초과")
                return {"success": False, "error": "시간 초과"}
            
            # 결과 가져오기
            try:
                result = sync_collector.result_queue.get_nowait()
                return result
            except:
                logger.error("결과를 가져올 수 없음")
                return {"success": False, "error": "결과 없음"}
                
        except Exception as e:
            logger.error(f"쿠팡이츠 리뷰 수집 실패: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}

    async def collect_yogiyo_reviews(self, store_info: dict, start_date: str, end_date: str) -> dict:
        """요기요 리뷰 수집 - 스레드 방식으로 동기 실행"""
        try:
            logger.info(f"요기요 리뷰 수집 시작 - 매장: {store_info['store_name']}")
            
            # 암호화된 비밀번호 복호화
            try:
                decrypted_id = self.encryption.decrypt(store_info['platform_id'])
                decrypted_pw = self.encryption.decrypt(store_info['platform_pw'])
                
                if not decrypted_id:
                    decrypted_id = store_info['platform_id']
                if not decrypted_pw:
                    decrypted_pw = store_info['platform_pw']
                    
            except Exception as e:
                logger.warning(f"복호화 실패, 평문 사용: {str(e)}")
                decrypted_id = store_info['platform_id']
                decrypted_pw = store_info['platform_pw']
            
            # ID와 PW가 없으면 스킵
            if not decrypted_id or not decrypted_pw:
                logger.warning(f"로그인 정보 없음: {store_info['store_name']}")
                return {"success": True, "collected": 0, "saved": 0}
            
            # 복호화된 정보로 store_info 업데이트
            store_info_copy = store_info.copy()
            store_info_copy['platform_id'] = decrypted_id
            store_info_copy['platform_pw'] = decrypted_pw
            
            # 동기 수집기에서 요기요 크롤러 사용
            from .review_collector_service_sync import SyncReviewCollector
            sync_collector = SyncReviewCollector()
            
            # 스레드에서 실행
            thread = threading.Thread(
                target=sync_collector.run_yogiyo_in_thread,
                args=(store_info_copy, start_date, end_date)
            )
            thread.start()
            
            # 스레드 완료 대기 (최대 60초)
            thread.join(timeout=60)
            
            if thread.is_alive():
                logger.error("요기요 리뷰 수집 시간 초과")
                return {"success": False, "error": "시간 초과"}
            
            # 결과 가져오기
            try:
                result = sync_collector.result_queue.get_nowait()
                return result
            except:
                logger.error("결과를 가져올 수 없음")
                return {"success": False, "error": "결과 없음"}
                
        except Exception as e:
            logger.error(f"요기요 리뷰 수집 실패: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}
        
    async def collect_naver_reviews(self, store_info: dict, start_date: str, end_date: str) -> dict:
        """네이버 리뷰 수집 - 스레드 방식으로 동기 실행"""
        try:
            logger.info(f"네이버 리뷰 수집 시작 - 매장: {store_info['store_name']}")
            
            # 암호화된 비밀번호 복호화
            try:
                decrypted_id = self.encryption.decrypt(store_info['platform_id'])
                decrypted_pw = self.encryption.decrypt(store_info['platform_pw'])
                
                if not decrypted_id:
                    decrypted_id = store_info['platform_id']
                if not decrypted_pw:
                    decrypted_pw = store_info['platform_pw']
                    
            except Exception as e:
                logger.warning(f"복호화 실패, 평문 사용: {str(e)}")
                decrypted_id = store_info['platform_id']
                decrypted_pw = store_info['platform_pw']
            
            # ID와 PW가 없으면 스킵
            if not decrypted_id or not decrypted_pw:
                logger.warning(f"로그인 정보 없음: {store_info['store_name']}")
                return {"success": True, "collected": 0, "saved": 0}
            
            # 복호화된 정보로 store_info 업데이트
            store_info_copy = store_info.copy()
            store_info_copy['platform_id'] = decrypted_id
            store_info_copy['platform_pw'] = decrypted_pw
            
            # 동기 수집기에서 네이버 크롤러 사용
            from .review_collector_service_sync import SyncReviewCollector
            sync_collector = SyncReviewCollector()
            
            # 스레드에서 실행
            thread = threading.Thread(
                target=sync_collector.run_naver_in_thread,
                args=(store_info_copy, start_date, end_date)
            )
            thread.start()
            
            # 스레드 완료 대기 (최대 60초)
            thread.join(timeout=60)
            
            if thread.is_alive():
                logger.error("네이버 리뷰 수집 시간 초과")
                return {"success": False, "error": "시간 초과"}
            
            # 결과 가져오기
            try:
                result = sync_collector.result_queue.get_nowait()
                return result
            except:
                logger.error("결과를 가져올 수 없음")
                return {"success": False, "error": "결과 없음"}
                
        except Exception as e:
            logger.error(f"네이버 리뷰 수집 실패: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}
    
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
            
            # 동시 실행 제한 (3개로 줄임 - 브라우저 리소스 고려)
            semaphore = asyncio.Semaphore(3)
            
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