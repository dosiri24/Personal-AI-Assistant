"""
MCP 도구 시스템 설정

모든 MCP 도구들을 등록하고 초기화하는 설정 모듈입니다.
"""

import logging
import asyncio
from typing import List, Dict, Any, Type

from .registry import get_registry, ToolRegistry
from .smart_file_finder import SmartFileFinderTool
from ..tools.base.tool import BaseTool

logger = logging.getLogger(__name__)


async def setup_mcp_tools() -> bool:
    """
    모든 MCP 도구들을 등록하고 설정합니다.
    
    Returns:
        bool: 설정 성공 여부
    """
    try:
        logger.info("🔧 MCP 도구 시스템 설정 시작...")
        
        registry = get_registry()
        
        # 내장 도구들 등록
        tools_to_register: List[Type[BaseTool]] = [
            SmartFileFinderTool,  # type: ignore
            # 여기에 다른 MCP 도구들 추가
        ]
        
        success_count = 0
        total_count = len(tools_to_register)
        
        for tool_class in tools_to_register:
            try:
                success = await registry.register_tool(tool_class, auto_initialize=True)
                if success:
                    success_count += 1
                    logger.info(f"✅ 도구 등록 성공: {tool_class.__name__}")
                else:
                    logger.error(f"❌ 도구 등록 실패: {tool_class.__name__}")
            except Exception as e:
                logger.error(f"❌ 도구 등록 중 예외: {tool_class.__name__} - {e}")
        
        logger.info(f"🎯 MCP 도구 등록 완료: {success_count}/{total_count}")
        
        # 등록된 도구 목록 출력
        available_tools = registry.list_tools()
        logger.info(f"📋 사용 가능한 도구들: {', '.join(available_tools)}")
        
        return success_count == total_count
        
    except Exception as e:
        logger.error(f"❌ MCP 도구 설정 실패: {e}")
        return False


async def get_available_tools() -> List[str]:
    """
    사용 가능한 도구 목록을 반환합니다.
    
    Returns:
        List[str]: 도구 이름 목록
    """
    try:
        registry = get_registry()
        return registry.list_tools()
    except Exception as e:
        logger.error(f"도구 목록 조회 실패: {e}")
        return []


async def get_tool_info(tool_name: str) -> Dict[str, Any]:
    """
    특정 도구의 정보를 반환합니다.
    
    Args:
        tool_name: 도구 이름
        
    Returns:
        Dict[str, Any]: 도구 정보
    """
    try:
        registry = get_registry()
        tool = await registry.get_tool(tool_name)
        
        if tool:
            return {
                "name": tool.metadata.name,
                "description": tool.metadata.description,
                "category": tool.metadata.category.value,
                "parameters": [
                    {
                        "name": param.name,
                        "type": param.type,
                        "description": param.description,
                        "required": param.required
                    }
                    for param in tool.metadata.parameters
                ]
            }
        else:
            return {"error": f"도구를 찾을 수 없습니다: {tool_name}"}
            
    except Exception as e:
        logger.error(f"도구 정보 조회 실패: {tool_name} - {e}")
        return {"error": str(e)}


async def cleanup_mcp_tools() -> None:
    """
    모든 MCP 도구들을 정리합니다.
    """
    try:
        logger.info("🧹 MCP 도구 시스템 정리 시작...")
        registry = get_registry()
        await registry.cleanup_all()
        logger.info("✅ MCP 도구 시스템 정리 완료")
    except Exception as e:
        logger.error(f"❌ MCP 도구 정리 실패: {e}")


# 초기화 시 자동으로 설정 실행 (옵션)
_initialized = False

async def ensure_initialized() -> bool:
    """
    MCP 도구 시스템이 초기화되었는지 확인하고, 
    필요시 초기화를 수행합니다.
    
    Returns:
        bool: 초기화 성공 여부
    """
    global _initialized
    
    if not _initialized:
        success = await setup_mcp_tools()
        if success:
            _initialized = True
        return success
    
    return True
