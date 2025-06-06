"""
크롤러 패키지
각 플랫폼별 크롤러 모듈 제공
"""
from .base_crawler import BaseCrawler
from .baemin_crawler import BaeminCrawler
from .yogiyo_crawler import YogiyoCrawler
from .coupang_crawler import CoupangCrawler
from contextlib import asynccontextmanager

__all__ = [
    'BaseCrawler',
    'BaeminCrawler', 
    'YogiyoCrawler',
    'CoupangCrawler',
    'get_crawler'
]

# 플랫폼별 크롤러 매핑
CRAWLER_MAPPING = {
    'baemin': BaeminCrawler,
    'yogiyo': YogiyoCrawler,
    'coupang': CoupangCrawler
}

@asynccontextmanager
async def get_crawler(platform: str, headless: bool = True):
    """플랫폼명으로 크롤러 인스턴스 생성 (async context manager)"""
    crawler_class = CRAWLER_MAPPING.get(platform.lower())
    if not crawler_class:
        raise ValueError(f"지원하지 않는 플랫폼입니다: {platform}")
    
    crawler = crawler_class(headless=headless)
    try:
        await crawler.start_browser()
        yield crawler
    finally:
        await crawler.close_browser()
