"""
FastAPI 서버 실행 스크립트
"""
import uvicorn
import sys

if __name__ == "__main__":
    try:
        print("FastAPI 서버를 시작합니다...")
        print("URL: http://localhost:8000")
        print("API 문서: http://localhost:8000/docs")
        print("")
        print("종료하려면 Ctrl+C를 누르세요.")
        
        uvicorn.run(
            "api.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n서버를 종료합니다.")
        sys.exit(0)
    except Exception as e:
        print(f"서버 실행 중 오류 발생: {e}")
        sys.exit(1)
