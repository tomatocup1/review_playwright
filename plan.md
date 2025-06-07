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

#### 2. 크롤러 개발 ✅ 완료
- **배민 크롤러** (`baemin_windows_crawler.py`): ✅ 완료
  - 로그인 기능
  - 매장 목록 조회
  - 팝업 처리
  - 스크린샷 저장

- **쿠팡이츠 크롤러** (`coupang_crawler.py`): ✅ 완료
  - 로그인 기능 (실제 셀렉터 적용)
  - 매장 목록 조회
  - 팝업 자동 닫기
  - 매장 선택 기능

- **요기요 크롤러** (`yogiyo_crawler.py`): ✅ 완료
  - 로그인 기능
  - 매장 목록 조회 (드롭다운 파싱)
  - 매장 선택 기능
  - 현재 매장 정보 가져오기

- **크롤러 서브프로세스** (`crawler_subprocess.py`): ✅ 완료
  - 배민(동기), 쿠팡/요기요(비동기) 통합 처리
  - FastAPI 이벤트 루프와 분리 실행

#### 3. 웹 인터페이스
- **매장 등록 페이지** (`store_register_fixed.html`): ✅ 완료
  - 플랫폼 선택 (배민/요기요/쿠팡)
  - 로그인 정보 입력
  - **매장 정보 크롤링 기능** ✅
    - 배민: 드롭다운 select에서 매장 목록 가져오기
    - 쿠팡이츠: 커스텀 드롭다운에서 매장 목록 파싱
    - 요기요: 드롭다운 메뉴에서 매장 목록 파싱
  - **매장 선택 후 Supabase 등록** ✅
  - 답글 정책 설정
  - 운영 설정

- **매장 관리 페이지** (`stores/list.html`): ✅ 완료
  - 등록된 매장 목록 표시
  - 매장 정보 수정/삭제
  - 필터링 및 페이징

#### 4. API 엔드포인트
- **인증 관련** ✅
  - `/api/auth/register`: 회원가입
  - `/api/auth/login`: 로그인
  - `/api/auth/refresh`: 토큰 갱신
  - `/api/auth/me`: 현재 사용자 정보

- **매장 관련** ✅
  - `/api/stores/crawl`: 매장 정보 크롤링 (3개 플랫폼 모두 동작)
  - `/api/stores/register`: 매장 등록 (Supabase 저장 확인)
  - `/api/stores`: 매장 목록 조회
  - `/api/stores/{store_code}`: 매장 상세 조회
  - `/api/stores/{store_code}`: 매장 업데이트
  - `/api/stores/{store_code}`: 매장 삭제

#### 5. 답글 정책 설정
- **시작 인사말**: "안녕하세요"
- **끝 인사말**: null
- **AI 역할**: "유쾌한 가게 사장님으로 '이름','별점','리뷰'를 보고 고객을 생각하는 느낌을 주도록 text로만 리뷰를 작성"
- **톤**: "전문성과 친근함이 조화된 밝고 경험 많은 사장님의 어조"
- **금지 단어**: ["매우","레스토랑","셰프","유감","방문","안타"]
- **답글 최대 길이**: 배민/요기요 450자, 쿠팡이츠 300자
- **자동 답글 운영 시간**: "10:00-20:00"
- **답글 지연 시간**: 30분

### 🚀 최근 완료 작업 (2025년 1월 7일)

