"""
동기 크롤러를 subprocess로 실행하는 스크립트
Windows asyncio 문제 회피 + Supabase 연동
"""
import subprocess
import sys
import json
import os
from typing import Dict, List
from dotenv import load_dotenv
from datetime import datetime

# 환경변수 로드
load_dotenv()

# Supabase 클라이언트 가져오기
sys.path.append(r"C:\Review_playwright")
from config.supabase_client import get_supabase_client
from api.services.encryption import decrypt_password  # 복호화 함수 import

def get_baemin_stores():
    """Supabase에서 모든 배민 매장 정보 가져오기"""
    print("[DB] Supabase에서 매장 정보 조회 중...")
    supabase = get_supabase_client()
    
    # 배민 매장만 조회
    response = supabase.table('platform_reply_rules')\
        .select('*')\
        .eq('platform', 'baemin')\
        .eq('is_active', True)\
        .execute()
    
    print(f"[DB] {len(response.data)}개의 배민 매장 발견")
    
    # 비밀번호 복호화
    stores = response.data
    for store in stores:
        try:
            # 암호화된 비밀번호 복호화
            store['platform_pw_decrypted'] = decrypt_password(store['platform_pw'])
            print(f"[복호화] 성공: {store['store_name']}")
        except Exception as e:
            print(f"[복호화] 실패: {store['store_name']} - {e}")
            store['platform_pw_decrypted'] = None
    
    return stores

def save_reviews_to_supabase(store_info: Dict, reviews: List[Dict]) -> Dict[str, int]:
    """수집한 리뷰를 Supabase에 저장 (동기 버전)"""
    from config.supabase_client import get_supabase_client
    
    print(f"\n[DB] {len(reviews)}개 리뷰 저장 시작...")
    
    # Supabase 클라이언트 직접 사용
    supabase = get_supabase_client()
    
    # 저장 통계
    saved_count = 0
    failed_count = 0
    duplicate_count = 0
    
    for review in reviews:
        try:
            # 중복 체크
            existing = supabase.table('reviews').select('review_id').eq('review_id', review['review_id']).execute()
            
            if existing.data:
                print(f"[DB] 중복 리뷰 스킵: {review['review_id']} - {review['review_name']}")
                duplicate_count += 1
                continue
            
            # DB에 맞게 데이터 정제
            review_data = {
                'review_id': review['review_id'],
                'platform': review['platform'],
                'platform_code': review['platform_code'],
                'store_code': review['store_code'],
                'review_name': review['review_name'],
                'rating': review['rating'],
                'review_content': review['review_content'],
                'review_date': review['review_date'],
                'ordered_menu': review['ordered_menu'],
                'delivery_review': review['delivery_review'],
                'response_status': 'pending',  # 기본값: 미답변 상태
                'crawled_at': datetime.now().isoformat()
            }
            
            # review_images를 PostgreSQL 배열 형식으로 변환
            if isinstance(review.get('review_images'), list):
                # PostgreSQL TEXT[] 형식: {url1,url2,url3}
                if review['review_images']:
                    # 리스트가 비어있지 않은 경우
                    review_data['review_images'] = review['review_images']  # Supabase가 자동 변환
                else:
                    # 빈 리스트인 경우
                    review_data['review_images'] = []
            else:
                review_data['review_images'] = []
            
            # 리뷰 저장
            result = supabase.table('reviews').insert(review_data).execute()
            
            if result.data:
                print(f"[DB] 저장 성공: {review['review_id']} - {review['review_name']}")
                saved_count += 1
            else:
                print(f"[DB] 저장 실패: {review['review_id']} - {review['review_name']}")
                failed_count += 1
                
        except Exception as e:
            print(f"[DB] 저장 중 오류: {review['review_id']} - {str(e)}")
            failed_count += 1
    
    # 사용량 업데이트
    if saved_count > 0:
        try:
            supabase.rpc('update_usage', {
                'p_user_code': store_info['owner_user_code'],
                'p_reviews_increment': saved_count,
                'p_ai_api_calls_increment': 0,
                'p_web_api_calls_increment': 0,
                'p_manual_replies_increment': 0,
                'p_error_increment': 0
            }).execute()
        except Exception as e:
            print(f"[DB] 사용량 업데이트 실패: {str(e)}")
    
    print(f"\n[DB] 저장 완료:")
    print(f"  - 성공: {saved_count}개")
    print(f"  - 중복: {duplicate_count}개")
    print(f"  - 실패: {failed_count}개")
    
    return {
        'saved': saved_count,
        'duplicate': duplicate_count,
        'failed': failed_count
    }

