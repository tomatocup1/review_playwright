"""
Supabase 클라이언트 설정
"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def get_supabase_client() -> Client:
    """Supabase 클라이언트 인스턴스 반환"""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    
    if not url or not key:
        raise ValueError("SUPABASE_URL과 SUPABASE_ANON_KEY 환경변수를 설정해주세요.")
    
    return create_client(url, key)
