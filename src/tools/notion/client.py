"""
Notion API 클라이언트

Notion API와의 통신을 담당하는 클라이언트 클래스입니다.
인증, 오류 처리, 재시도 로직 등을 포함합니다.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone
from notion_client import Client, AsyncClient
from notion_client.errors import APIResponseError, APIErrorCode
from pydantic import BaseModel, Field

from ...config import Settings
from ...utils.logger import get_logger


logger = get_logger(__name__)


class NotionError(Exception):
    """Notion API 관련 오류"""
    def __init__(self, message: str, code: Optional[str] = None, status_code: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class NotionRateLimitError(NotionError):
    """Notion API 요청 제한 오류"""
    pass


class NotionConnectionConfig(BaseModel):
    """Notion 연결 설정"""
    api_token: str = Field(..., description="Notion API 토큰")
    rate_limit_per_second: int = Field(default=3, description="초당 요청 제한")
    timeout_seconds: int = Field(default=60, description="요청 타임아웃 (초)")
    retry_attempts: int = Field(default=3, description="재시도 횟수")
    retry_delay: float = Field(default=1.0, description="재시도 지연 시간 (초)")


class NotionClient:
    """
    Notion API 클라이언트
    
    동기/비동기 모드를 모두 지원하며, 요청 제한, 오류 처리, 재시도 로직을 포함합니다.
    """
    
    def __init__(self, config: Optional[NotionConnectionConfig] = None, use_async: bool = False):
        """
        Notion 클라이언트 초기화
        
        Args:
            config: Notion 연결 설정
            use_async: 비동기 클라이언트 사용 여부
        """
        if config is None:
            settings = Settings()
            if not settings.notion_api_token:
                raise NotionError("Notion API 토큰이 설정되지 않았습니다")
            
            config = NotionConnectionConfig(
                api_token=settings.notion_api_token,
                rate_limit_per_second=settings.notion_api_rate_limit
            )
        
        self.config = config
        self.use_async = use_async
        
        # 클라이언트 초기화
        if use_async:
            self.client = AsyncClient(
                auth=config.api_token,
                timeout_ms=config.timeout_seconds * 1000,
                log_level=logging.WARNING
            )
        else:
            self.client = Client(
                auth=config.api_token,
                timeout_ms=config.timeout_seconds * 1000,
                log_level=logging.WARNING
            )
        
        # 요청 제한 관리
        self._last_request_time = 0.0
        self._request_interval = 1.0 / config.rate_limit_per_second
        
        logger.info(f"Notion 클라이언트 초기화 완료 (비동기: {use_async})")
    
    async def _wait_for_rate_limit(self):
        """요청 제한을 위한 대기"""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self._request_interval:
            wait_time = self._request_interval - time_since_last
            await asyncio.sleep(wait_time)
        
        self._last_request_time = asyncio.get_event_loop().time()
    
    def _handle_api_error(self, error: APIResponseError) -> NotionError:
        """API 오류를 내부 오류로 변환"""
        if error.code == APIErrorCode.RateLimited:
            return NotionRateLimitError(
                "Notion API 요청 제한에 도달했습니다",
                code=error.code,
                status_code=error.status
            )
        
        return NotionError(
            f"Notion API 오류: {str(error)}",
            code=error.code,
            status_code=error.status
        )
    
    async def _execute_with_retry(self, operation, *args, **kwargs) -> Any:
        """재시도 로직을 포함한 작업 실행"""
        for attempt in range(self.config.retry_attempts):
            try:
                if self.use_async:
                    await self._wait_for_rate_limit()
                
                if asyncio.iscoroutinefunction(operation):
                    return await operation(*args, **kwargs)
                else:
                    return operation(*args, **kwargs)
                    
            except APIResponseError as e:
                error = self._handle_api_error(e)
                
                if isinstance(error, NotionRateLimitError) and attempt < self.config.retry_attempts - 1:
                    wait_time = self.config.retry_delay * (2 ** attempt)  # 지수적 백오프
                    logger.warning(f"요청 제한으로 인한 재시도 (시도 {attempt + 1}/{self.config.retry_attempts}), {wait_time}초 대기")
                    await asyncio.sleep(wait_time)
                    continue
                
                logger.error(f"Notion API 오류 (시도 {attempt + 1}/{self.config.retry_attempts}): {error}")
                if attempt == self.config.retry_attempts - 1:
                    raise error
                
                await asyncio.sleep(self.config.retry_delay)
            
            except Exception as e:
                logger.error(f"예기치 않은 오류 (시도 {attempt + 1}/{self.config.retry_attempts}): {e}")
                if attempt == self.config.retry_attempts - 1:
                    raise NotionError(f"작업 실행 실패: {e}")
                
                await asyncio.sleep(self.config.retry_delay)
    
    # =============================================================================
    # 데이터베이스 작업
    # =============================================================================
    
    async def get_database(self, database_id: str) -> Dict[str, Any]:
        """데이터베이스 정보 조회"""
        try:
            logger.debug(f"데이터베이스 조회: {database_id}")
            
            # 직접 클라이언트 호출 (래퍼 함수 사용)
            async def _get_database_operation():
                return await self.client.databases.retrieve(database_id=database_id)
            
            result = await self._execute_with_retry(_get_database_operation)
            return result if result is not None else {}
        except Exception as e:
            logger.error(f"데이터베이스 조회 실패: {e}")
            raise
    
    async def query_database(
        self, 
        database_id: str, 
        filter_criteria: Optional[Dict] = None,
        sorts: Optional[List[Dict]] = None,
        start_cursor: Optional[str] = None,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """데이터베이스 쿼리"""
        try:
            query_params = {
                "database_id": database_id,
                "page_size": page_size
            }
            
            if filter_criteria:
                query_params["filter"] = filter_criteria
            if sorts:
                query_params["sorts"] = sorts
            if start_cursor:
                query_params["start_cursor"] = start_cursor
            
            logger.debug(f"데이터베이스 쿼리: {database_id}, 필터: {filter_criteria}")
            
            # 직접 클라이언트 호출 (래퍼 함수 사용)
            async def _query_operation():
                return await self.client.databases.query(**query_params)
            
            result = await self._execute_with_retry(_query_operation)
            return result if result is not None else {}
        except Exception as e:
            logger.error(f"데이터베이스 쿼리 실패: {e}")
            raise
    
    async def create_database(
        self,
        parent_page_id: str,
        title: str,
        properties: Dict[str, Any],
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """데이터베이스 생성"""
        try:
            create_params = {
                "parent": {
                    "type": "page_id",
                    "page_id": parent_page_id
                },
                "title": [
                    {
                        "type": "text",
                        "text": {
                            "content": title
                        }
                    }
                ],
                "properties": properties
            }
            
            if description:
                create_params["description"] = [
                    {
                        "type": "text",
                        "text": {
                            "content": description
                        }
                    }
                ]
            
            logger.info(f"데이터베이스 생성: {title}")
            result = await self._execute_with_retry(
                self.client.databases.create,
                **create_params
            )
            return result if result is not None else {}
        except Exception as e:
            logger.error(f"데이터베이스 생성 실패: {e}")
            raise
    
    # =============================================================================
    # 페이지 작업
    # =============================================================================
    
    async def get_page(self, page_id: str) -> Dict[str, Any]:
        """페이지 정보 조회"""
        try:
            logger.debug(f"페이지 조회: {page_id}")
            
            await self._wait_for_rate_limit()
            
            async def _get_page_operation():
                if self.use_async:
                    return await self.client.pages.retrieve(page_id=page_id)
                else:
                    return self.client.pages.retrieve(page_id=page_id)
            
            result = await self._execute_with_retry(_get_page_operation)
            return result if result is not None else {}
        except Exception as e:
            logger.error(f"페이지 조회 실패: {e}")
            raise
    
    async def create_page(
        self,
        parent_id: str,
        title: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        children: Optional[List[Dict]] = None,
        parent_type: str = "database_id"
    ) -> Dict[str, Any]:
        """페이지 생성"""
        try:
            create_params = {
                "parent": {
                    "type": parent_type,
                    parent_type: parent_id
                },
                "properties": {}
            }
            
            # 제목이 있고 properties에 title 타입이 없으면 기본 Name 속성 추가
            if title and properties and not any(prop.get("title") for prop in properties.values()):
                create_params["properties"]["Name"] = {
                    "title": [
                        {
                            "text": {
                                "content": title
                            }
                        }
                    ]
                }
            
            # 추가 속성이 있다면 병합
            if properties:
                create_params["properties"].update(properties)
            
            # 자식 블록이 있다면 추가
            if children:
                create_params["children"] = children
            
            logger.info(f"페이지 생성: {title}")
            
            # 직접 클라이언트 호출 (래퍼 함수 사용)
            async def _create_page_operation():
                return await self.client.pages.create(**create_params)
            
            result = await self._execute_with_retry(_create_page_operation)
            return result if result is not None else {}
        except Exception as e:
            logger.error(f"페이지 생성 실패: {e}")
            raise
    
    async def update_page(
        self,
        page_id: str,
        properties: Optional[Dict[str, Any]] = None,
        archived: Optional[bool] = None
    ) -> Dict[str, Any]:
        """페이지 속성 업데이트"""
        try:
            logger.info(f"페이지 업데이트: {page_id}")
            
            update_params: Dict[str, Any] = {"page_id": page_id}
            
            if properties is not None:
                update_params["properties"] = properties
                
            if archived is not None:
                update_params["archived"] = archived
            
            result = await self._execute_with_retry(
                self.client.pages.update,
                **update_params
            )
            return result if result is not None else {}
        except Exception as e:
            logger.error(f"페이지 업데이트 실패: {e}")
            raise
    
    # =============================================================================
    # 블록 작업
    # =============================================================================
    
    async def get_block_children(
        self,
        block_id: str,
        start_cursor: Optional[str] = None,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """블록의 자식 블록들 조회"""
        try:
            params = {
                "block_id": block_id,
                "page_size": page_size
            }
            
            if start_cursor:
                params["start_cursor"] = start_cursor
            
            logger.debug(f"블록 자식 조회: {block_id}")
            result = await self._execute_with_retry(
                self.client.blocks.children.list,
                **params
            )
            return result if result is not None else {}
        except Exception as e:
            logger.error(f"블록 자식 조회 실패: {e}")
            raise
    
    async def append_block_children(
        self,
        block_id: str,
        children: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """블록에 자식 블록 추가"""
        try:
            logger.info(f"블록 자식 추가: {block_id}, {len(children)}개 블록")
            result = await self._execute_with_retry(
                self.client.blocks.children.append,
                block_id=block_id,
                children=children
            )
            return result if result is not None else {}
        except Exception as e:
            logger.error(f"블록 자식 추가 실패: {e}")
            raise
    
    # =============================================================================
    # 유틸리티 메서드
    # =============================================================================
    
    async def test_connection(self) -> bool:
        """Notion API 연결 테스트"""
        try:
            logger.info("Notion API 연결 테스트 시작")
            result = await self._execute_with_retry(self.client.users.me)
            if result and isinstance(result, dict):
                logger.info(f"연결 테스트 성공: {result.get('name', 'Unknown User')}")
            else:
                logger.info("연결 테스트 성공")
            return True
        except Exception as e:
            logger.error(f"Notion API 연결 테스트 실패: {e}")
            return False
    
    async def search(
        self,
        query: str,
        filter_criteria: Optional[Dict] = None,
        sort: Optional[Dict] = None,
        start_cursor: Optional[str] = None,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """워크스페이스 검색"""
        try:
            search_params = {
                "query": query,
                "page_size": page_size
            }
            
            if filter_criteria:
                search_params["filter"] = filter_criteria
            if sort:
                search_params["sort"] = sort
            if start_cursor:
                search_params["start_cursor"] = start_cursor
            
            logger.debug(f"워크스페이스 검색: {query}")
            
            # 직접 클라이언트 호출 (래퍼 함수 사용)
            async def _search_operation():
                return await self.client.search(**search_params)
            
            result = await self._execute_with_retry(_search_operation)
            return result if result is not None else {}
        except Exception as e:
            logger.error(f"워크스페이스 검색 실패: {e}")
            raise
    
    def __del__(self):
        """소멸자"""
        logger.debug("Notion 클라이언트 정리 완료")


# =============================================================================
# 헬퍼 함수들
# =============================================================================

def create_notion_client(settings: Optional[Settings] = None, use_async: bool = True) -> NotionClient:
    """편의 함수: Notion 클라이언트 생성"""
    if settings is None:
        settings = Settings()
    
    if not settings.notion_api_token:
        raise NotionError("Notion API 토큰이 설정되지 않았습니다")
    
    config = NotionConnectionConfig(
        api_token=settings.notion_api_token,
        rate_limit_per_second=settings.notion_api_rate_limit
    )
    
    return NotionClient(config=config, use_async=use_async)


def create_notion_property(property_type: str, value: Any) -> Dict[str, Any]:
    """Notion 속성 생성 헬퍼"""
    if property_type == "title":
        return {
            "title": [
                {
                    "text": {
                        "content": str(value)
                    }
                }
            ]
        }
    elif property_type == "rich_text":
        return {
            "rich_text": [
                {
                    "text": {
                        "content": str(value)
                    }
                }
            ]
        }
    elif property_type == "number":
        return {
            "number": float(value) if value is not None else None
        }
    elif property_type == "select":
        return {
            "select": {
                "name": str(value)
            } if value else None
        }
    elif property_type == "multi_select":
        if isinstance(value, (list, tuple)):
            return {
                "multi_select": [{"name": str(v)} for v in value]
            }
        else:
            return {
                "multi_select": [{"name": str(value)}]
            }
    elif property_type == "date":
        if isinstance(value, datetime):
            iso_string = value.isoformat()
        else:
            iso_string = str(value)
        
        return {
            "date": {
                "start": iso_string
            }
        }
    elif property_type == "checkbox":
        return {
            "checkbox": bool(value)
        }
    elif property_type == "status":
        return {
            "status": {
                "name": str(value)
            } if value else None
        }
    else:
        raise NotionError(f"지원되지 않는 속성 타입: {property_type}")


def create_text_block(content: str, block_type: str = "paragraph") -> Dict[str, Any]:
    """텍스트 블록 생성 헬퍼"""
    return {
        "object": "block",
        "type": block_type,
        block_type: {
            "rich_text": [
                {
                    "type": "text",
                    "text": {
                        "content": content
                    }
                }
            ]
        }
    }
