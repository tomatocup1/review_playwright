"""
Reviews 테이블 필드 확인 및 AI 답글 시스템 구현
"""
import sys
sys.path.append(r"C:\Review_playwright")

from config.supabase_client import get_supabase_client
from datetime import datetime, timedelta
import json

# Supabase 클라이언트
supabase = get_supabase_client()

# 1. platform_reply_rules 테이블에서 설정 확인
print("=== AI 답글 설정 확인 ===")
rules_response = supabase.table('platform_reply_rules').select('*').eq('is_active', True).limit(1).execute()

if rules_response.data:
    rule = rules_response.data[0]
    print(f"\n매장: {rule['store_name']}")
    print(f"인사말 시작: {rule['greeting_start']}")
    print(f"인사말 끝: {rule['greeting_end']}")
    print(f"AI 역할: {rule['role']}")
    print(f"톤: {rule['tone']}")
    print(f"금지 단어: {rule['prohibited_words']}")
    print(f"최대 길이: {rule['max_length']}")
    print(f"\n별점별 답글 설정:")
    print(f"  5점: {rule['rating_5_reply']}")
    print(f"  4점: {rule['rating_4_reply']}")
    print(f"  3점: {rule['rating_3_reply']}")
    print(f"  2점: {rule['rating_2_reply']}")
    print(f"  1점: {rule['rating_1_reply']}")

# 2. Reviews 테이블 구조 확인을 위한 테스트 삽입
print("\n\n=== Reviews 테이블 테스트 ===")

# 날짜 변환 함수
def parse_review_date(date_str):
    """리뷰 날짜 문자열을 실제 날짜로 변환"""
    today = datetime.now().date()
    
    if date_str == '오늘':
        return today.strftime('%Y-%m-%d')
    elif date_str == '어제':
        return (today - timedelta(days=1)).strftime('%Y-%m-%d')
    elif date_str == '그제':
        return (today - timedelta(days=2)).strftime('%Y-%m-%d')
    elif '일 전' in date_str:
        days = int(date_str.replace('일 전', '').strip())
        return (today - timedelta(days=days)).strftime('%Y-%m-%d')
    elif '개월 전' in date_str:
        months = int(date_str.replace('개월 전', '').strip())
        return (today - timedelta(days=months*30)).strftime('%Y-%m-%d')
    else:
        return today.strftime('%Y-%m-%d')

# 테스트 리뷰 데이터
test_review = {
    'review_id': 'test_' + datetime.now().strftime('%Y%m%d%H%M%S'),
    'store_code': 'STR_20250607112756_854269',
    'platform': 'baemin',
    'platform_code': '14638971',
    'review_name': '테스트고객',
    'rating': 5,
    'review_content': '정말 맛있어요! 양도 많고 배달도 빨라요.',
    'ordered_menu': '(겉바속촉) 3~4인 세트/반반',
    'delivery_review': '좋아요',
    'review_date': parse_review_date('오늘'),
    'review_images': [],
    'response_status': 'pending',
    'boss_reply_needed': True,
    'review_reason': None,
    'ai_response': None,
    'manual_response': None,
    'final_response': None,
    'response_method': None,
    'response_at': None,
    'response_by': None,
    'response_quality_score': None,
    'customer_reaction': None,
    'follow_up_required': False,
    'retry_count': 0,
    'last_retry_at': None,
    'error_message': None,
    'processing_duration': None,
    'crawled_at': datetime.now().isoformat(),
    'processed_at': None,
    'is_deleted': False,
    'deleted_at': None,
    'notes': None
}

try:
    # 테스트 삽입
    insert_response = supabase.table('reviews').insert(test_review).execute()
    print("✅ 테스트 리뷰 삽입 성공")
    print(f"삽입된 데이터: {json.dumps(insert_response.data[0], indent=2, ensure_ascii=False)}")
    
    # 삭제
    delete_response = supabase.table('reviews').delete().eq('review_id', test_review['review_id']).execute()
    print("\n✅ 테스트 리뷰 삭제 완료")
    
except Exception as e:
    print(f"❌ 오류 발생: {e}")
    print(f"오류 타입: {type(e)}")
