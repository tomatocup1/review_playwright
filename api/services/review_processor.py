"""
리뷰 수집 및 AI 답글 통합 시스템
"""
import sys
sys.path.append(r"C:\Review_playwright")

from datetime import datetime, timedelta
from typing import Dict, Any, List
import json

from config.supabase_client import get_supabase_client
from api.services.ai_reply_service import AIReplyGenerator


class ReviewProcessor:
    """리뷰 처리 및 AI 답글 생성 클래스"""
    
    def __init__(self):
        self.supabase = get_supabase_client()
        self.ai_generator = None
        
        # OpenAI API 키가 있을 때만 AI 생성기 초기화
        try:
            self.ai_generator = AIReplyGenerator()
        except ValueError as e:
            print(f"[경고] AI 답글 생성기 비활성화: {e}")
    
    def parse_review_date(self, date_str: str) -> str:
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
            # 기본값은 오늘
            return today.strftime('%Y-%m-%d')
    
    def clean_review_name(self, raw_name: str) -> str:
        """리뷰 작성자명 정제"""
        # 긴 텍스트에서 실제 작성자명만 추출
        # 예: "소워닝오늘완존 맛있어요..." -> "소워닝"
        
        # 날짜 키워드 제거
        for keyword in ['오늘', '어제', '그제', '일 전', '개월 전']:
            if keyword in raw_name:
                name = raw_name.split(keyword)[0].strip()
                return name[:20]  # 최대 20자
        
        # 기타 키워드로 분리
        for keyword in ['주문메뉴', '배달리뷰', '사장님']:
            if keyword in raw_name:
                name = raw_name.split(keyword)[0].strip()
                return name[:20]
        
        # 첫 10자만 반환
        return raw_name[:10]
    
    def save_reviews_to_supabase(self, reviews: List[Dict[str, Any]], store_info: Dict[str, Any]) -> Dict[str, int]:
        """리뷰를 Supabase에 저장"""
        saved_count = 0
        failed_count = 0
        
        for review in reviews:
            try:
                # 리뷰 데이터 정제
                review_data = {
                    'review_id': review['review_id'],
                    'store_code': review['store_code'],
                    'platform': review['platform'],
                    'platform_code': review['platform_code'],
                    'review_name': self.clean_review_name(review['review_name']),
                    'rating': review['rating'],
                    'review_content': review.get('review_content', ''),
                    'ordered_menu': review.get('ordered_menu', ''),
                    'delivery_review': review.get('delivery_review', ''),
                    'review_date': self.parse_review_date(review.get('review_date', '오늘')),
                    'review_images': review.get('review_images', []),
                    'response_status': 'pending',
                    'boss_reply_needed': review.get('writableComment', True),
                    'has_reply': review.get('has_reply', False),
                    'crawled_at': datetime.now().isoformat(),
                    'is_deleted': False
                }
                
                # 중복 체크
                existing = self.supabase.table('reviews').select('*').eq('review_id', review_data['review_id']).execute()
                
                if not existing.data:
                    # 새 리뷰 저장
                    insert_response = self.supabase.table('reviews').insert(review_data).execute()
                    print(f"[저장] {review_data['review_name']} - {review_data['rating']}점")
                    saved_count += 1
                    
                    # AI 답글 생성 (자동 답글이 활성화된 경우)
                    if self.should_generate_ai_reply(store_info, review_data):
                        self.generate_and_save_ai_reply(review_data, store_info)
                else:
                    print(f"[중복] {review_data['review_name']} - 이미 존재하는 리뷰")
                    
            except Exception as e:
                print(f"[오류] 리뷰 저장 실패: {e}")
                failed_count += 1
        
        return {
            'total': len(reviews),
            'saved': saved_count,
            'failed': failed_count
        }
    
    def should_generate_ai_reply(self, store_info: Dict[str, Any], review: Dict[str, Any]) -> bool:
        """AI 답글을 생성해야 하는지 확인"""
        # AI 생성기가 없으면 False
        if not self.ai_generator:
            return False
        
        # 자동 답글이 비활성화되어 있으면 False
        if not store_info.get('auto_reply_enabled', True):
            return False
        
        # 이미 답글이 있으면 False
        if review.get('has_reply'):
            return False
        
        # 답글 작성이 불가능하면 False
        if not review.get('boss_reply_needed', True):
            return False
        
        # 운영 시간 확인
        auto_reply_hours = store_info.get('auto_reply_hours', '10:00-20:00')
        if auto_reply_hours and not self.is_within_operating_hours(auto_reply_hours):
            print(f"[정보] 자동 답글 운영 시간이 아닙니다: {auto_reply_hours}")
            return False
        
        # 별점별 답글 설정 확인
        rating = review.get('rating', 5)
        rating_key = f'rating_{rating}_reply'
        if not store_info.get(rating_key, True):
            print(f"[정보] {rating}점 리뷰에 대한 자동 답글이 비활성화되어 있습니다")
            return False
        
        return True
    
    def is_within_operating_hours(self, hours_str: str) -> bool:
        """현재 시간이 운영 시간 내인지 확인"""
        try:
            start_str, end_str = hours_str.split('-')
            start_hour = int(start_str.split(':')[0])
            start_min = int(start_str.split(':')[1])
            end_hour = int(end_str.split(':')[0])
            end_min = int(end_str.split(':')[1])
            
            now = datetime.now()
            current_minutes = now.hour * 60 + now.minute
            start_minutes = start_hour * 60 + start_min
            end_minutes = end_hour * 60 + end_min
            
            return start_minutes <= current_minutes <= end_minutes
        except:
            return True  # 파싱 실패시 True 반환
    
    def generate_and_save_ai_reply(self, review: Dict[str, Any], store_info: Dict[str, Any]) -> bool:
        """AI 답글 생성 및 저장"""
        try:
            print(f"\n[AI] {review['review_name']}님의 리뷰에 대한 답글 생성 중...")
            
            # platform_reply_rules에서 답글 규칙 가져오기
            reply_rules = {
                'greeting_start': store_info.get('greeting_start', '안녕하세요'),
                'greeting_end': store_info.get('greeting_end'),
                'role': store_info.get('role', '친근한 사장님'),
                'tone': store_info.get('tone', '전문성과 친근함이 조화된 어조'),
                'prohibited_words': store_info.get('prohibited_words', []),
                'max_length': store_info.get('max_length', 450),
                f"rating_{review['rating']}_reply": True
            }
            
            # AI 답글 생성
            ai_response = self.ai_generator.generate_reply(review, reply_rules)
            
            if ai_response:
                # 답글 업데이트
                update_data = {
                    'ai_response': ai_response,
                    'response_status': 'generated',
                    'processed_at': datetime.now().isoformat(),
                    'response_quality_score': 0.8  # 기본 품질 점수
                }
                
                self.supabase.table('reviews').update(update_data).eq('review_id', review['review_id']).execute()
                
                print(f"[AI] 답글 생성 완료:")
                print(f"     {ai_response[:100]}...")
                print(f"     (총 {len(ai_response)}자)")
                
                return True
            else:
                print("[AI] 답글 생성 실패")
                return False
                
        except Exception as e:
            print(f"[오류] AI 답글 생성 중 오류: {e}")
            
            # 에러 정보 업데이트
            error_data = {
                'response_status': 'failed',
                'error_message': str(e),
                'processed_at': datetime.now().isoformat()
            }
            
            self.supabase.table('reviews').update(error_data).eq('review_id', review['review_id']).execute()
            
            return False


