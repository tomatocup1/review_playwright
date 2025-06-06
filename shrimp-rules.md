# 리뷰 자동화 SaaS 개발 규칙

## 프로젝트 개요

- **프로젝트명**: 리뷰 자동화 SaaS 서비스
- **대상 플랫폼**: 배민, 요기요, 쿠팡이츠
- **기술 스택**: Python 3.x, Playwright, Supabase, FastAPI, OpenAI API
- **루트 경로**: C:\Review_playwright
- **로컬 URL**: http://localhost/playwright

## 프로젝트 아키텍처

### 필수 디렉토리 구조
```
C:\Review_playwright\
├── crawler/              # 플랫폼별 크롤러 모듈
│   ├── base.py           # 크롤러 베이스 클래스
│   ├── baemin/
│   ├── yogiyo/
│   └── coupang/
├── api/                  # FastAPI 백엔드
│   ├── main.py           # FastAPI 앱 엔트리포인트
│   ├── routes/           # API 엔드포인트
│   ├── models/           # Pydantic 모델
│   └── services/         # 비즈니스 로직
├── web/                  # 웹 대시보드
│   ├── static/           # 정적 파일 (CSS, JS, 이미지)
│   ├── templates/        # Jinja2 HTML 템플릿
│   └── components/       # 재사용 가능한 UI 컴포넌트
├── logs/                 # 로그 파일 저장
├── config/              # 설정 파일
├── sessions/            # 크롤러 세션 저장
├── screenshots/         # 크롤링 스크린샷
└── tests/               # 테스트 코드
```

## 웹 대시보드 개발 규칙

### FastAPI 사용 규칙
- **기본 포트**: 8000 (uvicorn 사용)
- **비동기 처리**: 모든 데이터베이스 작업은 async/await
- **라우팅**: RESTful API 패턴 준수
- **인증**: JWT 토큰 기반 (python-jose 사용)
- **CORS 설정**: localhost/playwright 허용

### 파일 구조 패턴
```python
# api/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="리뷰 자동화 API")

# 정적 파일 및 템플릿 설정
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# api/routes/auth.py
@router.post("/api/auth/register")
async def register(user: UserCreate):
    # 1. 비밀번호 해싱 (bcrypt)
    # 2. user_code 자동 생성 (USR001, USR002...)
    # 3. Supabase users 테이블에 저장
    # 4. 기본 구독 생성 (FREE_TRIAL)
    # 5. JWT 토큰 반환

# api/routes/stores.py  
@router.post("/api/stores/register")
async def register_store(store: StoreCreate, user=Depends(get_current_user)):
    # 1. 플랫폼 로그인 정보로 크롤러 실행
    # 2. platform_code 자동 가져오기
    # 3. platform_reply_rules 테이블에 저장
    # 4. 기본 답글 정책 설정
```

### HTML 템플릿 구조
```html
<!-- web/templates/base.html -->
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>{% block title %}리뷰 자동화{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', path='/css/style.css') }}">
</head>
<body>
    {% block content %}{% endblock %}
    <script src="{{ url_for('static', path='/js/main.js') }}"></script>
</body>
</html>
```

### 회원가입/로그인 프로세스
1. **회원가입 플로우**
   ```
   /register → 이메일/비밀번호 입력 → 이메일 중복 확인
   → bcrypt 해싱 → users 테이블 저장 → 무료 구독 생성
   → JWT 토큰 발급 → 대시보드 리다이렉트
   ```

2. **로그인 플로우**
   ```
   /login → 이메일/비밀번호 입력 → bcrypt 검증
   → JWT 토큰 발급 → 세션 스토리지 저장 → 대시보드
   ```

