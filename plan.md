# 리뷰 자동화 프로젝트 진행 현황

## 프로젝트 개요
- **프로젝트명**: 리뷰 자동화 SaaS 서비스
- **목적**: 배달의민족, 요기요, 쿠팡이츠의 리뷰에 AI 자동 답글 작성
- **프로젝트 루트**: C:\Review_playwright
- **웹 URL**: http://localhost/playwright
- **데이터베이스**: Supabase (PostgreSQL)

## 기술 스택
- **백엔드**: Python (FastAPI)
- **프론트엔드**: HTML/CSS/JavaScript
- **데이터베이스**: Supabase (PostgreSQL)
- **크롤링**: Playwright
- **AI**: OpenAI API

## 현재 진행 상황 (2025년 1월 8일 기준)

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

#### 2. 크롤러 개발
- **배민 크롤러** (`baemin_windows_crawler.py`): ✅ 완료
  - 로그인 기능
  - 매장 목록 조회
  - 팝업 처리
  - 스크린샷 저장

- **배민 리뷰 크롤러** (`baemin_sync_review_crawler.py`): ✅ 완료
  - 리뷰 페이지 이동
  - 미답변 탭 클릭
  - API 응답 가로채기로 리뷰 수집
  - 날짜 파싱 (리뷰 ID에서 추출)

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

#### 3. 웹 인터페이스
- **메인 대시보드** (`index.html`): ✅ 완료
- **매장 등록 페이지** (`store_register_fixed.html`): ✅ 완료
- **매장 관리 페이지** (`stores/list.html`): ✅ 완료
- **리뷰 관리 페이지** (`reviews.html`): ✅ 완료

#### 4. API 엔드포인트
- **인증 관련** ✅
- **매장 관련** ✅
- **리뷰 관련** ✅

### 🚀 최근 완료 작업 (2025년 1월 8일 20:45)

#### 1. 리뷰 통계 기능 구현 ✅ 완료
- **SupabaseService 통계 메서드 추가**:
  - `get_review_stats()` 메서드 구현
  - 최근 30일 기준 통계 계산 
  - 전체 리뷰수, 평균 별점, 답변율, 미답변 리뷰수 계산
- **프론트엔드 디버그 기능 추가**:
  - 디버그 토글 버튼 추가
  - API 호출 과정 실시간 추적
  - 에러 발생시 상세 정보 표시
- **통계 API 호출 로직 개선**:
  - `loadStats()` 함수에서 `/reviews/stats/{store_code}` 호출
  - 통계 데이터 UI 업데이트 로직 추가
  - 에러 처리 강화

#### 2. Windows 동기식 크롤러 개발 ✅
- **문제 해결**: Windows asyncio 이벤트 루프 호환성 문제
- **해결 방법**: 동기식 크롤러 개발
  - `baemin_sync_crawler.py`: 배민 동기식 크롤러 베이스
  - `baemin_sync_review_crawler.py`: 배민 리뷰 크롤러
  - `run_sync_crawler.py`: 메인 실행 스크립트

#### 3. 리뷰 크롤링 기능 ✅ 완료
- **리뷰 수집 성공**: 배민 미답변 리뷰 정상 수집
- **수집 데이터**:
  - 리뷰 ID (고유 식별자)
  - 작성자명
  - 별점 (1-5점)
  - 리뷰 내용
  - 주문 메뉴
  - 배달 리뷰 (좋아요/별로)
  - 리뷰 이미지 URL
  - 작성 날짜 (ID에서 추출)
- **날짜 추출 로직**:
  - 리뷰 ID 형식: `YYYYMMDD` + 추가 숫자
  - 예: `2025060802465251` → `2025-06-08`

#### 4. Supabase 저장 기능 ✅ 완료
- **중복 체크**: review_id로 중복 확인
- **데이터 타입 처리**: 
  - PostgreSQL TEXT[] 배열 형식 처리
  - Python 리스트를 직접 전달 (Supabase 자동 변환)
- **저장 통계**: 성공/중복/실패 개수 표시
- **사용량 추적**: RPC 함수로 사용량 업데이트

### 📋 현재 상태 및 다음 작업

#### 🔵 Phase 1: 리뷰 크롤링 (100% 완료)
- [x] 배민 리뷰 페이지 분석
- [x] 리뷰 목록 파싱 구현
- [x] 리뷰 데이터 추출 (작성자, 별점, 내용, 메뉴 등)
- [x] Supabase 저장 로직 구현
- [x] 리뷰 통계 API 및 UI 완성
- [x] 테스트 및 디버깅

#### 🟡 Phase 2: AI 답글 시스템 (0% 완료)
- [ ] OpenAI API 설정
- [ ] 프롬프트 템플릿 개발
- [ ] 답글 생성 API 엔드포인트
- [ ] 답글 품질 검증 로직

#### 🔴 Phase 3: 답글 자동 등록 (0% 완료)
- [ ] 각 플랫폼별 답글 등록 분석
- [ ] 답글 POST 기능 구현
- [ ] 에러 처리 및 로깅

