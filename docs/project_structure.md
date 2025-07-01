# 📁 C:\Review_playwright 프로젝트 전체 구조 (최종 정리)

## 🏢 프로젝트 개요

- **프로젝트명**: 리뷰 자동화 SaaS 서비스
- **주요 기능**: 배민/요기요/쿠팡이츠 리뷰 크롤링 및 AI 답글 자동화
- **URL**: http://localhost/playwright
- **기술 스택**: Python, FastAPI, Playwright, Supabase, OpenAI GPT-4

## 📂 전체 폴더 구조

```
C:\Review_playwright/
├── 📄 .env                     # 환경변수 (API키, DB연결정보)
├── 📄 requirements.txt         # Python 패키지 의존성
├── 📄 run_server.bat          # 서버 실행 스크립트
├── 📄 run_review_automation.py # 리뷰 자동화 실행 스크립트
│
├── 📁 api/                    # 백엔드 핵심 로직
│   ├── 📁 crawlers/          # 크롤러 모듈 ⭐
│   ├── 📁 services/          # 비즈니스 로직 ⭐
│   ├── 📁 routes/            # API 엔드포인트 ⭐
│   ├── 📁 schemas/           # API 요청/응답 스키마
│   ├── 📁 auth/              # 인증/권한 관리
│   ├── 📁 utils/             # 유틸리티 함수
│   └── 📄 dependencies.py    # FastAPI 의존성 주입
│
├── 📁 web/                    # 프론트엔드 UI
│   ├── 📁 css/               # 스타일시트
│   ├── 📁 js/                # JavaScript
│   ├── 📁 images/            # 이미지 리소스
│   ├── index.html            # 로그인 페이지
│   ├── dashboard.html        # 메인 대시보드
│   ├── register.html         # 매장 등록
│   └── reviews.html          # 리뷰 관리
│
├── 📁 config/                 # 설정 파일
│   ├── supabase_client.py    # DB 클라이언트
│   ├── openai_client.py      # OpenAI 클라이언트
│   └── settings.py           # 앱 전역 설정
│
├── 📁 logs/                   # 로그 및 스크린샷
│   ├── app.log               # 애플리케이션 로그
│   └── 📁 screenshots/       # 크롤링 스크린샷
│       ├── 📁 baemin/
│       ├── 📁 coupang/
│       ├── 📁 yogiyo/
│       └── 📁 errors/        # 에러 스크린샷
│
├── 📁 scripts/                # 유틸리티 스크립트
│   └── test_supabase.py      # DB 연결 테스트
│
├── 📁 docs/                   # 문서
│   ├── SQL_playwright.txt    # DB 스키마 문서
│   └── project_structure.md  # 프로젝트 구조 문서
│
├── 📁 tests/                  # 테스트 코드
│   └── ... (테스트 파일들)


### 📁 /api/crawlers/ - 크롤러 모듈

```
crawlers/
├── 📄 base_crawler.py              # 추상 베이스 크롤러
├── 📄 coupang_crawler.py          # 쿠팡이츠 크롤러
├── 📄 yogiyo_crawler.py           # 요기요 크롤러
├── 📄 __init__.py                 # 크롤러 팩토리
│
├── 📁 review_crawlers/            # 리뷰 수집 전문 ⭐
│   ├── 📄 run_sync_crawler.py    # 메인 실행 스크립트 (배민 리뷰 크롤링)
│   ├── 📄 run_coupang_async_crawler.py  # 쿠팡 비동기 크롤링 실행
│   ├── 📄 run_yogiyo_async_crawler.py   # 요기요 비동기 크롤링 실행
│   ├── 📄 baemin_sync_crawler.py # 배민 기본 크롤러 (매장목록 크롤링)
│   ├── 📄 baemin_sync_review_crawler.py  # 배민 리뷰 크롤러
│   ├── 📄 baemin_review_crawler.py       # 배민 비동기 버전
│   ├── 📄 coupang_async_review_crawler.py # 쿠팡 비동기 리뷰 크롤러
│   ├── 📄 yogiyo_async_review_crawler.py  # 요기요 비동기 리뷰 크롤러
│   ├── 📄 windows_async_crawler.py       # Windows 최적화
│   └── 📄 __init__.py
│
├── 📁 store_crawlers/             # 매장 정보 수집
│   ├── 📄 crawler_subprocess.py   # 서브프로세스 실행
│   └── 📄 __init__.py
│
├── 📁 reply_managers/             # 답글 관리
│   ├── 📄 reply_manager.py        # 답글 관리 베이스
│   ├── 📄 baemin_reply_manager.py # 배민 답글 관리
│   ├── 📄 coupang_reply_manager.py # 쿠팡 답글 관리
│   ├── 📄 yogiyo_reply_manager.py  # 요기요 답글 관리
│   └── 📄 __init__.py
│
├── 📁 review_parsers/             # 리뷰 파싱
│   ├── 📄 baemin_review_parser.py # 배민 리뷰 파서
│   ├── 📄 coupang_review_parser.py # 쿠팡 리뷰 파서
│   └── 📄 __init__.py
│
└── 📁 deprecated/                 # 사용 중단
    └── 📄 baemin_windows_crawler.py
