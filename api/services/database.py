"""
Supabase 데이터베이스 서비스
"""
import os
from typing import List, Dict, Any, Optional
import logging
from supabase import create_client, Client
from dotenv import load_dotenv
import asyncio
from functools import wraps

load_dotenv()

logger = logging.getLogger(__name__)


def async_wrapper(func):
    """동기 함수를 비동기로 래핑"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)
    return wrapper


class Database:
    """Supabase 데이터베이스 클래스"""
    
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_ANON_KEY")
        
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL과 SUPABASE_ANON_KEY 환경변수를 설정해주세요.")
        
        self._client = None
    
    @property
    def client(self) -> Client:
        """Supabase 클라이언트 반환"""
        if not self._client:
            self._client = create_client(self.url, self.key)
        return self._client
    
    async def create_pool(self):
        """커넥션 풀 생성 (Supabase는 필요없음)"""
        pass
    
    async def close_pool(self):
        """커넥션 풀 종료 (Supabase는 필요없음)"""
        pass
    
    async def execute(self, query: str, params: tuple = None) -> int:
        """쿼리 실행 (INSERT, UPDATE, DELETE)"""
        try:
            # SQL 쿼리를 파싱하여 Supabase API 호출로 변환
            query_lower = query.lower().strip()
            
            if query_lower.startswith("insert into"):
                return await self._execute_insert(query, params)
            elif query_lower.startswith("update"):
                return await self._execute_update(query, params)
            elif query_lower.startswith("delete"):
                return await self._execute_delete(query, params)
            else:
                logger.error(f"지원하지 않는 쿼리 타입: {query}")
                return 0
                
        except Exception as e:
            logger.error(f"쿼리 실행 오류: {e}")
            raise
    
    async def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """단일 행 조회"""
        try:
            # SELECT 쿼리를 파싱하여 Supabase API 호출로 변환
            table_name = self._extract_table_name(query)
            
            # 간단한 쿼리 파싱 (실제로는 더 복잡한 파싱 필요)
            if "WHERE" in query.upper():
                # WHERE 절 파싱
                where_clause = query.split("WHERE", 1)[1].strip()
                
                # 단순한 예: user_code = ? 형태 처리
                if "user_code = ?" in where_clause and params:
                    response = await self._async_select(
                        self.client.table(table_name).select("*").eq("user_code", params[0])
                    )
                elif "email = ?" in where_clause and params:
                    response = await self._async_select(
                        self.client.table(table_name).select("*").eq("email", params[0])
                    )
                elif "store_code = ?" in where_clause and params:
                    response = await self._async_select(
                        self.client.table(table_name).select("*").eq("store_code", params[0])
                    )
                else:
                    # 더 복잡한 WHERE 절은 추가 구현 필요
                    response = await self._async_select(
                        self.client.table(table_name).select("*")
                    )
            else:
                response = await self._async_select(
                    self.client.table(table_name).select("*")
                )
            
            data = response.data
            return data[0] if data else None
            
        except Exception as e:
            logger.error(f"fetch_one 오류: {e}")
            return None
    
    async def fetch_all(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """다중 행 조회"""
        try:
            table_name = self._extract_table_name(query)
            
            # WHERE 절 처리
            if "WHERE" in query.upper():
                where_clause = query.split("WHERE", 1)[1].strip()
                
                if "owner_user_code = ?" in where_clause and params:
                    response = await self._async_select(
                        self.client.table(table_name).select("*").eq("owner_user_code", params[0])
                    )
                elif "user_code = ?" in where_clause and params:
                    response = await self._async_select(
                        self.client.table(table_name).select("*").eq("user_code", params[0])
                    )
                else:
                    response = await self._async_select(
                        self.client.table(table_name).select("*")
                    )
            else:
                response = await self._async_select(
                    self.client.table(table_name).select("*")
                )
            
            return response.data or []
            
        except Exception as e:
            logger.error(f"fetch_all 오류: {e}")
            return []
    
    async def fetch_value(self, query: str, params: tuple = None) -> Any:
        """단일 값 조회"""
        result = await self.fetch_one(query, params)
        if result:
            return list(result.values())[0]
        return None
    
    # Helper 메서드들
    def _extract_table_name(self, query: str) -> str:
        """쿼리에서 테이블명 추출"""
        query_upper = query.upper()
        
        if "FROM" in query_upper:
            # SELECT ... FROM table_name 형태
            from_index = query_upper.index("FROM")
            after_from = query[from_index + 4:].strip()
            # 공백이나 WHERE까지의 부분 추출
            table_name = after_from.split()[0]
        elif "INSERT INTO" in query_upper:
            # INSERT INTO table_name 형태
            insert_index = query_upper.index("INSERT INTO")
            after_insert = query[insert_index + 11:].strip()
            table_name = after_insert.split()[0].split("(")[0]
        elif "UPDATE" in query_upper:
            # UPDATE table_name 형태
            update_index = query_upper.index("UPDATE")
            after_update = query[update_index + 6:].strip()
            table_name = after_update.split()[0]
        else:
            raise ValueError(f"테이블명을 추출할 수 없습니다: {query}")
        
        return table_name.strip()
    
    async def _execute_insert(self, query: str, params: tuple) -> int:
        """INSERT 쿼리 실행"""
        table_name = self._extract_table_name(query)
        
        # 간단한 INSERT 쿼리 파싱
        # INSERT INTO users (user_code, email, ...) VALUES (?, ?, ...)
        columns_part = query.split("(")[1].split(")")[0]
        columns = [col.strip() for col in columns_part.split(",")]
        
        # 파라미터와 컬럼을 매핑
        data = {}
        for i, col in enumerate(columns):
            if i < len(params) and params[i] is not None:
                # NOW() 같은 함수 처리
                if params[i] != "NOW()":
                    data[col] = params[i]
        
        response = await self._async_insert(
            self.client.table(table_name).insert(data)
        )
        
        return 1 if response.data else 0
    
    async def _execute_update(self, query: str, params: tuple) -> int:
        """UPDATE 쿼리 실행"""
        table_name = self._extract_table_name(query)
        
        # SET 절 파싱
        set_part = query.split("SET")[1].split("WHERE")[0].strip()
        updates = {}
        
        # 간단한 파싱 (field = ? 형태)
        set_items = set_part.split(",")
        param_index = 0
        
        for item in set_items:
            if "=" in item and "?" in item:
                field = item.split("=")[0].strip()
                if param_index < len(params):
                    updates[field] = params[param_index]
                    param_index += 1
        
        # WHERE 절 파싱
        where_clause = query.split("WHERE")[1].strip()
        
        # 단순한 예: user_code = ? 형태
        if "user_code = ?" in where_clause:
            response = await self._async_update(
                self.client.table(table_name).update(updates).eq("user_code", params[-1])
            )
        else:
            # 더 복잡한 WHERE 절은 추가 구현 필요
            raise NotImplementedError(f"복잡한 WHERE 절은 아직 지원하지 않습니다: {where_clause}")
        
        return 1 if response.data else 0
    
    async def _execute_delete(self, query: str, params: tuple) -> int:
        """DELETE 쿼리 실행"""
        table_name = self._extract_table_name(query)
        
        # WHERE 절 파싱
        where_clause = query.split("WHERE")[1].strip()
        
        if "user_code = ?" in where_clause and params:
            response = await self._async_delete(
                self.client.table(table_name).delete().eq("user_code", params[0])
            )
        else:
            raise NotImplementedError(f"복잡한 WHERE 절은 아직 지원하지 않습니다: {where_clause}")
        
        return 1 if response.data else 0
    
    # 비동기 래퍼 메서드들
    @async_wrapper
    def _async_select(self, query):
        return query.execute()
    
    @async_wrapper
    def _async_insert(self, query):
        return query.execute()
    
    @async_wrapper
    def _async_update(self, query):
        return query.execute()
    
    @async_wrapper
    def _async_delete(self, query):
        return query.execute()


# 동기 버전도 동일하게 Supabase 사용
class SyncDatabase(Database):
    """동기 데이터베이스 클래스 (Supabase)"""
    
    def execute(self, query: str, params: tuple = None) -> int:
        """동기 쿼리 실행"""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(super().execute(query, params))
        finally:
            loop.close()
    
    def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """동기 단일 행 조회"""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(super().fetch_one(query, params))
        finally:
            loop.close()
    
    def fetch_all(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """동기 다중 행 조회"""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(super().fetch_all(query, params))
        finally:
            loop.close()
