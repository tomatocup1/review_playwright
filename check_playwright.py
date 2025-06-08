"""
Playwright 설치 및 설정 확인
"""
import subprocess
import sys
import os

def check_playwright():
    """Playwright 설치 상태 확인"""
    
    print("=== Playwright 설치 확인 ===\n")
    
    # 1. playwright 패키지 확인
    try:
        import playwright
        print(f"✓ Playwright 패키지 설치됨: {playwright.__version__}")
    except ImportError:
        print("✗ Playwright 패키지가 설치되지 않음")
        print("  설치 명령: pip install playwright")
        return False
    
    # 2. 브라우저 설치 확인
    print("\n브라우저 설치 확인 중...")
    
    # playwright 브라우저 경로 확인
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--help"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✓ Playwright CLI 사용 가능")
        else:
            print("✗ Playwright CLI 문제 발생")
            
    except Exception as e:
        print(f"✗ Playwright CLI 확인 실패: {e}")
    
    # 3. 브라우저 설치
    print("\n브라우저 설치 시도...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✓ Chromium 브라우저 설치 완료")
        else:
            print(f"✗ Chromium 설치 실패: {result.stderr}")
            
    except Exception as e:
        print(f"✗ 브라우저 설치 실패: {e}")
    
    # 4. 간단한 테스트
    print("\n간단한 Playwright 테스트...")
    test_code = """
import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://www.google.com')
        title = await page.title()
        await browser.close()
        return title

# Windows 이벤트 루프 설정
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

try:
    title = asyncio.run(test())
    print(f"✓ Playwright 테스트 성공: {title}")
except Exception as e:
    print(f"✗ Playwright 테스트 실패: {e}")
"""
    
    try:
        exec(test_code)
    except Exception as e:
        print(f"✗ 테스트 실행 실패: {e}")
    
    print("\n=== 환경 정보 ===")
    print(f"Python 버전: {sys.version}")
    print(f"운영체제: {sys.platform}")
    print(f"Python 경로: {sys.executable}")
    
    # 환경변수 확인
    print("\n=== 관련 환경변수 ===")
    pw_browsers = os.environ.get('PLAYWRIGHT_BROWSERS_PATH')
    if pw_browsers:
        print(f"PLAYWRIGHT_BROWSERS_PATH: {pw_browsers}")
    else:
        print("PLAYWRIGHT_BROWSERS_PATH: 설정되지 않음 (기본 경로 사용)")
    
    return True


if __name__ == "__main__":
    check_playwright()
    
    print("\n문제가 계속되면 다음을 시도해보세요:")
    print("1. pip uninstall playwright")
    print("2. pip install playwright==1.40.0")
    print("3. python -m playwright install chromium")
    print("4. python -m playwright install-deps")  # Linux/Mac only
