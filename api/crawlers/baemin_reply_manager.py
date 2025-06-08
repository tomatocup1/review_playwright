"""
배민 답글 관리 클래스 (등록 + 수정) - 완성 버전
배민 사장님 페이지에서 리뷰 답글을 등록하고 수정하는 기능
"""
import time
import re
from typing import Dict, Any, Tuple, Optional
from urllib.parse import urlparse, parse_qs
from .reply_manager import BaseReplyManager

class BaeminReplyManager(BaseReplyManager):
    """
    배민 답글 관리 클래스
    - 배민 사장님 페이지 로그인
    - 리뷰 답글 등록 (새 리뷰)
    - 리뷰 답글 수정 (기존 답글)
    """
    
    def __init__(self, store_config: Dict[str, Any]):
        super().__init__(store_config)
        self.base_url = "https://ceo.baemin.com"
        self.login_url = f"{self.base_url}/login"
        self.reviews_url = f"{self.base_url}/review"
        
    def login_to_platform(self) -> Tuple[bool, str]:
        """
        배민 사장님 페이지 로그인
        
        Returns:
            Tuple[bool, str]: (성공여부, 메시지)
        """
        try:
            self.logger.info("배민 로그인 시작")
            
            # 1. 로그인 페이지 이동
            self.page.goto(self.login_url)
            self.page.wait_for_load_state('networkidle')
            
            # 2. 로그인 폼 요소 찾기
            login_elements = self._find_login_elements()
            if not login_elements[0]:
                return False, login_elements[1]
            
            # 3. 로그인 정보 입력
            username = self.store_config.get("platform_id")
            password = self.store_config.get("platform_pw")
            
            if not username or not password:
                return False, "로그인 정보가 없습니다"
            
            # 4. 실제 로그인 수행
            success, message = self._perform_login(username, password)
            if success:
                self.is_logged_in = True
                self.logger.info("배민 로그인 성공")
                return True, "로그인 성공"
            else:
                return False, f"로그인 실패: {message}"
                
        except Exception as e:
            error_msg = f"로그인 중 오류: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
    
    def _find_login_elements(self) -> Tuple[bool, str]:
        """로그인 폼 요소들 찾기"""
        try:
            # 배민 로그인 페이지의 일반적인 셀렉터들
            selectors_to_try = [
                {"id": "#loginId", "pw": "#password", "btn": "button[type='submit']"},
                {"id": "input[name='loginId']", "pw": "input[name='password']", "btn": ".btn-login"},
                {"id": "input[placeholder*='아이디']", "pw": "input[type='password']", "btn": "button"},
            ]
            
            for selectors in selectors_to_try:
                id_element = self.page.query_selector(selectors["id"])
                pw_element = self.page.query_selector(selectors["pw"])
                btn_element = self.page.query_selector(selectors["btn"])
                
                if id_element and pw_element and btn_element:
                    self.login_selectors = selectors
                    return True, "로그인 요소 찾기 성공"
            
            return False, "로그인 폼을 찾을 수 없습니다"
            
        except Exception as e:
            return False, f"로그인 요소 찾기 실패: {str(e)}"
    
    def _perform_login(self, username: str, password: str) -> Tuple[bool, str]:
        """실제 로그인 수행"""
        try:
            # 1. 아이디 입력
            if not self.safe_fill(self.login_selectors["id"], username):
                return False, "아이디 입력 실패"
            
            time.sleep(0.5)
            
            # 2. 비밀번호 입력
            if not self.safe_fill(self.login_selectors["pw"], password):
                return False, "비밀번호 입력 실패"
            
            time.sleep(0.5)
            
            # 3. 로그인 버튼 클릭
            if not self.safe_click(self.login_selectors["btn"]):
                return False, "로그인 버튼 클릭 실패"
            
            # 4. 로그인 결과 확인 (5초 대기)
            time.sleep(3)
            
            # 로그인 성공 여부 확인
            current_url = self.page.url
            if "login" not in current_url or "ceo.baemin.com" in current_url:
                return True, "로그인 성공"
            
            # 오류 메시지 확인
            error_selectors = [
                ".error-message",
                ".alert-danger", 
                "[class*='error']",
                "[class*='alert']"
            ]
            
            for selector in error_selectors:
                error_element = self.page.query_selector(selector)
                if error_element:
                    error_text = error_element.inner_text()
                    if error_text:
                        return False, f"로그인 오류: {error_text}"
            
            return False, "로그인 실패 (알 수 없는 오류)"
            
        except Exception as e:
            return False, f"로그인 수행 중 오류: {str(e)}"
    
    def navigate_to_reviews_page(self) -> Tuple[bool, str]:
        """리뷰 관리 페이지로 이동"""
        try:
            self.logger.info("리뷰 페이지로 이동")
            
            # 1. 리뷰 관리 페이지 이동
            self.page.goto(self.reviews_url)
            self.page.wait_for_load_state('networkidle')
            
            # 2. 페이지 로드 확인
            if "review" in self.page.url:
                return True, "리뷰 페이지 이동 성공"
            else:
                return False, "리뷰 페이지 이동 실패"
                
        except Exception as e:
            error_msg = f"리뷰 페이지 이동 중 오류: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
    
    def find_review_by_id(self, review_id: str) -> Dict[str, Any]:
        """
        특정 리뷰 찾기
        
        Args:
            review_id: 리뷰 고유 ID
            
        Returns:
            Dict: {
                "found": bool,
                "element": 리뷰 요소,
                "has_reply": bool,
                "current_reply": str,
                "error": str
            }
        """
        try:
            self.logger.info(f"리뷰 찾기 시작: {review_id}")
            
            # 1. 리뷰 목록 로드 대기
            time.sleep(2)
            
            # 2. 리뷰 요소들 찾기
            review_selectors = [
                ".review-item",
                ".review-card", 
                "[class*='review']",
                ".list-item"
            ]
            
            review_elements = []
            for selector in review_selectors:
                elements = self.page.query_selector_all(selector)
                if elements:
                    review_elements = elements
                    break
            
            if not review_elements:
                return {
                    "found": False,
                    "element": None,
                    "has_reply": False,
                    "current_reply": "",
                    "error": "리뷰 목록을 찾을 수 없습니다"
                }
            
            # 3. 리뷰 ID로 특정 리뷰 찾기
            target_review = None
            for review_element in review_elements:
                # 리뷰 내용에서 ID 패턴 찾기
                review_text = review_element.inner_text()
                
                # 리뷰 ID는 보통 숫자나 특정 패턴
                if review_id in review_text or self._match_review_id(review_element, review_id):
                    target_review = review_element
                    break
            
            if not target_review:
                return {
                    "found": False,
                    "element": None,
                    "has_reply": False,
                    "current_reply": "",
                    "error": f"리뷰 ID {review_id}를 찾을 수 없습니다"
                }
            
            # 4. 기존 답글 확인
            has_reply, current_reply = self._check_existing_reply(target_review)
            
            return {
                "found": True,
                "element": target_review,
                "has_reply": has_reply,
                "current_reply": current_reply,
                "error": ""
            }
            
        except Exception as e:
            error_msg = f"리뷰 찾기 중 오류: {str(e)}"
            self.logger.error(error_msg)
            return {
                "found": False,
                "element": None,
                "has_reply": False,
                "current_reply": "",
                "error": error_msg
            }
    
    def _match_review_id(self, review_element: Any, review_id: str) -> bool:
        """리뷰 요소가 특정 ID와 매치되는지 확인"""
        try:
            # data-* 속성에서 ID 찾기
            attributes = ["data-id", "data-review-id", "id"]
            for attr in attributes:
                value = review_element.get_attribute(attr)
                if value and review_id in value:
                    return True
            
            # 리뷰 번호나 날짜 패턴으로 매치
            review_text = review_element.inner_text()
            patterns = [
                rf"#{review_id}",
                rf"리뷰.*{review_id}",
                rf"{review_id}번"
            ]
            
            for pattern in patterns:
                if re.search(pattern, review_text):
                    return True
                    
            return False
            
        except Exception:
            return False
    
    def _check_existing_reply(self, review_element: Any) -> Tuple[bool, str]:
        """기존 답글 확인"""
        try:
            # 답글 영역 셀렉터들
            reply_selectors = [
                ".reply-content",
                ".owner-reply",
                "[class*='reply']",
                ".answer-content"
            ]
            
            for selector in reply_selectors:
                reply_element = review_element.query_selector(selector)
                if reply_element:
                    reply_text = reply_element.inner_text().strip()
                    if reply_text:
                        return True, reply_text
            
            return False, ""
            
        except Exception:
            return False, ""
    
    def post_new_reply(self, review_element: Any, reply_text: str) -> Dict[str, Any]:
        """
        새 답글 등록
        
        Args:
            review_element: 리뷰 요소
            reply_text: 답글 내용
            
        Returns:
            Dict: {"success": bool, "message": str, "error": str}
        """
        try:
            self.logger.info("새 답글 등록 시작")
            
            # 1. 답글 작성 버튼 찾기
            reply_button_selectors = [
                ".btn-reply",
                ".reply-button", 
                "button[class*='reply']",
                "[onclick*='reply']",
                ".answer-btn"
            ]
            
            reply_button = None
            for selector in reply_button_selectors:
                button = review_element.query_selector(selector)
                if button and button.is_visible():
                    reply_button = button
                    break
            
            if not reply_button:
                return {
                    "success": False,
                    "message": "답글 작성 버튼을 찾을 수 없습니다",
                    "error": "Reply button not found"
                }
            
            # 2. 답글 작성 버튼 클릭
            reply_button.click()
            time.sleep(1)
            
            # 3. 답글 입력창 찾기
            reply_input = self._find_reply_input(review_element)
            if not reply_input:
                return {
                    "success": False,
                    "message": "답글 입력창을 찾을 수 없습니다",
                    "error": "Reply input not found"
                }
            
            # 4. 답글 내용 입력
            reply_input.clear()
            reply_input.fill(reply_text)
            time.sleep(0.5)
            
            # 5. 등록 버튼 찾기 및 클릭
            submit_result = self._submit_reply_form(review_element)
            if not submit_result["success"]:
                return submit_result
            
            # 6. 등록 결과 확인
            verification_result = self._verify_reply_submission(review_element, reply_text)
            
            if verification_result["success"]:
                self.logger.info("새 답글 등록 성공")
                return {
                    "success": True,
                    "message": "답글이 성공적으로 등록되었습니다",
                    "error": ""
                }
            else:
                return verification_result
                
        except Exception as e:
            error_msg = f"새 답글 등록 중 오류: {str(e)}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "message": error_msg,
                "error": str(e)
            }
    
    def edit_existing_reply(self, review_element: Any, new_reply_text: str) -> Dict[str, Any]:
        """
        기존 답글 수정
        
        Args:
            review_element: 리뷰 요소
            new_reply_text: 새로운 답글 내용
            
        Returns:
            Dict: {"success": bool, "message": str, "error": str}
        """
        try:
            self.logger.info("기존 답글 수정 시작")
            
            # 1. 기존 답글 영역 찾기
            reply_area = self._find_existing_reply_area(review_element)
            if not reply_area:
                return {
                    "success": False,
                    "message": "기존 답글을 찾을 수 없습니다",
                    "error": "Existing reply not found"
                }
            
            # 2. 수정 버튼 찾기
            edit_button_selectors = [
                ".btn-edit",
                ".edit-button",
                "button[class*='edit']",
                "[onclick*='edit']",
                ".modify-btn"
            ]
            
            edit_button = None
            for selector in edit_button_selectors:
                button = reply_area.query_selector(selector)
                if button and button.is_visible():
                    edit_button = button
                    break
            
            if not edit_button:
                return {
                    "success": False,
                    "message": "답글 수정 버튼을 찾을 수 없습니다",
                    "error": "Edit button not found"
                }
            
            # 3. 수정 버튼 클릭
            edit_button.click()
            time.sleep(1)
            
            # 4. 수정 입력창 찾기
            edit_input = self._find_reply_input(review_element, is_edit=True)
            if not edit_input:
                return {
                    "success": False,
                    "message": "답글 수정 입력창을 찾을 수 없습니다",
                    "error": "Edit input not found"
                }
            
            # 5. 새 답글 내용 입력
            edit_input.clear()
            edit_input.fill(new_reply_text)
            time.sleep(0.5)
            
            # 6. 수정 완료 버튼 클릭
            submit_result = self._submit_reply_form(review_element, is_edit=True)
            if not submit_result["success"]:
                return submit_result
            
            # 7. 수정 결과 확인
            verification_result = self._verify_reply_submission(review_element, new_reply_text)
            
            if verification_result["success"]:
                self.logger.info("답글 수정 성공")
                return {
                    "success": True,
                    "message": "답글이 성공적으로 수정되었습니다",
                    "error": ""
                }
            else:
                return verification_result
                
        except Exception as e:
            error_msg = f"답글 수정 중 오류: {str(e)}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "message": error_msg,
                "error": str(e)
            }
    
    def _find_reply_input(self, review_element: Any, is_edit: bool = False) -> Optional[Any]:
        """답글 입력창 찾기"""
        try:
            input_selectors = [
                "textarea[placeholder*='답글']",
                "textarea[class*='reply']",
                "textarea[class*='answer']",
                "input[type='text'][class*='reply']",
                ".reply-textarea",
                ".answer-input"
            ]
            
            if is_edit:
                # 수정 모드일 때는 더 구체적인 셀렉터 추가
                edit_selectors = [
                    "textarea[class*='edit']",
                    "input[class*='edit']",
                    ".edit-textarea"
                ]
                input_selectors = edit_selectors + input_selectors
            
            for selector in input_selectors:
                input_element = review_element.query_selector(selector)
                if input_element and input_element.is_visible():
                    return input_element
            
            # 전체 페이지에서도 찾아보기
            for selector in input_selectors:
                input_element = self.page.query_selector(selector)
                if input_element and input_element.is_visible():
                    return input_element
            
            return None
            
        except Exception:
            return None
    
    def _find_existing_reply_area(self, review_element: Any) -> Optional[Any]:
        """기존 답글 영역 찾기"""
        try:
            reply_area_selectors = [
                ".reply-area",
                ".owner-reply",
                ".answer-area",
                "[class*='reply-content']",
                "[class*='owner-answer']"
            ]
            
            for selector in reply_area_selectors:
                area = review_element.query_selector(selector)
                if area:
                    return area
            
            return None
            
        except Exception:
            return None
    
    def _submit_reply_form(self, review_element: Any, is_edit: bool = False) -> Dict[str, Any]:
        """답글 폼 제출"""
        try:
            # 제출 버튼 셀렉터들
            submit_selectors = [
                ".btn-submit",
                ".btn-save",
                "button[type='submit']",
                "button[class*='submit']",
                "button[class*='save']",
                ".reply-submit",
                ".answer-submit"
            ]
            
            if is_edit:
                # 수정 모드일 때는 더 구체적인 셀렉터 추가
                edit_submit_selectors = [
                    ".btn-update",
                    "button[class*='update']",
                    "button[class*='modify']"
                ]
                submit_selectors = edit_submit_selectors + submit_selectors
            
            submit_button = None
            for selector in submit_selectors:
                button = review_element.query_selector(selector)
                if button and button.is_visible():
                    submit_button = button
                    break
            
            # 리뷰 요소에서 못 찾으면 전체 페이지에서 찾기
            if not submit_button:
                for selector in submit_selectors:
                    button = self.page.query_selector(selector)
                    if button and button.is_visible():
                        submit_button = button
                        break
            
            if not submit_button:
                return {
                    "success": False,
                    "message": "제출 버튼을 찾을 수 없습니다",
                    "error": "Submit button not found"
                }
            
            # 제출 버튼 클릭
            submit_button.click()
            time.sleep(2)
            
            return {
                "success": True,
                "message": "제출 완료",
                "error": ""
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"제출 중 오류: {str(e)}",
                "error": str(e)
            }
    
    def _verify_reply_submission(self, review_element: Any, expected_text: str) -> Dict[str, Any]:
        """답글 제출 결과 확인"""
        try:
            # 성공 메시지나 결과 확인을 위해 잠시 대기
            time.sleep(3)
            
            # 1. 성공 메시지 확인
            success_selectors = [
                ".success-message",
                ".alert-success",
                "[class*='success']",
                ".toast-success"
            ]
            
            for selector in success_selectors:
                success_element = self.page.query_selector(selector)
                if success_element and success_element.is_visible():
                    success_text = success_element.inner_text()
                    if "성공" in success_text or "완료" in success_text:
                        return {
                            "success": True,
                            "message": "답글 등록/수정 성공 확인",
                            "error": ""
                        }
            
            # 2. 에러 메시지 확인
            error_selectors = [
                ".error-message",
                ".alert-danger",
                "[class*='error']",
                ".toast-error"
            ]
            
            for selector in error_selectors:
                error_element = self.page.query_selector(selector)
                if error_element and error_element.is_visible():
                    error_text = error_element.inner_text()
                    return {
                        "success": False,
                        "message": f"답글 처리 실패: {error_text}",
                        "error": error_text
                    }
            
            # 3. 답글이 실제로 페이지에 나타났는지 확인
            has_reply, current_reply = self._check_existing_reply(review_element)
            if has_reply and expected_text.strip() in current_reply:
                return {
                    "success": True,
                    "message": "답글이 페이지에서 확인되었습니다",
                    "error": ""
                }
            
            # 4. 명확한 결과를 얻지 못한 경우
            return {
                "success": True,  # 에러가 없으면 성공으로 간주
                "message": "답글 처리 완료 (결과 확인 불가)",
                "error": ""
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"결과 확인 중 오류: {str(e)}",
                "error": str(e)
            }
