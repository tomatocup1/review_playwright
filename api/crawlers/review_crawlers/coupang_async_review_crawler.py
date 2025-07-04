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
    async def start(self):
        """브라우저 시작 (호환성을 위한 별칭)"""
        await self.start_browser()
    
    async def close(self):
        """브라우저 종료 (호환성을 위한 별칭)"""
        await self.close_browser()
        
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
                logger.info("미답변 탭 처리 완료")
            except Exception as e:
                logger.error(f"미답변 탭 클릭 중 예외: {str(e)}")
            
            # 페이지에 표시된 리뷰 확인
            await asyncio.sleep(3)  # UI 렌더링 대기
            
            # DOM에서 리뷰 요소 직접 확인
            review_info = await self.page.evaluate('''() => {
                const reviewCards = document.querySelectorAll('[class*="review-card"], [class*="ReviewCard"], [class*="review-item"]');
                const reviewTexts = [];
                
                reviewCards.forEach((card, index) => {
                    const text = card.textContent || '';
                    const hasReplyButton = !!card.querySelector('button:has-text("답글"), button:has-text("답변")');
                    reviewTexts.push({
                        index: index,
                        textPreview: text.substring(0, 100),
                        hasReplyButton: hasReplyButton
                    });
                });
                
                // 리뷰가 없다면 더 넓은 범위로 검색
                if (reviewTexts.length === 0) {
                    const allDivs = document.querySelectorAll('div');
                    allDivs.forEach(div => {
                        const text = div.textContent || '';
                        if (text.includes('리뷰') || text.includes('별점') || text.includes('고객')) {
                            reviewTexts.push({
                                className: div.className,
                                textPreview: text.substring(0, 50)
                            });
                        }
                    });
                }
                
                return {
                    reviewCount: reviewCards.length,
                    reviews: reviewTexts.slice(0, 5),  // 처음 5개만
                    pageText: document.body.textContent.includes('리뷰가 없습니다') || 
                              document.body.textContent.includes('표시할 리뷰가 없습니다')
                };
            }''')
            
            logger.info(f"DOM 리뷰 정보: {json.dumps(review_info, ensure_ascii=False, indent=2)}")
            
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
            
            # 미답변 탭 클릭
            await self.page.click('text=미답변', timeout=5000)
            logger.info("미답변 탭 클릭 완료!")
            
            # 클릭 후 페이지 업데이트 대기
            await asyncio.sleep(3)
            
            # 미답변 탭 활성화 확인
            is_active = await self.page.evaluate('''() => {
                const divs = document.querySelectorAll('div.e1fz5w2d5');
                for (const div of divs) {
                    const span = div.querySelector('span');
                    if (span && span.textContent === '미답변') {
                        return div.className.includes('css-183zt73');
                    }
                }
                return false;
            }''')
            
            if is_active:
                logger.info("미답변 탭 활성화 확인!")
                
                # 페이지에 표시된 요소 개수 확인
                element_counts = await self.page.evaluate('''() => {
                    return {
                        reviews: document.querySelectorAll('[class*="review"]').length,
                        buttons: document.querySelectorAll('button').length,
                        divs: document.querySelectorAll('div[class*="css-"]').length
                    };
                }''')
                
                logger.info(f"페이지 요소 개수: {element_counts}")
            else:
                logger.warning("미답변 탭 활성화 확인 실패")
            
            return True
            
        except Exception as e:
            logger.error(f"미답변 탭 클릭 실패: {str(e)}")
            return True

    async def save_review_screenshot(self, name: str):
        """리뷰 관련 스크린샷 저장"""
        if not self.page:
            logger.warning("페이지 객체가 없어 스크린샷을 저장할 수 없습니다")
            return
            
        try:
            logger.info(f"스크린샷 저장 시작: {name}")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}.png"
            filepath = self.review_screenshot_dir / filename
            
            await self.page.screenshot(path=str(filepath))
            logger.info(f"리뷰 스크린샷 저장 완료: {filepath}")
            
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
            # 페이지네이션 영역에서 다음 버튼 확인
            has_next = await self.page.evaluate('''() => {
                const containers = document.querySelectorAll('div[class*="css-"]');
                for (const container of containers) {
                    const buttons = container.querySelectorAll('button');
                    if (buttons.length >= 3) {  // 페이지네이션 버튼들
                        const lastButton = buttons[buttons.length - 1];
                        if (lastButton && lastButton.querySelector('svg')) {
                            return !lastButton.disabled;
                        }
                    }
                }
                return false;
            }''')
            
            return has_next
            
        except Exception as e:
            logger.error(f"다음 페이지 확인 실패: {str(e)}")
            return False

    async def go_to_next_page(self) -> bool:
        """다음 페이지로 이동"""
        try:
            # JavaScript로 다음 페이지 버튼 클릭
            clicked = await self.page.evaluate('''() => {
                const containers = document.querySelectorAll('div[class*="css-"]');
                for (const container of containers) {
                    const buttons = container.querySelectorAll('button');
                    if (buttons.length >= 3) {  // 페이지네이션 버튼들
                        const lastButton = buttons[buttons.length - 1];
                        if (lastButton && lastButton.querySelector('svg') && !lastButton.disabled) {
                            lastButton.click();
                            return true;
                        }
                    }
                }
                return false;
            }''')
            
            if clicked:
                logger.info("다음 페이지 버튼 클릭 성공")
                await asyncio.sleep(2)
                return True
            else:
                logger.warning("다음 페이지 버튼을 찾을 수 없습니다")
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
            
            # 수집된 리뷰를 저장할 리스트와 중복 확인용 Set
            all_collected_reviews = []
            collected_review_ids = set()  # 중복 체크용
            api_responses_received = 0
            current_page = 1
            total_pages = 1
            
            # 미답변 탭 클릭 후에만 수집하도록 플래그 추가
            start_collecting = False
            
            # 네트워크 응답 핸들러
            async def handle_response_async(response):
                nonlocal all_collected_reviews, collected_review_ids, api_responses_received, total_pages, start_collecting
                
                # 리뷰 API 응답만 처리
                if response.status == 200 and '/api/v1/merchant/reviews/search' in response.url:
                    # 미답변 탭 클릭 후의 응답만 처리
                    if not start_collecting:
                        logger.info(f"[스킵] 미답변 탭 클릭 전 응답 무시")
                        return
                        
                    try:
                        content_type = response.headers.get('content-type', '')
                        if 'application/json' in content_type:
                            data = await response.json()
                            
                            if 'data' in data and isinstance(data['data'], dict):
                                if 'content' in data['data']:
                                    reviews_list = data['data']['content']
                                    page_info = {
                                        'pageNumber': data['data'].get('pageNumber', 1),
                                        'pageSize': data['data'].get('pageSize', 5),
                                        'total': data['data'].get('total', 0)
                                    }
                                    
                                    # 총 페이지 수 계산
                                    if page_info['pageSize'] > 0:
                                        total_pages = (page_info['total'] + page_info['pageSize'] - 1) // page_info['pageSize']
                                    
                                    logger.info(f"페이지 {page_info['pageNumber']}/{total_pages} - {len(reviews_list)}개 리뷰 발견")
                                    api_responses_received += 1
                                    
                                    for review in reviews_list:
                                        try:
                                            order_review_id = str(review.get("orderReviewId", ""))
                                            
                                            # 중복 체크
                                            if order_review_id in collected_review_ids:
                                                logger.debug(f"중복 리뷰 스킵: {order_review_id}")
                                                continue
                                            
                                            collected_review_ids.add(order_review_id)
                                            
                                            # 리뷰 데이터 파싱
                                            created_at = review.get("createdAt", "")
                                            if created_at and "T" in str(created_at):
                                                review_date = str(created_at).split("T")[0]
                                            else:
                                                review_date = datetime.now().strftime("%Y-%m-%d")
                                            
                                            order_info = review.get("orderInfo", [])
                                            ordered_menu = ", ".join([
                                                item.get("dishName", "") 
                                                for item in order_info 
                                                if isinstance(item, dict)
                                            ])
                                            
                                            review_images = review.get("images", [])
                                            image_urls = []
                                            if isinstance(review_images, list):
                                                for img in review_images:
                                                    if isinstance(img, str):
                                                        image_urls.append(img)
                                            
                                            replies = review.get("replies", [])
                                            has_reply = len(replies) > 0
                                            
                                            review_data = {
                                                'review_id': self.generate_review_id('coupang', order_review_id),
                                                'original_id': order_review_id,
                                                'platform': 'coupang',
                                                'platform_code': platform_code,
                                                'store_code': store_code,
                                                'review_name': review.get("customerName", "익명"),
                                                'rating': int(review.get("rating", 5)),
                                                'review_content': review.get("comment", ""),
                                                'review_date': review_date,
                                                'ordered_menu': ordered_menu,
                                                'review_images': image_urls,
                                                'delivery_review': "",
                                                'has_reply': has_reply,
                                                'writableComment': not has_reply
                                            }
                                            
                                            all_collected_reviews.append(review_data)
                                            logger.info(f"리뷰 수집 [{len(all_collected_reviews)}]: {order_review_id} - {review_data['review_name']}")
                                            
                                            # 수집 한도 확인
                                            if len(all_collected_reviews) >= limit:
                                                logger.info(f"수집 한도 {limit}개 도달")
                                                return
                                                
                                        except Exception as e:
                                            logger.error(f"리뷰 파싱 중 오류: {str(e)}")
                                            continue
                                            
                    except Exception as e:
                        logger.error(f"API 응답 처리 중 오류: {str(e)}")
            
            # 비동기 핸들러를 동기 핸들러로 래핑
            def handle_response(response):
                asyncio.create_task(handle_response_async(response))
            
            # 리스너 등록
            self.page.on("response", handle_response)
            
            try:
                # 리뷰 페이지로 이동 (미답변 탭 클릭 포함)
                if not await self.navigate_to_reviews(store_name):
                    logger.error("리뷰 페이지 이동 실패")
                    return []
                
                # 미답변 탭 클릭 후부터 수집 시작
                start_collecting = True
                logger.info("미답변 탭 활성화 - 리뷰 수집 시작")
                
                # 첫 페이지 API 응답 대기 (중요!)
                logger.info("첫 페이지 리뷰 로딩 대기 중...")
                wait_count = 0
                while api_responses_received == 0 and wait_count < 10:
                    await asyncio.sleep(0.5)
                    wait_count += 1
                
                if api_responses_received == 0:
                    logger.warning("첫 페이지 API 응답 없음 - 페이지 새로고침 시도")
                    # 조회 버튼 재클릭
                    search_button = await self.page.query_selector('button:has-text("조회")')
                    if search_button:
                        await search_button.click()
                        logger.info("조회 버튼 재클릭 완료")
                        await asyncio.sleep(3)
                
                # 페이지네이션 처리
                page_count = 0
                max_pages = min(total_pages, 20)  # 최대 20페이지까지만
                
                while len(all_collected_reviews) < limit and page_count < max_pages:
                    page_count += 1
                    logger.info(f"페이지 {page_count}/{max_pages} 처리 중...")
                    
                    # 첫 페이지는 이미 로드됨
                    if page_count == 1:
                        # 첫 페이지 데이터가 수집되었는지 확인
                        await asyncio.sleep(1)
                        if len(all_collected_reviews) == 0:
                            logger.warning("첫 페이지에서 리뷰를 찾지 못함")
                    else:
                        # 다음 페이지 존재 확인 및 이동
                        if await self.has_next_page():
                            if await self.go_to_next_page():
                                logger.info(f"페이지 {page_count}로 이동 완료")
                                # 페이지 로드 대기
                                await asyncio.sleep(3)
                            else:
                                logger.info("페이지 이동 실패")
                                break
                        else:
                            logger.info("더 이상 페이지가 없습니다")
                            break
                
                logger.info(f"\n========== 총 {len(all_collected_reviews)}개의 리뷰 수집 완료 ==========")
                
                # 수집된 리뷰 요약
                if all_collected_reviews:
                    logger.info("\n수집된 리뷰 요약:")
                    for i, review in enumerate(all_collected_reviews[:10]):
                        logger.info(f"  {i+1}. [{review['original_id']}] {review['review_name']} - {review['rating']}점")
                        if review['review_content']:
                            logger.info(f"     내용: {review['review_content'][:50]}...")
                    if len(all_collected_reviews) > 10:
                        logger.info(f"  ... 외 {len(all_collected_reviews) - 10}개")
                else:
                    logger.warning("수집된 리뷰가 없습니다.")
                
                return all_collected_reviews
                
            finally:
                # 리스너 제거
                self.page.remove_listener("response", handle_response)
                
        except Exception as e:
            logger.error(f"리뷰 수집 중 오류: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []