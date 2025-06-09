"""
배민 답글 등록을 위한 subprocess 실행 스크립트
async 충돌을 피하기 위해 별도 프로세스에서 실행
"""
import sys
import json
import logging
from api.crawlers.baemin_reply_manager import BaeminReplyManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """메인 함수"""
    if len(sys.argv) < 4:
        print(json.dumps({"error": "Invalid arguments"}))
        return
    
    try:
        # 인자 파싱
        store_config = json.loads(sys.argv[1])
        review_id = sys.argv[2]
        reply_content = sys.argv[3]
        
        logger.info(f"배민 답글 등록 시작: review_id={review_id}")
        
        # BaeminReplyManager 인스턴스 생성
        reply_manager = BaeminReplyManager(store_config)
        
        # 브라우저 설정 및 초기화
        browser_setup = reply_manager.setup_browser(headless=True)
        if not browser_setup:
            print(json.dumps({
                'success': False,
                'error': '브라우저 초기화 실패',
                'review_id': review_id,
                'platform': 'baemin'
            }))
            return
        
        try:
            # 로그인
            login_success, login_message = reply_manager.login_to_platform()
            if not login_success:
                print(json.dumps({
                    'success': False,
                    'error': f'로그인 실패: {login_message}',
                    'review_id': review_id,
                    'platform': 'baemin'
                }))
                return
            
            # 리뷰 관리 페이지로 이동
            nav_success, nav_message = reply_manager.navigate_to_reviews_page()
            if not nav_success:
                print(json.dumps({
                    'success': False,
                    'error': f'리뷰 페이지 이동 실패: {nav_message}',
                    'review_id': review_id,
                    'platform': 'baemin'
                }))
                return
            
            # 답글 등록 수행
            reply_result = reply_manager.manage_reply(
                review_id=review_id,
                reply_text=reply_content,
                action="auto"
            )
            
            if reply_result['success']:
                print(json.dumps({
                    'success': True,
                    'review_id': review_id,
                    'platform': 'baemin',
                    'store_name': store_config.get('store_name', ''),
                    'final_status': 'posted',
                    'action_taken': reply_result.get('action_taken', 'posted'),
                    'message': reply_result.get('message', '답글 등록 성공')
                }))
            else:
                print(json.dumps({
                    'success': False,
                    'error': reply_result.get('message', '답글 등록 실패'),
                    'review_id': review_id,
                    'platform': 'baemin',
                    'error_details': reply_result
                }))
                
        finally:
            reply_manager.close_browser()
            
    except Exception as e:
        print(json.dumps({
            'success': False,
            'error': f'답글 등록 중 오류: {str(e)}',
            'review_id': review_id if 'review_id' in locals() else 'unknown',
            'platform': 'baemin'
        }))

if __name__ == "__main__":
    main()
