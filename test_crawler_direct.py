"""
크롤링 API 직접 테스트
"""
import asyncio
from api.crawlers import get_crawler

async def test_crawler():
    """크롤러 직접 테스트"""
    try:
        print("=== Crawler Direct Test ===")
        
        # 테스트 모드로 크롤러 생성
        async with get_crawler('baemin', headless=True) as crawler:
            print("Crawler created successfully")
            
            # 실제 크롤링은 하지 않고 브라우저만 테스트
            if crawler.page:
                print("Browser page is available")
                await crawler.page.goto("https://www.google.com")
                title = await crawler.page.title()
                print(f"Test page title: {title}")
            
        print("Crawler closed successfully")
        print("\nTest completed!")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_crawler())
