"""
사용자 권한 추가 스크립트
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.services.supabase_service import SupabaseService
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def add_user_permission(user_code: str, store_code: str):
    """사용자에게 매장 권한 추가"""
    supabase = SupabaseService()
    
    logger.info(f"\n=== 사용자 권한 추가 ===")
    logger.info(f"사용자: {user_code}")
    logger.info(f"매장: {store_code}")
    
    # 권한 데이터
    permission_data = {
        'user_code': user_code,
        'store_code': store_code,
        'permission_level': 'admin',
        'can_view': True,
        'can_edit_settings': True,
        'can_reply': True,
        'can_manage_rules': True,
        'can_manage_alerts': True,
        'can_view_analytics': True,
        'can_export_data': True,
        'can_manage_users': True,
        'granted_by': 'ADMIN001',
        'granted_at': datetime.now().isoformat(),
        'is_active': True
    }
    
    try:
        # 기존 권한 확인
        response = await supabase._execute_query(
            supabase.client.table('user_store_permissions')
            .select('*')
            .eq('user_code', user_code)
            .eq('store_code', store_code)
        )
        
        if response.data:
            # 기존 권한 업데이트
            logger.info("기존 권한이 있어 업데이트합니다...")
            response = await supabase._execute_query(
                supabase.client.table('user_store_permissions')
                .update(permission_data)
                .eq('user_code', user_code)
                .eq('store_code', store_code)
            )
        else:
            # 새 권한 추가
            logger.info("새로운 권한을 추가합니다...")
            response = await supabase._execute_query(
                supabase.client.table('user_store_permissions')
                .insert(permission_data)
            )
        
        if response.data:
            logger.info("✓ 권한 추가/업데이트 성공!")
            logger.info(f"  - 사용자 {user_code}는 이제 매장 {store_code}에 대한 모든 권한을 가집니다.")
        else:
            logger.error("✗ 권한 추가/업데이트 실패")
            
    except Exception as e:
        logger.error(f"권한 추가 오류: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("사용법: python add_user_permission.py <user_code> <store_code>")
        print("예시: python add_user_permission.py TST001 STR_20250607112756_854269")
        sys.exit(1)
    
    user_code = sys.argv[1]
    store_code = sys.argv[2]
    
    asyncio.run(add_user_permission(user_code, store_code))
