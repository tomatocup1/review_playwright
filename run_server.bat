@echo off
echo ========================================
echo 리뷰 자동화 서버 시작
echo ========================================
echo.

cd /d C:\Review_playwright

echo Python 가상환경 활성화 중...
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo 가상환경이 없습니다. 직접 실행합니다.
)

echo.
echo FastAPI 서버 시작 중...
echo URL: http://localhost:8000
echo API 문서: http://localhost:8000/docs
echo.

python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

pause
