"""
사용자 관련 비즈니스 로직 처리 (Supabase 버전)
"""
from datetime import datetime
from typing import Optional, List, Dict
import secrets
import logging
from supabase import Client
import asyncio
from functools import wraps

from ..schemas.auth import UserCreate, User, UserInDB
from ..auth.utils import get_password_hash

logger = logging.getLogger(__name__)


def async_wrapper(func):
    """동기 함수를 비동기로 래핑"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)
    return wrapper


class UserService:
    def __init__(self, supabase_client: Client):
        self.client = supabase_client
    
    async def generate_user_code(self) -> str:
        """고유한 사용자 코드 생성"""
        while True:
            # USR + 랜덤 6자리 숫자
            code = f"USR{secrets.randbelow(1000000):06d}"
            
            # 중복 확인
            @async_wrapper
            def check_exists():
                response = self.client.table('users').select('user_code').eq('user_code', code).execute()
                return response
            
            response = await check_exists()
            if not response.data:
                return code
    
    async def create_user(self, user_data: UserCreate) -> Dict:
        """새로운 사용자 생성"""
        try:
            user_code = await self.generate_user_code()
            password_hash = get_password_hash(user_data.password)
            
            # 사용자 데이터 준비
            user_dict = {
                "user_code": user_code,
                "email": user_data.email,
                "password_hash": password_hash,
                "name": user_data.name,
                "phone": user_data.phone,
                "role": user_data.role or 'owner',
                "company_name": user_data.company_name,
                "email_verified": False,
                "phone_verified": False,
                "is_active": True,
                "marketing_consent": user_data.marketing_consent,
                "signup_date": datetime.now().isoformat(),
                "login_count": 0,
                "timezone": "Asia/Seoul",
                "language": "ko",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            @async_wrapper
            def insert_user():
                response = self.client.table('users').insert(user_dict).execute()
                return response
            
            response = await insert_user()
            
            if response.data:
                return response.data[0]
            else:
                raise Exception("사용자 생성 실패")
                
        except Exception as e:
            logger.error(f"사용자 생성 실패: {e}")
            if "duplicate" in str(e).lower():
                raise ValueError("이미 존재하는 이메일입니다.")
            raise
    
    async def get_user_by_email(self, email: str) -> Optional[Dict]:
        """이메일로 사용자 조회"""
        @async_wrapper
        def fetch_user():
            response = self.client.table('users').select('*').eq('email', email).execute()
            return response
        
        response = await fetch_user()
        return response.data[0] if response.data else None
    
    async def get_user_by_code(self, user_code: str) -> Optional[Dict]:
        """사용자 코드로 사용자 조회"""
        @async_wrapper
        def fetch_user():
            response = self.client.table('users').select('*').eq('user_code', user_code).execute()
            return response
        
        response = await fetch_user()
        return response.data[0] if response.data else None
    
    async def update_last_login(self, user_code: str) -> None:
        """마지막 로그인 시간 업데이트"""
        @async_wrapper
        def update_login():
            # 먼저 현재 login_count 조회
            user_response = self.client.table('users').select('login_count').eq('user_code', user_code).execute()
            current_count = user_response.data[0]['login_count'] if user_response.data else 0
            
            # 업데이트
            response = self.client.table('users').update({
                'last_login': datetime.now().isoformat(),
                'login_count': current_count + 1
            }).eq('user_code', user_code).execute()
            return response
        
        await update_login()
    
    async def update_user(self, user_code: str, update_data: dict) -> Optional[Dict]:
        """사용자 정보 업데이트"""
        # 업데이트 가능한 필드만 필터링
        allowed_fields = [
            'name', 'phone', 'company_name', 'profile_image_url',
            'timezone', 'language', 'marketing_consent'
        ]
        
        filtered_data = {}
        for field, value in update_data.items():
            if field in allowed_fields and value is not None:
                filtered_data[field] = value
        
        if not filtered_data:
            return await self.get_user_by_code(user_code)
        
        filtered_data['updated_at'] = datetime.now().isoformat()
        
        @async_wrapper
        def update():
            response = self.client.table('users').update(filtered_data).eq('user_code', user_code).execute()
            return response
        
        response = await update()
        return response.data[0] if response.data else None
    
    async def verify_email(self, user_code: str) -> bool:
        """이메일 인증 처리"""
        @async_wrapper
        def verify():
            response = self.client.table('users').update({
                'email_verified': True
            }).eq('user_code', user_code).execute()
            return response
        
        response = await verify()
        return bool(response.data)
    
    async def deactivate_user(self, user_code: str) -> bool:
        """사용자 비활성화"""
        @async_wrapper
        def deactivate():
            response = self.client.table('users').update({
                'is_active': False
            }).eq('user_code', user_code).execute()
            return response
        
        response = await deactivate()
        return bool(response.data)
    
    async def get_user_stores(self, user_code: str) -> List[Dict]:
        """사용자가 관리하는 매장 목록 조회"""
        @async_wrapper
        def fetch_stores():
            response = self.client.table('platform_reply_rules').select('*').eq('owner_user_code', user_code).order('created_at', desc=True).execute()
            return response
        
        response = await fetch_stores()
        return response.data if response.data else []
    
    async def get_user_subscription(self, user_code: str) -> Optional[Dict]:
        """사용자의 현재 구독 정보 조회"""
        @async_wrapper
        def fetch_subscription():
            # subscriptions 테이블과 pricing_plans 테이블 조인
            response = self.client.table('subscriptions').select(
                '*, pricing_plans(*)'
            ).eq('user_code', user_code).in_('status', ['active', 'trial']).order('end_date', desc=True).limit(1).execute()
            return response
        
        response = await fetch_subscription()
        
        if response.data:
            # 플랫한 구조로 변환
            subscription = response.data[0]
            if 'pricing_plans' in subscription:
                plan = subscription['pricing_plans']
                subscription.update({
                    'plan_name': plan.get('plan_name'),
                    'max_stores': plan.get('max_stores'),
                    'max_reviews_per_month': plan.get('max_reviews_per_month'),
                    'features': plan.get('features')
                })
                del subscription['pricing_plans']
            return subscription
        return None
    
    async def check_email_exists(self, email: str) -> bool:
        """이메일 중복 확인"""
        @async_wrapper
        def check():
            response = self.client.table('users').select('email').eq('email', email).execute()
            return response
        
        response = await check()
        return bool(response.data)
