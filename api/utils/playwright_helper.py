"""
Playwright 브라우저 관리 헬퍼
"""
import os
import logging
import asyncio
from typing import Optional
from pathlib import Path

from playwright.async_api import async_playwright, Browser, Playwright, Error as PlaywrightError

logger = logging.getLogger(__name__)


class PlaywrightHelper:
    """Playwright 브라우저 인스턴스 관리 클래스"""
    
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context = None  # 추가
        self._lock = asyncio.Lock()
        
    async def initialize(self):
        """Playwright 초기화"""
        async with self._lock:
            if not self.playwright:
                self.playwright = await async_playwright().start()
                logger.info("Playwright 초기화 완료")
    
    async def create_browser(self, headless: bool = False) -> Browser:
        """브라우저 인스턴스 생성"""
        await self.initialize()
        
        try:
            # 브라우저 실행 파일 경로 설정
            browser_path = self._get_browser_path()
            
            # 브라우저 옵션 설정
            browser_args = [
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-gpu',
                '--lang=ko-KR',
            ]
            
            if headless:
                browser_args.extend([
                    '--window-size=1920,1080',
                ])
            
            # 브라우저 실행
            logger.info(f"브라우저 실행 중... (headless={headless})")
            
            # 사용자 데이터 디렉토리 설정
            user_data_dir = Path("C:/Review_playwright/browser_data")
            user_data_dir.mkdir(exist_ok=True, parents=True)
            
            # launch_persistent_context 옵션 설정
            launch_options = {
                'headless': headless,
                'args': browser_args
            }
            
            # 브라우저 경로가 있으면 설정
            if browser_path:
                launch_options['executable_path'] = browser_path
                logger.info(f"사용자 정의 브라우저 경로 사용: {browser_path}")
            
            # persistent context로 브라우저 실행
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                **launch_options
            )
            
            logger.info("브라우저 실행 성공")
            
            # context를 browser로 반환 (호환성 유지)
            return self.context
            
        except PlaywrightError as e:
            logger.error(f"브라우저 실행 실패: {str(e)}")
            
            # Playwright 브라우저 설치 확인
            if "executable doesn't exist" in str(e):
                logger.info("브라우저가 설치되지 않았습니다. 설치를 시작합니다...")
                await self._install_browser()
                # 재시도
                return await self.create_browser(headless)
            raise
        except Exception as e:
            logger.error(f"브라우저 생성 중 예상치 못한 오류: {str(e)}")
            raise
    
    def _get_browser_path(self) -> Optional[str]:
        """브라우저 실행 파일 경로 가져오기"""
        # 환경 변수에서 경로 확인
        custom_path = os.environ.get('PLAYWRIGHT_BROWSER_PATH')
        if custom_path and os.path.exists(custom_path):
            return custom_path
        
        # Playwright 기본 브라우저 경로 확인
        playwright_path = os.path.expanduser('~/.cache/ms-playwright')
        if os.name == 'nt':  # Windows
            playwright_path = os.path.join(
                os.environ.get('LOCALAPPDATA', ''),
                'ms-playwright'
            )
        
        # 설치된 브라우저 버전 확인
        if os.path.exists(playwright_path):
            logger.info(f"Playwright browsers path set to: {playwright_path}")
            
            # chromium 디렉토리 찾기
            for item in os.listdir(playwright_path):
                if item.startswith('chromium-'):
                    chromium_path = os.path.join(playwright_path, item)
                    
                    # Windows 실행 파일 경로
                    if os.name == 'nt':
                        exe_path = os.path.join(chromium_path, 'chrome-win', 'chrome.exe')
                        if os.path.exists(exe_path):
                            logger.info(f"Found {item} at: {exe_path}")
                            return exe_path
                    # Linux/Mac 실행 파일 경로
                    else:
                        exe_path = os.path.join(chromium_path, 'chrome-linux', 'chrome')
                        if os.path.exists(exe_path):
                            logger.info(f"Found {item} at: {exe_path}")
                            return exe_path
        
        return None
    
    async def _install_browser(self):
        """Playwright 브라우저 설치"""
        try:
            logger.info("Chromium 브라우저 설치 중...")
            # 설치 명령 실행
            import subprocess
            result = subprocess.run(
                ['playwright', 'install', 'chromium'],
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            if result.returncode == 0:
                logger.info("브라우저 설치 완료")
            else:
                logger.error(f"브라우저 설치 실패: {result.stderr}")
                raise Exception("브라우저 설치 실패")
                
        except Exception as e:
            logger.error(f"브라우저 설치 중 오류: {str(e)}")
            raise
    
    def _on_browser_disconnected(self):
        """브라우저 연결 해제 이벤트 핸들러"""
        logger.warning("브라우저 연결이 해제되었습니다")
        self.browser = None
        self.context = None  # 추가
    
    async def get_browser(self, headless: bool = False) -> Browser:
        """브라우저 인스턴스 가져오기 (재사용)"""
        async with self._lock:
            if not self.context:
                logger.info("새 브라우저 인스턴스 생성")
                self.context = await self.create_browser(headless)
            else:
                logger.info("기존 브라우저 인스턴스 재사용")
            
            return self.context
    
    async def close_browser(self):
        """브라우저 종료"""
        async with self._lock:
            if self.context:
                try:
                    await self.context.close()
                    logger.info("브라우저 컨텍스트 종료 완료")
                except Exception as e:
                    logger.error(f"브라우저 종료 중 오류: {str(e)}")
                finally:
                    self.context = None
                    self.browser = None
    
    async def cleanup(self):
        """리소스 정리"""
        await self.close_browser()
        
        if self.playwright:
            try:
                await self.playwright.stop()
                logger.info("Playwright 정리 완료")
            except Exception as e:
                logger.error(f"Playwright 정리 중 오류: {str(e)}")
            finally:
                self.playwright = None


# 싱글톤 인스턴스
_playwright_helper = PlaywrightHelper()


async def get_playwright_helper() -> PlaywrightHelper:
    """Playwright 헬퍼 인스턴스 가져오기"""
    return _playwright_helper


async def create_browser(headless: bool = False) -> Browser:
    """브라우저 생성 함수 (편의 함수)"""
    helper = await get_playwright_helper()
    return await helper.create_browser(headless)


async def get_browser(headless: bool = False) -> Browser:
    """브라우저 가져오기 함수 (편의 함수)"""
    helper = await get_playwright_helper()
    return await helper.get_browser(headless)


async def cleanup_playwright():
    """Playwright 정리 함수 (편의 함수)"""
    helper = await get_playwright_helper()
    await helper.cleanup()