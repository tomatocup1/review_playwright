# 리뷰 자동화 프로젝트 진행 현황

## 프로젝트 개요
- **프로젝트명**: 리뷰 자동화 SaaS 서비스
- **목적**: 배달의민족, 요기요, 쿠팡이츠의 리뷰에 AI 자동 답글 작성
- **프로젝트 루트**: C:\Review_playwright
- **웹 URL**: http://localhost:8000
- **데이터베이스**: Supabase (PostgreSQL)

## 기술 스택
- **백엔드**: Python (FastAPI)
- **프론트엔드**: HTML/CSS/JavaScript
- **데이터베이스**: Supabase (PostgreSQL)
- **크롤링**: Playwright
- **AI**: OpenAI API

## 현재 진행 상황 (2025년 1월 7일 기준)

### ✅ 완료된 작업

#### 1. 데이터베이스 설계 및 구축
- SQL 스키마 작성 완료 (SQL_playwright.txt)
- Supabase로 마이그레이션 완료
- 주요 테이블:
  - `users`: 사용자 관리
  - `platform_reply_rules`: 매장별 답글 정책
  - `reviews`: 리뷰 및 답글 데이터
  - `subscriptions`, `payments`: 구독 및 결제 관리
  - 기타 시스템 관리 테이블들
- **최근 수정**: 
  - `business_hours`, `store_address`, `store_phone` 컬럼 삭제
  - 테이블 스키마 단순화

#### 2. 크롤러 개발
- **배민 동기 크롤러** (`baemin_sync_crawler.py`): ✅ 완료
  - 로그인 기능 (동작 확인)
  - 매장 목록 조회 (동작 확인)
  - 팝업 처리
  - 스크린샷 저장
- **비동기 크롤러** (`windows_async_crawler.py`): ✅ 완료
  - Windows 환경 최적화
  - 비동기 처리 지원

#### 3. 웹 인터페이스
- **매장 등록 페이지** (`store_register.html`): ✅ 완료
  - 플랫폼 선택 (배민/요기요/쿠팡)
  - 로그인 정보 입력
  - 매장 정보 가져오기 (크롤링)
  - **다중 매장 선택 기능 추가** ✅
  - 전체 선택/해제 기능
  - 선택된 매장 수 표시
  - 답글 정책 설정 (고정값 처리)
  - 매장 유형 및 별점별 답글 설정

- **매장 관리 페이지** (`stores/list.html`): 🔧 수정 중
  - API는 정상 동작 (test_stores_api.py로 확인)
  - 프론트엔드 렌더링 문제 해결 중
  - 디버그 모드 추가

#### 4. API 엔드포인트
- **인증 관련** ✅
  - `/api/auth/register`: 회원가입
  - `/api/auth/login`: 로그인
  - `/api/auth/refresh`: 토큰 갱신
  - `/api/auth/me`: 현재 사용자 정보

- **매장 관련** ✅
  - `/api/stores/crawl`: 매장 정보 크롤링 (동작 확인)
  - `/api/stores/register`: 매장 등록 (동작 확인)
  - `/api/stores`: 매장 목록 조회 (API 동작 확인)
  - `/api/stores/{store_code}`: 매장 상세 조회
  - `/api/stores/{store_code}`: 매장 업데이트
  - `/api/stores/{store_code}`: 매장 삭제

#### 5. 답글 정책 고정값 설정
- **시작 인사말**: "안녕하세요"
- **끝 인사말**: null
- **AI 역할**: "유쾌한 가게 사장님으로 '이름','별점','리뷰'를 보고 고객을 생각하는 느낌을 주도록 text로만 리뷰를 작성"
- **톤**: "전문성과 친근함이 조화된 밝고 경험 많은 사장님의 어조"
- **금지 단어**: ["매우","레스토랑","셰프","유감","방문","안타"]
- **답글 최대 길이**: 배민/요기요 450자, 쿠팡이츠 300자
- **자동 답글 운영 시간**: "10:00-20:00"
- **답글 지연 시간**: 30분

### 🔧 현재 이슈

