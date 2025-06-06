"""
FastAPI 서버 실행 스크립트
"""
import uvicorn
import logging
from datetime import datetime
import os

# 로깅 설정
log_dir = "C:/Review_playwright/logs"
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, f"server_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("리뷰 자동화 서버 시작...")
    
    # Uvicorn 설정
    config = uvicorn.Config(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        # 워커 프로세스 설정
        workers=1,  # 개발 환경에서는 1로 설정
        # 연결 제한 설정
        limit_concurrency=100,
        limit_max_requests=1000,
        # 타임아웃 설정
        timeout_keep_alive=5,
        timeout_notify=60,
        # 우아한 종료
        timeout_graceful_shutdown=30,
    )
    
    server = uvicorn.Server(config)
    
    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("서버 종료 요청...")
    except Exception as e:
        logger.error(f"서버 오류: {str(e)}")
    finally:
        logger.info("서버 종료")