1. **쿠팡이츠 크롤러 완성**
   - HTML 셀렉터 수정 (#loginId, #password)
   - 팝업 자동 닫기 기능 추가
   - 드롭다운 매장 목록 파싱 구현

2. **요기요 크롤러 완성**
   - 로그인 기능 구현 (name 속성 사용)
   - 드롭다운 매장 목록 파싱 (ul.List__VendorList-sc-2ocjy3-8)
   - 매장 선택 기능 구현

3. **크롤러 통합**
   - crawler_subprocess.py에서 3개 플랫폼 모두 지원
   - 웹 페이지에서 매장 정보 크롤링 → Supabase 등록 완료

### 🔄 진행 중인 작업

1. **리뷰 크롤링 기능**
   - 각 플랫폼별 리뷰 목록 가져오기
   - 리뷰 상세 정보 파싱
   - 기존 답글 여부 확인

2. **AI 답글 시스템**
   - OpenAI API 연동
   - 프롬프트 엔지니어링
   - 답글 생성 로직

3. **답글 자동 등록**
   - 각 플랫폼별 답글 등록 기능
   - 답글 등록 결과 확인

### 📋 향후 작업 계획

#### 1. 리뷰 및 답글 기능
- [ ] 리뷰 크롤링 기능 구현
  - [ ] 배민 리뷰 목록 가져오기
  - [ ] 쿠팡이츠 리뷰 목록 가져오기
  - [ ] 요기요 리뷰 목록 가져오기
- [ ] AI 답글 생성 시스템
  - [ ] OpenAI API 연동
  - [ ] 프롬프트 최적화
  - [ ] 답글 품질 검증
- [ ] 답글 자동 등록
  - [ ] 각 플랫폼별 답글 POST 기능
  - [ ] 등록 결과 확인 및 로깅

#### 2. 대시보드 개발
- [ ] 메인 대시보드 페이지
- [ ] 리뷰 관리 페이지
- [ ] 통계 및 분석 페이지
- [ ] 답글 이력 조회

#### 3. 백그라운드 작업
- [ ] 스케줄러 구현 (자동 크롤링)
- [ ] 큐 시스템 구현 (답글 처리)
- [ ] 알림 시스템 구현

#### 4. 관리 기능
- [ ] 답글 템플릿 관리
- [ ] 금지 단어 관리
- [ ] 사용자 권한 관리
- [ ] 시스템 설정

#### 5. 결제 시스템
- [ ] 요금제 선택 페이지
- [ ] 결제 연동 (토스페이먼츠 등)
- [ ] 구독 관리 기능

## 주요 파일 구조
```
C:\Review_playwright\
├── api/
│   ├── crawlers/
│   │   ├── baemin_windows_crawler.py  # 배민 크롤러
│   │   ├── coupang_crawler.py         # 쿠팡이츠 크롤러
│   │   ├── yogiyo_crawler.py          # 요기요 크롤러
│   │   ├── crawler_subprocess.py      # 크롤러 통합 실행
│   │   └── windows_async_crawler.py   # 비동기 크롤러 베이스
│   ├── routes/
│   │   ├── auth.py                    # 인증 관련 API
│   │   ├── stores.py                  # 매장 관련 API
│   │   └── ...
│   └── main.py                        # FastAPI 메인
├── web/
│   ├── templates/
│   │   ├── store_register_fixed.html  # 매장 등록 페이지
│   │   ├── stores/
│   │   │   └── list.html             # 매장 목록 페이지
│   │   └── ...
│   └── static/
│       ├── css/
│       └── js/
│           └── auth.js                # 인증 관련 JavaScript
├── logs/
│   └── screenshots/                   # 크롤링 스크린샷
│       ├── baemin/
│       ├── coupang/
│       └── yogiyo/
├── SQL_playwright.txt                 # 데이터베이스 스키마
├── test_coupang_crawler.py           # 쿠팡 크롤러 테스트
├── test_yogiyo_crawler.py            # 요기요 크롤러 테스트
└── plan.md                           # 프로젝트 계획 (이 파일)
```

## 테스트 방법

### 크롤러 개별 테스트
```bash
# 배민 크롤러 테스트
python C:\Review_playwright\api\crawlers\baemin_windows_crawler.py

# 쿠팡이츠 크롤러 테스트
python C:\Review_playwright\api\crawlers\coupang_crawler.py

# 요기요 크롤러 테스트
python C:\Review_playwright\api\crawlers\yogiyo_crawler.py
```

### 웹 서비스 테스트
1. FastAPI 서버 실행: `python -m api.main`
2. http://localhost:8000/stores/register 접속
3. 플랫폼 선택 후 로그인 정보 입력
4. "매장 정보 가져오기" 클릭
5. 매장 선택 후 등록

## 환경 설정
- **Python**: 3.10
- **Playwright**: Chromium 브라우저
- **Supabase**: 프로젝트 연결 완료
- **로그 경로**: `C:\Review_playwright\logs`

## 주의사항
- Windows 환경에서 asyncio 이벤트 루프 정책 설정 필요
- Playwright 설치 필요 (`playwright install chromium`)
- Supabase 연결 정보 `.env` 파일에 설정
- 각 플랫폼별 실제 계정 필요
- 크롤링 시 headless=True로 설정하여 백그라운드 실행

---
*최종 업데이트: 2025년 1월 7일 12:30*
