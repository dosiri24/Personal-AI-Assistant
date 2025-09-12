"""
MCP Doctor - MCP 도구 사용법 안내 및 오류 해결 전문 도구

이 도구는 MCP 시스템의 모든 도구들의 사용법을 안내하고,
매개변수 오류 발생 시 해결책을 제안하는 전문 상담사 역할을 합니다.
"""

import asyncio
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.tools.base import (
    BaseTool, ToolResult, ToolMetadata, ToolParameter, 
    ParameterType, ToolCategory, ExecutionStatus
)
from src.ai_engine.llm_provider import LLMProvider, ChatMessage
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MCPDoctorTool(BaseTool):
    """MCP 도구 사용법 안내 및 오류 해결 전문 도구"""
    
    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        super().__init__()
        self.llm_provider = llm_provider
        
        # MCP 도구 사용법 데이터베이스
        self.tool_usage_db = {
            "filesystem": {
                "description": "파일 및 폴더 관리를 위한 도구",
                "valid_actions": ["list", "create_dir", "copy", "move", "delete"],
                "invalid_actions": ["delete_file", "remove", "find", "search", "list_files"],
                "parameters": {
                    "action": {
                        "type": "string",
                        "required": True,
                        "choices": ["list", "create_dir", "copy", "move", "delete"],
                        "examples": {
                            "list": "폴더 내용 보기",
                            "create_dir": "새 폴더 만들기", 
                            "copy": "파일 복사",
                            "move": "파일 이동/이름변경",
                            "delete": "파일 삭제"
                        }
                    },
                    "path": {
                        "type": "string", 
                        "required": True,
                        "description": "대상 파일/폴더의 절대 경로"
                    },
                    "destination": {
                        "type": "string",
                        "required": False,
                        "description": "copy, move 작업 시 목적지 경로"
                    }
                },
                "common_errors": {
                    "delete_file": "❌ 'delete_file'는 유효하지 않습니다. ✅ 'delete'를 사용하세요.",
                    "remove": "❌ 'remove'는 유효하지 않습니다. ✅ 'delete'를 사용하세요.",
                    "find": "❌ filesystem에서 'find'는 지원되지 않습니다. ✅ system_explorer의 'find' 사용하세요."
                }
            },
            "system_explorer": {
                "description": "시스템 파일 구조 탐색 및 파일 검색 도구",
                "valid_actions": ["tree", "find", "locate", "explore_common", "get_structure", "search_files"],
                "invalid_actions": ["find_files", "list", "search", "list_files"],
                "parameters": {
                    "action": {
                        "type": "string",
                        "required": True,
                        "choices": ["tree", "find", "locate", "explore_common", "get_structure", "search_files"],
                        "examples": {
                            "tree": "폴더 구조 트리 보기",
                            "find": "파일명으로 검색",
                            "locate": "시스템 전체에서 파일 위치 찾기",
                            "explore_common": "일반적인 폴더들 탐색",
                            "get_structure": "디렉토리 구조 분석",
                            "search_files": "패턴 기반 파일 검색"
                        }
                    },
                    "path": {
                        "type": "string",
                        "required": False,
                        "description": "탐색할 시작 경로 (기본값: 홈 디렉토리)"
                    },
                    "pattern": {
                        "type": "string", 
                        "required": False,
                        "description": "검색할 파일 패턴 (예: '*.txt', 'screenshot*')"
                    },
                    "depth": {
                        "type": "integer",
                        "required": False,
                        "description": "탐색 깊이 (1-5, 기본값: 2)"
                    }
                },
                "common_errors": {
                    "find_files": "❌ 'find_files'는 유효하지 않습니다. ✅ 'search_files' 또는 'find'를 사용하세요.",
                    "list": "❌ 'list'는 system_explorer에서 지원되지 않습니다. ✅ filesystem의 'list' 사용하세요.",
                    "search": "❌ 'search'는 유효하지 않습니다. ✅ 'search_files'를 사용하세요."
                }
            }
        }
    
    @property
    def metadata(self) -> ToolMetadata:
        """도구 메타데이터 반환"""
        return ToolMetadata(
            name="mcp_doctor",
            version="1.0.0",
            description="MCP 도구 사용법 안내 및 오류 해결 전문 상담사",
            category=ToolCategory.SYSTEM,
            parameters=[
                ToolParameter(
                    name="query_type",
                    type=ParameterType.STRING,
                    description="문의 유형",
                    required=True,
                    choices=["usage_guide", "error_diagnosis", "parameter_help", "tool_recommendation"]
                ),
                ToolParameter(
                    name="tool_name",
                    type=ParameterType.STRING,
                    description="도구명 (해당하는 경우)",
                    required=False
                ),
                ToolParameter(
                    name="error_message", 
                    type=ParameterType.STRING,
                    description="오류 메시지 (error_diagnosis 시 필요)",
                    required=False
                ),
                ToolParameter(
                    name="task_description",
                    type=ParameterType.STRING, 
                    description="수행하려는 작업 설명 (tool_recommendation 시 필요)",
                    required=False
                )
            ],
            timeout=30
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """도구 실행"""
        try:
            # 매개변수 검증
            validation_errors = self.validate_parameters(parameters)
            if validation_errors:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"매개변수 검증 실패: {', '.join(validation_errors)}"
                )
            
            query_type = parameters["query_type"]
            tool_name = parameters.get("tool_name")
            error_message = parameters.get("error_message", "")
            task_description = parameters.get("task_description", "")
            
            # 문의 유형별 처리
            if query_type == "usage_guide":
                result = await self._provide_usage_guide(tool_name)
            elif query_type == "error_diagnosis":
                result = await self._diagnose_error(tool_name, error_message)
            elif query_type == "parameter_help":
                result = await self._provide_parameter_help(tool_name)
            elif query_type == "tool_recommendation":
                result = await self._recommend_tool(task_description)
            else:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"지원되지 않는 문의 유형: {query_type}"
                )
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data=result,
                metadata={
                    "query_type": query_type,
                    "tool_name": tool_name,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"MCP Doctor 실행 오류: {e}")
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"MCP Doctor 실행 중 오류 발생: {str(e)}"
            )
    
    async def _provide_usage_guide(self, tool_name: Optional[str]) -> Dict[str, Any]:
        """도구 사용법 안내"""
        if tool_name and tool_name in self.tool_usage_db:
            tool_info = self.tool_usage_db[tool_name]
            return {
                "tool_name": tool_name,
                "description": tool_info["description"],
                "valid_actions": tool_info["valid_actions"],
                "invalid_actions": tool_info["invalid_actions"],
                "parameters": tool_info["parameters"],
                "usage_examples": self._generate_usage_examples(tool_name),
                "common_pitfalls": tool_info["common_errors"]
            }
        elif tool_name:
            return {
                "error": f"도구 '{tool_name}'에 대한 정보를 찾을 수 없습니다.",
                "available_tools": list(self.tool_usage_db.keys())
            }
        else:
            return {
                "available_tools": {
                    name: info["description"] 
                    for name, info in self.tool_usage_db.items()
                },
                "general_guidelines": self._get_general_guidelines()
            }
    
    async def _diagnose_error(self, tool_name: Optional[str], error_message: str) -> Dict[str, Any]:
        """오류 진단 및 해결책 제안"""
        diagnosis = {
            "error_message": error_message,
            "diagnosis": [],
            "solutions": [],
            "corrected_examples": []
        }
        
        # 일반적인 오류 패턴 분석
        error_lower = error_message.lower()
        
        # 매개변수 오류 진단
        if "매개변수" in error_message and "유효하지 않습니다" in error_message:
            diagnosis["diagnosis"].append("🔍 매개변수 값 오류 감지")
            
            # 구체적인 오류 값 추출
            if "action" in error_message:
                invalid_value = self._extract_invalid_value(error_message)
                if invalid_value:
                    diagnosis["diagnosis"].append(f"❌ 잘못된 action 값: '{invalid_value}'")
                    
                    # 도구별 해결책 제안
                    if tool_name and tool_name in self.tool_usage_db:
                        tool_info = self.tool_usage_db[tool_name]
                        if invalid_value in tool_info["common_errors"]:
                            diagnosis["solutions"].append(tool_info["common_errors"][invalid_value])
                        
                        diagnosis["solutions"].append(f"✅ {tool_name}에서 사용 가능한 action 값들:")
                        for action in tool_info["valid_actions"]:
                            example = tool_info["parameters"]["action"]["examples"].get(action, "")
                            diagnosis["solutions"].append(f"  - '{action}': {example}")
        
        # LLM을 통한 고급 진단 (선택적)
        if self.llm_provider:
            advanced_diagnosis = await self._get_llm_diagnosis(tool_name, error_message)
            diagnosis["advanced_analysis"] = advanced_diagnosis
        
        return diagnosis
    
    async def _provide_parameter_help(self, tool_name: Optional[str]) -> Dict[str, Any]:
        """매개변수 도움말 제공"""
        if tool_name and tool_name in self.tool_usage_db:
            tool_info = self.tool_usage_db[tool_name]
            return {
                "tool_name": tool_name,
                "parameters": tool_info["parameters"],
                "parameter_combinations": self._get_parameter_combinations(tool_name),
                "validation_rules": self._get_validation_rules(tool_name)
            }
        else:
            return {"error": f"도구 '{tool_name}'에 대한 매개변수 정보를 찾을 수 없습니다."}
    
    async def _recommend_tool(self, task_description: str) -> Dict[str, Any]:
        """작업에 적합한 도구 추천"""
        recommendations = []
        
        task_lower = task_description.lower()
        
        # 키워드 기반 추천
        if any(keyword in task_lower for keyword in ["파일", "삭제", "복사", "이동", "폴더"]):
            if any(keyword in task_lower for keyword in ["찾", "검색", "탐색"]):
                recommendations.append({
                    "tool": "system_explorer",
                    "reason": "파일 검색 및 탐색에 특화",
                    "suggested_action": "search_files 또는 find",
                    "workflow": "1. system_explorer로 파일 찾기 → 2. filesystem으로 작업 수행"
                })
            else:
                recommendations.append({
                    "tool": "filesystem", 
                    "reason": "파일 관리 작업에 특화",
                    "suggested_actions": ["list", "copy", "move", "delete"],
                    "workflow": "filesystem 도구로 직접 파일 작업 수행"
                })
        
        if any(keyword in task_lower for keyword in ["구조", "트리", "탐색"]):
            recommendations.append({
                "tool": "system_explorer",
                "reason": "시스템 구조 탐색에 특화", 
                "suggested_actions": ["tree", "explore_common", "get_structure"],
                "workflow": "system_explorer로 전체 구조 파악"
            })
        
        return {
            "task_description": task_description,
            "recommendations": recommendations,
            "best_practices": self._get_best_practices_for_task(task_description)
        }
    
    def _generate_usage_examples(self, tool_name: str) -> List[Dict[str, Any]]:
        """사용 예시 생성"""
        if tool_name == "filesystem":
            return [
                {
                    "purpose": "파일 삭제",
                    "parameters": {"action": "delete", "path": "/Users/username/Desktop/file.txt"},
                    "description": "데스크탑의 file.txt 삭제"
                },
                {
                    "purpose": "폴더 생성", 
                    "parameters": {"action": "create_dir", "path": "/Users/username/Documents/NewFolder"},
                    "description": "Documents에 NewFolder 생성"
                },
                {
                    "purpose": "파일 복사",
                    "parameters": {"action": "copy", "path": "/source/file.txt", "destination": "/dest/file.txt"},
                    "description": "파일을 다른 위치로 복사"
                }
            ]
        elif tool_name == "system_explorer":
            return [
                {
                    "purpose": "스크린샷 파일 찾기",
                    "parameters": {"action": "search_files", "pattern": "screenshot*", "path": "/Users/username/Desktop"},
                    "description": "데스크탑에서 스크린샷 파일들 검색"
                },
                {
                    "purpose": "폴더 구조 보기",
                    "parameters": {"action": "tree", "path": "/Users/username/Documents", "depth": 2},
                    "description": "Documents 폴더의 2단계 구조 보기"
                }
            ]
        return []
    
    def _extract_invalid_value(self, error_message: str) -> Optional[str]:
        """오류 메시지에서 잘못된 값 추출"""
        import re
        
        # "값이 유효하지 않습니다: invalid_value" 패턴 매칭
        pattern = r"값이 유효하지 않습니다:\s*([^\s,\n]+)"
        match = re.search(pattern, error_message)
        if match:
            return match.group(1).strip("'\"")
        
        return None
    
    async def _get_llm_diagnosis(self, tool_name: Optional[str], error_message: str) -> str:
        """LLM을 통한 고급 오류 진단"""
        if not self.llm_provider:
            return "LLM 진단 서비스를 사용할 수 없습니다."
        
        diagnosis_prompt = f"""
MCP 도구 사용 중 오류가 발생했습니다. 전문가로서 진단해주세요.

**도구명**: {tool_name or '알 수 없음'}
**오류 메시지**: {error_message}

**요청사항**:
1. 오류의 근본 원인 분석
2. 구체적인 해결 방법 제시
3. 앞으로 같은 오류를 방지하는 방법

간결하고 실용적인 조언을 해주세요.
"""
        
        try:
            response = await self.llm_provider.generate_response([
                ChatMessage(role="user", content=diagnosis_prompt)
            ], temperature=0.3, max_tokens=1024)
            
            return response.content if response else "LLM 진단을 생성할 수 없습니다."
        except Exception as e:
            return f"LLM 진단 중 오류 발생: {str(e)}"
    
    def _get_parameter_combinations(self, tool_name: str) -> List[Dict[str, Any]]:
        """유효한 매개변수 조합 반환"""
        if tool_name == "filesystem":
            return [
                {"action": "list", "required": ["path"], "optional": []},
                {"action": "delete", "required": ["path"], "optional": []},
                {"action": "copy", "required": ["path", "destination"], "optional": []},
                {"action": "move", "required": ["path", "destination"], "optional": []}
            ]
        elif tool_name == "system_explorer":
            return [
                {"action": "tree", "required": [], "optional": ["path", "depth"]},
                {"action": "search_files", "required": ["pattern"], "optional": ["path"]},
                {"action": "find", "required": ["pattern"], "optional": ["path", "depth"]}
            ]
        return []
    
    def _get_validation_rules(self, tool_name: str) -> List[str]:
        """검증 규칙 반환"""
        rules = [
            "모든 경로는 절대 경로를 사용하세요",
            "필수 매개변수는 반드시 포함해야 합니다",
            "action 값은 정확히 지정된 값만 사용하세요"
        ]
        
        if tool_name == "filesystem":
            rules.extend([
                "copy, move 작업 시 destination 매개변수 필수",
                "delete 작업 시 신중하게 경로 확인"
            ])
        elif tool_name == "system_explorer": 
            rules.extend([
                "pattern은 shell glob 패턴 사용 (예: '*.txt')",
                "depth는 1-5 사이 값만 허용"
            ])
        
        return rules
    
    def _get_general_guidelines(self) -> List[str]:
        """일반적인 MCP 사용 지침"""
        return [
            "🔍 파일 작업 전에는 항상 system_explorer로 먼저 탐색하세요",
            "📁 경로는 절대 경로를 사용하세요 (상대 경로 지양)",
            "⚡ action 매개변수는 정확한 값만 사용하세요",
            "🛡️ 중요한 파일 작업 전에는 백업을 고려하세요",
            "🔄 오류 발생 시 mcp_doctor를 통해 해결책을 찾으세요",
            "📝 매개변수 조합을 확인하고 필수 값을 빠뜨리지 마세요"
        ]
    
    def _get_best_practices_for_task(self, task_description: str) -> List[str]:
        """작업별 모범 사례"""
        practices = []
        task_lower = task_description.lower()
        
        if "삭제" in task_lower:
            practices.extend([
                "삭제 전에 system_explorer로 정확한 파일 위치 확인",
                "중요한 파일은 삭제 전에 백업 고려",
                "삭제할 파일이 여러 개인 경우 하나씩 신중하게 처리"
            ])
        
        if "검색" in task_lower or "찾" in task_lower:
            practices.extend([
                "system_explorer의 search_files 또는 find 사용",
                "패턴 매칭을 활용한 효율적인 검색",
                "검색 범위를 적절히 제한하여 성능 최적화"
            ])
        
        return practices
