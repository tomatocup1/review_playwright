"""
Playwright 환경 설정 및 브라우저 경로 헬퍼
"""
import os
import sys
import logging

logger = logging.getLogger(__name__)

def setup_playwright_env():
    """Playwright 환경 변수 설정"""
    try:
        # 사용자 홈 디렉토리
        home = os.path.expanduser("~")
        
        # Playwright 브라우저 경로 설정
        playwright_path = os.path.join(home, "AppData", "Local", "ms-playwright")
        
        if os.path.exists(playwright_path):
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = playwright_path
            logger.info(f"Playwright browsers path set to: {playwright_path}")
            
            # 브라우저 실행 파일 경로들
            browser_paths = {
                "chromium-1091": os.path.join(playwright_path, "chromium-1091", "chrome-win", "chrome.exe"),
                "chromium-1169": os.path.join(playwright_path, "chromium-1169", "chrome-win", "chrome.exe"),
            }
            
            # 사용 가능한 브라우저 찾기
            for version, path in browser_paths.items():
                if os.path.exists(path):
                    logger.info(f"Found {version} at: {path}")
                    return playwright_path, path
                    
        logger.warning("Playwright browsers path not found")
        return None, None
        
    except Exception as e:
        logger.error(f"Error setting up Playwright environment: {e}")
        return None, None

def get_chromium_executable():
    """사용 가능한 Chromium 실행 파일 경로 반환"""
    playwright_path, chrome_path = setup_playwright_env()
    return chrome_path
