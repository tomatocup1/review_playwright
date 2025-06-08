"""
동기 크롤러를 subprocess로 실행하는 스크립트 (개선 버전)
Windows asyncio 문제 회피 + Supabase 연동 + 실시간 로그 출력
"""
import subprocess
import sys
import json
import os
import time
import threading
from queue import Queue, Empty
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# Supabase 클라이언트 가져오기
sys.path.append(r"C:\Review_playwright")
from config.supabase_client import get_supabase_client
from api.services.encryption import decrypt_password  # 복호화 함수 import

def enqueue_output(out, queue):
    """출력을 큐에 넣는 함수 (비블로킹)"""
    for line in iter(out.readline, ''):
        queue.put(line)
    out.close()

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
            print(f"[복호화] OK: {store['store_name']}")
        except Exception as e:
            print(f"[복호화] FAIL: {store['store_name']} - {e}")
            store['platform_pw_decrypted'] = None
    
    return stores

def run_crawler_for_store(store_info, headless=True, debug=False):
    """특정 매장에 대해 크롤러 실행 (실시간 출력)"""
    
    # 복호화된 비밀번호 확인
    if not store_info.get('platform_pw_decrypted'):
        print(f"[오류] 비밀번호 복호화 실패: {store_info['store_name']}")
        return None
    
    print(f"\n[크롤러] {store_info['store_name']} 크롤링 시작...")
    print(f"[크롤러] 플랫폼 ID: {store_info['platform_id']}")
    print(f"[크롤러] 플랫폼 코드: {store_info['platform_code']}")
    print(f"[크롤러] Headless: {headless}")
    
    # 크롤러 실행 스크립트 내용
    crawler_script = f'''
import asyncio
import sys
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import json
import logging
from pathlib import Path
sys.path.append(r"C:\\Review_playwright")

from api.crawlers.baemin_sync_review_crawler import BaeminSyncReviewCrawler

# 로깅 설정 - 콘솔과 파일 모두에 출력
import os
log_dir = Path(r"C:\\Review_playwright\\logs")
log_dir.mkdir(exist_ok=True)

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# 콘솔 핸들러
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('[%(levelname)s] %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# 파일 핸들러
file_handler = logging.FileHandler(log_dir / "crawler_debug.log", encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# stdout 플러시를 자주 하도록 설정
import functools
print = functools.partial(print, flush=True)

print("=" * 50)
print("크롤러 프로세스 시작")
print("=" * 50)

# 로그인 정보 출력
print("매장 정보:")
print(f"  - 매장명: {store_info['store_name']}")
print(f"  - 플랫폼 ID: {store_info['platform_id']}")
print(f"  - 플랫폼 코드: {store_info['platform_code']}")
print(f"  - 스토어 코드: {store_info['store_code']}")

try:
    print("\\n[1/5] BaeminSyncReviewCrawler 초기화 중...")
    crawler = BaeminSyncReviewCrawler(headless={headless})
    print("[1/5] OK: 크롤러 초기화 완료")
    
    print("\\n[2/5] 브라우저 시작 중...")
    crawler.start_browser()
    print("[2/5] OK: 브라우저 시작 완료")
    
    # 로그인
    user_id = "{store_info['platform_id']}"
    password = "{store_info['platform_pw_decrypted']}"  # 복호화된 비밀번호 사용
    
    print(f"\\n[3/5] 로그인 시도 중... (ID: {{user_id}})")
    
    login_result = crawler.login(user_id, password)
    
    if login_result:
        print("[3/5] OK: 로그인 성공!")
        
        # 리뷰 가져오기
        platform_code = "{store_info['platform_code']}"
        store_code = "{store_info['store_code']}"
        
        print(f"\\n[4/5] 리뷰 수집 시작...")
        print(f"  - 플랫폼 코드: {{platform_code}}")
        print(f"  - 스토어 코드: {{store_code}}")
        
        reviews = crawler.get_reviews(platform_code, store_code, limit=10)
        
        print(f"\\n[5/5] OK: 리뷰 수집 완료: {{len(reviews)}}개")
        
        # 수집된 리뷰 샘플 출력
        if reviews:
            print("\\n수집된 리뷰 샘플:")
            for i, review in enumerate(reviews[:3], 1):
                print(f"  {{i}}. {{review.get('review_name', '익명')}} - {{review.get('rating', 0)}}점")
                content = review.get('review_content', '')[:50]
                if content:
                    print(f"     내용: {{content}}...")
        
        # 결과를 JSON으로 출력
        print("\\nRESULT_START")
        print(json.dumps({{
            "success": True,
            "store_name": "{store_info['store_name']}",
            "platform_code": "{store_info['platform_code']}",
            "reviews": reviews
        }}, ensure_ascii=False))
        print("RESULT_END")
    else:
        print("[3/5] FAIL: 로그인 실패!")
        print(f"  - 현재 URL: {{crawler.page.url if crawler.page else 'No page'}}")
        print("\\nRESULT_START")
        print(json.dumps({{
            "success": False,
            "store_name": "{store_info['store_name']}",
            "error": "LOGIN_FAILED"
        }}, ensure_ascii=False))
        print("RESULT_END")
        
except Exception as e:
    print(f"\\n[오류] 예외 발생: {{str(e)}}")
    import traceback
    traceback.print_exc()
    
    print("\\nRESULT_START")
    print(json.dumps({{
        "success": False,
        "store_name": "{store_info['store_name']}",
        "error": str(e)
    }}, ensure_ascii=False))
    print("RESULT_END")
    
finally:
    if not {headless}:
        input("\\n브라우저를 닫으려면 Enter를 누르세요...")
    try:
        crawler.close_browser()
        print("\\n브라우저 종료 완료")
    except:
        pass
'''
    
    # subprocess로 실행 (실시간 출력)
    process = subprocess.Popen(
        [sys.executable, '-u', '-c', crawler_script],  # -u 옵션 추가 (unbuffered)
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # stderr를 stdout으로 리다이렉트
        universal_newlines=True,
        encoding='utf-8',
        bufsize=1  # 라인 버퍼링
    )
    
    # 실시간 출력 및 결과 수집
    output_lines = []
    result_json = None
    in_result = False
    
    print("\n--- 크롤러 출력 시작 ---")
    
    # 실시간으로 출력 읽기
    for line in iter(process.stdout.readline, ''):
        if line:
            line = line.rstrip()
            output_lines.append(line)
            
            # 실시간 출력
            if debug or not in_result:
                print(f"  {line}")
            
            # 결과 파싱
            if "RESULT_START" in line:
                in_result = True
                result_json = ""
            elif "RESULT_END" in line:
                in_result = False
                try:
                    result = json.loads(result_json)
                    return result
                except Exception as e:
                    print(f"\n[오류] 결과 파싱 실패: {e}")
                    print(f"JSON: {result_json}")
            elif in_result and line:
                result_json += line
    
    process.wait()
    print("--- 크롤러 출력 종료 ---\n")
    
    # 프로세스가 종료되었는데 결과가 없는 경우
    if process.returncode != 0:
        print(f"[오류] 크롤러 프로세스가 비정상 종료됨 (코드: {process.returncode})")
    
    return None

def main():
    """메인 함수"""
    print("=" * 60)
    print("배민 리뷰 수집 프로그램 v2.0")
    print("=" * 60)
    print()
    
    # Supabase에서 배민 매장 목록 가져오기
    stores = get_baemin_stores()
    
    # 복호화 성공한 매장만 필터링
    valid_stores = [s for s in stores if s.get('platform_pw_decrypted')]
    
    print(f"\n[요약] 총 {len(stores)}개 매장 중 {len(valid_stores)}개 사용 가능")
    
    if not valid_stores:
        print("\n[오류] 사용 가능한 매장이 없습니다.")
        print("       비밀번호 복호화를 확인하세요.")
        return
    
    # 테스트할 매장 선택
    print("\n실행 모드를 선택하세요:")
    print("1. 전체 매장 자동 실행 (headless)")
    print("2. 첫 번째 매장만 브라우저 표시하며 테스트")
    print("3. 특정 매장 선택하여 테스트")
    print("4. 디버그 모드 (상세 로그)")
    
    choice = input("\n선택 (1/2/3/4): ").strip()
    
    if choice == "2":
        # 첫 번째 매장만 테스트
        store = valid_stores[0]
        print(f"\n[선택] {store['store_name']}")
        
        result = run_crawler_for_store(store, headless=False, debug=True)
        
        if result and result.get('success'):
            print(f"\n[성공] {len(result.get('reviews', []))}개 리뷰 수집")
        else:
            print(f"\n[실패] {result.get('error', 'Unknown error') if result else 'No result'}")
            
    elif choice == "3":
        # 매장 목록 표시
        print("\n=== 매장 목록 ===")
        for idx, store in enumerate(valid_stores, 1):
            print(f"{idx}. {store['store_name']} (코드: {store['platform_code']})")
        
        try:
            store_idx = int(input("\n테스트할 매장 번호: ")) - 1
            
            if 0 <= store_idx < len(valid_stores):
                store = valid_stores[store_idx]
                print(f"\n[선택] {store['store_name']}")
                
                result = run_crawler_for_store(store, headless=False, debug=True)
                
                if result and result.get('success'):
                    print(f"\n[성공] {len(result.get('reviews', []))}개 리뷰 수집")
                else:
                    print(f"\n[실패] {result.get('error', 'Unknown error') if result else 'No result'}")
            else:
                print("\n[오류] 잘못된 번호입니다.")
        except ValueError:
            print("\n[오류] 숫자를 입력하세요.")
            
    elif choice == "4":
        # 디버그 모드
        print("\n[디버그 모드] 첫 번째 매장으로 테스트")
        store = valid_stores[0]
        print(f"\n[선택] {store['store_name']}")
        
        # 로그 파일 경로 표시
        print(f"\n[로그] 상세 로그는 다음 파일에서 확인:")
        print(f"       C:\\Review_playwright\\logs\\crawler_debug.log")
        
        result = run_crawler_for_store(store, headless=True, debug=True)
        
        if result and result.get('success'):
            print(f"\n[성공] {len(result.get('reviews', []))}개 리뷰 수집")
        else:
            print(f"\n[실패] {result.get('error', 'Unknown error') if result else 'No result'}")
            
    else:
        # 전체 실행
        print("\n[전체 실행 모드]")
        total_reviews = 0
        successful_stores = 0
        failed_stores = []
        
        for idx, store in enumerate(valid_stores, 1):
            print(f"\n[{idx}/{len(valid_stores)}] {store['store_name']} 처리 중...")
            
            result = run_crawler_for_store(store, headless=True, debug=False)
            
            if result and result.get('success'):
                review_count = len(result.get('reviews', []))
                print(f"  [성공] {review_count}개 리뷰")
                total_reviews += review_count
                successful_stores += 1
            else:
                print(f"  [실패] {result.get('error', 'Unknown') if result else 'No result'}")
                failed_stores.append(store['store_name'])
            
            # 잠시 대기 (서버 부하 방지)
            if idx < len(valid_stores):
                time.sleep(2)
        
        print("\n" + "=" * 60)
        print("수집 완료 요약")
        print("=" * 60)
        print(f"성공: {successful_stores}/{len(valid_stores)} 매장")
        print(f"총 리뷰 수: {total_reviews}개")
        
        if failed_stores:
            print(f"\n실패한 매장:")
            for store_name in failed_stores:
                print(f"  - {store_name}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[중단] 사용자가 프로그램을 중단했습니다.")
    except Exception as e:
        print(f"\n\n[오류] 예기치 않은 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n프로그램을 종료합니다.")
