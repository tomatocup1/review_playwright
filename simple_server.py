"""
간단한 FastAPI 서버 테스트
"""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

app = FastAPI()

# 템플릿 설정
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """홈페이지"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "title": "리뷰 자동화 서비스"
    })

@app.get("/test")
async def test():
    return {"message": "서버가 정상 작동 중입니다!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
