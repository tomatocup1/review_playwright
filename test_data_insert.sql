-- =====================================
-- 테스트 데이터 입력 스크립트
-- 외래 키 제약 조건을 고려한 순서대로 입력
-- =====================================

-- 1. 요금제 데이터 입력 (다른 테이블에서 참조하므로 가장 먼저)
INSERT INTO pricing_plans (plan_code, plan_name, description, monthly_price, yearly_price, yearly_discount_rate, max_stores, max_reviews_per_month, max_users, features, trial_days, is_popular) 
VALUES 
('FREE_TRIAL', '무료 체험', '7일 무료 체험으로 서비스 경험해보세요', 0.00, 0.00, 0, 2, 50, 1, '{"ai_reply": true, "analytics": false, "priority_support": false, "api_access": false}', 7, false),
('BASIC', '베이직', '개인 사장님에게 최적화된 기본 플랜', 29000.00, 290000.00, 17, 5, 500, 1, '{"ai_reply": true, "analytics": true, "priority_support": false, "api_access": false, "custom_rules": false}', 0, false),
('PRO', '프로', '다매장 운영자를 위한 프리미엄 플랜', 59000.00, 590000.00, 17, 20, 2000, 3, '{"ai_reply": true, "analytics": true, "priority_support": true, "api_access": true, "custom_rules": true, "advanced_analytics": true}', 0, true),
('ENTERPRISE', '엔터프라이즈', '프랜차이즈 및 대기업을 위한 맞춤 솔루션', 150000.00, 1500000.00, 17, 100, 10000, 10, '{"ai_reply": true, "analytics": true, "priority_support": true, "api_access": true, "custom_rules": true, "advanced_analytics": true, "white_label": true, "dedicated_support": true}', 0, false)
ON CONFLICT (plan_code) DO NOTHING;

-- 2. 테스트 사용자 생성 (owner_user_code에 필요)
INSERT INTO users (user_code, email, password_hash, name, phone, role, email_verified, is_active) 
VALUES 
('TEST_USER_001', 'test@example.com', '$2b$12$LQv3c1yqBwkvHiOWlK.DE.JK1k2Gv.K1uK1KvK1K1K1K1K1K1K1K1', '테스트사장님', '010-1234-5678', 'owner', true, true)
ON CONFLICT (user_code) DO NOTHING;

-- 3. 테스트 구독 생성
INSERT INTO subscriptions (subscription_code, user_code, plan_code, status, billing_cycle, start_date, end_date, payment_amount, original_amount, auto_renewal) 
VALUES 
('SUB_TEST_001', 'TEST_USER_001', 'BASIC', 'active', 'monthly', CURRENT_DATE, CURRENT_DATE + INTERVAL '30 days', 29000.00, 29000.00, true)
ON CONFLICT (subscription_code) DO NOTHING;

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
)
ON CONFLICT (store_code) DO NOTHING;

-- 5. 월별 사용량 추적 초기화
INSERT INTO usage_tracking (user_code, tracking_month, stores_count, reviews_processed) 
VALUES 
('TEST_USER_001', DATE_TRUNC('month', CURRENT_DATE), 1, 0)
ON CONFLICT (user_code, tracking_month) DO NOTHING;

-- 6. 추가 테스트 사용자 데이터 (원본 SQL에서 참조)
INSERT INTO users (user_code, email, password_hash, name, role, email_verified, marketing_consent) VALUES 
('TST001', 'test.owner@example.com', '$2b$12$test_hash_here', '테스트사장님', 'owner', true, false),
('TST002', 'test.franchise@example.com', '$2b$12$test_hash_here', '테스트프랜차이즈', 'franchise', true, false),
('TST003', 'test.sales@example.com', '$2b$12$test_hash_here', '테스트영업자', 'sales', true, false)
ON CONFLICT (user_code) DO NOTHING;

-- 7. 추가 테스트 구독
INSERT INTO subscriptions (subscription_code, user_code, plan_code, status, billing_cycle, start_date, end_date, payment_amount) VALUES 
('SUB_TST001', 'TST001', 'BASIC', 'active', 'monthly', CURRENT_DATE, CURRENT_DATE + INTERVAL '30 days', 29000.00),
('SUB_TST002', 'TST002', 'PRO', 'active', 'monthly', CURRENT_DATE, CURRENT_DATE + INTERVAL '30 days', 59000.00)
ON CONFLICT (subscription_code) DO NOTHING;

-- 8. 추가 테스트 매장
INSERT INTO platform_reply_rules (store_code, store_name, platform, platform_code, platform_id, platform_pw, owner_user_code, greeting_start, greeting_end) VALUES 
('TST_STORE001', '테스트맛집', 'baemin', 'shop_test_001', 'test_baemin_id', 'test_password', 'TST001', '안녕하세요!', '감사합니다'),
('TST_STORE002', '테스트치킨집', 'baemin', 'shop_test_002', 'test_baemin_id2', 'test_password2', 'TST001', '반갑습니다', '좋은 하루 되세요')
ON CONFLICT (store_code) DO NOTHING;

-- 9. 관리자 계정이 없는 경우 추가
INSERT INTO users (user_code, email, password_hash, name, role, email_verified, is_active) VALUES 
('ADMIN001', 'admin@reviewbot.co.kr', '$2b$12$LQv3c1yqBwkvHiOWlK.DE.JK1k2Gv.K1uK1KvK1K1K1K1K1K1K1K1', '시스템관리자', 'admin', true, true)
ON CONFLICT (user_code) DO NOTHING;

-- 10. 테스트 권한 부여
INSERT INTO user_store_permissions (user_code, store_code, permission_level, can_view, can_edit_settings, can_reply, granted_by) VALUES 
('TST002', 'TST_STORE001', 'write', true, true, true, 'ADMIN001'),  -- 프랜차이즈가 매장 관리
('TST003', 'TST_STORE001', 'read', true, false, false, 'TST002')   -- 영업자는 조회만
ON CONFLICT (user_code, store_code) DO NOTHING;

-- 확인 쿼리
SELECT 'Pricing Plans:' as table_name, COUNT(*) as count FROM pricing_plans
UNION ALL
SELECT 'Users:', COUNT(*) FROM users
UNION ALL
SELECT 'Subscriptions:', COUNT(*) FROM subscriptions
UNION ALL
SELECT 'Stores:', COUNT(*) FROM platform_reply_rules;
