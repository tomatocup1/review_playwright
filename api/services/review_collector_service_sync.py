"""
동기식 리뷰 수집 서비스
asyncio subprocess 문제를 해결하기 위한 동기 버전
"""
import logging
import subprocess
import json
import sys
import os
import re
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
import threading
import queue

logger = logging.getLogger(__name__)

class SyncReviewCollector:
    """동기식 리뷰 수집기"""
    
    def __init__(self):
        self.result_queue = queue.Queue()
    
    def collect_baemin_reviews_sync(self, store_info: dict, start_date: str, end_date: str) -> dict:
        """배민 리뷰 수집 - 동기 방식"""
        try:
            logger.info(f"[동기] 배민 리뷰 수집 시작 - 매장: {store_info['store_name']}")
            
            # 크롤러 데이터 준비
            crawler_data = {
                "platform_id": store_info.get('platform_id', ''),
                "platform_pw": store_info.get('platform_pw', ''),
                "platform_code": store_info['platform_code'],
                "store_code": store_info['store_code'],
                "store_name": store_info['store_name'],
                "owner_user_code": store_info.get('owner_user_code', 'SYSTEM'),
                "start_date": start_date,
                "end_date": end_date
            }
            
            # subprocess로 실행
            script_path = Path(__file__).parent.parent / "crawlers" / "review_crawlers" / "run_sync_crawler.py"
            
            if not script_path.exists():
                logger.error(f"크롤러 스크립트를 찾을 수 없습니다: {script_path}")
                return {"success": False, "error": "크롤러 스크립트 없음"}
            
            # 동기 subprocess 실행
            # Windows 환경에서 한글 인코딩 문제 해결
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            
            process = subprocess.Popen(
                [sys.executable, str(script_path), json.dumps(crawler_data, ensure_ascii=False)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',  # 디코딩 에러 발생 시 대체 문자 사용
                env=env
            )
            
            try:
                stdout, stderr = process.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                logger.error("크롤러 실행 시간 초과")
                process.kill()
                return {"success": False, "error": "크롤러 실행 시간 초과"}
            
            if process.returncode == 0:
                try:
                    # stdout에서 JSON 찾기
                    json_pattern = r'\{[^{}]*"success"[^{}]*\}'
                    matches = re.findall(json_pattern, stdout)
                    
                    if matches:
                        result = json.loads(matches[-1])
                        return result
                    else:
                        logger.warning("JSON 결과를 찾을 수 없음")
                        return {"success": True, "collected": 0, "saved": 0}
                        
                except json.JSONDecodeError as e:
                    logger.error(f"JSON 파싱 실패: {e}")
                    return {"success": True, "collected": 0, "saved": 0}
            else:
                logger.error(f"크롤러 실행 실패: {stderr[:200]}")
                return {"success": False, "error": stderr[:200]}
                
        except Exception as e:
            logger.error(f"배민 리뷰 수집 실패: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def collect_yogiyo_reviews_sync(self, store_info: dict, start_date: str, end_date: str) -> dict:
        """요기요 리뷰 수집 - 동기 방식 (Supabase 저장 포함)"""
        try:
            logger.info(f"[동기] 요기요 리뷰 수집 시작 - 매장: {store_info['store_name']}")
            
            # 요기요 동기 크롤러 직접 사용
            from api.crawlers.review_crawlers.yogiyo_sync_review_crawler import YogiyoSyncReviewCrawler
            
            crawler = YogiyoSyncReviewCrawler(headless=True)  # 자동화를 위해 headless=True
            
            try:
                # 브라우저 시작
                if not crawler.start_browser():
                    logger.error("요기요 브라우저 시작 실패")
                    return {"success": False, "error": "브라우저 시작 실패"}
                
                # 로그인
                login_success = crawler.login(
                    store_info.get('platform_id', ''),
                    store_info.get('platform_pw', '')
                )
                
                if not login_success:
                    logger.error("요기요 로그인 실패")
                    return {"success": False, "error": "로그인 실패"}
                
                # 리뷰 수집 및 Supabase 저장
                result = crawler.get_reviews_and_save(
                    store_info['platform_code'],
                    store_info['store_code'],
                    store_info,  # 저장을 위한 store_info 전달
                    limit=50
                )
                
                if result['success']:
                    logger.info(f"요기요 리뷰 수집 완료: 수집 {result['collected']}개, 저장 {result['saved']}개")
                    return {
                        "success": True,
                        "collected": result['collected'],
                        "saved": result['saved']
                    }
                else:
                    logger.error(f"요기요 리뷰 수집 실패: {result.get('error', '알 수 없는 오류')}")
                    return {
                        "success": False,
                        "error": result.get('error', '알 수 없는 오류')
                    }
                
            finally:
                crawler.close_browser()
                
        except Exception as e:
            logger.error(f"요기요 리뷰 수집 실패: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}
    
    def collect_coupang_reviews_sync(self, store_info: dict, start_date: str, end_date: str) -> dict:
        """쿠팡이츠 리뷰 수집 - 동기 방식 (Supabase 저장 포함)"""
        try:
            logger.info(f"[동기] 쿠팡이츠 리뷰 수집 시작 - 매장: {store_info['store_name']}")
            
            # 쿠팡 동기 크롤러 직접 사용
            from api.crawlers.review_crawlers.coupang_sync_review_crawler import CoupangSyncReviewCrawler
            
            crawler = CoupangSyncReviewCrawler(headless=True)  # 로그인 문제 해결되어 headless=True로 변경
            
            try:
                # 브라우저 시작
                if not crawler.start_browser():
                    logger.error("쿠팡이츠 브라우저 시작 실패")
                    return {"success": False, "error": "브라우저 시작 실패"}
                
                # 로그인
                login_success = crawler.login(
                    store_info.get('platform_id', ''),
                    store_info.get('platform_pw', '')
                )
                
                if not login_success:
                    logger.error("쿠팡이츠 로그인 실패")
                    return {"success": False, "error": "로그인 실패"}
                
                # 리뷰 수집 및 Supabase 저장
                result = crawler.get_reviews_and_save(
                    store_info['platform_code'],
                    store_info['store_code'],
                    store_info,  # 저장을 위한 store_info 전달
                    limit=50
                )
                
                if result['success']:
                    logger.info(f"쿠팡이츠 리뷰 수집 완료: 수집 {result['collected']}개, 저장 {result['saved']}개")
                    return {
                        "success": True,
                        "collected": result['collected'],
                        "saved": result['saved']
                    }
                else:
                    logger.error(f"쿠팡이츠 리뷰 수집 실패: {result.get('error', '알 수 없는 오류')}")
                    return {
                        "success": False,
                        "error": result.get('error', '알 수 없는 오류')
                    }
                
            finally:
                crawler.close_browser()
                
        except Exception as e:
            logger.error(f"쿠팡이츠 리뷰 수집 실패: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}
    
    def run_in_thread(self, store_info: dict, start_date: str, end_date: str):
        """스레드에서 실행 (배민용)"""
        result = self.collect_baemin_reviews_sync(store_info, start_date, end_date)
        self.result_queue.put(result)
    
    def run_yogiyo_in_thread(self, store_info: dict, start_date: str, end_date: str):
        """스레드에서 실행 (요기요용)"""
        result = self.collect_yogiyo_reviews_sync(store_info, start_date, end_date)
        self.result_queue.put(result)
    
    def run_coupang_in_thread(self, store_info: dict, start_date: str, end_date: str):
        """스레드에서 실행 (쿠팡용)"""
        result = self.collect_coupang_reviews_sync(store_info, start_date, end_date)
        self.result_queue.put(result)
    
    def collect_naver_reviews_sync(self, store_info: dict, start_date: str, end_date: str) -> dict:
        """네이버 리뷰 수집 - 동기 방식 (subprocess 사용)"""
        try:
            logger.info(f"[동기] 네이버 리뷰 수집 시작 - 매장: {store_info['store_name']}")
            
            # 네이버 크롤러 스크립트 경로
            script_path = Path(__file__).parent.parent / "crawlers" / "review_crawlers" / "run_naver_async_crawler.py"
            
            if not script_path.exists():
                logger.error(f"네이버 크롤러 스크립트를 찾을 수 없습니다: {script_path}")
                return {"success": False, "error": "크롤러 스크립트 없음"}
            
            # 크롤러 데이터 준비
            crawler_data = {
                "store_info": store_info,
                "start_date": start_date,
                "end_date": end_date
            }
            
            # subprocess로 실행 (별도 프로세스에서 asyncio 실행)
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            
            process = subprocess.Popen(
                [sys.executable, str(script_path), json.dumps(crawler_data, ensure_ascii=False)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env
            )
            
            try:
                stdout, stderr = process.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                logger.error("네이버 크롤러 실행 시간 초과")
                process.kill()
                return {"success": False, "error": "크롤러 실행 시간 초과"}
            
            if process.returncode == 0:
                try:
                    # stdout에서 JSON 결과 찾기
                    json_pattern = r'\{[^{}]*"success"[^{}]*\}'
                    matches = re.findall(json_pattern, stdout)
                    
                    if matches:
                        result = json.loads(matches[-1])
                        return result
                    else:
                        logger.warning("네이버 크롤러에서 JSON 결과를 찾을 수 없음")
                        return {"success": True, "collected": 0, "saved": 0}
                        
                except json.JSONDecodeError as e:
                    logger.error(f"네이버 크롤러 JSON 파싱 실패: {e}")
                    return {"success": True, "collected": 0, "saved": 0}
            else:
                logger.error(f"네이버 크롤러 실행 실패: {stderr[:200]}")
                return {"success": False, "error": stderr[:200]}
                
        except Exception as e:
            logger.error(f"네이버 리뷰 수집 실패: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def run_naver_in_thread(self, store_info: dict, start_date: str, end_date: str):
        """스레드에서 실행 (네이버용)"""
        result = self.collect_naver_reviews_sync(store_info, start_date, end_date)
        self.result_queue.put(result)