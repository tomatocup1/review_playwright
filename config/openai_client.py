"""
OpenAI 클라이언트 설정
"""
import os
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# 전역 클라이언트 인스턴스
_openai_client = None

def get_openai_client() -> OpenAI:
    """OpenAI 클라이언트 반환 (싱글톤 패턴)"""
    global _openai_client
    
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            raise ValueError("OPENAI_API_KEY 환경변수를 설정해주세요.")
        
        if api_key.startswith('sk-') and len(api_key) < 20:
            raise ValueError("유효하지 않은 OpenAI API 키입니다.")
        
        try:
            _openai_client = OpenAI(api_key=api_key)
            logger.info("OpenAI 클라이언트 초기화 완료")
        except Exception as e:
            logger.error(f"OpenAI 클라이언트 초기화 실패: {e}")
            raise
    
    return _openai_client

def test_openai_connection() -> bool:
    """OpenAI 연결 테스트"""
    try:
        client = get_openai_client()
        # 간단한 테스트 요청
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "안녕하세요"}],
            max_tokens=10
        )
        logger.info("OpenAI 연결 테스트 성공")
        return True
    except Exception as e:
        logger.error(f"OpenAI 연결 테스트 실패: {e}")
        return False