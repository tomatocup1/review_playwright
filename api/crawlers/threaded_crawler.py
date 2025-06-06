"""
Windows 환경을 위한 스레드 기반 크롤러 래퍼
동기 크롤러를 별도 스레드에서 실행하여 비동기 환경과의 충돌 방지
"""
import asyncio
import threading
import logging
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import functools

logger = logging.getLogger(__name__)

class ThreadedCrawlerWrapper:
    """동기 크롤러를 별도 스레드에서 실행하는 래퍼"""
    
    def __init__(self, sync_crawler_class, headless: bool = True):
        self.sync_crawler_class = sync_crawler_class
        self.headless = headless
        self.sync_crawler = None
        self.executor = ThreadPoolExecutor(max_workers=1)
        self._lock = threading.Lock()
        
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        await self._run_in_thread(self._start_browser)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        await self._run_in_thread(self._close_browser)
        self.executor.shutdown(wait=True)
        
    async def _run_in_thread(self, func, *args, **kwargs):
        """동기 함수를 별도 스레드에서 실행"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, func, *args, **kwargs)
        
    def _start_browser(self):
        """브라우저 시작 (스레드에서 실행)"""
        with self._lock:
            if not self.sync_crawler:
                self.sync_crawler = self.sync_crawler_class(headless=self.headless)
                self.sync_crawler.start_browser()
                
    def _close_browser(self):
        """브라우저 종료 (스레드에서 실행)"""
        with self._lock:
            if self.sync_crawler:
                self.sync_crawler.close_browser()
                self.sync_crawler = None
                
    async def start_browser(self):
        """비동기 인터페이스로 브라우저 시작"""
        await self._run_in_thread(self._start_browser)
        
    async def close_browser(self):
        """비동기 인터페이스로 브라우저 종료"""
        await self._run_in_thread(self._close_browser)
        
    async def login(self, username: str, password: str) -> bool:
        """비동기 인터페이스로 로그인"""
        return await self._run_in_thread(self._login, username, password)
        
    def _login(self, username: str, password: str) -> bool:
        """로그인 (스레드에서 실행)"""
        with self._lock:
            if self.sync_crawler:
                return self.sync_crawler.login(username, password)
            return False
            
    async def get_store_list(self) -> List[Dict[str, Any]]:
        """비동기 인터페이스로 매장 목록 조회"""
        return await self._run_in_thread(self._get_store_list)
        
    def _get_store_list(self) -> List[Dict[str, Any]]:
        """매장 목록 조회 (스레드에서 실행)"""
        with self._lock:
            if self.sync_crawler:
                return self.sync_crawler.get_store_list()
            return []
            
    async def select_store(self, platform_code: str) -> bool:
        """비동기 인터페이스로 매장 선택"""
        return await self._run_in_thread(self._select_store, platform_code)
        
    def _select_store(self, platform_code: str) -> bool:
        """매장 선택 (스레드에서 실행)"""
        with self._lock:
            if self.sync_crawler:
                return self.sync_crawler.select_store(platform_code)
            return False
            
    async def get_store_info(self) -> Dict[str, Any]:
        """비동기 인터페이스로 매장 정보 조회"""
        return await self._run_in_thread(self._get_store_info)
        
    def _get_store_info(self) -> Dict[str, Any]:
        """매장 정보 조회 (스레드에서 실행)"""
        with self._lock:
            if self.sync_crawler:
                return self.sync_crawler.get_store_info()
            return {}
            
    async def get_reviews(self, limit: int = 50) -> List[Dict[str, Any]]:
        """비동기 인터페이스로 리뷰 조회"""
        return await self._run_in_thread(self._get_reviews, limit)
        
    def _get_reviews(self, limit: int = 50) -> List[Dict[str, Any]]:
        """리뷰 조회 (스레드에서 실행)"""
        with self._lock:
            if self.sync_crawler:
                return self.sync_crawler.get_reviews(limit)
            return []
            
    async def post_reply(self, review_id: str, reply_text: str) -> bool:
        """비동기 인터페이스로 답글 작성"""
        return await self._run_in_thread(self._post_reply, review_id, reply_text)
        
    def _post_reply(self, review_id: str, reply_text: str) -> bool:
        """답글 작성 (스레드에서 실행)"""
        with self._lock:
            if self.sync_crawler:
                return self.sync_crawler.post_reply(review_id, reply_text)
            return False
            
    async def save_screenshot(self, name: str):
        """비동기 인터페이스로 스크린샷 저장"""
        await self._run_in_thread(self._save_screenshot, name)
        
    def _save_screenshot(self, name: str):
        """스크린샷 저장 (스레드에서 실행)"""
        with self._lock:
            if self.sync_crawler:
                self.sync_crawler.save_screenshot(name)


class ProcessBasedCrawler:
    """별도 프로세스에서 크롤러 실행 (더 안정적인 방법)"""
    
    def __init__(self, sync_crawler_class, headless: bool = True):
        self.sync_crawler_class = sync_crawler_class
        self.headless = headless
        self.request_queue = Queue()
        self.response_queue = Queue()
        self.process = None
        self.thread = None
        
    def _crawler_process(self):
        """크롤러를 실행하는 별도 프로세스"""
        import asyncio
        import sys
        
        # 새로운 이벤트 루프 생성
        if sys.platform == 'win32':
            # Windows에서는 ProactorEventLoop 사용 가능
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        crawler = self.sync_crawler_class(headless=self.headless)
        crawler.start_browser()
        
        try:
            while True:
                request = self.request_queue.get()
                if request['action'] == 'stop':
                    break
                    
                method = getattr(crawler, request['method'])
                args = request.get('args', ())
                kwargs = request.get('kwargs', {})
                
                try:
                    result = method(*args, **kwargs)
                    self.response_queue.put({'success': True, 'result': result})
                except Exception as e:
                    self.response_queue.put({'success': False, 'error': str(e)})
                    
        finally:
            crawler.close_browser()
            
    async def _send_request(self, method: str, *args, **kwargs):
        """요청을 큐에 넣고 응답 대기"""
        self.request_queue.put({
            'action': 'execute',
            'method': method,
            'args': args,
            'kwargs': kwargs
        })
        
        # 비동기적으로 응답 대기
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self.response_queue.get)
        
        if response['success']:
            return response['result']
        else:
            raise Exception(response['error'])
