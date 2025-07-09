#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
네이버 매장을 자동화 시스템에 등록하는 스크립트
"""
import sys
import os
from pathlib import Path

# 프로젝트 루트 경로를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.supabase_client import get_supabase_client
from api.services.encryption import encrypt_password
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_naver_store_to_automation():
    """네이버 매장을 24시간 자동화 시스템에 등록"""
    
    # 네이버 매장 정보 입력
    print("=== 네이버 매장 자동화 등록 ===")
    
    store_name = input("매장명을 입력하세요: ").strip()
    if not store_name:
        print("매장명은 필수입니다.")
        return
    
    platform_code = input("네이버 플랫폼 코드(매장 ID)를 입력하세요: ").strip()
    if not platform_code:
        print("플랫폼 코드는 필수입니다.")
        return
    
    platform_id = input("네이버 로그인 ID를 입력하세요: ").strip()
    if not platform_id:
        print("로그인 ID는 필수입니다.")
        return
    
    platform_pw = input("네이버 로그인 비밀번호를 입력하세요: ").strip()
    if not platform_pw:
        print("로그인 비밀번호는 필수입니다.")
        return
    
    owner_user_code = input("소유자 사용자 코드를 입력하세요 (기본값: SYSTEM): ").strip()
    if not owner_user_code:
        owner_user_code = "SYSTEM"
    
    try:
        # Supabase 클라이언트 가져오기
        supabase = get_supabase_client()
        
        # 비밀번호 암호화
        try:
            encrypted_pw = encrypt_password(platform_pw)
            logger.info("비밀번호 암호화 완료")
        except Exception as e:
            logger.warning(f"암호화 실패, 평문으로 저장: {str(e)}")
            encrypted_pw = platform_pw
        
        # 고유 store_code 생성
        store_code = f"NAVER_{platform_code}_{datetime.now().strftime('%Y%m%d')}"
        
        # platform_reply_rules 테이블에 데이터 삽입
        store_data = {
            'store_code': store_code,
            'store_name': store_name,
            'platform': 'naver',
            'platform_code': platform_code,
            'platform_id': platform_id,
            'platform_pw': encrypted_pw,
            'owner_user_code': owner_user_code,
            'is_active': True,
            'auto_reply_enabled': True,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            # 네이버 기본 답글 설정
            'greeting_start': '안녕하세요',
            'greeting_end': '감사합니다',
            'role': '사장',
            'tone': 'friendly',
            'max_reply_length': 200,
            'include_store_name': True,
            'auto_thank_positive': True,
            'auto_apologize_negative': True
        }
        
        # 중복 확인
        existing = supabase.table('platform_reply_rules')\
            .select('store_code')\
            .eq('platform_code', platform_code)\
            .eq('platform', 'naver')\
            .execute()
        
        if existing.data:
            print(f"이미 등록된 네이버 매장입니다: {platform_code}")
            return
        
        # 데이터 삽입
        result = supabase.table('platform_reply_rules').insert(store_data).execute()
        
        if result.data:
            print("✅ 네이버 매장이 성공적으로 등록되었습니다!")
            print(f"   매장명: {store_name}")
            print(f"   매장 코드: {store_code}")
            print(f"   플랫폼 코드: {platform_code}")
            print(f"   자동 답글: 활성화")
            print(f"   24시간 자동화: 활성화")
            print("")
            print("🔄 다음 자동화 주기부터 네이버 리뷰 수집이 시작됩니다.")
            print("   - 리뷰 수집: 3분마다")
            print("   - AI 답글 생성: 1분마다") 
            print("   - 답글 등록: 2분마다")
        else:
            print("❌ 매장 등록에 실패했습니다.")
            
    except Exception as e:
        logger.error(f"매장 등록 중 오류: {str(e)}")
        print(f"❌ 오류 발생: {str(e)}")

if __name__ == "__main__":
    add_naver_store_to_automation()