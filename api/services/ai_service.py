"""
OpenAI 답글 생성 서비스 - 매장 정책 반영 (오류 수정)
"""
import os
import time
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from config.openai_client import get_openai_client

logger = logging.getLogger(__name__)


class AIService:
    """AI 답글 생성 서비스"""
    
    def __init__(self):
        self.client = get_openai_client()
        self.model = os.getenv("AI_MODEL", "gpt-4o-mini")
        self.max_tokens = int(os.getenv("AI_MAX_TOKENS", "600"))
        self.temperature = float(os.getenv("AI_TEMPERATURE", "0.7"))
        
    async def generate_reply(
        self, 
        review_data: Dict[str, Any], 
        store_rules: Dict[str, Any]
    ) -> Dict[str, Any]:
        """리뷰에 대한 답글 생성 (매장 정책 반영)"""
        start_time = time.time()
        
        try:
            # 답글 생성 가능 여부 확인
            if not self._should_generate_reply(review_data, store_rules):
                return {
                    'success': False,
                    'error': '해당 별점에 대한 자동 답글이 비활성화되어 있습니다',
                    'reply': None,
                    'quality_score': 0.0,
                    'processing_time_ms': 0,
                    'token_usage': 0
                }
            
            # 프롬프트 생성
            prompt = self._create_prompt(review_data, store_rules)
            system_prompt = self._create_system_prompt(store_rules)
            
            # OpenAI API 호출
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            generated_reply = response.choices[0].message.content
            if generated_reply:
                generated_reply = generated_reply.strip()
            else:
                generated_reply = ""
            
            token_usage = response.usage.total_tokens if response.usage else 0
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # 답글 품질 검증
            is_valid, quality_score = self._validate_reply(
                generated_reply, review_data, store_rules
            )
            
            # 매장 정책에 맞게 답글 조정
            final_reply = self._apply_store_formatting(generated_reply, store_rules)
            
            return {
                'success': True,
                'reply': final_reply,
                'quality_score': quality_score,
                'is_valid': is_valid,
                'processing_time_ms': processing_time_ms,
                'token_usage': token_usage,
                'model_used': self.model,
                'prompt_used': prompt
            }
            
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"답글 생성 실패: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'reply': None,
                'quality_score': 0.0,
                'processing_time_ms': processing_time_ms,
                'token_usage': 0
            }
    
    def _should_generate_reply(
        self, 
        review_data: Dict[str, Any], 
        store_rules: Dict[str, Any]
    ) -> bool:
        """답글 생성 가능 여부 확인"""
        rating = review_data.get('rating', 5)
        
        # 별점별 답글 활성화 확인
        rating_key = f'rating_{rating}_reply'
        if not store_rules.get(rating_key, True):
            return False
        
        # 자동 답글 기능 활성화 확인
        if not store_rules.get('auto_reply_enabled', True):
            return False
        
        return True
    
    def _create_system_prompt(self, store_rules: Dict[str, Any]) -> str:
        """시스템 프롬프트 생성 (매장 정책 반영)"""
        role = store_rules.get('role', '친절한 사장님') or '친절한 사장님'
        tone = store_rules.get('tone', '친근함') or '친근함'
        max_length = store_rules.get('max_length', 300) or 300
        store_name = store_rules.get('store_name', '저희 매장') or '저희 매장'
        
        tone_instructions = self._get_tone_instructions(tone)
        
        system_prompt = f"""당신은 {store_name}의 {role}입니다.

답글 작성 규칙:
1. 말투: {tone_instructions}
2. 최대 길이: {max_length}자 이내
3. 항상 '고객님'이라고 호칭
4. 감사 인사를 포함
5. 구체적인 내용에 대한 언급
6. 재방문을 유도하는 마무리

금지사항:
- 과도한 할인이나 이벤트 언급 금지
- 다른 업체나 경쟁사 언급 금지
- 개인정보 요청 금지
- 부적절한 표현 사용 금지

매장 정보:
- 매장명: {store_name}
- 플랫폼: {store_rules.get('platform', '배달앱') or '배달앱'}
"""
        
        # 금지어가 있는 경우 추가
        prohibited_words = store_rules.get('prohibited_words', [])
        if prohibited_words and isinstance(prohibited_words, list):
            system_prompt += f"\n추가 금지어: {', '.join(prohibited_words)}"
        
        return system_prompt
    
    def _create_prompt(
        self, 
        review_data: Dict[str, Any], 
        store_rules: Dict[str, Any]
    ) -> str:
        """프롬프트 생성 (리뷰 내용 반영)"""
        rating = review_data.get('rating', 5)
        content = review_data.get('review_content', '') or ''
        menu = review_data.get('ordered_menu', '') or ''
        name = review_data.get('review_name', '고객') or '고객'
        delivery_review = review_data.get('delivery_review', '') or ''
        
        prompt = f"""다음 리뷰에 대한 답글을 작성해주세요:

고객명: {name}님
별점: {rating}점
주문메뉴: {menu}
리뷰내용: {content}"""
        
        if delivery_review:
            prompt += f"\n배달리뷰: {delivery_review}"
        
        # 별점별 추가 지침
        rating_instructions = self._get_rating_instructions(rating)
        prompt += f"\n\n답글 작성 가이드:\n{rating_instructions}"
        
        return prompt
    
    def _get_tone_instructions(self, tone: str) -> str:
        """톤앤매너별 지침 생성"""
        tone_map = {
            '친근함': '친근하고 따뜻한 말투로 작성해주세요. 반말은 사용하지 말고 존댓말을 사용하되 딱딱하지 않게.',
            '정중함': '정중하고 예의바른 말투로 작성해주세요. 격식을 갖춘 존댓말 사용.',
            '격식있음': '매우 정중하고 격식있는 말투로 작성해주세요. 공식적인 존댓말 사용.',
            '유쾌함': '밝고 유쾌한 말투로 작성해주세요. 긍정적인 에너지가 느껴지도록.',
            '진중함': '진지하고 신중한 말투로 작성해주세요. 책임감 있는 태도 표현.'
        }
        
        return tone_map.get(tone, tone_map['친근함'])
    
    def _get_rating_instructions(self, rating: int) -> str:
        """별점별 답글 전략"""
        if rating == 5:
            return """5점 만점 리뷰:
- 깊은 감사 표현
- 만족하신 구체적인 부분 언급
- 앞으로도 최선을 다할 것을 약속
- 재방문 따뜻하게 유도"""
        
        elif rating == 4:
            return """4점 리뷰:
- 감사 표현
- 만족하신 부분에 대한 언급
- 더 나은 서비스를 위해 노력할 것을 약속
- 재방문 유도"""
        
        elif rating == 3:
            return """3점 리뷰:
- 이용해주신 것에 대한 감사
- 아쉬운 부분이 있었다면 개선 의지 표현
- 더 나은 경험을 위해 노력하겠다는 약속
- 재방문 기회 요청"""
        
        elif rating == 2:
            return """2점 리뷰:
- 불편을 드린 점에 대한 진심어린 사과
- 구체적인 개선 의지 표현
- 다음에는 더 나은 서비스를 제공하겠다는 약속
- 재방문 기회 간곡히 요청"""
        
        else:  # rating == 1
            return """1점 리뷰:
- 깊은 사과와 죄송함 표현
- 고객님의 불편한 경험에 대한 책임감 표현
- 즉시 개선할 구체적인 방안 제시
- 신뢰 회복을 위한 노력 약속
- 다시 한 번 기회를 달라는 간절한 요청"""
    
    def _apply_store_formatting(
        self, 
        reply: str, 
        store_rules: Dict[str, Any]
    ) -> str:
        """매장별 형식 적용 (None 체크 추가)"""
        # None 체크 및 기본값 처리
        greeting_start = store_rules.get('greeting_start') or ''
        greeting_end = store_rules.get('greeting_end') or ''
        
        # 안전하게 strip() 호출
        greeting_start = greeting_start.strip() if greeting_start else ''
        greeting_end = greeting_end.strip() if greeting_end else ''
        
        # 시작 인사가 이미 포함되어 있지 않은 경우에만 추가
        if greeting_start and not reply.startswith(greeting_start):
            reply = f"{greeting_start} {reply}"
        
        # 마무리 인사가 이미 포함되어 있지 않은 경우에만 추가
        if greeting_end and not reply.endswith(greeting_end):
            reply = f"{reply} {greeting_end}"
        
        # 최대 길이 제한
        max_length = store_rules.get('max_length', 300) or 300
        if len(reply) > max_length:
            # 마무리 인사를 보존하면서 자르기
            if greeting_end:
                available_length = max_length - len(greeting_end) - 1
                reply = reply[:available_length].rstrip() + f" {greeting_end}"
            else:
                reply = reply[:max_length]
        
        return reply.strip()
    
    def _validate_reply(
        self, 
        reply: str, 
        review_data: Dict[str, Any], 
        store_rules: Dict[str, Any]
    ) -> Tuple[bool, float]:
        """답글 품질 검증"""
        score = 1.0
        is_valid = True
        rating = review_data.get('rating', 5)
        
        # 답글이 비어있는지 확인
        if not reply or not reply.strip():
            score = 0.0
            is_valid = False
            logger.error("생성된 답글이 비어있습니다")
            return is_valid, score
        
        # 길이 체크
        min_length = 20
        max_length = store_rules.get('max_length', 300) or 300
        
        if len(reply) < min_length:
            score -= 0.4
            is_valid = False
            logger.warning(f"답글이 너무 짧습니다: {len(reply)}자")
        elif len(reply) > max_length + 50:  # 여유분 고려
            score -= 0.2
            logger.warning(f"답글이 너무 깁니다: {len(reply)}자")
        
        # 필수 요소 체크
        if "고객님" not in reply:
            score -= 0.15
        
        # 별점별 필수 요소 체크
        if rating >= 3:
            if "감사" not in reply:
                score -= 0.1
        
        if rating <= 2:
            if not any(word in reply for word in ["죄송", "사과", "미안"]):
                score -= 0.3
                logger.warning("저평점 리뷰에 사과 표현이 없습니다")
        
        # 매장별 금지어 체크
        prohibited_words = store_rules.get('prohibited_words', [])
        if prohibited_words and isinstance(prohibited_words, list):
            for word in prohibited_words:
                if word and word in reply:
                    score = 0
                    is_valid = False
                    logger.error(f"매장 금지어 발견: {word}")
                    break
        
        # 일반 금지어 체크
        general_forbidden = ['싫', '별로', '최악', '쓰레기', '더럽', '짜증']
        for word in general_forbidden:
            if word in reply:
                score = 0
                is_valid = False
                logger.error(f"부적절한 표현 발견: {word}")
                break
        
        # 품질 임계점 확인
        threshold = store_rules.get('manual_review_threshold', 0.3) or 0.3
        if score < threshold:
            is_valid = False
            logger.warning(f"품질 점수가 임계점 미만: {score} < {threshold}")
        
        return is_valid, max(0, score)
    
    async def regenerate_reply(
        self, 
        review_data: Dict[str, Any], 
        store_rules: Dict[str, Any],
        previous_attempts: int = 0
    ) -> Dict[str, Any]:
        """답글 재생성 (다른 파라미터 사용)"""
        # 재생성시 temperature를 조금 높여서 다양성 확보
        original_temp = self.temperature
        self.temperature = min(1.0, self.temperature + 0.1 + (previous_attempts * 0.05))
        
        try:
            result = await self.generate_reply(review_data, store_rules)
            result['generation_type'] = 'ai_retry'
            result['attempt_number'] = previous_attempts + 1
            return result
        finally:
            # 원래 temperature 복원
            self.temperature = original_temp