```
│
├── 📁 SHIRMP/                 # Shrimp Task Manager
│   └── ... (작업 관리 파일들)
│
└── 📁 backups/                # 백업 파일
    📁 downloads/              # 다운로드 임시 파일
    📁 temp/                   # 임시 파일
```

## 🎯 핵심 모듈 상세 구조

### 📁 /api/services/ - 비즈니스 로직

```
services/
├── 📄 ai_service.py               # GPT-4 답글 생성 ⭐
├── 📄 review_collector_service.py # 리뷰 수집 통합 관리 ⭐
├── 📄 reply_posting_service.py    # 답글 등록 서비스 ⭐
├── 📄 supabase_service.py        # DB 연결 관리 ⭐
├── 📄 encryption.py              # 암호화 처리
├── 📄 error_logger.py            # 에러 로깅
├── 📄 user_service.py            # 사용자 관리
├── 📄 database.py                # DB 초기화
├── 📄 review_service.py          # 리뷰 관리
├── 📄 review_processor.py        # 리뷰 처리
├── 📄 reply_service.py           # 답글 관리
├── 📄 ai_reply_service.py        # AI 답글 (중복)
├── 📄 supabase_extension.py     # DB 확장
├── 📄 supabase_extension_methods.py
│
└── 📁 platforms/                  # 플랫폼별 서비스
    ├── 📄 baemin_subprocess.py   # 배민 답글 등록 실행
    └── 📄 baemin_reply_manager.py
```

## 🔄 핵심 프로세스 흐름

### 1. **리뷰 수집 프로세스**

```
웹/스케줄러 → review_collector_service → BaeminSyncReviewCrawler
→ 네트워크 API 캡처 → BaeminReviewParser → Supabase 저장
```

### 2. **AI 답글 생성 프로세스**

```
리뷰 선택 → ai_service → 매장 정책 조회
→ GPT-4 API → 품질 검증 → DB 저장
```

### 3. **답글 등록 프로세스**

```
답글 승인 → reply_posting_service → subprocess 실행
→ baemin_subprocess.py → Playwright 자동화 → 상태 업데이트
```

## 🚀 실행 방법

### 1. **개발 환경 설정**

```bash
# 1. 가상환경 생성
python -m venv venv
venv\Scripts\activate

# 2. 패키지 설치
pip install -r requirements.txt

# 3. 환경변수 설정 (.env)
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_key
OPENAI_API_KEY=your_openai_key
ENCRYPTION_KEY=your_encryption_key
```

### 2. **서버 실행**

```bash
# 방법 1: 배치 파일
run_server.bat

# 방법 2: 직접 실행
uvicorn main:app --reload --port 8000
```

### 3. **수동 테스트**

```bash
# 리뷰 수집 테스트
cd api\crawlers\review_crawlers
python run_sync_crawler.py

# DB 연결 테스트
python scripts\test_supabase.py
