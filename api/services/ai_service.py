"""
OpenAI 답글 생성 서비스
"""
import logging
from typing import Dict, Any, Optional
from config.openai_client import get_openai_client

logger = logging.getLogger(__name__)


class AIService:
    """AI 답글 생성 서비스"""
    
    def __init__(self):
        self.client = get_openai_client()
        self.model = "gpt-3.5-turbo"  # 또는 "gpt-4"
        
    async def generate_reply(self, review_data: Dict[str, Any]) -> Dict[str, Any]:
        """리뷰에 대한 답글 생성"""
        try:
            # 프롬프트 생성
            prompt = self._create_prompt(review_data)
            
            # OpenAI API 호출
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """당신은 친절한 음식점 사장님입니다. 
                        고객 리뷰에 대해 감사하고 진심어린 답글을 작성해주세요.
                        - 항상 고객님이라고 호칭
                        - 감사 인사로 시작
                        - 구체적인 내용에 대한 언급
                        - 재방문 유도하는 마무리
                        - 최대 200자 이내"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=300
            )
            
            generated_reply = response.choices[0].message.content.strip()
            
            # 답글 품질 검증
            is_valid, quality_score = await self.validate_reply(generated_reply, review_data)
            
            return {
                'success': True,
                'reply': generated_reply,
                'quality_score': quality_score,
                'is_valid': is_valid
            }
            
        except Exception as e:
            logger.error(f"답글 생성 실패: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'reply': None
            }
    
    def _create_prompt(self, review_data: Dict[str, Any]) -> str:
        """프롬프트 생성"""
        rating = review_data.get('rating', 5)
        content = review_data.get('review_content', '')
        menu = review_data.get('ordered_menu', '')
        name = review_data.get('review_name', '고객')
        
        prompt = f"""
        다음 리뷰에 대한 답글을 작성해주세요:
        
        고객명: {name}님
        별점: {rating}점
        주문메뉴: {menu}
        리뷰내용: {content}
        
        답글 작성 규칙:
        1. {name}님으로 시작
        2. 감사 인사 포함
        3. 구체적인 메뉴나 내용 언급
        4. 재방문 유도
        5. 200자 이내
        """
        
        # 별점별 추가 지침
        if rating == 5:
            prompt += "\n매우 만족하신 고객님께 감사를 표현하고 재방문을 유도해주세요."
        elif rating == 4:
            prompt += "\n만족하신 부분에 감사하고, 더 나은 서비스를 약속해주세요."
        elif rating == 3:
            prompt += "\n아쉬운 부분에 대해 사과하고 개선 의지를 보여주세요."
        elif rating <= 2:
            prompt += "\n불편을 드린 점 진심으로 사과하고, 구체적인 개선 약속을 해주세요."
        
        return prompt
    
    async def validate_reply(self, reply: str, review_data: Dict[str, Any]) -> tuple[bool, float]:
        """답글 품질 검증"""
        score = 1.0
        is_valid = True
        
        # 길이 체크
        if len(reply) < 20:
            score -= 0.3
            is_valid = False
            logger.warning("답글이 너무 짧습니다")
        elif len(reply) > 300:
            score -= 0.2
            logger.warning("답글이 너무 깁니다")
        
        # 필수 요소 체크
        if "고객님" not in reply:
            score -= 0.1
        
        if "감사" not in reply and review_data.get('rating', 5) >= 3:
            score -= 0.1
        
        if review_data.get('rating', 5) <= 2 and "죄송" not in reply:
            score -= 0.2
            
        # 금지어 체크
        forbidden_words = ['싫', '별로', '최악', '쓰레기']
        for word in forbidden_words:
            if word in reply:
                score = 0
                is_valid = False
                logger.error(f"금지어 발견: {word}")
                break
        
        return is_valid, max(0, score)
