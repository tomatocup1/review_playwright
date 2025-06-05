"""
OpenAI 클라이언트 설정
"""
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def get_openai_client() -> OpenAI:
    """OpenAI 클라이언트 인스턴스 반환"""
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        raise ValueError("OPENAI_API_KEY 환경변수를 설정해주세요.")
    
    return OpenAI(api_key=api_key)
