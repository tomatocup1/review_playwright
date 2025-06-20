"""
크롤러 패키지
각 플랫폼별 크롤러 모듈 제공
"""
import sys
import os
import asyncio
import logging
import json
import subprocess
from contextlib import asynccontextmanager
from typing import Union, AsyncContextManager, List, Dict, Any
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from .base_crawler import BaseCrawler

logger = logging.getLogger(__name__)

__all__ = [
    'BaseCrawler',
    'get_crawler',
    'get_crawler_sync'
]

# Windows 환경 체크
IS_WINDOWS = sys.platform == 'win32'

# 스레드 풀 실행자
executor = ThreadPoolExecutor(max_workers=2)

class SubprocessCrawlerWrapper:
    """서브프로세스로 크롤러를 실행하는 래퍼 클래스"""
    
    def __init__(self, platform: str, headless: bool = True):
        self.platform = platform
        self.headless = headless
        self.username = None
        self.password = None
        
    async def start_browser(self):
        """브라우저 시작 (서브프로세스에서 실제로 시작됨)"""
        logger.info(f"SubprocessCrawlerWrapper: {self.platform} 준비")
        
    async def close_browser(self):
        """브라우저 종료 (서브프로세스가 종료될 때 자동으로 종료됨)"""
        logger.info(f"SubprocessCrawlerWrapper: {self.platform} 종료")
        
    async def login(self, username: str, password: str) -> bool:
        """로그인 정보 저장 (실제 로그인은 get_store_list에서 수행)"""
        self.username = username
        self.password = password
        return True  # 실제 로그인은 get_store_list에서 수행
        
    def _run_subprocess(self, cmd: List[str]) -> Dict[str, Any]:
        """서브프로세스를 동기적으로 실행"""
        try:
            logger.info(f"서브프로세스 실행: {' '.join(cmd)}")
            
            # subprocess.run을 사용하여 실행
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # 60초 타임아웃
            )
            
            if result.stderr:
                logger.error(f"서브프로세스 표준 에러: {result.stderr}")
            
            # stdout 파싱
            output = result.stdout.strip()
            if not output:
                logger.error("서브프로세스에서 출력이 없습니다")
                return {"error": "No output from subprocess"}
            
            logger.info(f"서브프로세스 출력 (처음 200자): {output[:200]}")
            
            # JSON 파싱 시도
            try:
                # 로그 메시지와 JSON을 분리
                lines = output.split('\n')
                json_output = None
                
                # 마지막 줄부터 역순으로 JSON 찾기
                for line in reversed(lines):
                    line = line.strip()
                    if line.startswith('{') and line.endswith('}'):
                        try:
                            json_output = json.loads(line)
                            break
                        except json.JSONDecodeError:
                            continue
                
                if json_output:
                    return json_output
                else:
                    logger.error("JSON 출력을 찾을 수 없습니다")
                    logger.error(f"전체 출력: {output}")
                    return {"error": "Invalid JSON output"}
                    
            except Exception as e:
                logger.error(f"JSON 파싱 에러: {e}")
                logger.error(f"원본 출력: {output}")
                return {"error": f"JSON parse error: {str(e)}"}
                
        except subprocess.TimeoutExpired:
            logger.error("서브프로세스 타임아웃")
            return {"error": "Subprocess timeout"}
        except Exception as e:
            logger.error(f"서브프로세스 실행 에러: {str(e)}")
            return {"error": str(e)}
        
    async def get_store_list(self) -> List[Dict[str, Any]]:
        """서브프로세스로 매장 목록 조회"""
        if not self.username or not self.password:
            logger.error("로그인 정보가 없습니다")
            return []
            
        try:
            # 크롤러 스크립트 경로
            crawler_script = Path(__file__).parent / "store_crawlers" / "crawler_subprocess.py"
            
            if not crawler_script.exists():
                logger.error(f"크롤러 스크립트를 찾을 수 없습니다: {crawler_script}")
                raise Exception("크롤러 스크립트를 찾을 수 없습니다")
            
            # 서브프로세스 명령어
            cmd = [
                sys.executable,
                str(crawler_script),
                self.platform,
                self.username,
                self.password,
                "get_stores",
                str(self.headless).lower()
            ]
            
            # 별도 스레드에서 서브프로세스 실행
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(executor, self._run_subprocess, cmd)
            
            if data.get('error'):
                logger.error(f"크롤러 에러: {data['error']}")
                
                # 배민 가게 미등록 특별 처리
                if data.get('error_type') == 'NO_STORES_REGISTERED':
                    return []  # 빈 리스트 반환하여 상위에서 처리
                    
                if data.get('login_success') == False:
                    raise Exception("로그인 실패")
                return []
            
            return data.get('stores', [])
                
        except Exception as e:
            logger.error(f"get_store_list 에러: {str(e)}")
            raise
            
    async def select_store(self, platform_code: str) -> bool:
        """매장 선택 (구현 필요시 추가)"""
        return True
        
    async def get_store_info(self):
        """매장 정보 조회 (구현 필요시 추가)"""
        return {}
        
    async def get_reviews(self, limit: int = 50):
        """리뷰 목록 조회 (구현 필요시 추가)"""
        return []
        
    async def post_reply(self, review_id: str, reply_text: str) -> bool:
        """답글 작성 (구현 필요시 추가)"""
        return False

@asynccontextmanager
async def get_crawler(platform: str, headless: bool = True):
    """플랫폼명으로 크롤러 인스턴스 생성 (async context manager)"""
    
    # 서브프로세스 크롤러 래퍼 사용
    crawler = SubprocessCrawlerWrapper(platform, headless)
    
    try:
        await crawler.start_browser()
        yield crawler
    finally:
        await crawler.close_browser()

def get_crawler_sync(platform: str, headless: bool = True):
    """동기 모드 크롤러 생성 (테스트용)"""
    raise NotImplementedError("동기 모드는 현재 지원하지 않습니다. get_crawler를 사용하세요.")