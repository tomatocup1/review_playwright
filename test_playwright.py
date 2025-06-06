"""
Playwright 테스트 스크립트
"""
import asyncio
from playwright.async_api import async_playwright

async def test_playwright():
    """Playwright 기본 테스트"""
    try:
        print("Playwright 테스트 시작...")
        
        async with async_playwright() as p:
            # 브라우저 실행
            browser = await p.chromium.launch(headless=True)
            print("브라우저 실행 성공")
            
            # 새 페이지 생성
            page = await browser.new_page()
            print("페이지 생성 성공")
            
            # 구글 접속
            await page.goto("https://www.google.com")
            print("Google 접속 성공")
            
            # 타이틀 확인
            title = await page.title()
            print(f"페이지 타이틀: {title}")
            
            # 브라우저 종료
            await browser.close()
            print("브라우저 종료 성공")
            
        print("\n✅ Playwright 정상 작동!")
        
    except Exception as e:
        print(f"\n❌ Playwright 오류: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_playwright())
