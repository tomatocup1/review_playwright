#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from config.supabase_client import get_supabase_client

async def check_real_stores():
    """Supabase에서 실제 매장 정보 확인"""
    try:
        supabase = get_supabase_client()
        
        # 모든 매장 정보 조회
        response = supabase.table('platform_reply_rules').select('*').execute()
        
        if response.data:
            print("\n=== 등록된 매장 목록 ===")
            for store in response.data:
                print(f"\n매장명: {store.get('store_name', 'N/A')}")
                print(f"플랫폼: {store.get('platform', 'N/A')}")
                print(f"플랫폼 코드: {store.get('platform_code', 'N/A')}")
                print(f"매장 코드: {store.get('store_code', 'N/A')}")
                print(f"활성화: {'O' if store.get('is_active') else 'X'}")
                print(f"자동답글: {'O' if store.get('auto_reply_enabled') else 'X'}")
                print("-" * 50)
            
            # 실제 배민 매장 찾기
            real_baemin_stores = [
                store for store in response.data 
                if store.get('platform') == 'baemin' and 
                   store.get('platform_code') not in ['test_store_001', 'test_store_002']
            ]
            
            if real_baemin_stores:
                print("\n=== 실제 배민 매장 ===")
                for store in real_baemin_stores:
                    print(f"\n매장명: {store['store_name']}")
                    print(f"플랫폼 코드: {store['platform_code']}")
                    print(f"매장 코드: {store['store_code']}")
                    print(f"플랫폼 ID: {store.get('platform_id', 'N/A')}")
                    
                return real_baemin_stores[0]  # 첫 번째 실제 매장 반환
            else:
                print("\n실제 배민 매장이 없습니다.")
                
        else:
            print("등록된 매장이 없습니다.")
            
    except Exception as e:
        print(f"\n오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_real_stores())
