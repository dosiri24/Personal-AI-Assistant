"""
MCP (Model Context Protocol) 모듈

이 모듈은 AI 에이전트가 다양한 도구들과 통신할 수 있는 
표준화된 프로토콜을 제공합니다.

주요 컴포넌트:
- protocol: JSON-RPC 기반 MCP 프로토콜 구현
- registry: 도구 등록 및 관리 시스템
- executor: 안전한 도구 실행 환경
- base_tool: 도구 인터페이스 추상화
- apple: Apple 앱 통합 모듈
- mcp_integration: 통합 관리자
"""

from .protocol import MCPProtocol, MCPMessage, MCPRequest, MCPResponse, MCPError
from .base_tool import BaseTool, ToolMetadata, ToolParameter, ToolResult
from .registry import ToolRegistry, get_registry, register_tool, get_tool
from .executor import ToolExecutor, ExecutionResult, ExecutionMode, get_executor, execute_tool
from .mcp_integration import MCPIntegration

# Apple 모듈은 필요시 별도 import
# from .apple import AppleAppsAgent, AppleAppsManager

__all__ = [
    "MCPProtocol",
    "MCPMessage", 
    "MCPRequest",
    "MCPResponse",
    "MCPError",
    "BaseTool",
    "ToolMetadata",
    "ToolParameter", 
    "ToolResult",
    "ToolRegistry",
    "get_registry",
    "register_tool",
    "get_tool",
    "ToolExecutor",
    "ExecutionResult",
    "ExecutionMode",
    "get_executor",
    "execute_tool",
    "MCPIntegration"
]
