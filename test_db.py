import asyncio
import os
from dotenv import load_dotenv
from supabase import create_client, Client
import json

load_dotenv()

# Supabase 설정
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

async def test_reviews():
    store_code = "STR_20250607112756_854269"
    
    # 리뷰 조회
    print(f"매장 {store_code}의 리뷰 조회 중...")
    try:
        response = supabase.table('reviews').select('*').eq('store_code', store_code).limit(5).execute()
        
        print(f"총 {len(response.data)}개의 리뷰를 찾았습니다.")
        
        if response.data:
            for i, review in enumerate(response.data, 1):
                print(f"\n--- 리뷰 {i} ---")
                print(f"ID: {review.get('review_id')}")
                print(f"작성자: {review.get('review_name')}")
                print(f"날짜: {review.get('review_date')}")
                print(f"별점: {review.get('rating')}")
                print(f"상태: {review.get('response_status')}")
                print(f"내용: {review.get('review_content', '')[:50]}...")
        else:
            print("리뷰가 없습니다.")
            
    except Exception as e:
        print(f"오류 발생: {e}")
        print(f"오류 타입: {type(e)}")
        
# 실행
if __name__ == "__main__":
    asyncio.run(test_reviews())
