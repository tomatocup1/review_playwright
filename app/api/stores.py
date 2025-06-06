"""
매장 관련 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List, Optional
from datetime import datetime
import logging
import secrets
import asyncio
import json

from ..dependencies import get_current_user, get_db
from ..schemas.store import (
    StoreRegisterRequest, StoreRegisterResponse, StoreInfo,
    StoreListResponse, StoreUpdateRequest, StoreCrawlRequest,
    PlatformStoresResponse, PlatformStore, PlatformEnum
)
from ..schemas.auth import User
from ..services.database import Database
from ..services.encryption import encrypt_password, decrypt_password
from ..crawlers import get_crawler

router = APIRouter(prefix="/stores", tags=["stores"])
logger = logging.getLogger(__name__)

def generate_store_code():
    """매장 코드 생성"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_str = secrets.token_hex(3).upper()
    return f"STR_{timestamp}_{random_str}"

@router.get("/platforms", response_model=List[str])
async def get_supported_platforms():
    """지원하는 플랫폼 목록 조회"""
    return [platform.value for platform in PlatformEnum]

@router.post("/crawl", response_model=PlatformStoresResponse)
async def crawl_platform_stores(
    request: StoreCrawlRequest,
    current_user: User = Depends(get_current_user)
):
    """플랫폼에서 매장 정보 크롤링"""
    try:
        # 크롤러 인스턴스 생성
        async with get_crawler(request.platform.value, headless=True) as crawler:
            # 로그인
            login_success = await crawler.login(request.platform_id, request.platform_pw)
            if not login_success:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"{request.platform.value} 로그인에 실패했습니다. ID/PW를 확인해주세요."
                )
            
            # 매장 목록 가져오기
            stores_data = await crawler.get_store_list()
            
            # 응답 형식으로 변환
            stores = []
            for store_data in stores_data:
                store = PlatformStore(
                    platform=request.platform,
                    platform_code=store_data.get('platform_code', ''),
                    store_name=store_data.get('store_name', ''),
                    store_type=store_data.get('store_type'),
                    category=store_data.get('category'),
                    brand_name=store_data.get('brand_name'),
                    status=store_data.get('status')
                )
                stores.append(store)
            
            return PlatformStoresResponse(
                platform=request.platform,
                stores=stores,
                count=len(stores)
            )
            
    except Exception as e:
        logger.error(f"매장 크롤링 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"매장 정보 크롤링 중 오류가 발생했습니다: {str(e)}"
        )

