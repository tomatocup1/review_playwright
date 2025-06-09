"""
배민 답글 등록을 위한 subprocess 실행 스크립트
"""
import sys
import json
import os
import logging
from typing import Dict, Any

# 환경 변수 설정
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.expanduser("~") + r"\AppData\Local\ms-playwright"

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_baemin_reply(params: Dict[str, Any]) -> Dict[str, Any]:
    """배민 답글 등록 실행"""
    try:
        from api.crawlers.baemin_reply_manager import BaeminReplyManager
        
        store_config = params['store_config']
        review_id = params['review_id']
        reply_content = params['reply_content']
        
        logger.info(f"배민 답글 등록 프로세스 시작: review_id={review_id}")
        
        # BaeminReplyManager 인스턴스 생성
        reply_manager = BaeminReplyManager(store_config)
        
        # 브라우저 설정 및 초기화
        browser_setup = reply_manager.setup_browser(headless=True)  # headless 모드로 실행
        if not browser_setup:
            return {
                'success': False,
                'error': '브라우저 초기화 실패',
                'review_id': review_id,
                'platform': 'baemin'
            }
        
        try:
            # 로그인
            login_success, login_message = reply_manager.login_to_platform()
            if not login_success:
                return {
                    'success': False,
                    'error': f'로그인 실패: {login_message}',
                    'review_id': review_id,
                    'platform': 'baemin'
                }
            
            # 리뷰 관리 페이지로 이동
            nav_success, nav_message = reply_manager.navigate_to_reviews_page()
            if not nav_success:
                return {
                    'success': False,
                    'error': f'리뷰 페이지 이동 실패: {nav_message}',
                    'review_id': review_id,
                    'platform': 'baemin'
                }
            
            # 답글 등록 수행
            reply_result = reply_manager.manage_reply(
                review_id=review_id,
                reply_text=reply_content,
                action="auto"
            )
            
            if reply_result['success']:
                return {
                    'success': True,
                    'review_id': review_id,
                    'platform': 'baemin',
                    'store_name': store_config.get('store_name', ''),
                    'final_status': 'posted',
                    'action_taken': reply_result.get('action_taken', 'posted'),
                    'message': reply_result.get('message', '답글 등록 성공')
                }
            else:
                return {
                    'success': False,
                    'error': reply_result.get('message', '답글 등록 실패'),
                    'review_id': review_id,
                    'platform': 'baemin',
                    'error_details': reply_result
                }
                
        finally:
            # 브라우저 정리
            reply_manager.close_browser()
            
    except Exception as e:
        logger.error(f"배민 답글 등록 중 오류: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'success': False,
            'error': f'프로세스 실행 중 오류: {str(e)}',
            'review_id': params.get('review_id', 'unknown'),
            'platform': 'baemin',
            'error_details': {
                'exception': str(e),
                'type': type(e).__name__
            }
        }

def main():
    """메인 함수 - stdin으로 파라미터 받아 실행"""
    try:
        # stdin으로 JSON 파라미터 받기
        input_data = sys.stdin.read()
        params = json.loads(input_data)
        
        # 답글 등록 실행
        result = run_baemin_reply(params)
        
        # 결과를 JSON으로 출력
        print(json.dumps(result, ensure_ascii=False))
        
    except Exception as e:
        error_result = {
            'success': False,
            'error': f'파라미터 파싱 오류: {str(e)}',
            'platform': 'baemin'
        }
        print(json.dumps(error_result, ensure_ascii=False))

if __name__ == "__main__":
    main()
