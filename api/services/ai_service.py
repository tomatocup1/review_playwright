"""
OpenAI 답글 생성 서비스 - 매장 정책 반영 (오류 수정)
"""
import os
import time
import logging
import asyncio
import json
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from config.openai_client import get_openai_client
from ..utils.error_handler import log_api_error, ErrorType

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
        store_rules: Dict[str, Any],
        retry_count: int = 0,
        max_retries: int = 3
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
            
            # 재시도시 temperature 조정
            adjusted_temperature = self.temperature
            if retry_count > 0:
                adjusted_temperature = min(1.0, self.temperature + (retry_count * 0.1))
                logger.info(f"재시도 {retry_count}회차: temperature를 {adjusted_temperature}로 조정")
            
            # OpenAI API 호출
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=adjusted_temperature,
                    max_tokens=self.max_tokens
                )
            except Exception as api_error:
                # API 에러 로깅
                error_type = ErrorType.API_TIMEOUT
                error_message = str(api_error)
                
                if "rate_limit" in error_message.lower() or "quota" in error_message.lower():
                    error_type = ErrorType.API_RATE_LIMIT
                elif "timeout" in error_message.lower():
                    error_type = ErrorType.API_TIMEOUT
                elif "invalid" in error_message.lower():
                    error_type = ErrorType.INVALID_RESPONSE
                
                await log_api_error(
                    api_type='openai',
                    error_type=error_type,
                    error_message=error_message,
                    request_data={
                        'model': self.model,
                        'temperature': adjusted_temperature,
                        'max_tokens': self.max_tokens,
                        'prompt_length': len(prompt)
                    },
                    store_code=review_data.get('store_code'),
                    review_id=review_data.get('review_id')
                )
                
                raise  # 에러 재발생
                
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
            
            # 품질이 낮고 재시도 가능한 경우
            if not is_valid and retry_count < max_retries:
                logger.warning(f"답글 품질 미달 (점수: {quality_score:.2f}), 재시도 {retry_count + 1}/{max_retries}")
                
                # 짧은 대기 후 재시도
                await asyncio.sleep(0.5)
                
                # 재귀적으로 재시도
                retry_result = await self.generate_reply(
                    review_data, 
                    store_rules, 
                    retry_count + 1,
                    max_retries
                )
                
                # 재시도 정보 추가
                retry_result['total_attempts'] = retry_count + 2
                retry_result['final_quality_score'] = retry_result['quality_score']
                
                return retry_result
            
            # 매장 정책에 맞게 답글 조정
            final_reply = self._apply_store_formatting(generated_reply, store_rules)
            
            # AI 기반 사장님 확인 필요 여부 분석
            boss_review_needed, review_reason, urgency_score = await self._analyze_review_for_boss_attention(
                review_data
            )
            
            # 최대 재시도 후에도 품질이 낮은 경우에만 사장님 확인 필요
            if not is_valid and retry_count >= max_retries:
                boss_review_needed = True
                review_reason = f"AI 답글 품질 미달 ({max_retries}회 재시도 후에도 품질 기준 미달, 점수: {quality_score:.2f})"
                urgency_score = max(urgency_score, 0.6)
            
            return {
                'success': True,
                'reply': final_reply,
                'quality_score': quality_score,
                'is_valid': is_valid,
                'processing_time_ms': processing_time_ms,
                'token_usage': token_usage,
                'model_used': self.model,
                'prompt_used': prompt,
                'boss_review_needed': boss_review_needed,
                'review_reason': review_reason,
                'urgency_score': urgency_score,
                'retry_count': retry_count,
                'total_attempts': retry_count + 1
            }
            
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"답글 생성 실패: {str(e)}")
            
            # 오류 발생시 사장님 확인 필요
            return {
                'success': False,
                'error': str(e),
                'reply': None,
                'quality_score': 0.0,
                'processing_time_ms': processing_time_ms,
                'token_usage': 0,
                'boss_review_needed': True,
                'review_reason': f'AI 답글 생성 오류: {str(e)}',
                'urgency_score': 0.8,
                'retry_count': retry_count,
                'total_attempts': retry_count + 1
            }
    
    def _should_generate_reply(
        self, 
        review_data: Dict[str, Any], 
        store_rules: Dict[str, Any]
    ) -> bool:
        """답글 생성 가능 여부 확인"""
        rating = review_data.get('rating')
        
        # 별점이 있는 경우만 별점별 답글 설정 확인
        if rating is not None:
            rating_key = f'rating_{rating}_reply'
            if not store_rules.get(rating_key, True):
                return False
        
        # 자동 답글 기능 활성화 확인
        if not store_rules.get('auto_reply_enabled', True):
            return False
        
        return True
    
    def _create_system_prompt(self, store_rules: Dict[str, Any]) -> str:
        """시스템 프롬프트 생성 - AI의 자율성 강화"""
        store_name = store_rules.get('store_name', '우리 매장') or '우리 매장'
        role = store_rules.get('role', '친절한 사장님') or '친절한 사장님'
        tone = store_rules.get('tone', '친근하고 따뜻한') or '친근하고 따뜻한'
        greeting_start = store_rules.get('greeting_start', '안녕하세요') or '안녕하세요'
        greeting_end = store_rules.get('greeting_end', '감사합니다') or '감사합니다'
        max_length = store_rules.get('max_length', 300) or 300
        
        system_prompt = f"""당신은 '{store_name}' {role}입니다.

답글 작성 원칙:
1. 리뷰 내용을 정확히 파악하여 맥락에 맞는 답변 작성
2. {tone} 말투로 일관되게 작성
3. 시작: {greeting_start} / 종료: {greeting_end}
4. {max_length}자 이내로 간결하게
5. 이모티콘은 적절히 사용 (최대 2개)
6. 항상 '고객님'이라고 호칭

중요: 리뷰의 감정(긍정/부정/중립)을 파악하여 그에 맞는 적절한 답변을 하세요.
- 긍정적 리뷰: 감사 표현과 재방문 유도
- 부정적 리뷰: 진심어린 사과와 개선 약속
- 질문 포함: 명확한 답변 제공
- 별점이 없는 경우: 내용으로 판단하여 대응, 별점 언급 금지

금지사항:
- 과도한 할인이나 이벤트 언급 금지
- 다른 업체나 경쟁사 언급 금지
- 개인정보 요청 금지
- 부적절한 표현 사용 금지"""
        
        # 금지어가 있다면 추가
        prohibited_words = store_rules.get('prohibited_words', [])
        if prohibited_words and isinstance(prohibited_words, list):
            prohibited_words = [word for word in prohibited_words if word]
            if prohibited_words:
                system_prompt += f"\n\n금지어: {', '.join(prohibited_words)}"
        
        return system_prompt
    
    def _create_prompt(
        self, 
        review_data: Dict[str, Any], 
        store_rules: Dict[str, Any]
    ) -> str:
        """프롬프트 생성 (리뷰 내용 반영)"""
        rating = review_data.get('rating')
        content = review_data.get('review_content', '') or ''
        menu = review_data.get('ordered_menu', '') or ''
        name = review_data.get('review_name', '고객') or '고객'
        delivery_review = review_data.get('delivery_review', '') or ''
        
        # 기본 프롬프트 구성
        prompt = f"""다음 리뷰에 대한 답글을 작성해주세요:

고객명: {name}님"""
        
        if rating is not None:
            prompt += f"\n별점: {rating}점"
        
        if menu:
            prompt += f"\n주문메뉴: {menu}"
            
        prompt += f"\n리뷰내용: {content}"
        
        if delivery_review:
            prompt += f"\n배달리뷰: {delivery_review}"
        
        # 답글 작성 가이드 추가
        prompt += f"\n\n답글 작성 가이드:"
        
        if rating is None:
            prompt += "\n- 별점이 없으므로 리뷰 내용의 감정과 맥락을 파악하여 적절히 대응하세요"
            prompt += "\n- 별점이나 평점을 언급하지 마세요"
        else:
            prompt += f"\n{self._get_rating_instructions(rating)}"
        
        prompt += "\n- 리뷰 내용에 맞는 적절한 톤으로 답변하세요"
        prompt += "\n- 부정적인 내용이 있다면 사과와 개선 의지를 표현하세요"
        prompt += "\n- 긍정적인 내용이 있다면 감사를 표현하세요"
        prompt += "\n- 질문이 있다면 명확하게 답변하세요"
        
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
    
    def _get_rating_instructions(self, rating: Optional[int]) -> str:
        """별점별 답글 전략 - 간소화 버전"""
        if rating is None:
            return "리뷰 내용을 바탕으로 적절한 답글을 작성하세요."
        elif rating >= 4:
            return "긍정적인 리뷰에 대한 감사 표현과 재방문 유도"
        elif rating == 3:
            return "이용 감사와 더 나은 서비스를 위한 노력 약속"
        else:  # rating <= 2
            return "진심어린 사과와 구체적인 개선 의지 표현"
    
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
        rating = review_data.get('rating')
        
        # 답글이 비어있는지 확인
        if not reply or not reply.strip():
            score = 0.0
            is_valid = False
            logger.error("생성된 답글이 비어있습니다")
            return is_valid, score
        
        # 길이 체크
        min_length = 30  # 최소 길이를 20에서 30으로 상향
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
            logger.warning("'고객님' 호칭이 없습니다")
        
        # 별점이 있는 경우에만 별점별 필수 요소 체크
        if rating is not None:
            if rating >= 3:
                if "감사" not in reply:
                    score -= 0.1
                    logger.warning("감사 표현이 없습니다")
            
            if rating <= 2:
                if not any(word in reply for word in ["죄송", "사과", "미안"]):
                    score -= 0.3
                    is_valid = False  # 저평점에서 사과 없으면 무조건 재시도
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
        
        # 답글의 구체성 체크
        review_content = review_data.get('review_content', '')
        if len(review_content) > 50:  # 리뷰가 상세한 경우
            # 리뷰 내용을 전혀 반영하지 않은 일반적인 답글인지 체크
            generic_replies = ['이용해 주셔서 감사합니다', '다음에도 방문해 주세요', '좋은 하루 되세요']
            if any(generic in reply and len(reply) < 50 for generic in generic_replies):
                score -= 0.3
                logger.warning("리뷰 내용을 반영하지 않은 일반적인 답글")
        
        # 품질 임계점 확인 (더 엄격하게 조정)
        threshold = store_rules.get('manual_review_threshold', 0.5) or 0.5  # 0.3에서 0.5로 상향
        if score < threshold:
            is_valid = False
            logger.warning(f"품질 점수가 임계점 미만: {score} < {threshold}")
        
        return is_valid, max(0, score)
    
    async def _analyze_review_for_boss_attention(
        self, 
        review_data: Dict[str, Any]
    ) -> Tuple[bool, str, float]:
        """AI를 사용하여 사장님 확인 필요 여부 분석"""
        try:
            review_content = review_data.get('review_content', '') or ''
            rating = review_data.get('rating')
            ordered_menu = review_data.get('ordered_menu', '') or ''
            delivery_review = review_data.get('delivery_review', '') or ''
            
            # 분석용 프롬프트 생성
            analysis_prompt = f"""다음 리뷰를 분석하여 사장님이 직접 확인해야 하는지 판단해주세요.

리뷰 정보:"""
            
            if rating is not None:
                analysis_prompt += f"\n- 별점: {rating}점"
            else:
                analysis_prompt += f"\n- 별점: 없음 (내용으로 판단 필요)"
                
            analysis_prompt += f"""
- 주문 메뉴: {ordered_menu}
- 리뷰 내용: {review_content}
- 배달 평가: {delivery_review}

판단 기준:
1. 고객의 직접적인 질문이 있는가?
2. 심각한 불만이나 항의가 포함되어 있는가?
3. 위생, 안전, 건강 관련 이슈가 있는가?
4. 법적 문제나 배상 요구가 있는가?
5. 직원의 심각한 잘못이나 서비스 문제가 있는가?
6. 단골 고객의 실망이나 이탈 위험이 있는가?
7. 즉각적인 대응이 필요한 긴급 사안인가?
8. 매장 운영에 대한 중요한 제안이나 피드백이 있는가?

응답 형식 (JSON):
{{
    "boss_review_needed": true/false,
    "reason": "구체적인 이유 (한국어로 간단명료하게)",
    "urgency_score": 0.0-1.0 (긴급도 점수)
}}

중요: 단순한 칭찬이나 일반적인 피드백은 false로 판단하세요."""

            # OpenAI API 호출
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": "당신은 음식점 리뷰를 분석하는 전문가입니다. 사장님이 직접 확인해야 할 중요한 리뷰를 정확히 식별합니다."
                    },
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.3,  # 더 일관된 판단을 위해 낮은 temperature
                max_tokens=200,
                response_format={"type": "json_object"}  # JSON 응답 강제
            )
            
            # 응답 파싱
            result_text = response.choices[0].message.content
            try:
                analysis_result = json.loads(result_text)
                boss_review_needed = analysis_result.get('boss_review_needed', False)
                reason = analysis_result.get('reason', '')
                urgency_score = float(analysis_result.get('urgency_score', 0.5))
                
                # 낮은 별점은 항상 확인 필요 (AI 판단과 무관하게)
                if rating is not None and rating <= 2 and not boss_review_needed:
                    boss_review_needed = True
                    reason = f"낮은 별점({rating}점) - {reason}" if reason else f"낮은 별점({rating}점)"
                    urgency_score = max(urgency_score, 0.7)
                
                return boss_review_needed, reason, urgency_score
                
            except json.JSONDecodeError:
                # JSON 파싱 실패시 기본 규칙 적용
                logger.warning("AI 분석 응답 파싱 실패, 기본 규칙 적용")
                return self._check_boss_review_needed_fallback(review_data)
                
        except Exception as e:
            logger.error(f"AI 리뷰 분석 실패: {str(e)}")
            # API 호출 실패시 기본 규칙 기반 판단
            return self._check_boss_review_needed_fallback(review_data)
    
    def _check_boss_review_needed_fallback(
        self, 
        review_data: Dict[str, Any]
    ) -> Tuple[bool, str, float]:
        """AI 분석 실패시 사용할 기본 규칙 - 간소화 버전"""
        rating = review_data.get('rating')
        review_content = (review_data.get('review_content', '') or '').lower()
        
        # 간단한 규칙만 적용
        if rating is not None and rating <= 2:
            return True, "낮은 별점", 0.8
        
        # 질문 마크가 있으면 확인 필요
        if '?' in review_content:
            return True, "질문 포함", 0.6
        
        # 위생/안전 관련 심각한 키워드만 체크
        serious_keywords = ['경찰', '신고', '보건소', '식중독', '병원', '환불', '소송']
        if any(keyword in review_content for keyword in serious_keywords):
            return True, "심각한 이슈 포함", 0.9
        
        # 그 외는 AI가 판단하도록
        return False, "", 0.3
    
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