def run_crawler_for_store(store_info, headless=True, debug=False):
    """특정 매장에 대해 크롤러 실행"""
    
    # 복호화된 비밀번호 확인
    if not store_info.get('platform_pw_decrypted'):
        print(f"[오류] 비밀번호 복호화 실패: {store_info['store_name']}")
        return None
    
    print(f"\n[크롤러] {store_info['store_name']} 크롤링 시작...")
    print(f"[크롤러] 플랫폼 ID: {store_info['platform_id']}")
    print(f"[크롤러] 플랫폼 코드: {store_info['platform_code']}")
    
    # 크롤러 실행 스크립트 내용
    crawler_script = f'''
# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import asyncio
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import json
import logging
from pathlib import Path
sys.path.append(r"C:\\Review_playwright")

from api.crawlers.review_crawlers.baemin_sync_review_crawler import BaeminSyncReviewCrawler

# stdout 버퍼링 비활성화
import functools
print = functools.partial(print, flush=True)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('C:/Review_playwright/logs/crawler.log', encoding='utf-8')
    ]
)

print("==================================================")
print("크롤러 프로세스 시작")
print("==================================================")
print(f"매장명: {store_info['store_name']}")
print(f"플랫폼 ID: {store_info['platform_id']}")
print(f"플랫폼 코드: {store_info['platform_code']}")

crawler = BaeminSyncReviewCrawler(headless={headless})
try:
    print("\\n[1단계] 브라우저 시작 중...")
    crawler.start_browser()
    print("[1단계] 브라우저 시작 완료")
    
    # 로그인
    user_id = "{store_info['platform_id']}"
    password = "{store_info['platform_pw_decrypted']}"  # 복호화된 비밀번호 사용
    
    print(f"\\n[2단계] 로그인 시도 중... (ID: {{user_id}})")
    
    login_result = crawler.login(user_id, password)
    print(f"[2단계] 로그인 결과: {{login_result}}")
    
    if login_result:
        print("\\n[3단계] 리뷰 수집 시작...")
        
        # 리뷰 가져오기
        platform_code = "{store_info['platform_code']}"
        store_code = "{store_info['store_code']}"
        
        reviews = crawler.get_reviews(platform_code, store_code, limit=10)
        
        print(f"[3단계] 수집된 리뷰 수: {{len(reviews)}}")
        
        # 결과를 JSON으로 출력
        print("\\nRESULT_START")
        print(json.dumps({{
            "store_name": "{store_info['store_name']}",
            "platform_code": "{store_info['platform_code']}",
            "reviews": reviews
        }}, ensure_ascii=False))
        print("RESULT_END")
    else:
        print("\\nLOGIN_FAILED")
        print(f"로그인 실패 상세: URL={{crawler.page.url if crawler.page else 'No page'}}")
        
except Exception as e:
    print(f"\\nERROR: {{str(e)}}")
    import traceback
    traceback.print_exc()
finally:
    if not {headless}:
        input("\\n브라우저를 닫으려면 Enter를 누르세요...")
    crawler.close_browser()
'''
    
    # subprocess로 실행 - 실시간 출력을 위해 수정
    # Windows 환경에서 한글 인코딩 문제 해결
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    
    process = subprocess.Popen(
        [sys.executable, '-u', '-c', crawler_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        encoding='utf-8',  # UTF-8로 변경
        bufsize=1,
        errors='replace',  # 인코딩 에러 시 ?로 대체
        env=env
    )
    
    # 실시간으로 출력 읽기
    print("\n--- 크롤러 출력 시작 ---")
    output_lines = []
    
    for line in iter(process.stdout.readline, ''):
        if line:
            line = line.rstrip()
            output_lines.append(line)
            print(f"  {line}")
    
    process.wait()
    print("--- 크롤러 출력 종료 ---\n")
    
    # 결과 파싱
    output = '\n'.join(output_lines)
    
    if "RESULT_START" in output and "RESULT_END" in output:
        start = output.find("RESULT_START") + len("RESULT_START")
        end = output.find("RESULT_END")
        result_json = output[start:end].strip()
        
        try:
            result = json.loads(result_json)
            
            # 리뷰 저장
            if result and 'reviews' in result and len(result['reviews']) > 0:
                save_stats = save_reviews_to_supabase(store_info, result['reviews'])
                result['save_stats'] = save_stats
            
            return result
        except Exception as e:
            print(f"결과 파싱 실패: {e}")
            return None
    elif "LOGIN_FAILED" in output:
        print(f"로그인 실패: {store_info['store_name']}")
        return None
    else:
        print(f"크롤링 실패: {store_info['store_name']}")
        return None

def main():
    """메인 함수 - subprocess에서 호출될 때 실행"""
    import sys
    
    # subprocess로 호출된 경우
    if len(sys.argv) > 1:
        try:
            # JSON 데이터 파싱
            crawler_data = json.loads(sys.argv[1])
            
            # 매장 정보로 크롤링 실행
            store_info = {
                'platform_id': crawler_data['platform_id'],
                'platform_pw': crawler_data['platform_pw'],
                'platform_code': crawler_data['platform_code'],
                'store_code': crawler_data['store_code'],
                'store_name': crawler_data['store_name'],
                'platform_pw_decrypted': crawler_data['platform_pw'],  # 이미 복호화됨
                'owner_user_code': 'SYSTEM'  # subprocess 실행시 기본값
            }
            
            # 크롤러 실행
            result = run_crawler_for_store(store_info, headless=True, debug=False)
            
            # 결과 JSON으로 출력
            if result and 'save_stats' in result:
                stats = result['save_stats']
                print(json.dumps({
                    "success": True,
                    "collected": len(result.get('reviews', [])),
                    "saved": stats['saved']
                }, ensure_ascii=False))
            else:
                print(json.dumps({
                    "success": False,
                    "error": "크롤링 실패"
                }, ensure_ascii=False))
                
            sys.exit(0)
            
        except Exception as e:
            print(json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False))
            sys.exit(1)
    
    # 기존 대화형 모드
    else:
        print("=== 배민 리뷰 수집 시작 ===\n")
        
        try:
            # Supabase에서 배민 매장 목록 가져오기
            stores = get_baemin_stores()
            
            # 복호화 성공한 매장만 필터링
            valid_stores = [s for s in stores if s.get('platform_pw_decrypted')]
            
            print(f"\n총 {len(stores)}개의 배민 매장 중 {len(valid_stores)}개 사용 가능\n")
            
            if not valid_stores:
                print("사용 가능한 매장이 없습니다. 비밀번호 복호화를 확인하세요.")
                return
            
            # 테스트할 매장 선택
            print("어떤 모드로 실행하시겠습니까?")
            print("1. 전체 매장 자동 실행 (headless)")
            print("2. 첫 번째 매장만 브라우저 표시하며 테스트")
            print("3. 특정 매장 선택하여 테스트")
            
            choice = input("\n선택 (1/2/3): ").strip()
            
            if choice == "2":
                # 첫 번째 매장만 테스트
                store = valid_stores[0]
                print(f"\n테스트 매장: {store['store_name']}")
                
                result = run_crawler_for_store(store, headless=False, debug=True)
                
                if result:
                    print(f"\n크롤링 성공: {len(result.get('reviews', []))}개 리뷰 수집")
                    if 'save_stats' in result:
                        stats = result['save_stats']
                        print(f"DB 저장 결과: 성공 {stats['saved']}개, 중복 {stats['duplicate']}개, 실패 {stats['failed']}개")
                else:
                    print("\n실패")
                    
            elif choice == "3":
                # 매장 목록 표시
                print("\n=== 매장 목록 ===")
                for idx, store in enumerate(valid_stores, 1):
                    print(f"{idx}. {store['store_name']} (코드: {store['platform_code']})")
                
                store_idx = int(input("\n테스트할 매장 번호: ")) - 1
                
                if 0 <= store_idx < len(valid_stores):
                    store = valid_stores[store_idx]
                    print(f"\n선택한 매장: {store['store_name']}")
                    
                    result = run_crawler_for_store(store, headless=False, debug=True)
                    
                    if result:
                        print(f"\n크롤링 성공: {len(result.get('reviews', []))}개 리뷰 수집")
                        if 'save_stats' in result:
                            stats = result['save_stats']
                            print(f"DB 저장 결과: 성공 {stats['saved']}개, 중복 {stats['duplicate']}개, 실패 {stats['failed']}개")
                    else:
                        print("\n실패")
                        
            else:
                # 전체 실행
                total_reviews = 0
                total_saved = 0
                successful_stores = 0
                
                for idx, store in enumerate(valid_stores, 1):
                    print(f"\n[{idx}/{len(valid_stores)}] {store['store_name']} 처리 중...")
                    
                    result = run_crawler_for_store(store, headless=True, debug=False)
                    
                    if result:
                        review_count = len(result.get('reviews', []))
                        print(f"  크롤링 성공: {review_count}개 리뷰 수집")
                        
                        if 'save_stats' in result:
                            stats = result['save_stats']
                            print(f"  DB 저장: 성공 {stats['saved']}개, 중복 {stats['duplicate']}개, 실패 {stats['failed']}개")
                            total_saved += stats['saved']
                        
                        total_reviews += review_count
                        successful_stores += 1
                    else:
                        print(f"  실패")
                
                print("\n=== 수집 완료 ===")
                print(f"성공: {successful_stores}/{len(valid_stores)} 매장")
                print(f"총 수집 리뷰: {total_reviews}개")
                print(f"총 저장 리뷰: {total_saved}개")
                
        except Exception as e:
            print(f"\n예기치 않은 오류: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()