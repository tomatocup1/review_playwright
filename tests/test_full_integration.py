"""
통합 테스트 스크립트
Supabase 연결, AI 답글 생성, 크롤링을 모두 테스트
"""
import asyncio
import logging
from pathlib import Path
import sys
from datetime import datetime
import os
from dotenv import load_dotenv

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent))

from crawler.baemin import BaeminCrawler
from config.database import DatabaseManager
from config.supabase_client import get_supabase_client
from config.openai_client import get_openai_client
import json

# 환경변수 로드
load_dotenv()

# 로깅 설정
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(
            log_dir / f"integration_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            encoding='utf-8'
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class IntegrationTester:
    """통합 테스트 클래스"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.supabase = get_supabase_client()
        self.openai = get_openai_client()
        self.crawler = None
        
    async def test_supabase_connection(self):
        """Supabase 연결 테스트"""
        logger.info("\n=== Supabase 연결 테스트 ===")
        try:
            # 사용자 테이블 조회 테스트
            result = self.supabase.table('users').select('*').limit(1).execute()
            logger.info(f"✓ Supabase 연결 성공")
            logger.info(f"  - users 테이블 접근 가능")
            
            # 각 테이블 존재 확인
            tables = ['users', 'subscriptions', 'platform_reply_rules', 'reviews']
            for table in tables:
                try:
                    self.supabase.table(table).select('*').limit(1).execute()
                    logger.info(f"  - {table} 테이블 확인됨")
                except Exception as e:
                    logger.error(f"  - {table} 테이블 오류: {str(e)}")
                    
            return True
        except Exception as e:
            logger.error(f"✗ Supabase 연결 실패: {str(e)}")
            return False
    
    async def test_ai_reply_generation(self):
        """AI 답글 생성 테스트"""
        logger.info("\n=== AI 답글 생성 테스트 ===")
        try:
            # 테스트용 리뷰 데이터
            test_review = {
                'author': '테스트고객',
                'rating': 5,
                'review_text': '음식이 정말 맛있었어요! 특히 버거가 신선하고 양도 많았습니다.',
                'order_menu': '더블 불고기버거 세트'
            }
            
            # 답글 정책 설정
            reply_rules = {
                'greeting_start': '안녕하세요',
                'greeting_end': '감사합니다',
                'tone': 'friendly',
                'max_length': 300
            }
            
            # AI 답글 생성
            prompt = f"""
            다음 리뷰에 대한 친근한 답글을 작성해주세요:
            작성자: {test_review['author']}
            별점: {test_review['rating']}점
            내용: {test_review['review_text']}
            주문메뉴: {test_review['order_menu']}
            
            답글은 {reply_rules['greeting_start']}로 시작하고 {reply_rules['greeting_end']}로 끝나야 합니다.
            {reply_rules['max_length']}자 이내로 작성해주세요.
            """
            
            response = self.openai.chat.completions.create(
                model=os.getenv('AI_MODEL', 'gpt-4o-mini'),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=int(os.getenv('AI_MAX_TOKENS', 600)),
                temperature=float(os.getenv('AI_TEMPERATURE', 0.7))
            )
            
            ai_reply = response.choices[0].message.content
            logger.info(f"✓ AI 답글 생성 성공")
            logger.info(f"  - 생성된 답글: {ai_reply}")
            logger.info(f"  - 답글 길이: {len(ai_reply)}자")
            
            # 답글 검증
            if reply_rules['greeting_start'] in ai_reply and reply_rules['greeting_end'] in ai_reply:
                logger.info(f"  - 인사말 규칙 준수 확인")
            else:
                logger.warning(f"  - 인사말 규칙 미준수")
                
            return True
        except Exception as e:
            logger.error(f"✗ AI 답글 생성 실패: {str(e)}")
            return False
    
    async def test_crawler_with_replies(self, store_config):
        """크롤러 + AI 답글 통합 테스트"""
        logger.info("\n=== 크롤러 + AI 답글 통합 테스트 ===")
        
        self.crawler = BaeminCrawler(store_config)
        
        try:
            # 1. 브라우저 초기화
            logger.info("브라우저 초기화 중...")
            await self.crawler.initialize()
            
            # 2. 로그인
            logger.info("로그인 시도 중...")
            login_success = await self.crawler.login()
            
            if not login_success:
                logger.error("로그인 실패")
                return False
                
            logger.info("✓ 로그인 성공")
            
            # 3. 리뷰 페이지로 이동
            logger.info("리뷰 페이지로 이동 중...")
            nav_success = await self.crawler.navigate_to_reviews(store_config['platform_code'])
            
            if not nav_success:
                logger.error("리뷰 페이지 이동 실패")
                return False
                
            # 4. 리뷰 목록 가져오기
            logger.info("리뷰 목록 가져오는 중...")
            reviews = await self.crawler.get_reviews()
            
            logger.info(f"✓ 총 {len(reviews)}개 리뷰 발견")
            
            # 5. 첫 번째 리뷰에 대해 AI 답글 생성
            if reviews:
                test_review = reviews[0]
                logger.info(f"\n첫 번째 리뷰에 대한 AI 답글 생성:")
                logger.info(f"  - 작성자: {test_review['author']}")
                logger.info(f"  - 별점: {test_review['rating']}점")
                logger.info(f"  - 내용: {test_review['review_text'][:100]}...")
                
                # AI 답글 생성
                prompt = f"""
                다음 리뷰에 대한 친근한 답글을 작성해주세요:
                작성자: {test_review['author']}
                별점: {test_review['rating']}점
                내용: {test_review['review_text']}
                주문메뉴: {test_review['order_menu']}
                
                답글은 '안녕하세요'로 시작하고 '감사합니다'로 끝나야 합니다.
                300자 이내로 작성해주세요.
                """
                
                response = self.openai.chat.completions.create(
                    model=os.getenv('AI_MODEL', 'gpt-4o-mini'),
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=int(os.getenv('AI_MAX_TOKENS', 600)),
                    temperature=float(os.getenv('AI_TEMPERATURE', 0.7))
                )
                
                ai_reply = response.choices[0].message.content
                logger.info(f"\n✓ AI 답글 생성 완료:")
                logger.info(f"{ai_reply}")
                
                # 실제 답글 등록은 테스트에서는 건너뜀
                logger.info("\n(주의: 실제 답글 등록은 테스트에서 건너뜁니다)")
                
            return True
            
        except Exception as e:
            logger.error(f"✗ 통합 테스트 실패: {str(e)}")
            await self.crawler.save_screenshot("error")
            return False
            
        finally:
            if self.crawler:
                await self.crawler.close()


async def main():
    """메인 테스트 실행"""
    logger.info("=" * 50)
    logger.info("통합 테스트 시작")
    logger.info("=" * 50)
    
    tester = IntegrationTester()
    
    # 1. Supabase 연결 테스트
    supabase_ok = await tester.test_supabase_connection()
    
    # 2. AI 답글 생성 테스트
    ai_ok = await tester.test_ai_reply_generation()
    
    # 3. 크롤링 + AI 통합 테스트 (선택적)
    crawler_ok = True
    run_crawler = input("\n크롤링 테스트를 실행하시겠습니까? (y/n): ")
    
    if run_crawler.lower() == 'y':
        # 테스트용 매장 설정
        store_config = {
            'store_code': 'TEST001',
            'platform_id': input("배민 로그인 ID: "),
            'platform_pw': input("배민 로그인 PW: "),
            'platform_code': input("플랫폼 매장 코드: "),
            'store_name': '테스트 매장'
        }
        
        crawler_ok = await tester.test_crawler_with_replies(store_config)
    
    # 결과 요약
    logger.info("\n=" * 50)
    logger.info("테스트 결과 요약")
    logger.info("=" * 50)
    logger.info(f"Supabase 연결: {'성공' if supabase_ok else '실패'}")
    logger.info(f"AI 답글 생성: {'성공' if ai_ok else '실패'}")
    logger.info(f"크롤링 통합: {'성공' if crawler_ok else '미실행' if run_crawler.lower() != 'y' else '실패'}")
    
    if supabase_ok and ai_ok and crawler_ok:
        logger.info("\n✓ 모든 테스트 통과!")
    else:
        logger.info("\n✗ 일부 테스트 실패")


if __name__ == "__main__":
    asyncio.run(main())
