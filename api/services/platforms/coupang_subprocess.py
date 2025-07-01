import asyncio
import json
import sys
import os
from pathlib import Path
import logging
from datetime import datetime

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# 절대 경로로 import
try:
    from api.crawlers.reply_managers.coupang_reply_manager import CoupangReplyManager
except ImportError:
    # 대체 경로 시도
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from crawlers.reply_managers.coupang_reply_manager import CoupangReplyManager

# 로깅 설정
log_dir = Path(project_root) / "logs"
log_dir.mkdir(exist_ok=True)

# 파일 핸들러만 사용 (콘솔 출력 제거)
file_handler = logging.FileHandler(log_dir / 'coupang_reply_subprocess.log', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)

async def main():
    """서브프로세스 메인 함수"""
    try:
        logger.info("="*50)
        logger.info("쿠팡 답글 등록 서브프로세스 시작")
        logger.info(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*50)
        
        # 커맨드 라인 인자로부터 데이터 받기
        if len(sys.argv) < 2:
            logger.error("No data provided")
            print(json.dumps({
                'success': False,
                'message': 'No data provided to subprocess',
                'error': 'Missing argument'
            }))
            sys.exit(1)
            
        # JSON 데이터 파싱
        try:
            data = json.loads(sys.argv[1])
            logger.info(f"입력 데이터 파싱 성공")
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 오류: {str(e)}")
            print(json.dumps({
                'success': False,
                'message': 'Invalid JSON data',
                'error': str(e)
            }))
            sys.exit(1)
        
        store_info = data.get('store_info', {})
        review_data = data.get('review_data', {})
        
        # 필수 정보 확인
        required_store_fields = ['platform_id', 'platform_pw', 'platform_code', 'store_code']
        for field in required_store_fields:
            if not store_info.get(field):
                error_msg = f"필수 매장 정보 누락: {field}"
                logger.error(error_msg)
                print(json.dumps({
                    'success': False,
                    'message': error_msg,
                    'error': 'Missing required field'
                }))
                sys.exit(1)
        
        logger.info(f"Starting reply process for store: {store_info.get('store_code')}")
        logger.info(f"Platform code: {store_info.get('platform_code')}")
        logger.info(f"Review ID: {review_data.get('review_id')}")
        logger.info(f"Review content length: {len(review_data.get('review_content', ''))} chars")
        logger.info(f"Reply content length: {len(review_data.get('reply_content', ''))} chars")
        
        # CoupangReplyManager 인스턴스 생성
        try:
            reply_manager = CoupangReplyManager(store_info)
            logger.info("CoupangReplyManager 인스턴스 생성 성공")
        except Exception as e:
            error_msg = f"CoupangReplyManager 생성 실패: {str(e)}"
            logger.error(error_msg)
            print(json.dumps({
                'success': False,
                'message': error_msg,
                'error': str(e)
            }))
            sys.exit(1)
        
        # 답글 등록 실행
        logger.info("답글 등록 프로세스 시작...")
        success, message = await reply_manager.post_reply(review_data)
        
        # 결과 처리
        if success:
            logger.info(f"✅ 답글 등록 성공: {message}")
            result = {
                'success': True,
                'message': message,
                'review_id': review_data.get('review_id')
            }
        else:
            logger.error(f"❌ 답글 등록 실패: {message}")
            result = {
                'success': False,
                'message': message,
                'error': message,
                'review_id': review_data.get('review_id')
            }
        
        # 결과 출력 (부모 프로세스에서 읽을 수 있도록)
        output_json = json.dumps(result, ensure_ascii=False)
        print(output_json)
        
        logger.info("="*50)
        logger.info(f"쿠팡 답글 등록 서브프로세스 종료")
        logger.info(f"종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"결과: {'성공' if success else '실패'}")
        logger.info("="*50)
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        logger.error(f"💥 Subprocess error: {str(e)}", exc_info=True)
        result = {
            'success': False,
            'message': f"Subprocess error: {str(e)}",
            'error': str(e),
            'review_id': review_data.get('review_id', 'unknown') if 'review_data' in locals() else 'unknown'
        }
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    # Windows 환경에서 UTF-8 설정
    if sys.platform == 'win32':
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        # Windows에서 ProactorEventLoop 사용 (subprocess 지원)
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # nest_asyncio 설치되어 있으면 사용
    try:
        import nest_asyncio
        nest_asyncio.apply()
    except ImportError:
        pass
    
    asyncio.run(main())