1. **매장 관리 페이지 표시 문제**
   - API는 정상 동작하나 프론트엔드에서 표시 안됨
   - `checkAuth` 함수 추가 완료
   - 디버그 정보 표시 기능 추가

2. **해결된 이슈**
   - ✅ 매장 다중 선택 기능 구현
   - ✅ Supabase 데이터 저장 확인

### 🔄 진행 중인 작업

1. **매장 관리 페이지 디버깅**
   - JavaScript 오류 확인 중
   - 토큰 관리 및 API 호출 문제 해결 중

2. **리뷰 크롤링 및 답글 작성**
   - 각 플랫폼별 리뷰 크롤러 개발 필요
   - AI 답글 생성 로직 구현 필요
   - 답글 자동 등록 기능 구현 필요

### 📋 향후 작업 계획

#### 1. 크롤러 완성
- [ ] 요기요 크롤러 개발
- [ ] 쿠팡이츠 크롤러 개발
- [ ] 리뷰 목록 가져오기 기능
- [ ] 답글 자동 작성 기능

#### 2. AI 답글 시스템
- [ ] OpenAI API 연동
- [ ] 프롬프트 엔지니어링
- [ ] 답글 품질 검증 시스템
- [ ] A/B 테스트 기능

#### 3. 대시보드 개발
- [ ] 메인 대시보드 페이지
- [ ] 리뷰 관리 페이지
- [ ] 통계 및 분석 페이지
- [ ] 사용자 설정 페이지

#### 4. 백그라운드 작업
- [ ] 스케줄러 구현 (자동 크롤링)
- [ ] 큐 시스템 구현 (답글 처리)
- [ ] 알림 시스템 구현

#### 5. 결제 시스템
- [ ] 요금제 선택 페이지
- [ ] 결제 연동 (토스페이먼츠 등)
- [ ] 구독 관리 기능

## 주요 파일 구조
```
C:\Review_playwright\
├── api/
│   ├── crawlers/
│   │   ├── baemin_sync_crawler.py     # 배민 동기 크롤러
│   │   ├── windows_async_crawler.py   # 비동기 크롤러 베이스
│   │   └── ...
│   ├── routes/
│   │   ├── auth.py                    # 인증 관련 API
│   │   ├── stores.py                  # 매장 관련 API
│   │   └── ...
│   └── main.py                        # FastAPI 메인
├── web/
│   ├── templates/
│   │   ├── store_register.html        # 매장 등록 페이지
│   │   ├── stores/
│   │   │   └── list.html             # 매장 목록 페이지
│   │   └── ...
│   └── static/
│       ├── css/
│       └── js/
│           └── auth.js                # 인증 관련 JavaScript
├── logs/
│   └── screenshots/                    # 크롤링 스크린샷
├── SQL_playwright.txt                  # 데이터베이스 스키마
├── test_stores_api.py                 # API 테스트 스크립트
└── plan.md                            # 프로젝트 계획 (이 파일)
```

## 테스트 및 디버깅

### API 테스트 방법
1. `test_stores_api.py` 사용
2. 브라우저 개발자 도구에서 토큰 복사
3. 스크립트에 토큰 입력 후 실행

### 프론트엔드 디버깅
1. 브라우저 개발자 도구 (F12)
2. Console 탭에서 에러 확인
3. Network 탭에서 API 요청 확인
4. Application > Local Storage에서 토큰 확인

## 환경 설정
- **Python**: 3.10
- **Node.js**: Playwright 실행용
- **Playwright**: Chromium 브라우저
- **Supabase**: 프로젝트 연결 완료
- **로그 경로**: `C:\Review_playwright\logs`

## 주의사항
- Windows 환경에서 asyncio 이벤트 루프 정책 설정 필요
- Playwright 설치 필요 (`playwright install chromium`)
- Supabase 연결 정보 `.env` 파일에 설정
- 로그는 `C:\Review_playwright\logs`에 저장
- 배민 크롤링 시 실제 계정 필요

---
*최종 업데이트: 2025년 1월 7일 11:30*
