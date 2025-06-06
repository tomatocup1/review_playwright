"""
사용자 관련 비즈니스 로직 처리
"""
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from typing import Optional, List
import secrets
import string

from ..models.user import UserCreate, UserInDB
from ..auth.utils import get_password_hash
from config.database import execute_query

class UserService:
    def __init__(self, db: Session):
        self.db = db
    
    def generate_user_code(self) -> str:
        """고유한 사용자 코드 생성"""
        while True:
            # USR + 랜덤 6자리 숫자
            code = f"USR{secrets.randbelow(1000000):06d}"
            # 중복 확인
            result = execute_query(
                "SELECT COUNT(*) as count FROM users WHERE user_code = %s",
                (code,)
            )
            if result and result[0]['count'] == 0:
                return code
    
    def create_user(self, user_data: UserCreate) -> UserInDB:
        """새로운 사용자 생성"""
        try:
            user_code = self.generate_user_code()
            password_hash = get_password_hash(user_data.password)
            
            query = """
                INSERT INTO users (
                    user_code, email, password_hash, name, phone, 
                    role, company_name, email_verified, is_active
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            params = (
                user_code,
                user_data.email,
                password_hash,
                user_data.name,
                user_data.phone,
                user_data.role or 'owner',
                user_data.company_name,
                False,  # email_verified
                True    # is_active
            )
            
            execute_query(query, params)
            
            # 생성된 사용자 조회
            return self.get_user_by_email(user_data.email)
            
        except IntegrityError as e:
            self.db.rollback()
            if "Duplicate entry" in str(e):
                raise ValueError("이미 존재하는 이메일입니다.")
            raise
    
    def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        """이메일로 사용자 조회"""
        query = """
            SELECT id, user_code, email, password_hash, name, phone, role,
                   company_name, email_verified, phone_verified, signup_date,
                   last_login, login_count, is_active, profile_image_url,
                   timezone, language, marketing_consent, created_at, updated_at
            FROM users
            WHERE email = %s
        """
        
        result = execute_query(query, (email,))
        
        if result:
            user_data = result[0]
            return UserInDB(**user_data)
        return None
    
    def get_user_by_code(self, user_code: str) -> Optional[UserInDB]:
        """사용자 코드로 사용자 조회"""
        query = """
            SELECT id, user_code, email, password_hash, name, phone, role,
                   company_name, email_verified, phone_verified, signup_date,
                   last_login, login_count, is_active, profile_image_url,
                   timezone, language, marketing_consent, created_at, updated_at
            FROM users
            WHERE user_code = %s
        """
        
        result = execute_query(query, (user_code,))
        
        if result:
            user_data = result[0]
            return UserInDB(**user_data)
        return None
    
    def update_last_login(self, user_code: str) -> None:
        """마지막 로그인 시간 업데이트"""
        query = """
            UPDATE users 
            SET last_login = NOW(), login_count = login_count + 1
            WHERE user_code = %s
        """
        execute_query(query, (user_code,))
    
    def update_user(self, user_code: str, update_data: dict) -> Optional[UserInDB]:
        """사용자 정보 업데이트"""
        # 업데이트 가능한 필드만 필터링
        allowed_fields = [
            'name', 'phone', 'company_name', 'profile_image_url',
            'timezone', 'language', 'marketing_consent'
        ]
        
        update_fields = []
        params = []
        
        for field, value in update_data.items():
            if field in allowed_fields and value is not None:
                update_fields.append(f"{field} = %s")
                params.append(value)
        
        if not update_fields:
            return self.get_user_by_code(user_code)
        
        params.append(user_code)
        query = f"""
            UPDATE users 
            SET {', '.join(update_fields)}, updated_at = NOW()
            WHERE user_code = %s
        """
        
        execute_query(query, params)
        return self.get_user_by_code(user_code)
    
    def verify_email(self, user_code: str) -> bool:
        """이메일 인증 처리"""
        query = "UPDATE users SET email_verified = TRUE WHERE user_code = %s"
        execute_query(query, (user_code,))
        return True
    
    def deactivate_user(self, user_code: str) -> bool:
        """사용자 비활성화"""
        query = "UPDATE users SET is_active = FALSE WHERE user_code = %s"
        execute_query(query, (user_code,))
        return True
    
    def get_user_stores(self, user_code: str) -> List[dict]:
        """사용자가 관리하는 매장 목록 조회"""
        query = """
            SELECT pr.store_code, pr.store_name, pr.platform, pr.platform_code,
                   pr.is_active, pr.created_at, pr.last_crawled, pr.last_reply,
                   pr.total_reviews_processed
            FROM platform_reply_rules pr
            WHERE pr.owner_user_code = %s
            ORDER BY pr.created_at DESC
        """
        
        result = execute_query(query, (user_code,))
        return result if result else []
    
    def get_user_subscription(self, user_code: str) -> Optional[dict]:
        """사용자의 현재 구독 정보 조회"""
        query = """
            SELECT s.subscription_code, s.plan_code, s.status, s.billing_cycle,
                   s.start_date, s.end_date, s.auto_renewal, s.payment_amount,
                   p.plan_name, p.max_stores, p.max_reviews_per_month, p.features
            FROM subscriptions s
            JOIN pricing_plans p ON s.plan_code = p.plan_code
            WHERE s.user_code = %s AND s.status IN ('active', 'trial')
            ORDER BY s.end_date DESC
            LIMIT 1
        """
        
        result = execute_query(query, (user_code,))
        return result[0] if result else None
