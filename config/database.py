"""
데이터베이스 매니저
"""
import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from .supabase_client import get_supabase_client, reset_supabase_client
from ..utils.error_handler import log_api_error, ErrorType

logger = logging.getLogger(__name__)


class DatabaseManager:
    """데이터베이스 관리 클래스"""
    
    def __init__(self):
        self.client = None
        self.max_retries = 3
        self.retry_delay = 2
    
    def connect(self):
        """데이터베이스 연결"""
        try:
            self.client = get_supabase_client()
            logger.info("Supabase 연결 성공")
        except Exception as e:
            logger.error(f"Supabase 연결 실패: {str(e)}")
            raise
    
    def close(self):
        """데이터베이스 연결 종료"""
        # Supabase는 명시적 종료 불필요
        self.client = None
        logger.info("데이터베이스 연결 종료")
    
    async def execute_with_retry(
        self,
        operation_name: str,
        operation_func,
        *args,
        **kwargs
    ) -> Optional[Any]:
        """
        재시도 로직과 함께 데이터베이스 작업 실행
        
        Args:
            operation_name: 작업명 (로깅용)
            operation_func: 실행할 함수
            *args, **kwargs: 함수 인자
        
        Returns:
            작업 결과
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                # 클라이언트 확인
                if not self.client:
                    self.connect()
                
                # 작업 실행
                result = await operation_func(*args, **kwargs)
                return result
                
            except Exception as e:
                last_error = e
                error_message = str(e)
                logger.warning(f"{operation_name} 실패 (시도 {attempt + 1}/{self.max_retries}): {error_message}")
                
                # 에러 타입 판단
                error_type = ErrorType.CONNECTION_FAILED
                if "timeout" in error_message.lower():
                    error_type = ErrorType.QUERY_TIMEOUT
                elif "duplicate" in error_message.lower():
                    error_type = ErrorType.DUPLICATE_KEY
                elif "transaction" in error_message.lower():
                    error_type = ErrorType.TRANSACTION_FAILED
                
                # 마지막 시도인 경우만 에러 로깅
                if attempt == self.max_retries - 1:
                    await log_api_error(
                        api_type='supabase',
                        error_type=error_type,
                        error_message=error_message,
                        request_data={
                            'operation': operation_name,
                            'attempt': attempt + 1
                        }
                    )
                else:
                    # 재시도 전 대기
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    
                    # 연결 문제인 경우 클라이언트 리셋
                    if error_type == ErrorType.CONNECTION_FAILED:
                        reset_supabase_client()
                        self.client = None
        
        # 모든 재시도 실패
        raise Exception(f"{operation_name} 실패: {last_error}")
    
    async def insert_data(
        self,
        table: str,
        data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """데이터 삽입"""
        async def _insert():
            return self.client.table(table).insert(data).execute()
        
        return await self.execute_with_retry(f"insert_{table}", _insert)
    
    async def update_data(
        self,
        table: str,
        data: Dict[str, Any],
        match: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """데이터 업데이트"""
        async def _update():
            query = self.client.table(table).update(data)
            for key, value in match.items():
                query = query.eq(key, value)
            return query.execute()
        
        return await self.execute_with_retry(f"update_{table}", _update)
    
    async def select_data(
        self,
        table: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """데이터 조회"""
        async def _select():
            query = self.client.table(table).select("*")
            
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            
            if limit:
                query = query.limit(limit)
            
            result = query.execute()
            return result.data if result else []
        
        return await self.execute_with_retry(f"select_{table}", _select)


# 싱글톤 인스턴스
db_manager = DatabaseManager()
