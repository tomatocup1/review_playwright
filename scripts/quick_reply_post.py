"""
답글 등록만 즉시 실행하는 간단한 스크립트
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.main import post_replies_batch_job
from api.services.reply_posting_service import ReplyPostingService
from api.services.supabase_service import get_supabase_service

async def main():
    print("답글 등록 작업 시작...")
    
    # 서비스 초기화
    supabase = get_supabase_service()
    reply_service = ReplyPostingService(supabase)
    
    # 답글 등록 작업 실행
    await post_replies_batch_job(reply_service)
    
    print("답글 등록 작업 완료!")

if __name__ == "__main__":
    asyncio.run(main())