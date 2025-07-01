"""
네이버 리뷰 파서
DOM에서 리뷰 데이터를 추출하고 DB 형식으로 변환
"""
import re
import json
import logging
import hashlib
from datetime import datetime
from typing import Dict, Optional, List
from playwright.async_api import Page, ElementHandle

logger = logging.getLogger(__name__)


class NaverReviewParser:
    def __init__(self, supabase=None):
        """파서 초기화"""
        self.supabase = supabase
    
    def generate_review_id(self, store_code: str, review_text: str, reviewer_name: str) -> str:
        """
        리뷰 고유 ID 생성
        
        Args:
            store_code: 매장 코드
            review_text: 리뷰 내용
            reviewer_name: 리뷰어 이름
            
        Returns:
            str: 해시 기반 고유 ID
        """
        # 리뷰의 고유성을 보장하기 위해 여러 필드 조합
        unique_string = f"{store_code}_{reviewer_name}_{review_text[:50]}"
        return hashlib.md5(unique_string.encode()).hexdigest()
    
    def parse_review_date(self, date_text: str) -> str:
        """
        네이버 날짜 형식을 YYYY-MM-DD로 변환
        예: "2025. 6. 30(월)" -> "2025-06-30"
        
        Args:
            date_text: 네이버 날짜 텍스트
            
        Returns:
            str: YYYY-MM-DD 형식의 날짜
        """
        try:
            # 괄호와 요일 제거
            date_text = re.sub(r'\([^)]*\)', '', date_text).strip()
            
            # "2025. 6. 30" 형식 처리
            if '. ' in date_text:
                parts = date_text.split('. ')
                if len(parts) >= 3:
                    year = parts[0]
                    month = parts[1].zfill(2)  # 한 자리 월을 두 자리로
                    day = parts[2].replace('.', '').strip().zfill(2)  # 한 자리 일을 두 자리로
                    return f"{year}-{month}-{day}"
            
            # "24.12.30." 형식 처리 (기존 코드)
            date_text = date_text.replace('.', '')
            if len(date_text) == 6:  # YYMMDD
                year = '20' + date_text[:2]
                month = date_text[2:4]
                day = date_text[4:6]
                return f"{year}-{month}-{day}"
            
            # 다른 형식의 경우 현재 날짜 반환
            return datetime.now().strftime('%Y-%m-%d')
            
        except Exception as e:
            logger.error(f"날짜 파싱 실패 - date_text: {date_text}, error: {e}")
            return datetime.now().strftime('%Y-%m-%d')
    
    async def parse_review_element(self, page: Page, review_element: ElementHandle, store_code: str) -> Optional[Dict]:
        """
        리뷰 DOM 요소에서 데이터 추출
        
        Args:
            page: Playwright page 객체
            review_element: 리뷰 DOM 요소
            store_code: 매장 코드
            
        Returns:
            dict: DB 저장용 형식의 리뷰 데이터
        """
        try:
            # 리뷰어 이름 추출 - 수정된 셀렉터
            reviewer_elem = await review_element.query_selector('span.pui__NMi-Dp')
            reviewer_name = await reviewer_elem.inner_text() if reviewer_elem else '익명'
            
            # 날짜 추출 - 수정된 셀렉터
            date_elem = await review_element.query_selector('div.pui__4rEbt5 time')
            if date_elem:
                review_date_text = await date_elem.inner_text()
                # "2025. 6. 30(월)" 형식 처리
                review_date = self.parse_review_date(review_date_text)
            else:
                review_date = datetime.now().strftime('%Y-%m-%d')
            
            # 별점 추출 - 네이버는 별점이 없을 수 있으므로 NULL 허용
            rating = None  # 기본값을 NULL로 변경
            rating_elem = await review_element.query_selector('[data-pui-rating-score]')
            if rating_elem:
                rating_score = await rating_elem.get_attribute('data-pui-rating-score')
                if rating_score:
                    rating = int(rating_score)
            else:
                # 대체 방법: 채워진 별 개수 세기
                filled_stars = await review_element.query_selector_all('path[fill="#FFD400"]')
                if filled_stars:
                    rating = len(filled_stars)
            
            # 리뷰 내용 추출 - 수정된 셀렉터
            content_elem = await review_element.query_selector('a.pui__xtsQN-')
            review_content = ''
            if content_elem:
                review_content = await content_elem.inner_text()
            
            # 이미지 URL 추출 - 수정된 셀렉터
            image_elems = await review_element.query_selector_all('div.Review_img_box__iZRS7 img')
            image_urls = []
            for img_elem in image_elems:
                img_url = await img_elem.get_attribute('src')
                if img_url:
                    image_urls.append(img_url)
            
            # 키워드/태그 추출 - 수정된 셀렉터
            keyword_elems = await review_element.query_selector_all('div.pui__HLNvmI span.pui__jhpEyP')
            keywords = []
            for keyword_elem in keyword_elems:
                keyword_text = await keyword_elem.inner_text()
                if keyword_text:
                    keywords.append(keyword_text.strip())
            
            # 답글 여부 확인
            reply_elem = await review_element.query_selector('div.pui__ogNNXj')  # 사장님 답글 영역
            has_reply = reply_elem is not None
            response_status = 'posted' if has_reply else 'pending'
            
            # 리뷰 ID 생성
            review_id = self.generate_review_id(store_code, review_content, reviewer_name)
            
            # platform_code 추출 (URL에서)
            current_url = page.url
            # URL 형식: https://new.smartplace.naver.com/bizes/place/{platform_code}/reviews
            match = re.search(r'/bizes/place/(\d+)', current_url)
            platform_code = match.group(1) if match else store_code
            
            # DB 형식으로 변환
            db_format = {
                'review_id': review_id,
                'store_code': store_code,
                'platform': 'naver',
                'platform_code': platform_code,
                'review_name': reviewer_name,
                'rating': rating,  # NULL 허용
                'review_content': review_content,
                'ordered_menu': None,  # 네이버는 주문 메뉴 정보가 없으므로 NULL
                'delivery_review': None,  # 네이버는 배달 리뷰 없음
                'review_date': review_date,
                'review_images': image_urls,
                'sentiment_score': None,
                'review_category': None,
                'keywords': keywords,  # 키워드는 별도 필드에 저장
                'urgency_level': 'low',
                'ai_response': None,
                'manual_response': None,
                'final_response': None,
                'response_status': response_status,
                'response_method': None,
                'response_at': None,
                'response_by': None,
                'response_quality_score': None,
                'customer_reaction': None,
                'follow_up_required': False,
                'boss_reply_needed': rating <= 3 if rating else False,  # rating이 NULL일 수도 있으므로 체크
                'review_reason': None,
                'retry_count': 0,
                'last_retry_at': None,
                'error_message': None,
                'processing_duration': None,
                'crawled_at': datetime.now().isoformat(),  # datetime 객체를 ISO 형식 문자열로 변환
                'processed_at': None,
                'is_deleted': False,
                'deleted_at': None,
                'notes': None
            }
            
            logger.debug(f"파싱된 네이버 리뷰: {reviewer_name} - {rating}점 - {review_date}")
            return db_format
            
        except Exception as e:
            logger.error(f"리뷰 요소 파싱 오류: {e}")
            logger.exception("상세 오류:")
            return None
    
    async def save_reviews(self, reviews: List[Dict], store_code: str) -> Dict:
        """리뷰 저장"""
        try:
            if not self.supabase:
                logger.error("Supabase 서비스가 초기화되지 않았습니다")
                return {
                    'saved': 0,
                    'total': len(reviews),
                    'errors': ['Supabase 서비스 없음']
                }
            
            saved_count = 0
            errors = []
            
            logger.info(f"네이버 리뷰 {len(reviews)}개 저장 시작 - store_code: {store_code}")
            
            for review in reviews:
                try:
                    # 저장 전 데이터 검증
                    logger.debug(f"저장할 네이버 리뷰 데이터: {review['review_id']} - {review.get('review_name')} - {review.get('rating')}점")
                    
                    # 필수 필드 확인 - rating을 제외
                    required_fields = ['review_id', 'store_code', 'platform', 'review_date']
                    missing_fields = [f for f in required_fields if f not in review or review[f] is None]

                    if missing_fields:
                        logger.error(f"필수 필드 누락: {missing_fields}")
                        errors.append(f"리뷰 {review.get('review_id', 'unknown')}: 필수 필드 누락 - {missing_fields}")
                        continue
                    
                    # is_deleted 필드 명시적 설정
                    if 'is_deleted' not in review:
                        review['is_deleted'] = False
                    
                    # 저장 시도
                    result = await self.supabase.save_review(review)
                    
                    if result:
                        saved_count += 1
                        logger.info(f"네이버 리뷰 저장 성공: {review['review_id']} - {review.get('review_name')} - {review.get('rating')}점")
                        
                        # 저장 직후 확인 조회
                        verify_query = self.supabase.client.table('reviews').select('*').eq('review_id', review['review_id'])
                        verify_response = await self.supabase._execute_query(verify_query)
                        
                        if verify_response.data:
                            logger.debug(f"저장 확인 - DB에 저장됨: {review['review_id']}")
                        else:
                            logger.warning(f"저장 확인 실패 - DB에서 찾을 수 없음: {review['review_id']}")
                    else:
                        logger.error(f"리뷰 저장 실패: {review['review_id']}")
                        errors.append(f"리뷰 {review['review_id']} 저장 실패")
                        
                except Exception as e:
                    logger.error(f"리뷰 저장 오류: {e}")
                    logger.exception("상세 오류:")
                    errors.append(f"리뷰 저장 오류: {str(e)}")
            
            # 저장 결과 요약
            logger.info(f"네이버 리뷰 저장 완료 - 성공: {saved_count}/{len(reviews)}")
            if errors:
                logger.warning(f"저장 실패 리뷰: {len(errors)}개")
                for error in errors[:5]:  # 처음 5개만 로그
                    logger.warning(f"  - {error}")
            
            # 저장 후 해당 매장의 네이버 리뷰 총 개수 확인
            if self.supabase:
                try:
                    count_query = self.supabase.client.table('reviews').select('*', count='exact').eq('store_code', store_code).eq('platform', 'naver')
                    count_response = await self.supabase._execute_query(count_query)
                    logger.info(f"매장 {store_code}의 총 네이버 리뷰 수: {count_response.count}")
                except Exception as e:
                    logger.error(f"리뷰 카운트 확인 오류: {e}")
            
            return {
                'saved': saved_count,
                'total': len(reviews),
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"리뷰 저장 중 오류: {e}")
            logger.exception("상세 오류:")
            return {
                'saved': 0,
                'total': len(reviews),
                'errors': [str(e)]
            }
    
    async def parse_reviews_from_page(self, page: Page, store_code: str) -> List[Dict]:
        """
        페이지에서 모든 리뷰 파싱
        
        Args:
            page: Playwright page 객체
            store_code: 매장 코드
            
        Returns:
            List[Dict]: 파싱된 리뷰 리스트
        """
        try:
            reviews = []
            
            # 리뷰 요소들 찾기
            review_elements = await page.query_selector_all('li.pui__X35jYm.EjjAW')
            logger.info(f"네이버 리뷰 요소 {len(review_elements)}개 발견")
            
            for idx, review_elem in enumerate(review_elements):
                try:
                    review_data = await self.parse_review_element(page, review_elem, store_code)
                    if review_data:
                        reviews.append(review_data)
                        logger.debug(f"리뷰 {idx+1}/{len(review_elements)} 파싱 성공")
                    else:
                        logger.warning(f"리뷰 {idx+1}/{len(review_elements)} 파싱 실패")
                except Exception as e:
                    logger.error(f"리뷰 {idx+1} 파싱 중 오류: {e}")
                    continue
            
            logger.info(f"총 {len(reviews)}개의 네이버 리뷰 파싱 완료")
            return reviews
            
        except Exception as e:
            logger.error(f"페이지 리뷰 파싱 오류: {e}")
            logger.exception("상세 오류:")
            return []