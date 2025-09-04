"""
MCP (Model Context Protocol) 기본 프로토콜 구현

JSON-RPC 2.0 기반의 표준화된 통신 프로토콜을 제공합니다.
AI 에이전트와 도구들 간의 안전하고 구조화된 통신을 지원합니다.
"""

import json
import uuid
import asyncio
from typing import Any, Dict, List, Optional, Union, Callable, Awaitable
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class MCPErrorCode(Enum):
    """MCP 표준 에러 코드"""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # MCP 특화 에러 코드
    TOOL_NOT_FOUND = -32001
    TOOL_EXECUTION_ERROR = -32002
    TOOL_TIMEOUT = -32003
    PERMISSION_DENIED = -32004
    RESOURCE_UNAVAILABLE = -32005


@dataclass
class MCPError:
    """MCP 에러 정보"""
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        result = {
            "code": self.code,
            "message": self.message
        }
        if self.data:
            result["data"] = self.data
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPError':
        """딕셔너리에서 생성"""
        return cls(
            code=data["code"],
            message=data["message"],
            data=data.get("data")
        )


@dataclass
class MCPMessage:
    """기본 MCP 메시지"""
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPMessage':
        """딕셔너리에서 생성"""
        return cls(**data)


@dataclass
class MCPRequest(MCPMessage):
    """MCP 요청 메시지"""
    method: str = ""
    params: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """요청 ID 자동 생성"""
        if self.id is None:
            self.id = str(uuid.uuid4())


@dataclass
class MCPResponse(MCPMessage):
    """MCP 응답 메시지"""
    result: Optional[Any] = None
    error: Optional[MCPError] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        result = {
            "jsonrpc": self.jsonrpc,
            "id": self.id
        }
        
        if self.result is not None:
            result["result"] = self.result
        elif self.error is not None:
            result["error"] = self.error.to_dict()
            
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPResponse':
        """딕셔너리에서 생성"""
        error_data = data.get("error")
        error = MCPError.from_dict(error_data) if error_data else None
        
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            result=data.get("result"),
            error=error
        )


