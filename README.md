# 리뷰 자동화 SaaS 서비스

배민, 요기요, 쿠팡이츠 리뷰 크롤링 및 AI 답글 자동화 시스템

## 프로젝트 구조

```
C:\Review_playwright\
├── crawler/              # 플랫폼별 크롤러 모듈
│   ├── base.py          # 크롤러 베이스 클래스
│   ├── baemin/          # 배민 크롤러
│   │   ├── crawler.py   # 배민 크롤러 구현
│   │   └── selectors.py # CSS 셀렉터 정의
│   ├── yogiyo/          # 요기요 크롤러 (추후 구현)
│   └── coupang/         # 쿠팡이츠 크롤러 (추후 구현)
├── api/                  # FastAPI 백엔드 (추후 구현)
├── web/                  # React/Next.js 프론트엔드 (추후 구현)
├── ai/                   # AI 답글 엔진 (추후 구현)
├── logs/                 # 로그 파일
├── config/              # 설정 파일
├── tests/               # 테스트 코드
├── .env.example         # 환경변수 템플릿
├── requirements.txt     # Python 패키지 목록
└── README.md           # 프로젝트 문서
```

## 설치 방법

### 1. Python 가상환경 생성 및 활성화

```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

### 2. 패키지 설치

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. 환경변수 설정

```bash
cp .env.example .env
# .env 파일을 편집하여 필요한 값 설정
```

## 배민 크롤러 사용법

### 기본 사용 예제

```python
from crawler.baemin import BaeminCrawler

# 매장 설정
store_config = {
    'store_code': 'STORE001',
    'platform_id': 'your_baemin_id',
    'platform_pw': 'your_baemin_pw',
    'platform_code': 'your_platform_code',
    'store_name': '우리 매장'
}

# 크롤러 생성 및 실행
crawler = BaeminCrawler(store_config)
await crawler.initialize()
await crawler.login()
reviews = await crawler.get_reviews()
```

### 테스트 실행

```bash
python tests/test_baemin_crawler.py
```

## 주요 기능

### 완료된 기능
- ✅ Playwright 기반 배민 크롤러
- ✅ 안티봇 우회 (playwright-stealth)
- ✅ 세션 재사용으로 로그인 유지
- ✅ 미답변 리뷰 수집
- ✅ 답글 등록 기능
- ✅ 금지어 감지 및 처리

### 개발 중인 기능
- 🚧 Supabase 데이터베이스 연동
- 🚧 AI 답글 생성 엔진
- 🚧 FastAPI 백엔드
- 🚧 React 대시보드
- 🚧 요기요/쿠팡이츠 크롤러

## 개발 가이드

### 코드 스타일
- Python: PEP 8 준수
- 비동기 함수 사용 (async/await)
- 타입 힌트 활용
- 적절한 로깅과 에러 처리

### 커밋 메시지 규칙
```
feat: 새로운 기능 추가
fix: 버그 수정
refactor: 코드 리팩토링
docs: 문서 수정
test: 테스트 추가/수정
chore: 빌드, 설정 변경
```

## 라이선스

Private - All rights reserved