### 📊 프로젝트 진행률
- **전체 진행률**: 약 45%
- **Phase 1 (리뷰 크롤링)**: 100%
- **Phase 2 (AI 답글)**: 0%
- **Phase 3 (답글 등록)**: 0%

### 🔧 즉시 필요한 작업

1. **OpenAI API 연동** (2-3시간)
   - API 키 설정 (.env)
   - 답글 생성 함수 개발
   - 프롬프트 최적화
   - 매장별 답글 정책 반영

2. **답글 등록 크롤러** (3-4시간)
   - 배민 답글 등록 분석
   - `post_reply()` 함수 구현
   - 성공/실패 처리

3. **쿠팡이츠, 요기요 리뷰 크롤러** (2-3시간)
   - 각 플랫폼별 리뷰 수집 기능
   - 통합 실행 시스템

4. **스케줄러 개발** (2시간)
   - 자동 실행 스케줄러
   - 매장별 크롤링 주기 설정
   - 백그라운드 작업 관리

### 🚨 해결된 이슈
- ✅ Windows asyncio 호환성 문제 → 동기식 크롤러로 해결
- ✅ 리뷰 HTML 파싱 문제 → API 응답 가로채기로 해결
- ✅ 인코딩 문제 → UTF-8 인코딩 설정
- ✅ DB 저장 오류 → PostgreSQL 배열 형식 처리
- ✅ 통계 API 오류 → 통계 메서드 구현 및 디버그 기능 추가

### 📁 주요 파일 구조 (업데이트)
```
C:\Review_playwright\
├── api/
│   ├── main.py                           # FastAPI 메인 애플리케이션
│   ├── crawlers/
│   │   ├── baemin_sync_crawler.py        # 배민 동기식 크롤러 ✅
│   │   ├── baemin_sync_review_crawler.py # 배민 리뷰 크롤러 ✅
│   │   ├── run_sync_crawler.py           # 메인 실행 스크립트 ✅
│   │   └── ...
│   └── services/
│       ├── supabase_service.py           # Supabase 서비스 레이어 ✅
│       └── encryption.py                 # 암호화/복호화
├── static/
│   ├── index.html                        # 메인 대시보드 ✅
│   ├── reviews.html                      # 리뷰 관리 페이지 ✅
│   └── stores/
│       └── list.html                     # 매장 관리 페이지 ✅
├── logs/
│   ├── screenshots/
│   │   └── baemin_reviews/               # 리뷰 스크린샷
│   └── crawler.log                       # 크롤러 로그
└── ...
```

## 권장 개발 순서

### 이번 주 목표 (1월 8-10일)
1. ~~**오늘**: 리뷰 Supabase 저장 구현~~ ✅ 완료
2. ~~**오늘**: 리뷰 통계 기능 구현~~ ✅ 완료
3. **내일**: OpenAI API 연동 및 답글 생성
4. **모레**: 답글 자동 등록 기능

### 다음 주 목표 (1월 13-17일)
1. 쿠팡이츠, 요기요 리뷰 크롤러
2. 전체 시스템 통합 테스트
3. 스케줄러 및 자동화
4. 배포 준비

## 테스트 명령어

### 웹 서버 실행
```bash
# FastAPI 서버 시작
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 브라우저에서 확인
# http://localhost:8000        (메인 대시보드)
# http://localhost:8000/reviews (리뷰 관리)
# http://localhost:8000/stores  (매장 관리)
```

### 리뷰 크롤링 및 저장 테스트
```bash
# 배민 리뷰 수집 (대화형)
python C:\Review_playwright\api\crawlers\run_sync_crawler.py

# 옵션 설명:
# 1: 전체 매장 자동 실행 (headless) - Enter 없이 자동 저장
# 2: 첫 번째 매장 브라우저 표시 - Enter 필요
# 3: 특정 매장 선택 테스트 - Enter 필요
```

### 저장 결과 확인
```
[DB] 저장 완료:
  - 성공: X개      # 새로 저장된 리뷰
  - 중복: Y개      # 이미 DB에 있는 리뷰
  - 실패: Z개      # 저장 실패한 리뷰
```

## 다음 작업 상세

### 1. AI 답글 생성 API (`/api/reviews/{review_id}/generate-reply`)
```python
async def generate_reply(review_id: str):
    # 1. 리뷰 정보 조회
    # 2. 매장 답글 정책 조회
    # 3. OpenAI API 호출
    # 4. 생성된 답글 반환
```

### 2. 답글 등록 API (`/api/reviews/{review_id}/post-reply`)
```python
async def post_reply(review_id: str, reply_text: str):
    # 1. 크롤러로 답글 등록
    # 2. DB 상태 업데이트
    # 3. 결과 반환
```

### 3. 쿠팡이츠/요기요 리뷰 크롤러
- 각 플랫폼별 리뷰 수집 로직 구현
- 통합 실행 시스템 개발

---
*최종 업데이트: 2025년 1월 8일 20:45*