class MCPProtocol:
    """
    MCP 프로토콜 핸들러
    
    JSON-RPC 2.0 기반으로 메시지 파싱, 검증, 라우팅을 처리합니다.
    """
    
    def __init__(self):
        self.handlers: Dict[str, Callable] = {}
        self.middleware: List[Callable] = []
        self.request_timeout = 30.0  # 기본 타임아웃 30초
        
    def register_handler(self, method: str, handler: Callable) -> None:
        """메서드 핸들러 등록"""
        self.handlers[method] = handler
        logger.info(f"MCP 핸들러 등록: {method}")
        
    def add_middleware(self, middleware: Callable) -> None:
        """미들웨어 추가"""
        self.middleware.append(middleware)
        logger.info(f"MCP 미들웨어 추가: {middleware.__name__}")
        
    def parse_message(self, raw_message: str) -> Union[MCPRequest, MCPResponse, MCPError]:
        """
        원시 메시지를 파싱하여 MCP 객체로 변환
        
        Args:
            raw_message: JSON 문자열 메시지
            
        Returns:
            파싱된 MCP 객체 또는 에러
        """
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError as e:
            return MCPError(
                code=MCPErrorCode.PARSE_ERROR.value,
                message=f"JSON 파싱 실패: {str(e)}"
            )
            
        # JSON-RPC 2.0 검증
        if data.get("jsonrpc") != "2.0":
            return MCPError(
                code=MCPErrorCode.INVALID_REQUEST.value,
                message="jsonrpc 필드가 '2.0'이어야 합니다"
            )
            
        # 요청인지 응답인지 판단
        if "method" in data:
            # 요청 메시지
            try:
                return MCPRequest(
                    jsonrpc=data["jsonrpc"],
                    id=data.get("id"),
                    method=data["method"],
                    params=data.get("params")
                )
            except Exception as e:
                return MCPError(
                    code=MCPErrorCode.INVALID_REQUEST.value,
                    message=f"요청 메시지 파싱 실패: {str(e)}"
                )
        
        elif "result" in data or "error" in data:
            # 응답 메시지
            try:
                return MCPResponse.from_dict(data)
            except Exception as e:
                return MCPError(
                    code=MCPErrorCode.INVALID_REQUEST.value,
                    message=f"응답 메시지 파싱 실패: {str(e)}"
                )
        
        else:
            return MCPError(
                code=MCPErrorCode.INVALID_REQUEST.value,
                message="요청에는 'method'가, 응답에는 'result' 또는 'error'가 필요합니다"
            )
    
    async def handle_request(self, request: MCPRequest) -> MCPResponse:
        """
        요청 처리
        
        Args:
            request: MCP 요청 객체
            
        Returns:
            MCP 응답 객체
        """
        logger.info(f"MCP 요청 처리: {request.method} (ID: {request.id})")
        
        # 미들웨어 실행
        for middleware in self.middleware:
            try:
                if asyncio.iscoroutinefunction(middleware):
                    await middleware(request)
                else:
                    middleware(request)
            except Exception as e:
                logger.error(f"미들웨어 실행 실패: {e}")
                return MCPResponse(
                    id=request.id,
                    error=MCPError(
                        code=MCPErrorCode.INTERNAL_ERROR.value,
                        message=f"미들웨어 오류: {str(e)}"
                    )
                )
        
        # 핸들러 찾기
        handler = self.handlers.get(request.method)
        if not handler:
            return MCPResponse(
                id=request.id,
                error=MCPError(
                    code=MCPErrorCode.METHOD_NOT_FOUND.value,
                    message=f"메서드를 찾을 수 없습니다: {request.method}"
                )
            )
        
        # 핸들러 실행
        try:
            if asyncio.iscoroutinefunction(handler):
                result = await asyncio.wait_for(
                    handler(request.params or {}),
                    timeout=self.request_timeout
                )
            else:
                result = handler(request.params or {})
                
            return MCPResponse(
                id=request.id,
                result=result
            )
            
        except asyncio.TimeoutError:
            logger.error(f"요청 타임아웃: {request.method}")
            return MCPResponse(
                id=request.id,
                error=MCPError(
                    code=MCPErrorCode.TOOL_TIMEOUT.value,
                    message=f"요청 타임아웃 ({self.request_timeout}초)"
                )
            )
            
        except Exception as e:
            logger.error(f"핸들러 실행 실패: {e}")
            return MCPResponse(
                id=request.id,
                error=MCPError(
                    code=MCPErrorCode.INTERNAL_ERROR.value,
                    message=f"핸들러 실행 오류: {str(e)}"
                )
            )
    
    async def process_message(self, raw_message: str) -> str:
        """
        원시 메시지를 처리하고 응답을 반환
        
        Args:
            raw_message: 원시 JSON 메시지
            
        Returns:
            JSON 응답 문자열
        """
        # 메시지 파싱
        parsed = self.parse_message(raw_message)
        
        if isinstance(parsed, MCPError):
            # 파싱 에러인 경우
            response = MCPResponse(error=parsed)
            return json.dumps(response.to_dict(), ensure_ascii=False, indent=2)
        
        elif isinstance(parsed, MCPRequest):
            # 요청인 경우 처리
            response = await self.handle_request(parsed)
            return json.dumps(response.to_dict(), ensure_ascii=False, indent=2)
        
        else:
            # 응답인 경우 (일반적으로 클라이언트에서만 처리)
            logger.warning("서버에서 응답 메시지를 받았습니다")
            error_response = MCPResponse(
                error=MCPError(
                    code=MCPErrorCode.INVALID_REQUEST.value,
                    message="서버는 응답 메시지를 처리할 수 없습니다"
                )
            )
            return json.dumps(error_response.to_dict(), ensure_ascii=False, indent=2)
    
    def create_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> str:
        """
        요청 메시지 생성
        
        Args:
            method: 호출할 메서드명
            params: 메서드 파라미터
            
        Returns:
            JSON 요청 문자열
        """
        request = MCPRequest(method=method, params=params)
        return json.dumps(request.to_dict(), ensure_ascii=False, indent=2)
    
    def create_response(self, request_id: Union[str, int], result: Any = None, 
                       error: Optional[MCPError] = None) -> str:
        """
        응답 메시지 생성
        
        Args:
            request_id: 요청 ID
            result: 성공 결과
            error: 에러 정보
            
        Returns:
            JSON 응답 문자열
        """
        response = MCPResponse(id=request_id, result=result, error=error)
        return json.dumps(response.to_dict(), ensure_ascii=False, indent=2)


# 편의를 위한 헬퍼 함수들
def create_error_response(request_id: Union[str, int], code: MCPErrorCode, 
                         message: str, data: Optional[Dict[str, Any]] = None) -> str:
    """에러 응답 생성 헬퍼"""
    error = MCPError(code=code.value, message=message, data=data)
    response = MCPResponse(id=request_id, error=error)
    return json.dumps(response.to_dict(), ensure_ascii=False, indent=2)


def create_success_response(request_id: Union[str, int], result: Any) -> str:
    """성공 응답 생성 헬퍼"""
    response = MCPResponse(id=request_id, result=result)
    return json.dumps(response.to_dict(), ensure_ascii=False, indent=2)
