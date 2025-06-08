"""
AI 답글 생성 서비스
OpenAI API를 사용하여 리뷰에 대한 답글 생성
"""
import os
from typing import Dict, Any, Optional
from datetime import datetime
import openai
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# OpenAI API 키 설정
openai.api_key = os.getenv('OPENAI_API_KEY')

class AIReplyGenerator:
    """AI 답글 생성기"""
    
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
        openai.api_key = self.api_key
    
    def generate_reply(self, review: Dict[str, Any], reply_rules: Dict[str, Any]) -> str:
        """
        리뷰에 대한 AI 답글 생성
        
        Args:
            review: 리뷰 정보 (review_name, rating, review_content, ordered_menu, delivery_review)
            reply_rules: 답글 규칙 (platform_reply_rules 테이블 데이터)
        
        Returns:
            생성된 답글 텍스트
        """
        # 별점에 따른 답글 활성화 확인
        rating = review.get('rating', 5)
        rating_key = f'rating_{rating}_reply'
        
        if not reply_rules.get(rating_key, True):
            return None  # 해당 별점에 대한 답글 비활성화
        
        # 프롬프트 생성
        prompt = self._create_prompt(review, reply_rules)
        
        try:
            # OpenAI API 호출
            response = openai.ChatCompletion.create(
                model="gpt-4-turbo-preview",  # 또는 "gpt-3.5-turbo"
                messages=[
                    {"role": "system", "content": self._get_system_prompt(reply_rules)},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=reply_rules.get('max_length', 450),
                temperature=0.7,
                top_p=0.9
            )
            
            # 답글 추출
            reply = response.choices[0].message.content.strip()
            
            # 금지 단어 필터링
            reply = self._filter_prohibited_words(reply, reply_rules)
            
            # 길이 조정
            reply = self._adjust_length(reply, reply_rules)
            
            # 인사말 추가
            reply = self._add_greetings(reply, reply_rules)
            
            return reply
            
        except Exception as e:
            print(f"AI 답글 생성 오류: {e}")
            return None
    
    def _get_system_prompt(self, reply_rules: Dict[str, Any]) -> str:
        """시스템 프롬프트 생성"""
        role = reply_rules.get('role', '친근한 사장님')
        tone = reply_rules.get('tone', '전문성과 친근함이 조화된 어조')
        
        return f"""당신은 {role}입니다.
        
답글 작성 시 다음 사항을 반드시 지켜주세요:
1. {tone}로 작성합니다.
2. 고객의 이름을 언급하며 개인화된 답글을 작성합니다.
3. 구체적인 리뷰 내용에 대해 감사를 표현합니다.
4. 별점에 맞는 적절한 톤으로 응대합니다:
   - 5점: 진심 어린 감사와 기쁨 표현
   - 4점: 감사하며 더 나은 서비스를 위한 의지 표현
   - 3점: 감사와 함께 개선 노력 약속
   - 2점: 사과와 구체적인 개선 방안 제시
   - 1점: 진정성 있는 사과와 재방문 유도
5. 답글은 자연스럽고 진정성 있게 작성합니다.
6. 이모티콘은 사용하지 않습니다."""
    
    def _create_prompt(self, review: Dict[str, Any], reply_rules: Dict[str, Any]) -> str:
        """사용자 프롬프트 생성"""
        review_name = review.get('review_name', '고객')
        rating = review.get('rating', 5)
        review_content = review.get('review_content', '')
        ordered_menu = review.get('ordered_menu', '')
        delivery_review = review.get('delivery_review', '')
        
        prompt = f"""다음 리뷰에 대한 답글을 작성해주세요:

고객명: {review_name}
별점: {rating}점
리뷰 내용: {review_content}
주문 메뉴: {ordered_menu}"""

        if delivery_review:
            prompt += f"\n배달 평가: {delivery_review}"
        
        prompt += f"\n\n답글은 {reply_rules.get('max_length', 450)}자 이내로 작성해주세요."
        
        return prompt
    
    def _filter_prohibited_words(self, reply: str, reply_rules: Dict[str, Any]) -> str:
        """금지 단어 필터링"""
        prohibited_words = reply_rules.get('prohibited_words', [])
        
        if not prohibited_words:
            return reply
        
        for word in prohibited_words:
            if word in reply:
                # 금지 단어를 유사한 의미의 다른 단어로 대체
                replacements = {
                    '매우': '정말',
                    '레스토랑': '저희 가게',
                    '셰프': '조리사',
                    '유감': '죄송',
                    '방문': '주문',
                    '안타': '아쉬'
                }
                reply = reply.replace(word, replacements.get(word, ''))
        
        return reply
    
    def _adjust_length(self, reply: str, reply_rules: Dict[str, Any]) -> str:
        """답글 길이 조정"""
        max_length = reply_rules.get('max_length', 450)
        
        if len(reply) > max_length:
            # 마지막 문장을 찾아서 자르기
            sentences = reply.split('. ')
            adjusted_reply = ''
            
            for sentence in sentences:
                if len(adjusted_reply + sentence + '. ') <= max_length:
                    adjusted_reply += sentence + '. '
                else:
                    break
            
            reply = adjusted_reply.rstrip()
        
        return reply
    
    def _add_greetings(self, reply: str, reply_rules: Dict[str, Any]) -> str:
        """인사말 추가"""
        greeting_start = reply_rules.get('greeting_start', '')
        greeting_end = reply_rules.get('greeting_end', '')
        
        # 시작 인사말이 이미 포함되어 있지 않으면 추가
        if greeting_start and not reply.startswith(greeting_start):
            reply = f"{greeting_start} {reply}"
        
        # 끝 인사말 추가
        if greeting_end and not reply.endswith(greeting_end):
            reply = f"{reply} {greeting_end}"
        
        return reply


# 테스트 함수
def test_ai_reply():
    """AI 답글 생성 테스트"""
    
    # 테스트 리뷰
    test_review = {
        'review_name': '소워닝',
        'rating': 5,
        'review_content': '완존 맛있어요 최고짱',
        'ordered_menu': '(겉바속촉) 3~4인 세트/반반',
        'delivery_review': '좋아요'
    }
    
    # 테스트 답글 규칙
    test_rules = {
        'greeting_start': '안녕하세요',
        'greeting_end': None,
        'role': '유쾌한 가게 사장님으로 이름, 별점, 리뷰를 보고 고객을 생각하는 느낌을 주도록 text로만 리뷰를 작성',
        'tone': '전문성과 친근함이 조화된 밝고 경험 많은 사장님의 어조',
        'prohibited_words': ['매우', '레스토랑', '셰프', '유감', '방문', '안타'],
        'max_length': 450,
        'rating_5_reply': True
    }
    
    # AI 답글 생성
    generator = AIReplyGenerator()
    reply = generator.generate_reply(test_review, test_rules)
    
    if reply:
        print("=== AI 생성 답글 ===")
        print(reply)
        print(f"\n글자 수: {len(reply)}자")
    else:
        print("답글 생성 실패")


if __name__ == "__main__":
    # API 키 확인
    if os.getenv('OPENAI_API_KEY'):
        print("OpenAI API 키 설정됨")
        test_ai_reply()
    else:
        print("OpenAI API 키가 설정되지 않았습니다.")
        print(".env 파일에 OPENAI_API_KEY=your-api-key 형식으로 추가하세요.")