### 매장 등록 프로세스
1. **platform_code 자동 가져오기**
   ```python
   async def get_platform_code(platform: str, login_id: str, login_pw: str):
       # 1. 해당 플랫폼 크롤러 인스턴스 생성
       # 2. 로그인 수행
       # 3. 매장 정보 페이지 접근
       # 4. platform_code 추출 (URL 또는 페이지에서)
       # 5. 매장명, 주소 등 기본 정보도 함께 수집
       return {
           "platform_code": "14662128",
           "store_name": "더블유버거",
           "store_address": "서울시 강남구..."
       }
   ```

2. **매장 등록 UI**
   ```
   플랫폼 선택 → ID/PW 입력 → "매장 정보 가져오기" 클릭
   → 로딩 표시 → 매장 정보 자동 입력 → 추가 설정
   → "등록" 클릭 → platform_reply_rules 저장
   ```

## 데이터베이스 작업 규칙

### Supabase 클라이언트 사용
```python
# config/supabase_client.py 임포트
from config.supabase_client import get_supabase_client

# 비동기 쿼리 예시
async def create_user(user_data: dict):
    supabase = get_supabase_client()
    
    # user_code 생성
    last_user = supabase.table('users').select('user_code').order('created_at', desc=True).limit(1).execute()
    user_code = generate_next_code(last_user.data[0]['user_code'] if last_user.data else 'USR000')
    
    user_data['user_code'] = user_code
    result = supabase.table('users').insert(user_data).execute()
    return result.data[0]
```

### 트랜잭션 처리
```python
# 여러 테이블 동시 작업시
async def register_user_with_subscription(user_data: dict):
    try:
        # 1. 사용자 생성
        user = await create_user(user_data)
        
        # 2. 구독 생성
        subscription_data = {
            'user_code': user['user_code'],
            'plan_code': 'FREE_TRIAL',
            'status': 'trial',
            # ...
        }
        subscription = await create_subscription(subscription_data)
        
        return user, subscription
    except Exception as e:
        # 롤백 처리
        logger.error(f"Registration failed: {e}")
        raise
```

## 크롤러 개발 규칙

### Playwright 사용 규칙
- **반드시 Playwright 사용** (Selenium 코드는 모두 마이그레이션)
- **브라우저 컨텍스트 재사용**: 로그인 세션 유지를 위해 context 저장
- **안티봇 우회**: playwright-stealth 사용 필수
- **비동기 처리**: 모든 크롤링 작업은 async/await 사용
- **헤드리스 모드**: 프로덕션에서는 headless=True

### 새 플랫폼 크롤러 추가시
1. `crawler/` 아래에 플랫폼명 폴더 생성
2. `crawler.py`에 BaseCrawler 상속 클래스 구현
3. 필수 메서드: `login()`, `get_reviews()`, `post_reply()`
4. 플랫폼별 특성 처리 (2FA, CAPTCHA 등)
5. 테스트 코드 작성 (`tests/test_{platform}_crawler.py`)

### 크롤링 작업 흐름
1. **구독 상태 확인** → 만료시 중단
2. **로그인 세션 확인** → 필요시 재로그인
3. **미답변 리뷰 수집** → 최대 100개/회
4. **AI 분석 요청** → 카테고리 분류
5. **답글 생성** → 품질 점수 확인
6. **답글 등록** → 실패시 최대 5회 재시도
7. **로그 기록** → logs/ 디렉터리에 저장

## AI 답글 생성 규칙

### OpenAI API 사용
```python
from config.openai_client import get_openai_client

async def generate_reply(review_data: dict, reply_rules: dict):
    client = get_openai_client()
    
    prompt = f"""
    역할: {reply_rules['role']}
    톤: {reply_rules['tone']}
    
    리뷰: {review_data['review_text']}
    별점: {review_data['rating']}점
    
    답글 작성 규칙:
    - {reply_rules['greeting_start']}로 시작
    - {reply_rules['greeting_end']}로 마무리
    - 최대 {reply_rules['max_length']}자
    - 금지어: {', '.join(reply_rules['prohibited_words'])}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=600,
        temperature=0.7
    )
    
    return response.choices[0].message.content
```

## 보안 규칙

