"""
쿠팡이츠 비동기 리뷰 크롤러
페이지네이션을 지원하며 네트워크 응답에서 orderReviewId를 사용
"""
import sys
import os
import re
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

# 상위 디렉토리 import 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from api.crawlers.coupang_crawler import CoupangCrawler

logger = logging.getLogger(__name__)


class CoupangAsyncReviewCrawler(CoupangCrawler):
    """쿠팡이츠 비동기 리뷰 크롤러"""
    
    def __init__(self, headless: bool = True):
        super().__init__(headless)
        self.reviews_data = []
        
        # 리뷰 스크린샷 저장 경로
        self.review_screenshot_dir = Path("C:/Review_playwright/logs/screenshots/coupang_reviews")
        self.review_screenshot_dir.mkdir(parents=True, exist_ok=True)
    
    async def navigate_to_reviews(self, store_name: str = None) -> bool:
        """리뷰 페이지로 이동 및 매장 선택"""
        try:
            logger.info("========== 리뷰 페이지 이동 시작 ==========")
            
            # 현재 URL 확인
            current_url = self.page.url
            logger.info(f"현재 URL: {current_url}")
            
            # 이미 리뷰 페이지에 있는지 확인
            if 'reviews' in current_url:
                logger.info("이미 리뷰 페이지에 있습니다")
            else:
                # 리뷰 관리 페이지로 이동
                logger.info(f"리뷰 페이지로 이동 시도: {self.reviews_url}")
                try:
                    await self.page.goto(self.reviews_url, wait_until='domcontentloaded', timeout=15000)
                    logger.info("페이지 이동 완료")
                except Exception as e:
                    logger.error(f"goto 실패: {str(e)}")
            
            await asyncio.sleep(2)
            
            # 팝업 닫기
            try:
                await self.close_popup()
            except:
                pass
            
            # 날짜 범위 설정 (1개월)
            try:
                logger.info("날짜 범위 설정 시작")
                await self.set_date_range()
            except Exception as e:
                logger.error(f"날짜 설정 실패: {str(e)}")
            
            # 미답변 탭 클릭
            try:
                await self.click_unanswered_tab()
            except Exception as e:
                logger.error(f"미답변 탭 클릭 실패: {str(e)}")
            
            # 스크린샷 저장
            await self.save_review_screenshot("after_navigation")
            
            logger.info("========== 리뷰 페이지 이동 완료 ==========")
            return True
            
        except Exception as e:
            logger.error(f"리뷰 페이지 이동 실패: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            await self.save_review_screenshot("navigation_error")
            return False
    
    async def set_date_range(self):
        """날짜 범위를 1개월로 설정"""
        try:
            logger.info("날짜 범위 설정 시작")
            
            # 날짜 선택 드롭다운 클릭
            date_dropdown = await self.page.query_selector('div.css-1rkgd7l:has(svg)')
            if date_dropdown:
                await date_dropdown.click()
                await asyncio.sleep(1)
                
                # 1개월 라디오 버튼을 직접 클릭하는 방식으로 변경
                # SVG를 포함한 라벨 전체를 클릭
                try:
                    # 방법 1: 라벨 텍스트로 찾아서 클릭
                    one_month_label = await self.page.query_selector('label:has-text("1개월")')
                    if one_month_label:
                        await one_month_label.click()
                        logger.info("1개월 라벨 클릭 완료")
                    else:
                        # 방법 2: SVG 요소를 직접 클릭
                        svg_element = await self.page.query_selector('label:has-text("1개월") svg')
                        if svg_element:
                            await svg_element.click()
                            logger.info("1개월 SVG 클릭 완료")
                    
                    await asyncio.sleep(1)
                    
                    # 조회 버튼 클릭
                    search_button = await self.page.query_selector('button:has-text("조회")')
                    if search_button:
                        await search_button.click()
                        logger.info("조회 버튼 클릭 완료")
                        await asyncio.sleep(2)
                    else:
                        logger.warning("조회 버튼을 찾을 수 없습니다")
                        
                except Exception as e:
                    logger.error(f"1개월 옵션 선택 중 오류: {str(e)}")
                    
            else:
                logger.warning("날짜 드롭다운을 찾을 수 없습니다")
                
        except Exception as e:
            logger.error(f"날짜 범위 설정 실패: {str(e)}")
    
    async def click_unanswered_tab(self):
        """미답변 탭 클릭"""
        try:
            logger.info("미답변 탭 클릭 시도")
            
            # 방법 1: 버튼 태그와 텍스트로 찾기
            try:
                unanswered_button = await self.page.query_selector('button:has-text("미답변")')
                if unanswered_button:
                    await unanswered_button.click()
                    logger.info("미답변 탭 클릭 완료 (button)")
                    await asyncio.sleep(2)
                    return
            except Exception as e:
                logger.debug(f"button 태그로 찾기 실패: {str(e)}")
            
            # 방법 2: div 태그와 텍스트로 찾기
            try:
                unanswered_div = await self.page.query_selector('div:has-text("미답변")')
                if unanswered_div:
                    await unanswered_div.click()
                    logger.info("미답변 탭 클릭 완료 (div)")
                    await asyncio.sleep(2)
                    return
            except Exception as e:
                logger.debug(f"div 태그로 찾기 실패: {str(e)}")
            
            # 방법 3: JavaScript로 직접 클릭
            try:
                await self.page.evaluate('''
                    const elements = document.querySelectorAll('*');
                    for (const element of elements) {
                        if (element.textContent && element.textContent.trim() === '미답변') {
                            // 부모 요소가 클릭 가능한지 확인
                            let clickTarget = element;
                            while (clickTarget && !clickTarget.onclick && !clickTarget.getAttribute('role')) {
                                clickTarget = clickTarget.parentElement;
                            }
                            if (clickTarget) {
                                clickTarget.click();
                                console.log('미답변 탭 클릭 성공');
                            } else {
                                element.click();
                            }
                            break;
                        }
                    }
                ''')
                logger.info("미답변 탭 클릭 완료 (JavaScript)")
            except Exception as e:
                logger.warning(f"JavaScript 클릭 실패: {str(e)}")
            
            await asyncio.sleep(2)
            
            # 클릭 후 스크린샷 저장
            await self.save_review_screenshot("after_unanswered_tab_click")
            
            except Exception as e:
            logger.error(f"미답변 탭 클릭 중 오류: {str(e)}")

    async def save_review_screenshot(self, name: str):
        """리뷰 관련 스크린샷 저장"""
        if not self.page:
            return
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}.png"
            filepath = self.review_screenshot_dir / filename
            
            await self.page.screenshot(path=str(filepath))
            logger.info(f"리뷰 스크린샷 저장: {filepath}")
            
        except Exception as e:
            logger.error(f"리뷰 스크린샷 저장 실패: {str(e)}")
        
    def generate_review_id(self, platform: str, order_review_id: str) -> str:
        """쿠팡이츠 리뷰 ID 생성"""
        return f"{platform}_{order_review_id}"
    
    async def get_current_page_number(self) -> int:
        """현재 페이지 번호 가져오기"""
        try:
            active_button = await self.page.query_selector('button.active')
            if active_button:
                text = await active_button.text_content()
                return int(text)
            return 1
        except:
            return 1
    
    async def has_next_page(self) -> bool:
        """다음 페이지 존재 여부 확인"""
        try:
            next_button = await self.page.query_selector('button.pagination-btn.next-btn')
            if next_button:
                # hide-btn 클래스가 없으면 다음 페이지 존재
                classes = await next_button.get_attribute('class')
                return 'hide-btn' not in classes
            return False
        except:
            return False
    
    async def go_to_next_page(self) -> bool:
        """다음 페이지로 이동"""
        try:
            if await self.has_next_page():
                next_button = await self.page.query_selector('button.pagination-btn.next-btn')
                if next_button:
                    await next_button.click()
                    await asyncio.sleep(2)
                    current_page = await self.get_current_page_number()
                    logger.info(f"다음 페이지로 이동: {current_page}")
                    return True
            return False
        except Exception as e:
            logger.error(f"페이지 이동 실패: {str(e)}")
            return False
    
    async def get_reviews_with_pagination(self, platform_code: str, store_code: str, store_name: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """리뷰 목록 가져오기 (페이지네이션 포함)"""
        try:
            logger.info(f"========== 리뷰 수집 시작 ==========")
            logger.info(f"매장 코드: {platform_code}")
            logger.info(f"매장명: {store_name}")
            logger.info(f"최대 수집 개수: {limit}")
            
            # 수집된 리뷰를 저장할 리스트
            all_collected_reviews = []
            api_responses_received = 0
            
            # 모든 네트워크 요청을 로깅하는 핸들러 추가 (디버그용)
            def log_all_requests(request):
                if 'api' in request.url or 'review' in request.url.lower():
                    logger.debug(f"[REQUEST] {request.method} {request.url}")
            
            # 네트워크 응답 핸들러
            def handle_response(response):
                nonlocal all_collected_reviews, api_responses_received
                
                logger.debug(f"[RESPONSE] {response.status} {response.url}")
                
                # API URL 패턴을 더 넓게 확인
                if (("review" in response.url.lower() or 
                    "api" in response.url.lower() or
                    "merchant" in response.url.lower()) and 
                    response.status == 200):
                    try:
                        # content-type 확인
                        content_type = response.headers.get('content-type', '')
                        if 'application/json' in content_type:
                            # 동기적으로 JSON 파싱
                            import asyncio
                            loop = asyncio.get_event_loop()
                            future = asyncio.ensure_future(response.json())
                            data = loop.run_until_complete(future)
                            
                            logger.info(f"JSON API 응답 수신: {response.url}")
                            logger.debug(f"응답 데이터 구조: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                            
                            # 다양한 형태의 리뷰 데이터 구조 확인
                            reviews_list = None
                            
                            # 패턴 1: data.list (쿠팡이츠 기본)
                            if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
                                if "list" in data["data"]:
                                    reviews_list = data["data"]["list"]
                                elif "reviews" in data["data"]:
                                    reviews_list = data["data"]["reviews"]
                                elif "items" in data["data"]:
                                    reviews_list = data["data"]["items"]
                            # 패턴 2: reviews 직접
                            elif isinstance(data, dict) and "reviews" in data:
                                reviews_list = data["reviews"]
                            # 패턴 3: items
                            elif isinstance(data, dict) and "items" in data:
                                reviews_list = data["items"]
                            # 패턴 4: result.data
                            elif isinstance(data, dict) and "result" in data and isinstance(data["result"], dict):
                                if "data" in data["result"]:
                                    reviews_list = data["result"]["data"]
                            # 패턴 5: 리스트 직접 반환
                            elif isinstance(data, list):
                                reviews_list = data
                            
                            if reviews_list:
                                api_responses_received += 1
                                logger.info(f"리뷰 리스트 발견: {len(reviews_list)}개")
                                
                                # 첫 번째 리뷰의 구조 확인
                                if reviews_list and len(reviews_list) > 0:
                                    logger.debug(f"첫 번째 리뷰 키: {list(reviews_list[0].keys())}")
                                
                                current_page_num = loop.run_until_complete(self.get_current_page_number())
                                logger.info(f"페이지 {current_page_num}에서 {len(reviews_list)}개 리뷰 처리")
                                
                                for idx, review in enumerate(reviews_list):
                                    try:
                                        # orderReviewId 추출 - 다양한 키 이름 확인
                                        order_review_id = str(
                                            review.get("orderReviewId", "") or 
                                            review.get("reviewId", "") or 
                                            review.get("id", "") or 
                                            review.get("review_id", "")
                                        )
                                        
                                        if not order_review_id:
                                            logger.warning(f"리뷰 ID를 찾을 수 없습니다: {list(review.keys())}")
                                            continue
                                        
                                        # 날짜 형식 변환
                                        created_at = (
                                            review.get("createdAt", "") or 
                                            review.get("created_at", "") or 
                                            review.get("writeDate", "") or
                                            review.get("reviewDate", "")
                                        )
                                        if created_at:
                                            # "2025-06-07T15:30:00" -> "2025-06-07"
                                            if "T" in str(created_at):
                                                review_date = str(created_at).split("T")[0]
                                            else:
                                                review_date = str(created_at)[:10]  # YYYY-MM-DD 형식 추출
                                        else:
                                            review_date = datetime.now().strftime("%Y-%m-%d")
                                        
                                        # 주문 메뉴 추출
                                        order_items = review.get("orderItems", []) or review.get("menus", [])
                                        if isinstance(order_items, list):
                                            ordered_menu = ", ".join([
                                                item.get("menuName", "") or item.get("name", "") 
                                                for item in order_items 
                                                if isinstance(item, dict)
                                            ])
                                        else:
                                            ordered_menu = review.get("menuName", "") or review.get("menu", "")
                                        
                                        # 이미지 URL 추출
                                        review_images = review.get("reviewImages", []) or review.get("images", [])
                                        if isinstance(review_images, list):
                                            image_urls = []
                                            for img in review_images:
                                                if isinstance(img, dict):
                                                    url = img.get("imageUrl", "") or img.get("url", "")
                                                    if url:
                                                        image_urls.append(url)
                                                elif isinstance(img, str):
                                                    image_urls.append(img)
                                        else:
                                            image_urls = []
                                        
                                        # 답글 여부 확인
                                        has_reply = (
                                            review.get("hasReply", False) or 
                                            review.get("has_reply", False) or 
                                            bool(review.get("reply", "")) or
                                            bool(review.get("replyContent", ""))
                                        )
                                        
                                        # 리뷰 내용 추출
                                        review_content = (
                                            review.get("reviewText", "") or 
                                            review.get("review_text", "") or 
                                            review.get("content", "") or
                                            review.get("comment", "")
                                        )
                                        
                                        # 리뷰 데이터 생성
                                        review_data = {
                                            'review_id': self.generate_review_id('coupang', order_review_id),
                                            'original_id': order_review_id,  # 쿠팡이츠 원본 ID
                                            'platform': 'coupang',
                                            'platform_code': platform_code,
                                            'store_code': store_code,
                                            'review_name': (
                                                review.get("customerNickname", "") or 
                                                review.get("customer_nickname", "") or 
                                                review.get("nickname", "") or
                                                review.get("writer", "") or
                                                "익명"
                                            ),
                                            'rating': int(
                                                review.get("rating", 5) or 
                                                review.get("score", 5) or 
                                                review.get("star", 5)
                                            ),
                                            'review_content': review_content,
                                            'review_date': review_date,
                                            'ordered_menu': ordered_menu,
                                            'review_images': image_urls,
                                            'delivery_review': review.get("deliveryReview", ""),
                                            'has_reply': has_reply,
                                            'writableComment': not has_reply
                                        }
                                        
                                        all_collected_reviews.append(review_data)
                                        logger.debug(f"리뷰 수집: {order_review_id} - {review_data['review_name']}")
                                        
                                        if len(all_collected_reviews) >= limit:
                                            logger.info(f"수집 한도 {limit}개 도달")
                                            return
                                            
                                    except Exception as e:
                                        logger.error(f"리뷰 파싱 중 오류: {str(e)}")
                                        logger.debug(f"문제가 된 리뷰 데이터: {json.dumps(review, ensure_ascii=False)[:200]}")
                                        continue
                            else:
                                # 리뷰 데이터를 찾지 못한 경우 전체 구조 로깅
                                logger.debug(f"리뷰 데이터를 찾을 수 없음. 전체 키: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                                        
                    except Exception as e:
                        logger.error(f"API 응답 처리 중 오류: {str(e)}")
                        logger.debug(f"오류 발생 URL: {response.url}")
            
            # 리스너 등록
            self.page.on("request", log_all_requests)
            self.page.on("response", handle_response)
            
            try:
                # 리뷰 페이지로 이동
                if not await self.navigate_to_reviews(store_name):
                    logger.error("리뷰 페이지 이동 실패")
                    return []
                
                # 첫 페이지 데이터 수집을 위해 잠시 대기
                await asyncio.sleep(3)
                
                # API 호출이 없었다면 수동으로 트리거 시도
                if api_responses_received == 0:
                    logger.info("API 응답이 없어 페이지 새로고침 시도")
                    await self.page.reload()
                    await asyncio.sleep(3)
                
                # 페이지네이션 처리
                page_count = 0
                max_pages = 20  # 무한 루프 방지
                
                while len(all_collected_reviews) < limit and page_count < max_pages:
                    page_count += 1
                    current_page = await self.get_current_page_number()
                    logger.info(f"현재 페이지: {current_page} (처리 {page_count}/{max_pages})")
                    
                    # 현재 페이지 스크린샷
                    await self.save_review_screenshot(f"page_{current_page}")
                    
                    # API 응답 대기
                    await asyncio.sleep(2)
                    
                    # 리뷰가 수집되지 않았다면 더 기다려보기
                    if len(all_collected_reviews) == 0 and page_count == 1:
                        logger.info("첫 페이지에서 리뷰를 찾지 못해 추가 대기")
                        await asyncio.sleep(3)
                    
                    # 다음 페이지가 있고 아직 한도에 도달하지 않은 경우
                    if await self.has_next_page():
                        if not await self.go_to_next_page():
                            logger.info("더 이상 페이지가 없습니다")
                            break
                        # 페이지 이동 후 API 응답 대기
                        await asyncio.sleep(3)
                    else:
                        logger.info("마지막 페이지입니다")
                        break
                
                logger.info(f"\n========== 총 {len(all_collected_reviews)}개의 리뷰 수집 완료 ==========")
                
                # 수집된 리뷰 요약
                if all_collected_reviews:
                    logger.info("\n수집된 리뷰 요약:")
                    for i, review in enumerate(all_collected_reviews[:5]):
                        logger.info(f"  {i+1}. [{review['original_id']}] {review['review_name']} - {review['rating']}점")
                        logger.info(f"     날짜: {review['review_date']}")
                        logger.info(f"     내용: {review['review_content'][:50]}...")
                else:
                    logger.warning("수집된 리뷰가 없습니다. API 응답을 확인해주세요.")
                
                return all_collected_reviews
                
            finally:
                # 리스너 제거
                self.page.remove_listener("request", log_all_requests)
                self.page.remove_listener("response", handle_response)
                
        except Exception as e:
            logger.error(f"리뷰 수집 중 오류: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []