"""
테스트 스크립트 - API 서버 import 체크
"""
import sys
import traceback

print("Python 경로:", sys.executable)
print("현재 디렉토리:", sys.path[0])
print("\n모듈 import 테스트 시작...\n")

try:
    print("1. api.main 모듈 import 시도...")
    from api.main import app
    print("OK: api.main 모듈 import 성공!")
    
    print("\n2. FastAPI 앱 정보:")
    print(f"   - 앱 타입: {type(app)}")
    print(f"   - 앱 제목: {app.title}")
    print(f"   - 앱 버전: {app.version}")
    
except Exception as e:
    print("ERROR: Import 실패!")
    print(f"에러 타입: {type(e).__name__}")
    print(f"에러 메시지: {str(e)}")
    print("\n상세 스택 트레이스:")
    traceback.print_exc()
