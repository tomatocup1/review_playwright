-- =====================================
-- 테스트 데이터 입력 스크립트
-- 외래 키 제약 조건을 고려한 순서대로 입력
-- =====================================

-- 1. 테스트 사용자 생성 (owner_user_code에 필요)
INSERT INTO users (user_code, email, password_hash, name, phone, role, email_verified, is_active) 
VALUES 
('TEST_USER_001', 'test@example.com', '$2b$12$LQv3c1yqBwkvHiOWlK.DE.JK1k2Gv.K1uK1KvK1K1K1K1K1K1K1K1', '테스트사장님', '010-1234-5678', 'owner', true, true);

-- 2. 요금제가 이미 있는지 확인 (초기 데이터에 이미 포함되어 있을 수 있음)
-- 없다면 아래 주석을 해제하여 실행
/*
INSERT INTO pricing_plans (plan_code, plan_name, description, monthly_price, yearly_price, yearly_discount_rate, max_stores, max_reviews_per_month, max_users, features, trial_days, is_popular) 
VALUES 
('BASIC', '베이직', '개인 사장님에게 최적화된 기본 플랜', 29000.00, 290000.00, 17, 5, 500, 1, '{"ai_reply": true, "analytics": true, "priority_support": false, "api_access": false}', 0, false);
*/

-- 3. 테스트 구독 생성
INSERT INTO subscriptions (subscription_code, user_code, plan_code, status, billing_cycle, start_date, end_date, payment_amount, original_amount, auto_renewal) 
VALUES 
('SUB_TEST_001', 'TEST_USER_001', 'BASIC', 'active', 'monthly', CURRENT_DATE, CURRENT_DATE + INTERVAL '30 days', 29000.00, 29000.00, true);

-- 4. 테스트 매장 정보 입력
INSERT INTO platform_reply_rules (
    store_code, 
    store_name, 
    platform, 
    platform_code, 
    platform_id, 
    platform_pw, 
    owner_user_code,
    greeting_start, 
    greeting_end,
    role,
    tone,
    max_length,
    auto_reply_enabled,
    rating_5_reply,
    rating_4_reply,
    rating_3_reply,
    rating_2_reply,
    rating_1_reply
) VALUES (
    'STORE_TEST_001',           -- store_code
    '더블유버거 테스트점',        -- store_name
    'baemin',                   -- platform
    '14662128',                 -- platform_code (실제 매장 코드)
    'kosain2',                  -- platform_id (실제 로그인 ID)
    'jjps0917@@@',              -- platform_pw (실제 비밀번호)
    'TEST_USER_001',            -- owner_user_code
    '안녕하세요',                -- greeting_start
    '감사합니다',                -- greeting_end
    '친근한 사장님',             -- role
    'friendly',                 -- tone
    300,                        -- max_length
    true,                       -- auto_reply_enabled
    true,                       -- rating_5_reply
    true,                       -- rating_4_reply
    true,                       -- rating_3_reply
    true,                       -- rating_2_reply
    true                        -- rating_1_reply
);

-- 5. 월별 사용량 추적 초기화
INSERT INTO usage_tracking (user_code, tracking_month, stores_count, reviews_processed) 
VALUES 
('TEST_USER_001', DATE_TRUNC('month', CURRENT_DATE), 1, 0);

-- 확인 쿼리
SELECT 'Users:' as table_name, COUNT(*) as count FROM users WHERE user_code = 'TEST_USER_001'
UNION ALL
SELECT 'Subscriptions:', COUNT(*) FROM subscriptions WHERE user_code = 'TEST_USER_001'
UNION ALL
SELECT 'Stores:', COUNT(*) FROM platform_reply_rules WHERE owner_user_code = 'TEST_USER_001';
