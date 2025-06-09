"""
사용자 권한 확인 및 추가 스크립트
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

async def check_and_add_permissions():
    """사용자 권한 확인 및 추가"""
    supabase = SupabaseService()
    
    store_code = "STR_20250607112756_854269"
    
    logger.info(f"\n=== 사용자 권한 확인 ===")
    logger.info(f"매장 코드: {store_code}")
    
    # 1. 매장 소유자 확인
    logger.info("\n1. 매장 소유자 확인")
    try:
        response = await supabase._execute_query(
            supabase.client.table('platform_reply_rules')
            .select('owner_user_code, store_name')
            .eq('store_code', store_code)
        )
        
        if response.data:
            owner_code = response.data[0]['owner_user_code']
            store_name = response.data[0]['store_name']
            logger.info(f"✓ 매장 소유자: {owner_code}")
            logger.info(f"✓ 매장명: {store_name}")
        else:
            logger.error(f"✗ 매장을 찾을 수 없음: {store_code}")
            return
    except Exception as e:
        logger.error(f"매장 조회 오류: {e}")
        return
    
    # 2. 모든 사용자 조회
    logger.info("\n2. 등록된 사용자 목록")
    try:
        response = await supabase._execute_query(
            supabase.client.table('users')
            .select('user_code, email, name, role')
            .order('created_at', desc=False)
        )
        
        if response.data:
            logger.info("등록된 사용자:")
            for user in response.data:
                logger.info(f"  - {user['user_code']}: {user['name']} ({user['email']}) - {user['role']}")
        else:
            logger.info("등록된 사용자 없음")
    except Exception as e:
        logger.error(f"사용자 조회 오류: {e}")
    
    # 3. 현재 권한 확인
    logger.info(f"\n3. 매장 {store_code}에 대한 권한 목록")
    try:
        response = await supabase._execute_query(
            supabase.client.table('user_store_permissions')
            .select('*')
            .eq('store_code', store_code)
        )
        
        if response.data:
            logger.info("현재 권한:")
            for perm in response.data:
                logger.info(f"  - 사용자: {perm['user_code']}")
                logger.info(f"    권한 레벨: {perm['permission_level']}")
                logger.info(f"    답글 작성 권한: {perm.get('can_reply', False)}")
                logger.info(f"    활성화: {perm.get('is_active', False)}")
        else:
            logger.info("설정된 권한 없음")
    except Exception as e:
        logger.error(f"권한 조회 오류: {e}")
    
    # 4. TST001 사용자에게 권한 추가 제안
    logger.info("\n4. 권한 추가 제안")
    logger.info("TST001 사용자에게 권한을 추가하려면 아래 스크립트를 실행하세요:")
    logger.info("python scripts/add_user_permission.py TST001 STR_20250607112756_854269")

if __name__ == "__main__":
    asyncio.run(check_and_add_permissions())
