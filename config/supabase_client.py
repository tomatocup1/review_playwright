"""
Supabase 클라이언트 설정
"""
import os
import logging
from supabase import create_client, Client
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

logger = logging.getLogger(__name__)

_supabase_client: Optional[Client] = None

def get_supabase_client() -> Client:
    """Supabase 클라이언트 인스턴스 반환 (싱글톤)"""
    global _supabase_client
    
    if _supabase_client is not None:
        return _supabase_client
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    
    if not url or not key:
        logger.error("Supabase 환경변수가 설정되지 않았습니다")
        raise ValueError("SUPABASE_URL과 SUPABASE_ANON_KEY 환경변수를 설정해주세요.")
    
    try:
        _supabase_client = create_client(url, key)
        logger.info("Supabase 클라이언트 초기화 성공")
        return _supabase_client
    except Exception as e:
        logger.error(f"Supabase 클라이언트 생성 실패: {str(e)}")
        raise

def reset_supabase_client():
    """Supabase 클라이언트 리셋 (연결 문제 해결용)"""
    global _supabase_client
    _supabase_client = None
    logger.info("Supabase 클라이언트 리셋")
    return create_client(url, key)
