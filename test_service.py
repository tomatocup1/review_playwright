import asyncio
from api.services.supabase_service import SupabaseService
from api.schemas.auth import User

async def test_get_reviews():
    supabase = SupabaseService()
    
    # 테스트 사용자 (TST001)
    test_user = User(
        user_code="TST001",
        email="test.owner@example.com",
        name="테스트사장님",
        role="owner",
        email_verified=True,
        is_active=True,
        phone_verified=False,
        login_count=0,
        created_at="2025-01-01T00:00:00"
    )
    
    store_code = "STR_20250607112756_854269"
    
    print(f"매장 {store_code}의 리뷰 조회 테스트...")
    
    try:
        # 권한 확인
        has_permission = await supabase.check_user_permission(
            test_user.user_code,
            store_code,
            'view'
        )
        print(f"권한 확인 결과: {has_permission}")
        
        # 리뷰 조회
        reviews = await supabase.get_reviews_by_store(
            store_code=store_code,
            status=None,
            rating=None,
            limit=20,
            offset=0
        )
        
        print(f"리뷰 조회 성공! 총 {len(reviews)}개")
        for i, review in enumerate(reviews[:3], 1):
            print(f"\n리뷰 {i}:")
            print(f"  ID: {review.get('review_id')}")
            print(f"  작성자: {review.get('review_name')}")
            print(f"  내용: {review.get('review_content', '')[:50]}...")
            
    except Exception as e:
        print(f"오류 발생: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_get_reviews())
