"""
배달의민족 Windows 동기식 리뷰 크롤러
비동기 문제를 피하기 위한 동기식 버전
"""
# Windows 이벤트 루프 정책 설정 (가장 먼저!)
import asyncio
import sys
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import re
import json
import logging
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

# 직접 실행을 위한 경로 설정
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 절대 경로로 import
from .baemin_sync_crawler import BaeminSyncCrawler

logger = logging.getLogger(__name__)

class BaeminSyncReviewCrawler(BaeminSyncCrawler):
    """배달의민족 동기식 리뷰 크롤러"""
    
    def __init__(self, headless: bool = True):
        super().__init__(headless)
        self.reviews_data = []
        
        # 리뷰 스크린샷 저장 경로
        self.review_screenshot_dir = Path("C:/Review_playwright/logs/screenshots/baemin_reviews")
        self.review_screenshot_dir.mkdir(parents=True, exist_ok=True)
    
    def close_popup(self):
        """팝업 닫기 - 다양한 기간의 '보지 않기' 옵션 처리"""
        try:
            # 팝업이 나타날 때까지 잠시 대기
            self.page.wait_for_timeout(2000)
            
            # 우선순위: 더 긴 기간의 "보지 않기" 버튼을 먼저 찾아서 클릭
            priority_selectors = [
                # 긴 기간부터 우선적으로 처리
                ('button:has-text("30일간 보지 않기")', '30일간'),
                ('span:has-text("30일간 보지 않기")', '30일간'),
                ('button:has-text("7일간 보지 않기")', '7일간'),
                ('span:has-text("7일간 보지 않기")', '7일간'),
                ('button:has-text("3일 동안 보지 않기")', '3일 동안'),
                ('span:has-text("3일 동안 보지 않기")', '3일 동안'),
                ('button:has-text("1일간 보지 않기")', '1일간'),
                ('span:has-text("1일간 보지 않기")', '1일간'),
                ('button:has-text("오늘 하루 보지 않기")', '오늘 하루'),
                ('span:has-text("오늘 하루 보지 않기")', '오늘 하루')
            ]
            
            # 먼저 우선순위 선택자로 시도
            for selector, period in priority_selectors:
                try:
                    if self.page.is_visible(selector):
                        self.page.click(selector)
                        logger.info(f"팝업을 닫았습니다: {period} 보지 않기")
                        self.page.wait_for_timeout(1000)
                        return True
                except:
                    continue
            
            # "보지 않기"가 포함된 모든 요소를 찾아서 처리
            try:
                elements_with_text = self.page.get_by_text("보지 않기")
                count = elements_with_text.count()
                
                if count > 0:
                    logger.info(f"'보지 않기' 텍스트가 포함된 {count}개의 요소 발견")
                    
                    for i in range(count):
                        try:
                            element = elements_with_text.nth(i)
                            if element.is_visible():
                                text_content = element.text_content()
                                element.click()
                                logger.info(f"팝업을 닫았습니다: {text_content}")
                                self.page.wait_for_timeout(1000)
                                return True
                        except:
                            continue
            except:
                pass
                
            logger.debug("닫을 팝업이 없거나 이미 닫혀있습니다")
            return False
            
        except Exception as e:
            logger.debug(f"팝업 처리 중 예외 발생: {str(e)}")
            return False

    def handle_popups(self):
        """모든 종류의 팝업 처리"""
        try:
            # 먼저 "보지 않기" 타입 팝업 처리 시도
            self.close_popup()
            
            # 추가적인 팝업 처리 (닫기, 확인 등)
            self.page.wait_for_timeout(1000)
            
            # 다양한 팝업 닫기 버튼 선택자
            popup_close_selectors = [
                'button:has-text("닫기")',
                'button:has-text("확인")',
                '[aria-label="Close"]',
                '[aria-label="닫기"]',
                '.close-button',
                '.popup-close',
                'button.close',
                'button[aria-label="close"]',
                'button[aria-label="닫기"]',
                '[role="button"][aria-label="close"]'
            ]
            
            closed_count = 0
            for selector in popup_close_selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    for element in elements:
                        if element.is_visible():
                            element.click()
                            closed_count += 1
                            logger.info(f"추가 팝업 닫기: {selector}")
                            self.page.wait_for_timeout(500)
                except:
                    continue
            
            if closed_count > 0:
                logger.info(f"추가로 {closed_count}개의 팝업을 닫았습니다")
                
        except Exception as e:
            logger.debug(f"팝업 처리 중 예외 발생: {str(e)}")

    def navigate_to_reviews(self, platform_code: str) -> bool:
        """리뷰 페이지로 이동"""
        try:
            logger.info("========== 리뷰 페이지 이동 시작 ==========")
            
            # 현재 열린 페이지 수 저장
            initial_pages = len(self.context.pages)
            logger.info(f"현재 열린 탭 수: {initial_pages}")
            
            review_url = f"https://self.baemin.com/shops/{platform_code}/reviews"
            logger.info(f"이동할 URL: {review_url}")
            
            logger.info("페이지 이동 중...")
            self.page.goto(review_url)
            
            logger.info("networkidle 대기 중...")
            self.page.wait_for_load_state('networkidle')
            
            logger.info("3초 추가 대기...")
            self.page.wait_for_timeout(3000)
            
            # 팝업 처리 추가
            logger.info("========== 팝업 처리 시작 ==========")
            self.handle_popups()
            logger.info("========== 팝업 처리 완료 ==========")

            # 새 탭이 열렸는지 확인하고 닫기
            current_pages = self.context.pages
            if len(current_pages) > initial_pages:
                logger.info(f"⚠️ 새 탭이 {len(current_pages) - initial_pages}개 열렸습니다.")
                for i, page in enumerate(current_pages[initial_pages:]):
                    logger.info(f"  새 탭 {i+1} URL: {page.url}")
                    page.close()
                    logger.info(f"  새 탭 {i+1} 닫음")
                # 원래 페이지로 포커스 이동
                self.page = self.context.pages[0]
                logger.info("원래 탭으로 포커스 이동")
            
            # 현재 URL 확인
            current_url = self.page.url
            logger.info(f"현재 URL: {current_url}")
            
            # 리뷰 페이지가 아닌 경우 다시 시도
            if "/reviews" not in current_url:
                logger.warning("⚠️ 리뷰 페이지가 아닙니다. 다시 이동 시도...")
                self.page.goto(review_url)
                self.page.wait_for_load_state('networkidle')
                self.page.wait_for_timeout(2000)
                logger.info(f"재이동 후 URL: {self.page.url}")
            
            # 미답변 탭 클릭 시도
            logger.info("========== 미답변 탭 클릭 시도 ==========")
            try:
                # 여러 가지 선택자로 시도
                unanswered_selectors = [
                    'button#no-comment',
                    'button:has-text("미답변")',
                    '//button[contains(text(), "미답변")]',
                    'text=미답변'
                ]
                
                clicked = False
                for selector in unanswered_selectors:
                    logger.info(f"선택자 시도: {selector}")
                    try:
                        if self.page.is_visible(selector):
                            self.page.click(selector)
                            logger.info(f"미답변 탭 클릭 성공: {selector}")
                            clicked = True
                            break
                        else:
                            logger.info(f"❌ {selector} - 보이지 않음")
                    except Exception as e:
                        logger.info(f"❌ {selector} - 에러: {e}")
                
                if clicked:
                    logger.info("2초 대기 중...")
                    self.page.wait_for_timeout(2000)
                else:
                    logger.warning("⚠️ 미답변 탭을 찾을 수 없습니다.")
                    
                    # 모든 버튼 찾아보기
                    all_buttons = self.page.query_selector_all('button')
                    logger.info(f"페이지의 총 버튼 수: {len(all_buttons)}")
                    for i, button in enumerate(all_buttons[:10]):  # 처음 10개만
                        try:
                            text = button.text_content()
                            if text:
                                logger.info(f"  버튼 {i}: '{text.strip()}'")
                        except:
                            pass
                            
            except Exception as e:
                logger.error(f"미답변 탭 클릭 중 예외: {e}")
            
            logger.info("========== 리뷰 페이지 이동 완료 ==========\n")
            return True
            
        except Exception as e:
            logger.error(f"리뷰 페이지 이동 실패: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            self.save_review_screenshot("navigation_error")
            return False
    
    def save_review_screenshot(self, name: str):
        """리뷰 관련 스크린샷 저장"""
        if not self.page:
            return
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}.png"
            filepath = self.review_screenshot_dir / filename
            
            self.page.screenshot(path=str(filepath))
            logger.info(f"리뷰 스크린샷 저장: {filepath}")
            
        except Exception as e:
            logger.error(f"리뷰 스크린샷 저장 실패: {str(e)}")
    
    def generate_review_id(self, platform: str, original_id: str) -> str:
        """배민 원본 ID를 사용한 리뷰 ID 생성"""
        # 플랫폼_원본ID 형식으로 간단하게
        # 예: "baemin_2025060801238589"
        return f"{platform}_{original_id}"

    def get_reviews(self, platform_code: str, store_code: str, limit: int = 50) -> List[Dict[str, Any]]:
        """리뷰 목록 가져오기 (네트워크 응답 가로채기 방식)"""
        try:
            logger.info(f"========== 리뷰 수집 시작 ==========")
            logger.info(f"매장 코드: {platform_code}")
            logger.info(f"스토어 코드: {store_code}")
            logger.info(f"최대 수집 개수: {limit}")
            
            # 수집된 리뷰를 저장할 리스트
            collected_reviews = []
            api_response_received = False
            
            # 네트워크 응답 핸들러
            def handle_response(response):
                nonlocal collected_reviews, api_response_received
                
                # 미답변 리뷰 API 응답인지 확인 (중요: no-comment가 포함된 URL만)
                if f"/shops/{platform_code}/reviews" in response.url and response.status == 200:
                    # 미답변 탭의 API인지 확인
                    if "no-comment" in response.url or "is_answered=false" in response.url or "/reviews?" in response.url:
                        try:
                            # JSON 응답 파싱
                            data = response.json()
                            logger.info(f"미답변 API 응답 수신: {response.url}")
                            
                            # reviews 배열이 있는지 확인
                            if "reviews" in data and isinstance(data["reviews"], list):
                                api_response_received = True
                                logger.info(f"미답변 API에서 {len(data['reviews'])}개 리뷰 발견")
                                
                                # collected_reviews 초기화 (이전 수집 내용 제거)
                                collected_reviews.clear()
                                
                                for idx, review in enumerate(data["reviews"][:limit]):
                                    try:
                                        # 원본 ID에서 날짜 추출
                                        original_id = str(review.get("id", ""))
                                        if len(original_id) >= 8:
                                            date_str = original_id[:8]  # "20250608"
                                            review_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                                        else:
                                            # ID가 없거나 형식이 다른 경우 createdDate 사용
                                            review_date = self._convert_relative_date(review.get("createdDate", "오늘"))
                                        
                                        # 메뉴 정보 추출
                                        menus = review.get("menus", [])
                                        ordered_menu = ", ".join([menu.get("name", "") for menu in menus if menu.get("name")])
                                        
                                        # 배달 리뷰 추출
                                        delivery_review = ""
                                        if "deliveryReviews" in review and review["deliveryReviews"]:
                                            recommendation = review["deliveryReviews"].get("recommendation", "")
                                            if recommendation == "GOOD":
                                                delivery_review = "좋아요"
                                            elif recommendation == "BAD":
                                                delivery_review = "별로"
                                            else:
                                                delivery_review = "보통"
                                        
                                        # 이미지 URL 추출
                                        images = review.get("images", [])
                                        review_images = [img.get("imageUrl", "") for img in images if img.get("imageUrl")]
                                        
                                        # 답글 여부 확인
                                        has_reply = len(review.get("comments", [])) > 0
                                        writableComment = review.get("writableComment", True)
                                        
                                        # 리뷰 내용에서 이모지 제거
                                        review_content = review.get("contents", "")
                                        if review_content:
                                            review_content = review_content.encode('utf-8', 'ignore').decode('utf-8')
                                        
                                        # 리뷰 데이터 생성
                                        review_data = {
                                            'review_id': self.generate_review_id('baemin', original_id),
                                            'original_id': original_id,  # 배민 원본 ID 저장
                                            'platform': 'baemin',
                                            'platform_code': platform_code,
                                            'store_code': store_code,
                                            'review_name': review.get("memberNickname", "익명"),
                                            'rating': int(review.get("rating", 5)),
                                            'review_content': review_content,
                                            'review_date': review_date,  # YYYY-MM-DD 형식
                                            'ordered_menu': ordered_menu,
                                            'review_images': review_images,
                                            'delivery_review': delivery_review,
                                            'has_reply': has_reply,
                                            'writableComment': writableComment
                                        }
                                        
                                        collected_reviews.append(review_data)
                                        
                                        logger.info(f"[API] 리뷰 {idx + 1} 수집:")
                                        logger.info(f"  ID: {original_id}")
                                        logger.info(f"  작성자: {review_data['review_name']}")
                                        logger.info(f"  날짜: {review_date}")
                                        logger.info(f"  내용: {review_content[:50]}...")
                                        
                                    except Exception as e:
                                        logger.error(f"리뷰 파싱 중 오류: {str(e)}")
                                        continue
                                        
                        except Exception as e:
                            logger.error(f"API 응답 처리 중 오류: {str(e)}")
                    else:
                        # 전체 리뷰 API는 무시
                        logger.info(f"전체 리뷰 API 응답 무시: {response.url}")
                
            # 네트워크 응답 리스너 등록
            self.page.on("response", handle_response)
            
            try:
                # 리뷰 페이지로 이동 (API 호출 트리거)
                if not self.navigate_to_reviews(platform_code):
                    logger.error("리뷰 페이지 이동 실패")
                    return []
                
                # API 응답 대기 (최대 10초)
                wait_time = 0
                while not api_response_received and wait_time < 10:
                    self.page.wait_for_timeout(1000)
                    wait_time += 1
                    
                if not api_response_received:
                    logger.warning("미답변 API 응답을 받지 못했습니다. DOM 파싱으로 대체합니다.")
                    return self._get_reviews_by_dom_parsing(platform_code, store_code, limit)
                
                logger.info(f"\n========== 총 {len(collected_reviews)}개의 미답변 리뷰 수집 완료 ==========")
                
                # 수집된 리뷰 요약
                if collected_reviews:
                    logger.info("\n수집된 미답변 리뷰 요약:")
                    for i, review in enumerate(collected_reviews[:5]):
                        logger.info(f"  {i+1}. [{review['original_id']}] {review['review_name']} - {review['rating']}점")
                        logger.info(f"     날짜: {review['review_date']}")
                        logger.info(f"     내용: {review['review_content'][:50]}...")
                
                return collected_reviews
                
            finally:
                # 리스너 제거
                self.page.remove_listener("response", handle_response)
                
        except Exception as e:
            logger.error(f"리뷰 수집 중 오류: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def _convert_relative_date(self, date_str: str) -> str:
        """상대적 날짜를 YYYY-MM-DD 형식으로 변환"""
        from datetime import datetime, timedelta
        
        now = datetime.now()
        
        if date_str == "오늘":
            return now.strftime("%Y-%m-%d")
        elif date_str == "어제":
            return (now - timedelta(days=1)).strftime("%Y-%m-%d")
        elif "일 전" in date_str:
            days = int(re.search(r'(\d+)일 전', date_str).group(1))
            return (now - timedelta(days=days)).strftime("%Y-%m-%d")
        elif "개월 전" in date_str:
            months = int(re.search(r'(\d+)개월 전', date_str).group(1))
            return (now - timedelta(days=months*30)).strftime("%Y-%m-%d")
        else:
            return now.strftime("%Y-%m-%d")
        
    def _get_reviews_by_dom_parsing(self, platform_code: str, store_code: str, limit: int) -> List[Dict[str, Any]]:
        """DOM 파싱 방식 (폴백용)"""
        logger.info("DOM 파싱 방식으로 리뷰 수집 시도...")
        
        reviews = []
        
        # 리뷰 카드 찾기
        review_cards = self.page.query_selector_all('div[class*="ReviewContent-module__"]')
        
        if not review_cards:
            logger.warning("DOM 파싱: 리뷰 카드를 찾을 수 없습니다")
            return []
        
        for idx, card in enumerate(review_cards[:limit]):
            try:
                card_text = card.text_content()
                
                # 간단한 파싱 로직
                review_data = {
                    'review_id': f"baemin_{platform_code}_{idx}_{datetime.now().strftime('%Y%m%d')}",
                    'original_id': f"dom_parsed_{idx}",
                    'platform': 'baemin',
                    'platform_code': platform_code,
                    'store_code': store_code,
                    'review_name': '익명',
                    'rating': 5,
                    'review_content': card_text[:100] if card_text else '',
                    'review_date': datetime.now().strftime('%Y-%m-%d'),
                    'ordered_menu': '',
                    'review_images': [],
                    'delivery_review': '',
                    'has_reply': False,
                    'writableComment': True
                }
                
                reviews.append(review_data)
                
            except Exception as e:
                logger.error(f"DOM 파싱 중 오류: {str(e)}")
                continue
        
        logger.info(f"DOM 파싱으로 {len(reviews)}개 리뷰 수집")
        return reviews
    
    def find_review_element(self, review_card, review_id: str):
        """특정 리뷰 요소 찾기"""
        # 리뷰 카드가 이미 전달된 경우 그대로 반환
        return review_card
    
    def post_reply(self, review_data: Dict[str, Any], reply_text: str) -> bool:
        """리뷰에 답글 작성"""
        try:
            logger.info(f"답글 작성 시작 - 리뷰 ID: {review_data.get('original_id', '')}")
            
            # 현재 페이지에서 해당 리뷰 찾기
            review_cards = self.page.query_selector_all('.ReviewCard-module__3e8e')
            
            target_card = None
            for card in review_cards:
                # 리뷰 내용으로 매칭 (더 정확한 매칭 로직 필요)
                content_element = card.query_selector('.ReviewCard-module__text_1xz9')
                if content_element and review_data['review_content'] in content_element.text_content():
                    target_card = card
                    break
            
            if not target_card:
                logger.error("리뷰 카드를 찾을 수 없습니다")
                return False
            
            # 답글 등록 버튼 찾기
            reply_button = target_card.query_selector('button:has-text("사장님 댓글 등록하기")')
            if not reply_button:
                logger.error("답글 등록 버튼을 찾을 수 없습니다")
                return False
            
            # 버튼 클릭
            reply_button.click()
            logger.info("답글 등록 버튼 클릭")
            self.page.wait_for_timeout(1000)
            
            # 텍스트 입력 영역 찾기
            textarea = self.page.query_selector('textarea[placeholder*="댓글"]')
            if not textarea:
                # 다른 선택자로 시도
                textarea = self.page.query_selector('textarea')
            
            if not textarea:
                logger.error("텍스트 입력 영역을 찾을 수 없습니다")
                return False
            
            # 기존 텍스트 삭제하고 새 답글 입력
            textarea.click()
            textarea.press('Control+A')
            textarea.type(reply_text)
            logger.info(f"답글 입력 완료: {reply_text[:50]}...")
            
            # 등록 버튼 찾기
            submit_button = self.page.query_selector('button:has-text("등록")')
            if not submit_button:
                logger.error("등록 버튼을 찾을 수 없습니다")
                return False
            
            # 등록 버튼 클릭
            submit_button.click()
            logger.info("답글 등록 버튼 클릭")
            
            # 등록 완료 대기
            self.page.wait_for_timeout(3000)
            
            return True
            
        except Exception as e:
            logger.error(f"답글 작성 중 오류: {str(e)}")
            self.save_review_screenshot("reply_error")
            return False


# 테스트 코드
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    crawler = BaeminSyncReviewCrawler(headless=False)
    try:
        crawler.start_browser()
        print("브라우저 시작 완료")
        
        # 테스트용 로그인 정보
        user_id = "hong7704002646"
        password = "bin986200#"
        
        login_success = crawler.login(user_id, password)
        print(f"로그인 결과: {login_success}")
        
        if login_success:
            # 실제 매장 코드로 테스트
            platform_code = "14545991"  # 닭클리닉 맛닭
            store_code = "STR_20250607112755_829127"
            
            reviews = crawler.get_reviews(platform_code, store_code, limit=5)
            print(f"\n발견된 리뷰: {len(reviews)}개")
            
            for review in reviews:
                print(f"\n작성자: {review['review_name']}")
                print(f"별점: {review['rating']}점")
                print(f"내용: {review['review_content'][:50]}...")
                print(f"날짜: {review['review_date']}")
        
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        input("\n브라우저를 닫으려면 Enter를 누르세요...")
        crawler.close_browser()