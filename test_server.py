"""
서버 실행 테스트 스크립트
"""
import sys
import os

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from api.main import app
    print("✅ API 모듈 import 성공!")
    
    from api.routes import auth, pages, stores
    print("✅ 라우터 모듈 import 성공!")
    
    # 라우터 확인
    print("\n📌 등록된 라우터:")
    for route in app.routes:
        if hasattr(route, 'path'):
            print(f"  - {route.methods} {route.path}")
    
except Exception as e:
    print(f"❌ 에러 발생: {e}")
    import traceback
    traceback.print_exc()