@router.post("/register", response_model=StoreRegisterResponse)
async def register_store(
    request: StoreRegisterRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """매장 등록"""
    try:
        # 1. 플랫폼 로그인 정보로 매장 정보 자동 조회 (platform_code가 없는 경우)
        if not request.platform_code or not request.store_name:
            async with get_crawler(request.platform.value, headless=True) as crawler:
                # 로그인
                login_success = await crawler.login(request.platform_id, request.platform_pw)
                if not login_success:
                    return StoreRegisterResponse(
                        success=False,
                        message=f"{request.platform.value} 로그인에 실패했습니다. ID/PW를 확인해주세요."
                    )
                
                # 매장 목록 가져오기
                stores = await crawler.get_store_list()
                
                if not stores:
                    return StoreRegisterResponse(
                        success=False,
                        message="등록 가능한 매장을 찾을 수 없습니다."
                    )
                
                # platform_code가 지정된 경우 해당 매장 찾기
                if request.platform_code:
                    store_info = next((s for s in stores if s['platform_code'] == request.platform_code), None)
                    if not store_info:
                        return StoreRegisterResponse(
                            success=False,
                            message=f"플랫폼 코드 {request.platform_code}에 해당하는 매장을 찾을 수 없습니다."
                        )
                else:
                    # 첫 번째 매장 선택
                    store_info = stores[0]
                
                # 요청 데이터 업데이트
                request.platform_code = store_info['platform_code']
                request.store_name = store_info['store_name']
        
        # 2. 중복 확인
        existing_store = await db.fetch_one(
            """
            SELECT store_code FROM platform_reply_rules 
            WHERE platform = ? AND platform_code = ? AND is_active = true
            """,
            (request.platform.value, request.platform_code)
        )
        
        if existing_store:
            return StoreRegisterResponse(
                success=False,
                message=f"이미 등록된 매장입니다. (매장코드: {existing_store['store_code']})"
            )
        
        # 3. 매장 코드 생성 및 비밀번호 암호화
        store_code = generate_store_code()
        encrypted_pw = encrypt_password(request.platform_pw)
        
        # 4. 매장 등록
        await db.execute(
            """
            INSERT INTO platform_reply_rules (
                store_code, store_name, platform, platform_code,
                platform_id, platform_pw, owner_user_code,
                greeting_start, greeting_end, role, tone,
                prohibited_words, max_length,
                rating_5_reply, rating_4_reply, rating_3_reply,
                rating_2_reply, rating_1_reply,
                auto_reply_enabled, auto_reply_hours, reply_delay_minutes,
                weekend_enabled, holiday_enabled,
                store_type, is_active,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                'delivery_only', true,
                ?, ?
            )
            """,
            (
                store_code, request.store_name, request.platform.value, request.platform_code,
                request.platform_id, encrypted_pw, current_user.user_code,
                request.greeting_start, request.greeting_end, request.role, request.tone,
                json.dumps(request.prohibited_words), request.max_length,
                request.rating_5_reply, request.rating_4_reply, request.rating_3_reply,
                request.rating_2_reply, request.rating_1_reply,
                request.auto_reply_enabled, request.auto_reply_hours, request.reply_delay_minutes,
                request.weekend_enabled, request.holiday_enabled,
                datetime.now(), datetime.now()
            )
        )
        
        # 5. 등록된 매장 정보 조회
        store_info = await get_store_info(store_code, db)
        
        logger.info(f"매장 등록 성공: {store_code} - {request.store_name}")
        
        return StoreRegisterResponse(
            success=True,
            message="매장이 성공적으로 등록되었습니다.",
            store_code=store_code,
            store_info=store_info
        )
        
    except Exception as e:
        logger.error(f"매장 등록 중 오류: {str(e)}")
        return StoreRegisterResponse(
            success=False,
            message=f"매장 등록 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("", response_model=StoreListResponse)
async def get_stores(
    page: int = 1,
    page_size: int = 20,
    platform: Optional[PlatformEnum] = None,
    is_active: Optional[bool] = True,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """내 매장 목록 조회"""
    try:
        # 조건 설정
        conditions = ["owner_user_code = ?"]
        params = [current_user.user_code]
        
        if platform:
            conditions.append("platform = ?")
            params.append(platform.value)
        
        if is_active is not None:
            conditions.append("is_active = ?")
            params.append(is_active)
        
        where_clause = " AND ".join(conditions)
        
        # 전체 개수 조회
        total_result = await db.fetch_one(
            f"SELECT COUNT(*) as total FROM platform_reply_rules WHERE {where_clause}",
            params
        )
        total = total_result['total']
        
        # 페이징 처리
        offset = (page - 1) * page_size
        params.extend([page_size, offset])
        
        # 매장 목록 조회
        stores = await db.fetch_all(
            f"""
            SELECT * FROM platform_reply_rules 
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            params
        )
        
        # StoreInfo 객체로 변환
        store_list = []
        for store in stores:
            store_info = await dict_to_store_info(store)
            store_list.append(store_info)
        
        return StoreListResponse(
            stores=store_list,
            total=total,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"매장 목록 조회 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"매장 목록 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/{store_code}", response_model=StoreInfo)
async def get_store(
    store_code: str,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """특정 매장 정보 조회"""
    store_info = await get_store_info(store_code, db)
    
    # 권한 확인
    if store_info.owner_user_code != current_user.user_code:
        # 관리자가 아닌 경우 권한 확인
        if current_user.role != "admin":
            # user_store_permissions 테이블에서 권한 확인
            permission = await db.fetch_one(
                """
                SELECT can_view FROM user_store_permissions
                WHERE user_code = ? AND store_code = ? AND is_active = true
                """,
                (current_user.user_code, store_code)
            )
            if not permission or not permission['can_view']:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="이 매장에 대한 접근 권한이 없습니다."
                )
    
    return store_info

@router.put("/{store_code}", response_model=StoreInfo)
async def update_store(
    store_code: str,
    request: StoreUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """매장 설정 업데이트"""
    # 매장 정보 확인
    store_info = await get_store_info(store_code, db)
    
    # 권한 확인
    if store_info.owner_user_code != current_user.user_code:
        if current_user.role != "admin":
            permission = await db.fetch_one(
                """
                SELECT can_edit_settings FROM user_store_permissions
                WHERE user_code = ? AND store_code = ? AND is_active = true
                """,
                (current_user.user_code, store_code)
            )
            if not permission or not permission['can_edit_settings']:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="이 매장을 수정할 권한이 없습니다."
                )
    
    # 업데이트할 필드만 처리
    update_fields = []
    update_values = []
    
    for field, value in request.dict(exclude_unset=True).items():
        if value is not None:
            if field == "prohibited_words":
                update_fields.append(f"{field} = ?")
                update_values.append(json.dumps(value))
            elif field == "business_hours":
                update_fields.append(f"{field} = ?")
                update_values.append(json.dumps(value))
            else:
                update_fields.append(f"{field} = ?")
                update_values.append(value)
    
    if update_fields:
        update_fields.append("updated_at = ?")
        update_values.append(datetime.now())
        update_values.append(store_code)
        
        await db.execute(
            f"""
            UPDATE platform_reply_rules 
            SET {", ".join(update_fields)}
            WHERE store_code = ?
            """,
            update_values
        )
    
    # 업데이트된 정보 반환
    return await get_store_info(store_code, db)

@router.delete("/{store_code}")
async def delete_store(
    store_code: str,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """매장 삭제 (비활성화)"""
    # 매장 정보 확인
    store_info = await get_store_info(store_code, db)
    
    # 권한 확인 (소유자만 삭제 가능)
    if store_info.owner_user_code != current_user.user_code and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 매장을 삭제할 권한이 없습니다."
        )
    
    # 비활성화 처리
    await db.execute(
        """
        UPDATE platform_reply_rules 
        SET is_active = false, updated_at = ?
        WHERE store_code = ?
        """,
        (datetime.now(), store_code)
    )
    
    return {"message": "매장이 성공적으로 삭제되었습니다."}

# 헬퍼 함수들
async def get_store_info(store_code: str, db: Database) -> StoreInfo:
    """매장 정보 조회 헬퍼"""
    store = await db.fetch_one(
        "SELECT * FROM platform_reply_rules WHERE store_code = ?",
        (store_code,)
    )
    
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="매장을 찾을 수 없습니다."
        )
    
    return await dict_to_store_info(store)

async def dict_to_store_info(store_dict: dict) -> StoreInfo:
    """딕셔너리를 StoreInfo 객체로 변환"""
    # JSON 필드 파싱
    prohibited_words = json.loads(store_dict.get('prohibited_words', '[]'))
    business_hours = json.loads(store_dict.get('business_hours', '{}')) if store_dict.get('business_hours') else None
    
    return StoreInfo(
        store_code=store_dict['store_code'],
        store_name=store_dict['store_name'],
        platform=store_dict['platform'],
        platform_code=store_dict['platform_code'],
        platform_id=store_dict['platform_id'],
        owner_user_code=store_dict['owner_user_code'],
        store_type=store_dict.get('store_type', 'delivery_only'),
        business_hours=business_hours,
        store_address=store_dict.get('store_address'),
        store_phone=store_dict.get('store_phone'),
        greeting_start=store_dict['greeting_start'],
        greeting_end=store_dict.get('greeting_end'),
        role=store_dict.get('role'),
        tone=store_dict.get('tone'),
        prohibited_words=prohibited_words,
        max_length=store_dict['max_length'],
        rating_5_reply=bool(store_dict['rating_5_reply']),
        rating_4_reply=bool(store_dict['rating_4_reply']),
        rating_3_reply=bool(store_dict['rating_3_reply']),
        rating_2_reply=bool(store_dict['rating_2_reply']),
        rating_1_reply=bool(store_dict['rating_1_reply']),
        auto_reply_enabled=bool(store_dict['auto_reply_enabled']),
        auto_reply_hours=store_dict['auto_reply_hours'],
        reply_delay_minutes=store_dict['reply_delay_minutes'],
        weekend_enabled=bool(store_dict['weekend_enabled']),
        holiday_enabled=bool(store_dict['holiday_enabled']),
        total_reviews_processed=store_dict.get('total_reviews_processed', 0),
        avg_rating=store_dict.get('avg_rating'),
        is_active=bool(store_dict['is_active']),
        last_crawled=store_dict.get('last_crawled'),
        last_reply=store_dict.get('last_reply'),
        created_at=store_dict['created_at'],
        updated_at=store_dict['updated_at']
    )