# 기존 run_sync_crawler.py에 통합할 함수
def process_crawled_reviews(reviews: List[Dict[str, Any]], store_info: Dict[str, Any]):
    """크롤링된 리뷰 처리 (저장 + AI 답글 생성)"""
    processor = ReviewProcessor()
    
    print(f"\n=== 리뷰 처리 시작 ===")
    print(f"매장: {store_info['store_name']}")
    print(f"총 리뷰 수: {len(reviews)}개")
    
    # 리뷰 저장 및 AI 답글 생성
    result = processor.save_reviews_to_supabase(reviews, store_info)
    
    print(f"\n=== 처리 완료 ===")
    print(f"저장 성공: {result['saved']}개")
    print(f"저장 실패: {result['failed']}개")
    print(f"중복 건수: {result['total'] - result['saved'] - result['failed']}개")


if __name__ == "__main__":
    # 테스트용
    test_reviews = [
        {
            'review_id': 'test123',
            'store_code': 'STR_20250607112756_854269',
            'platform': 'baemin',
            'platform_code': '14638971',
            'review_name': '테스트고객오늘맛있어요',
            'rating': 5,
            'review_content': '정말 맛있게 잘 먹었습니다!',
            'ordered_menu': '닭강정 세트',
            'delivery_review': '좋아요',
            'review_date': '오늘',
            'review_images': [],
            'has_reply': False,
            'writableComment': True
        }
    ]
    
    test_store_info = {
        'store_name': '테스트 매장',
        'auto_reply_enabled': True,
        'auto_reply_hours': '00:00-23:59',
        'greeting_start': '안녕하세요',
        'greeting_end': '감사합니다',
        'role': '친근한 사장님',
        'tone': '전문성과 친근함이 조화된 어조',
        'prohibited_words': ['매우', '레스토랑'],
        'max_length': 450,
        'rating_5_reply': True
    }
    
    process_crawled_reviews(test_reviews, test_store_info)