### 민감정보 처리
- **플랫폼 로그인 정보**: 암호화하여 저장 (cryptography 라이브러리)
- **API 키**: 환경변수로만 관리 (.env 파일 git ignore)
- **비밀번호**: bcrypt 해싱 (최소 12 라운드)
- **JWT 시크릿**: 강력한 랜덤 키 사용

### 접근 제어
```python
# 권한 검증 데코레이터
async def get_current_user(token: str = Depends(oauth2_scheme)):
    # JWT 토큰 검증
    # user_code 추출
    # 활성 상태 확인
    return user

async def check_store_permission(store_code: str, user: dict):
    # platform_reply_rules.owner_user_code 확인
    # user_store_permissions 확인
    # 권한 레벨 반환
```

## 코딩 스타일 규칙

### Python 코드
- **명명 규칙**: snake_case 사용
- **클래스명**: PascalCase 사용
- **상수**: UPPER_SNAKE_CASE 사용
- **Private 메서드**: 언더스코어(_) prefix
- **타입 힌트**: 모든 함수에 사용
- **Docstring**: 모든 클래스와 공개 메서드에 작성

### 파일 명명
- **Python 파일**: snake_case.py
- **테스트 파일**: test_*.py
- **설정 파일**: *_config.py

### 주석 규칙
- **한글 주석 사용**: 비즈니스 로직 설명
- **영어 주석**: 기술적 구현 상세
- **TODO 주석**: 구현 예정 기능 표시

## 로깅 및 에러 처리

### 로그 작성
```python
import logging
from pathlib import Path

# 로거 설정
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
```

### 에러 처리 패턴
```python
try:
    # 위험한 작업
    result = await risky_operation()
except PlaywrightTimeoutError as e:
    logger.error(f"크롤링 타임아웃: {e}")
    await save_screenshot("timeout_error")
    raise HTTPException(status_code=408, detail="크롤링 시간 초과")
except Exception as e:
    logger.error(f"예상치 못한 오류: {e}")
    # Supabase error_logs에 저장
    await log_error_to_db(e)
    raise
```

## 파일 작업 규칙

### 파일 생성/수정시
- **단계별 작업**: 큰 파일은 3-5개 섹션으로 나누어 작업
- **먼저 읽기**: 수정 전 항상 현재 내용 확인
- **Git 커밋**: 모든 변경사항은 즉시 커밋

### 연관 파일 동시 수정
- **API 수정시**: Pydantic 모델도 함께 수정
- **크롤러 수정시**: 테스트 코드도 함께 수정
- **데이터베이스 스키마 변경시**: 모델, API, 문서 모두 수정

## Git 작업 규칙

### 브랜치 전략
- **master**: 프로덕션 코드
- **develop**: 개발 통합 브랜치
- **feature/***: 기능 개발 브랜치

### 커밋 메시지
```
feat: 새로운 기능 추가
fix: 버그 수정
refactor: 코드 리팩토링
docs: 문서 수정
test: 테스트 추가/수정
chore: 빌드, 설정 변경
```

## AI 에이전트 작업 지침

### 작업 우선순위
1. **보안 이슈** → 즉시 수정
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
- **Selenium 사용** (Playwright로 대체)

### 피해야 할 사항
- 전역 변수 남용
- 중복 코드 (DRY 원칙)
- 테스트 없는 코드
- 문서화되지 않은 API
- 타입 힌트 생략

## 플랫폼별 특이사항

### 배민
- 2FA 인증 처리 필요
- 답글 등록시 최소 30초 간격
- 금지어 팝업 처리 필수
- platform_code는 URL에서 추출

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
- 세션 저장으로 재로그인 최소화

### 데이터베이스 최적화
- 인덱스 활용 (store_code, review_date)
- 배치 삽입/업데이트
- 커넥션 풀 관리
- 쿼리 결과 캐싱

### API 최적화
- 응답 압축 (gzip)
- 페이지네이션 구현
- 캐싱 헤더 설정
- 비동기 처리 활용
