"""
웹 페이지 렌더링을 위한 라우터
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional

from api.dependencies import get_current_user_optional

# 템플릿 설정
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

router = APIRouter(tags=["pages"])

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """홈페이지"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "title": "리뷰 자동화 서비스"
    })

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """로그인 페이지"""
    return templates.TemplateResponse("auth/login.html", {
        "request": request,
        "title": "로그인"
    })

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """회원가입 페이지"""
    return templates.TemplateResponse("auth/register.html", {
        "request": request,
        "title": "회원가입"
    })

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """대시보드 (로그인 필요)"""
    return templates.TemplateResponse("dashboard/index.html", {
        "request": request,
        "title": "대시보드"
    })

@router.get("/stores", response_class=HTMLResponse)
async def stores_list(request: Request):
    """매장 목록 페이지"""
    return templates.TemplateResponse("stores/list.html", {
        "request": request,
        "title": "매장 관리"
    })

@router.get("/stores/register", response_class=HTMLResponse)
async def store_register(request: Request):
    """매장 등록 페이지"""
    return templates.TemplateResponse("store_register.html", {
        "request": request,
        "title": "매장 등록"
    })

@router.get("/reviews", response_class=HTMLResponse)
async def reviews_list(request: Request):
    """리뷰 목록 페이지"""
    return templates.TemplateResponse("reviews/list_with_reply_posting.html", {
        "request": request,
        "title": "리뷰 관리"
    })

@router.get("/test-simple", response_class=HTMLResponse)
async def test_simple(request: Request):
    """테스트 페이지 (간단 버전)"""
    return templates.TemplateResponse("test_simple.html", {
        "request": request,
        "title": "리뷰 테스트"
    })

@router.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    """설정 페이지"""
    return templates.TemplateResponse("settings/index.html", {
        "request": request,
        "title": "설정"
    })
