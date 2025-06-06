"""
크롤러 패키지
각 플랫폼별 크롤러 모듈 제공
"""
import sys
import os
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Union, AsyncContextManager

from .base_crawler import BaseCrawler
from .baemin_crawler import BaeminCrawler
from .yogiyo_crawler import YogiyoCrawler
from .coupang_crawler import CoupangCrawler
from .sync_wrapper import SyncCrawlerWrapper

# Windows용 동기 크롤러 임포트
from .windows_sync_crawler import WindowsCrawlerAdapter
from .baemin_sync_crawler import BaeminSyncCrawler
from .threaded_crawler import ThreadedCrawlerWrapper

logger = logging.getLogger(__name__)

__all__ = [
    'BaseCrawler',
    'BaeminCrawler', 
    'YogiyoCrawler',
    'CoupangCrawler',
    'get_crawler',
    'get_crawler_sync'
]

# 플랫폼별 크롤러 매핑
CRAWLER_MAPPING = {
    'baemin': BaeminCrawler,
    'yogiyo': YogiyoCrawler,
    'coupang': CoupangCrawler
}

# Windows용 동기 크롤러 매핑
SYNC_CRAWLER_MAPPING = {
    'baemin': BaeminSyncCrawler,
    # 'yogiyo': YogiyoSyncCrawler,  # 추후 구현
    # 'coupang': CoupangSyncCrawler  # 추후 구현
}

# Windows 환경 체크
IS_WINDOWS = sys.platform == 'win32'
USE_SYNC_MODE = IS_WINDOWS and os.getenv('FORCE_ASYNC_CRAWLER', '').lower() != 'true'

@asynccontextmanager
async def get_crawler(platform: str, headless: bool = True):
    """플랫폼명으로 크롤러 인스턴스 생성 (async context manager)"""
    
    # Windows 환경에서는 스레드 기반 동기 크롤러 사용
    if USE_SYNC_MODE:
        sync_crawler_class = SYNC_CRAWLER_MAPPING.get(platform.lower())
        if sync_crawler_class:
            logger.info(f"Windows 환경: 스레드 기반 동기 크롤러 사용 ({platform})")
            
            # ThreadedCrawlerWrapper를 사용하여 별도 스레드에서 실행
            wrapper = ThreadedCrawlerWrapper(sync_crawler_class, headless=headless)
            
            try:
                await wrapper.__aenter__()
                yield wrapper
            finally:
                await wrapper.__aexit__(None, None, None)
            return
    
    # 기존 비동기 크롤러 사용 (Linux/Mac)
    crawler_class = CRAWLER_MAPPING.get(platform.lower())
    if not crawler_class:
        raise ValueError(f"지원하지 않는 플랫폼입니다: {platform}")
    
    crawler = crawler_class(headless=headless)
    try:
        await crawler.start_browser()
        yield crawler
    finally:
        await crawler.close_browser()


def get_crawler_sync(platform: str, headless: bool = True):
    """동기 모드 크롤러 생성 (컨텍스트 매니저)"""
    if IS_WINDOWS:
        sync_crawler_class = SYNC_CRAWLER_MAPPING.get(platform.lower())
        if sync_crawler_class:
            return sync_crawler_class(headless=headless)
    
    # Windows가 아니거나 동기 크롤러가 없는 경우
    crawler_class = CRAWLER_MAPPING.get(platform.lower())
    if not crawler_class:
        raise ValueError(f"지원하지 않는 플랫폼입니다: {platform}")
    
    return SyncCrawlerWrapper(crawler_class, headless=headless)


# 환경 변수 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
