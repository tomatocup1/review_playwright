"""
네이버 스마트플레이스 매장 정보 크롤러 (독립 실행용)
"""
import asyncio
from typing import List, Dict, Any
from playwright.async_api import async_playwright
import logging
import json
import os
from datetime import datetime

from api.crawlers.naver_crawler import NaverCrawler
from api.services.error_logger import setup_logging

# 로깅 설정
logger = setup_logging("naver_store_crawler")

async def crawl_naver_stores(platform_id: str, platform_pw: str) -> List[Dict[str, Any]]:
    """네이버 매장 정보 크롤링 메인 함수"""
    
    crawler = NaverCrawler()
    stores = []
    
    async with async_playwright() as p:
        # 브라우저 실행 (헤드리스 모드 끄기 - 디버깅용)
        browser = await p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        # 컨텍스트 생성
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        
        page = await context.new_page()
        
        try:
            # 로그인
            login_success = await crawler.login(page, platform_id, platform_pw)
            
            if not login_success:
                logger.error("로그인 실패")
                return []
                
            # 매장 목록 가져오기
            stores = await crawler.get_stores(page)
            
            # 결과 저장
            result_dir = os.path.join("logs", "crawl_results", "naver")
            os.makedirs(result_dir, exist_ok=True)
            
            result_file = os.path.join(
                result_dir, 
                f"stores_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(stores, f, ensure_ascii=False, indent=2)
                
            logger.info(f"크롤링 완료. 총 {len(stores)}개 매장 발견")
            logger.info(f"결과 저장: {result_file}")
            
        except Exception as e:
            logger.error(f"크롤링 중 오류 발생: {str(e)}")
            
        finally:
            await browser.close()
            
    return stores

# 독립 실행용
if __name__ == "__main__":
    # 테스트용 계정 정보 (실제 사용시 환경변수나 설정 파일에서 읽어오기)
    test_id = "gzgzgz09@naver.com"
    test_pw = "1qz2wx3ec#"
    
    result = asyncio.run(crawl_naver_stores(test_id, test_pw))
    print(f"크롤링 결과: {json.dumps(result, ensure_ascii=False, indent=2)}")