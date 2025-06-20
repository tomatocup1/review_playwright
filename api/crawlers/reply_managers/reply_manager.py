"""
답글 관리 기본 클래스 (등록 + 수정 통합)
모든 플랫폼에서 공통으로 사용할 기본 구조
"""
import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple, Any
from playwright.sync_api import sync_playwright, Browser, Page
import time
import traceback
import sys
from api.utils.playwright_helper import setup_playwright_env, get_chromium_executable

class BaseReplyManager(ABC):
    """
    답글 관리 기본 클래스
    - 답글 등록 (새 리뷰에 답글 작성)
    - 답글 수정 (기존 답글 내용 변경)
    - 답글 삭제 (필요시)
    """
    
    def __init__(self, store_config: Dict[str, Any]):
        """
        매장 설정을 받아서 초기화
        
        Args:
            store_config: {
                "platform_id": "로그인 아이디",
                "platform_pw": "로그인 비밀번호", 
                "store_name": "매장명",
                "platform": "플랫폼명",
                "store_code": "매장코드"
            }
        """
        self.store_config = store_config
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.is_logged_in = False
        
        # 로깅 설정
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """로깅 설정"""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def setup_browser(self, headless: bool = False) -> bool:
        """
        브라우저 설정 및 초기화
        
        Args:
            headless: 헤드리스 모드 여부
            
        Returns:
            bool: 성공 여부
        """
        try:
            # Windows에서 asyncio 이벤트 루프 정책 설정
            if sys.platform == 'win32':
                import asyncio
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
            # Playwright 환경 설정
            setup_playwright_env()
            
            self.playwright = sync_playwright().start()
            
            # 브라우저 실행 옵션
            launch_options = {
                "headless": headless,
                "slow_mo": 1000 if not headless else 0,  # 비헤드리스 모드에서 느리게 실행
                "args": [
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--lang=ko-KR'  # 한국어 설정 추가
                ]
            }
            
            # Chromium 브라우저 실행
            try:
                self.browser = self.playwright.chromium.launch(**launch_options)
            except Exception as e:
                self.logger.warning(f"Chromium launch failed: {e}")
                
                # 실행 파일 경로 직접 지정
                chrome_path = get_chromium_executable()
                if chrome_path and os.path.exists(chrome_path):
                    launch_options["executable_path"] = chrome_path
                    self.logger.info(f"Using chromium at: {chrome_path}")
                    self.browser = self.playwright.chromium.launch(**launch_options)
                else:
                    # 마지막 시도: 기본 경로로 시도
                    self.logger.warning("Chromium not found, trying default installation...")
                    import subprocess
                    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
                    self.browser = self.playwright.chromium.launch(**launch_options)
            
            context = self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1280, 'height': 720},
                locale='ko-KR'
            )
            self.page = context.new_page()
            
            self.logger.info("브라우저 초기화 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"브라우저 초기화 실패: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    @abstractmethod
    def login_to_platform(self) -> Tuple[bool, str]:
        """
        플랫폼에 로그인
        
        Returns:
            Tuple[bool, str]: (성공여부, 메시지)
        """
        pass
    
    @abstractmethod
    def navigate_to_reviews_page(self) -> Tuple[bool, str]:
        """
        리뷰 관리 페이지로 이동
        
        Returns:
            Tuple[bool, str]: (성공여부, 메시지)
        """
        pass
    
    @abstractmethod
    def find_review_by_id(self, review_id: str) -> Dict[str, Any]:
        """
        특정 리뷰 찾기
        
        Args:
            review_id: 리뷰 고유 ID
            
        Returns:
            Dict: {
                "found": bool,
                "element": 리뷰 요소,
                "has_reply": bool,  # 기존 답글 있는지
                "current_reply": str,  # 현재 답글 내용
                "error": str
            }
        """
        pass
    
    @abstractmethod
    def post_new_reply(self, review_element: Any, reply_text: str) -> Dict[str, Any]:
        """
        새 답글 등록
        
        Args:
            review_element: 리뷰 요소
            reply_text: 답글 내용
            
        Returns:
            Dict: {"success": bool, "message": str, "error": str}
        """
        pass
    
    @abstractmethod
    def edit_existing_reply(self, review_element: Any, new_reply_text: str) -> Dict[str, Any]:
        """
        기존 답글 수정
        
        Args:
            review_element: 리뷰 요소
            new_reply_text: 새로운 답글 내용
            
        Returns:
            Dict: {"success": bool, "message": str, "error": str}
        """
        pass
    
    def manage_reply(self, review_id: str, reply_text: str, action: str = "auto") -> Dict[str, Any]:
        """
        답글 관리 메인 함수 (등록/수정 자동 판단 또는 지정)
        
        Args:
            review_id: 리뷰 ID
            reply_text: 답글 내용
            action: "auto" (자동판단), "post" (강제등록), "edit" (강제수정)
            
        Returns:
            Dict: {
                "success": bool,
                "action_taken": str,  # "posted", "edited", "no_action"
                "message": str,
                "error": str
            }
        """
        try:
            self.logger.info(f"답글 관리 시작 - Review ID: {review_id}, Action: {action}")
            
            # 1. 리뷰 찾기
            review_info = self.find_review_by_id(review_id)
            if not review_info.get("found"):
                return {
                    "success": False,
                    "action_taken": "no_action",
                    "message": "리뷰를 찾을 수 없습니다",
                    "error": review_info.get("error", "Review not found")
                }
            
            review_element = review_info["element"]
            has_existing_reply = review_info.get("has_reply", False)
            current_reply = review_info.get("current_reply", "")
            
            # 2. 액션 결정
            if action == "auto":
                if has_existing_reply:
                    # 기존 답글과 새 답글이 같으면 변경 없음
                    if current_reply.strip() == reply_text.strip():
                        return {
                            "success": True,
                            "action_taken": "no_action",
                            "message": "답글 내용이 동일하여 변경하지 않습니다",
                            "error": ""
                        }
                    action = "edit"
                else:
                    action = "post"
            
            # 3. 액션 실행
            if action == "post":
                if has_existing_reply:
                    return {
                        "success": False,
                        "action_taken": "no_action", 
                        "message": "이미 답글이 존재합니다. 수정을 원하시면 action='edit'을 사용하세요",
                        "error": "Reply already exists"
                    }
                
                result = self.post_new_reply(review_element, reply_text)
                result["action_taken"] = "posted" if result["success"] else "no_action"
                
            elif action == "edit":
                if not has_existing_reply:
                    return {
                        "success": False,
                        "action_taken": "no_action",
                        "message": "수정할 답글이 없습니다. 새 답글 등록을 원하시면 action='post'를 사용하세요", 
                        "error": "No existing reply to edit"
                    }
                
                result = self.edit_existing_reply(review_element, reply_text)
                result["action_taken"] = "edited" if result["success"] else "no_action"
                
            else:
                return {
                    "success": False,
                    "action_taken": "no_action",
                    "message": f"잘못된 액션: {action}",
                    "error": "Invalid action"
                }
            
            return result
            
        except Exception as e:
            error_msg = f"답글 관리 중 오류 발생: {str(e)}"
            self.logger.error(f"{error_msg}\n{traceback.format_exc()}")
            return {
                "success": False,
                "action_taken": "no_action",
                "message": error_msg,
                "error": str(e)
            }
    
    def logout(self) -> bool:
        """로그아웃"""
        try:
            if self.page:
                # 플랫폼별로 구현
                self.logger.info("로그아웃 시도")
                return True
        except Exception as e:
            self.logger.error(f"로그아웃 실패: {str(e)}")
            return False
    
    def close_browser(self) -> None:
        """브라우저 종료"""
        try:
            if self.browser:
                self.browser.close()
            if hasattr(self, 'playwright'):
                self.playwright.stop()
            self.logger.info("브라우저 종료 완료")
        except Exception as e:
            self.logger.error(f"브라우저 종료 실패: {str(e)}")
    
    def wait_for_element(self, selector: str, timeout: int = 10000) -> Optional[Any]:
        """요소 대기"""
        try:
            return self.page.wait_for_selector(selector, timeout=timeout)
        except Exception:
            return None
    
    def safe_click(self, selector: str, timeout: int = 5000) -> bool:
        """안전한 클릭"""
        try:
            element = self.page.wait_for_selector(selector, timeout=timeout)
            if element:
                element.click()
                return True
            return False
        except Exception:
            return False
    
    def safe_fill(self, selector: str, text: str, timeout: int = 5000) -> bool:
        """안전한 텍스트 입력"""
        try:
            element = self.page.wait_for_selector(selector, timeout=timeout)
            if element:
                element.clear()
                element.fill(text)
                return True
            return False
        except Exception:
            return False
    
    def __enter__(self):
        """컨텍스트 매니저 진입"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        self.close_browser()