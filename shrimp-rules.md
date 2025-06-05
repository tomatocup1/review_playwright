# 리뷰 자동화 SaaS 개발 규칙

## 프로젝트 개요

- **프로젝트명**: 리뷰 자동화 SaaS 서비스
- **대상 플랫폼**: 배민, 요기요, 쿠팡이츠
- **기술 스택**: Playwright, Supabase, FastAPI, React/Next.js, GPT-4o-mini
- **루트 경로**: C:\Review_playwright
- **로컬 URL**: http://localhost/playwright

## 프로젝트 아키텍처

### 필수 디렉터리 구조
```
C:\Review_playwright\
├── crawler/              # 플랫폼별 크롤러 모듈
│   ├── baemin/
│   ├── yogiyo/
│   └── coupang/
├── api/                  # FastAPI 백엔드
│   ├── routes/
│   ├── models/
│   └── services/
├── web/                  # React/Next.js 프론트엔드
│   ├── components/
│   ├── pages/
│   └── hooks/
├── ai/                   # AI 답글 엔진
│   ├── prompts/
│   └── processors/
├── logs/                 # 로그 파일 저장
├── config/              # 설정 파일
└── tests/               # 테스트 코드
```

## 크롤러 개발 규칙

### Playwright 사용 규칙
- **반드시 Playwright 사용** (Selenium 코드는 모두 마이그레이션)
- **브라우저 컨텍스트 재사용**: 로그인 세션 유지를 위해 context 저장
- **안티봇 우회**: stealth 플러그인 사용 필수
- **비동기 처리**: 모든 크롤링 작업은 async/await 사용

### 크롤러 파일 구조
```python
# crawler/baemin/crawler.py 예시
class BaeminCrawler:
    def __init__(self, store_config):
        # Supabase에서 로그인 정보 복호화
        # Playwright 브라우저 초기화
    
    async def login(self):
        # 로그인 처리 (2FA 대응 포함)
    
    async def get_reviews(self):
        # 미답변 리뷰만 수집
    
    async def post_reply(self, review_id, reply_text):
        # 답글 등록 (재시도 로직 포함)
```

### 크롤링 작업 흐름
1. **구독 상태 확인** → 만료시 중단
2. **로그인 세션 확인** → 필요시 재로그인
3. **미답변 리뷰 수집** → 최대 100개/회
4. **AI 분석 요청** → 카테고리 분류
5. **답글 생성** → 품질 점수 확인
6. **답글 등록** → 실패시 최대 5회 재시도
7. **로그 기록** → logs/ 디렉터리에 저장

## Supabase 통합 규칙

### 데이터베이스 접근
- **환경변수 사용**: SUPABASE_URL, SUPABASE_ANON_KEY
- **RLS 정책 준수**: 모든 쿼리는 user_code 기반
- **타입 안전성**: TypeScript 인터페이스 정의 필수

### 필수 테이블 연동
```typescript
// 반드시 다음 테이블들과 연동
- users: 사용자 정보
- subscriptions: 구독 상태
- platform_reply_rules: 매장별 답글 정책
- reviews: 리뷰 및 답글 데이터
- error_logs: 에러 로깅
```

### Supabase 서비스 사용
- **인증**: Supabase Auth 사용 (JWT 토큰 관리)
- **실시간**: 리뷰 알림은 Realtime 구독 사용
- **스토리지**: 리뷰 이미지는 Storage 버킷에 저장
- **Edge Functions**: AI 답글 생성 서버리스 함수

## AI 답글 생성 규칙

### GPT 사용 규칙
- **모델**: gpt-4o-mini 사용 (비용 최적화)
- **프롬프트 관리**: ai/prompts/ 디렉터리에 JSON 파일로 저장
- **토큰 제한**: 답글당 최대 300 토큰
- **품질 검증**: 생성된 답글은 반드시 품질 점수 계산

### 답글 분류 로직
```python
def classify_review(review):
    if review.rating <= 2 and contains_complaint(review.content):
        return "BOSS_REPLY_NEEDED"  # 사장님 확인 필요
    elif review.rating >= 4 and is_simple_positive(review.content):
        return "AUTO_REPLY"  # AI 자동 답글
    else:
        return "AI_WITH_REVIEW"  # AI 생성 후 검토
```

### 프롬프트 템플릿
```json
{
  "system": "매장 사장님 역할로 친근하고 진정성 있는 답글 작성",
  "user": "리뷰: {review_content}\n평점: {rating}\n주문메뉴: {menu}",
  "constraints": [
    "최대 300자",
    "이모티콘 사용 금지",
    "할인 약속 금지",
    "{prohibited_words} 사용 금지"
  ]
}
```

