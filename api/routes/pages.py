"""
웹 페이지 렌더링을 위한 라우터
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional

from ..auth.utils import get_current_user

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
async def dashboard(request: Request, current_user = Depends(get_current_user)):
    """대시보드 (로그인 필요)"""
    return templates.TemplateResponse("dashboard/index.html", {
        "request": request,
        "title": "대시보드",
        "user": current_user
    })

@router.get("/stores", response_class=HTMLResponse)
async def stores_list(request: Request, current_user = Depends(get_current_user)):
    """매장 목록 페이지"""
    return templates.TemplateResponse("stores/list.html", {
        "request": request,
        "title": "매장 관리",
        "user": current_user
    })

@router.get("/stores/register", response_class=HTMLResponse)
async def store_register(request: Request, current_user = Depends(get_current_user)):
    """매장 등록 페이지"""
    return templates.TemplateResponse("stores/register.html", {
        "request": request,
        "title": "매장 등록",
        "user": current_user
    })

@router.get("/reviews", response_class=HTMLResponse)
async def reviews_list(request: Request, current_user = Depends(get_current_user)):
    """리뷰 목록 페이지"""
    return templates.TemplateResponse("reviews/list.html", {
        "request": request,
        "title": "리뷰 관리",
        "user": current_user
    })

@router.get("/settings", response_class=HTMLResponse)
async def settings(request: Request, current_user = Depends(get_current_user)):
    """설정 페이지"""
    return templates.TemplateResponse("settings/index.html", {
        "request": request,
        "title": "설정",
        "user": current_user
    })