## 보안 규칙

### 민감정보 처리
- **플랫폼 로그인 정보**: Supabase Vault 또는 암호화 저장
- **API 키**: 환경변수로만 관리 (.env 파일 git ignore)
- **결제 정보**: 토큰화하여 저장, 실제 카드번호 저장 금지

### 접근 제어
- **역할 기반 권한**: owner, franchise, sales, admin
- **매장별 권한**: user_store_permissions 테이블 확인
- **API Rate Limiting**: 사용자별 시간당 1000회 제한

## 로깅 및 모니터링

### 로그 작성 규칙
- **로그 경로**: C:\Review_playwright\logs\
- **로그 포맷**: JSON 형식 (timestamp, level, message, context)
- **로그 레벨**: ERROR > WARNING > INFO > DEBUG
- **로그 로테이션**: 일별 로테이션, 30일 보관

### 에러 처리
```python
try:
    # 크롤링 작업
except PlaywrightException as e:
    await log_error({
        "category": "크롤링실패",
        "platform": platform,
        "error_type": type(e).__name__,
        "error_message": str(e),
        "store_code": store_code
    })
    # Supabase error_logs 테이블에 저장
```

## 개발 워크플로우

### Git 브랜치 전략
- **master**: 프로덕션 코드
- **develop**: 개발 통합 브랜치  
- **feature/***: 기능 개발 브랜치
- **hotfix/***: 긴급 수정 브랜치

### 커밋 메시지 규칙
```
feat: 새로운 기능 추가
fix: 버그 수정
refactor: 코드 리팩토링
docs: 문서 수정
test: 테스트 추가/수정
chore: 빌드, 설정 변경
```

### 테스트 요구사항
- **단위 테스트**: 모든 서비스 클래스
- **통합 테스트**: API 엔드포인트
- **E2E 테스트**: 크롤러 주요 플로우

## 파일 작업 규칙

### 파일 수정시
- **search_file로 위치 확인** 후 edit_file_lines 사용
- **dryRun: true**로 먼저 검증
- **섹션별 분할**: 큰 파일은 3-5개 섹션으로 나누어 수정

### 연관 파일 동시 수정
- API 수정시: 프론트엔드 타입 정의도 수정
- 데이터베이스 스키마 변경시: 모델, 마이그레이션, 타입 모두 수정
- 크롤러 수정시: 테스트 코드도 함께 수정

## AI 에이전트 작업 지침

### 작업 우선순위
1. **구독/결제 관련** 버그 → 즉시 수정
2. **크롤링 실패** → 24시간 내 수정
3. **UI/UX 개선** → 계획된 스프린트에서 처리
4. **새 기능 추가** → 기획 검토 후 진행

### 의사결정 기준
- **보안 > 안정성 > 성능 > 기능**
- 불확실한 경우 보수적 접근
- 외부 의존성 최소화
- 비용 효율성 고려

## 금지 사항

### 절대 금지
- **하드코딩된 비밀번호나 API 키**
- **동기적 크롤링** (반드시 비동기 처리)
- **로그 미작성** (모든 중요 작업은 로깅)
- **권한 검증 생략**
- **에러 무시** (반드시 처리 또는 상위로 전파)

### 피해야 할 사항
- Selenium 코드 사용 (Playwright로 대체)
- 전역 변수 남용
- 중복 코드 (DRY 원칙)
- 테스트 없는 배포
- 문서화되지 않은 API

## 플랫폼별 특이사항

### 배민
- 2FA 인증 처리 필요
- 답글 등록시 최소 30초 간격
- 이미지 리뷰 우선 처리

### 요기요  
- CAPTCHA 우회 처리 필요
- 별점별 답글 템플릿 차별화
- 배달/포장 구분 처리

### 쿠팡이츠
- 쿠팡 통합 로그인 사용
- 답글 수정 불가 (신중히 작성)
- 쿠팡 리워드 연동 고려

## 성능 최적화

### 크롤링 최적화
- 브라우저 인스턴스 재사용
- 불필요한 리소스 차단 (이미지, 폰트)
- 병렬 처리 (최대 5개 동시)

### 데이터베이스 최적화
- 인덱스 활용 (store_code, review_date)
- 배치 삽입/업데이트
- 커넥션 풀 관리

### 프론트엔드 최적화
- 코드 스플리팅
- 이미지 lazy loading
- 캐싱 전략 (SWR 사용)