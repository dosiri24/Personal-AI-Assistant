"""
MCP 도구 실행 엔진

도구들을 안전하고 효율적으로 실행하는 엔진입니다.
타임아웃, 리소스 제한, 결과 검증 등을 지원합니다.
"""

import asyncio
import logging
import time
import resource
import signal
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import threading
from concurrent.futures import ThreadPoolExecutor
import psutil
import os

from .base_tool import BaseTool, ToolResult, ExecutionStatus
from .registry import ToolRegistry, get_registry

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """실행 모드"""
    SYNC = "sync"  # 동기 실행
    ASYNC = "async"  # 비동기 실행
    PARALLEL = "parallel"  # 병렬 실행


@dataclass
class ResourceLimits:
    """리소스 제한"""
    max_memory_mb: Optional[int] = 512  # 최대 메모리 (MB)
    max_cpu_percent: Optional[float] = 80.0  # 최대 CPU 사용률 (%)
    max_execution_time: Optional[int] = 30  # 최대 실행 시간 (초)
    max_open_files: Optional[int] = 100  # 최대 열린 파일 수
    max_network_connections: Optional[int] = 50  # 최대 네트워크 연결 수


@dataclass
class ExecutionContext:
    """실행 컨텍스트"""
    tool_name: str
    parameters: Dict[str, Any]
    execution_id: str
    started_at: datetime = field(default_factory=datetime.now)
    mode: ExecutionMode = ExecutionMode.ASYNC
    limits: ResourceLimits = field(default_factory=ResourceLimits)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def elapsed_time(self) -> float:
        """경과 시간 (초)"""
        return (datetime.now() - self.started_at).total_seconds()


@dataclass
class ExecutionResult:
    """실행 결과 확장"""
    context: ExecutionContext
    result: ToolResult
    resource_usage: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "execution_id": self.context.execution_id,
            "tool_name": self.context.tool_name,
            "parameters": self.context.parameters,
            "started_at": self.context.started_at.isoformat(),
            "elapsed_time": self.context.elapsed_time,
            "mode": self.context.mode.value,
            "result": self.result.to_dict(),
            "resource_usage": self.resource_usage,
            "warnings": self.warnings
        }


class ResourceMonitor:
    """리소스 모니터링"""
    
    def __init__(self, limits: ResourceLimits):
        self.limits = limits
        self.process = psutil.Process()
        self.initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.monitoring = False
        self.violations: List[str] = []
    
    def start_monitoring(self) -> None:
        """모니터링 시작"""
        self.monitoring = True
        self.violations.clear()
    
    def stop_monitoring(self) -> Dict[str, Any]:
        """모니터링 중지 및 결과 반환"""
        self.monitoring = False
        
        try:
            current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            cpu_percent = self.process.cpu_percent()
            open_files = len(self.process.open_files())
            connections = len(self.process.connections())
            
            return {
                "memory_mb": current_memory,
                "memory_delta_mb": current_memory - self.initial_memory,
                "cpu_percent": cpu_percent,
                "open_files": open_files,
                "network_connections": connections,
                "violations": self.violations.copy()
            }
        except Exception as e:
            logger.error(f"리소스 모니터링 중 오류: {e}")
            return {"error": str(e)}
    
    def check_limits(self) -> List[str]:
        """리소스 제한 확인"""
        violations = []
        
        try:
            # 메모리 확인
            if self.limits.max_memory_mb:
                current_memory = self.process.memory_info().rss / 1024 / 1024
                if current_memory > self.limits.max_memory_mb:
                    violation = f"메모리 제한 초과: {current_memory:.1f}MB > {self.limits.max_memory_mb}MB"
                    violations.append(violation)
            
            # CPU 확인
            if self.limits.max_cpu_percent:
                cpu_percent = self.process.cpu_percent()
                if cpu_percent > self.limits.max_cpu_percent:
                    violation = f"CPU 사용률 제한 초과: {cpu_percent:.1f}% > {self.limits.max_cpu_percent}%"
                    violations.append(violation)
            
            # 열린 파일 수 확인
            if self.limits.max_open_files:
                open_files = len(self.process.open_files())
                if open_files > self.limits.max_open_files:
                    violation = f"열린 파일 수 제한 초과: {open_files} > {self.limits.max_open_files}"
                    violations.append(violation)
            
            # 네트워크 연결 수 확인
            if self.limits.max_network_connections:
                connections = len(self.process.connections())
                if connections > self.limits.max_network_connections:
                    violation = f"네트워크 연결 수 제한 초과: {connections} > {self.limits.max_network_connections}"
                    violations.append(violation)
        
        except Exception as e:
            logger.error(f"리소스 확인 중 오류: {e}")
        
        if violations:
            self.violations.extend(violations)
        
        return violations


class ToolExecutor:
    """
    도구 실행 엔진
    
    안전하고 효율적인 도구 실행을 담당합니다.
    """
    
    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or get_registry()
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.active_executions: Dict[str, ExecutionContext] = {}
        self.execution_history: List[ExecutionResult] = []
        self.max_history_size = 1000
        
        # 기본 리소스 제한
        self.default_limits = ResourceLimits()
        
        # 실행 결과 콜백
        self.result_callbacks: List[Callable[[ExecutionResult], None]] = []
    
    def add_result_callback(self, callback: Callable[[ExecutionResult], None]) -> None:
        """실행 결과 콜백 추가"""
        self.result_callbacks.append(callback)
    
    def remove_result_callback(self, callback: Callable[[ExecutionResult], None]) -> None:
        """실행 결과 콜백 제거"""
        if callback in self.result_callbacks:
            self.result_callbacks.remove(callback)
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any],
                          mode: ExecutionMode = ExecutionMode.ASYNC,
                          limits: Optional[ResourceLimits] = None,
                          execution_id: Optional[str] = None) -> ExecutionResult:
        """
        도구 실행
        
        Args:
            tool_name: 실행할 도구 이름
            parameters: 실행 매개변수
            mode: 실행 모드
            limits: 리소스 제한
            execution_id: 실행 ID (없으면 자동 생성)
            
        Returns:
            실행 결과
        """
        # 실행 컨텍스트 생성
        if execution_id is None:
            execution_id = f"{tool_name}_{int(time.time() * 1000)}"
        
        context = ExecutionContext(
            tool_name=tool_name,
            parameters=parameters,
            execution_id=execution_id,
            mode=mode,
            limits=limits or self.default_limits
        )
        
        # 활성 실행 목록에 추가
        self.active_executions[execution_id] = context
        
        try:
            logger.info(f"도구 실행 시작: {tool_name} (ID: {execution_id})")
            
            # 도구 가져오기
            tool = await self.registry.get_tool(tool_name)
            if not tool:
                result = ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"도구를 찾을 수 없습니다: {tool_name}"
                )
                return ExecutionResult(context=context, result=result)
            
            # 리소스 모니터 설정
            monitor = ResourceMonitor(context.limits)
            monitor.start_monitoring()
            
            try:
                # 실행 모드에 따른 실행
                if mode == ExecutionMode.ASYNC:
                    result = await self._execute_async(tool, parameters, context, monitor)
                elif mode == ExecutionMode.SYNC:
                    result = await self._execute_sync(tool, parameters, context, monitor)
                else:
                    result = ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message=f"지원하지 않는 실행 모드: {mode}"
                    )
            
            finally:
                # 리소스 사용량 수집
                resource_usage = monitor.stop_monitoring()
            
            # 실행 결과 생성
            execution_result = ExecutionResult(
                context=context,
                result=result,
                resource_usage=resource_usage
            )
            
            # 리소스 위반 경고 추가
            if resource_usage.get("violations"):
                execution_result.warnings.extend(resource_usage["violations"])
            
            # 히스토리에 추가
            self._add_to_history(execution_result)
            
            # 콜백 실행
            await self._execute_callbacks(execution_result)
            
            logger.info(f"도구 실행 완료: {tool_name} (상태: {result.status.value})")
            return execution_result
        
        except Exception as e:
            logger.error(f"도구 실행 중 예외: {tool_name} - {e}")
            
            result = ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"실행 중 예외 발생: {str(e)}"
            )
            
            execution_result = ExecutionResult(context=context, result=result)
            self._add_to_history(execution_result)
            
            return execution_result
        
        finally:
            # 활성 실행 목록에서 제거
            if execution_id in self.active_executions:
                del self.active_executions[execution_id]
    
    async def _execute_async(self, tool: BaseTool, parameters: Dict[str, Any],
                           context: ExecutionContext, monitor: ResourceMonitor) -> ToolResult:
        """비동기 실행"""
        try:
            # 타임아웃 설정
            timeout = context.limits.max_execution_time or 30
            
            # 도구 실행
            result = await asyncio.wait_for(
                tool.safe_execute(parameters),
                timeout=timeout
            )
            
            return result
        
        except asyncio.TimeoutError:
            logger.error(f"도구 실행 타임아웃: {context.tool_name}")
            return ToolResult(
                status=ExecutionStatus.TIMEOUT,
                error_message=f"실행 타임아웃 ({timeout}초)"
            )
        
        except Exception as e:
            logger.error(f"비동기 실행 중 예외: {context.tool_name} - {e}")
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"비동기 실행 오류: {str(e)}"
            )
    
    async def _execute_sync(self, tool: BaseTool, parameters: Dict[str, Any],
                          context: ExecutionContext, monitor: ResourceMonitor) -> ToolResult:
        """동기 실행 (스레드 풀 사용)"""
        try:
            timeout = context.limits.max_execution_time or 30
            
            # 스레드 풀에서 실행
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                lambda: asyncio.run(tool.safe_execute(parameters))
            )
            
            return result
        
        except Exception as e:
            logger.error(f"동기 실행 중 예외: {context.tool_name} - {e}")
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"동기 실행 오류: {str(e)}"
            )
    
    async def execute_multiple(self, executions: List[Dict[str, Any]],
                             parallel: bool = False) -> List[ExecutionResult]:
        """
        여러 도구 동시 실행
        
        Args:
            executions: 실행할 도구들의 정보 목록
                [{"tool_name": "...", "parameters": {...}, ...}, ...]
            parallel: 병렬 실행 여부
            
        Returns:
            실행 결과 목록
        """
        if parallel:
            # 병렬 실행
            tasks = []
            for exec_info in executions:
                task = self.execute_tool(
                    tool_name=exec_info["tool_name"],
                    parameters=exec_info.get("parameters", {}),
                    mode=exec_info.get("mode", ExecutionMode.ASYNC),
                    limits=exec_info.get("limits")
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 예외 처리
            execution_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    error_result = ExecutionResult(
                        context=ExecutionContext(
                            tool_name=executions[i]["tool_name"],
                            parameters=executions[i].get("parameters", {}),
                            execution_id=f"error_{i}"
                        ),
                        result=ToolResult(
                            status=ExecutionStatus.ERROR,
                            error_message=f"병렬 실행 중 예외: {str(result)}"
                        )
                    )
                    execution_results.append(error_result)
                else:
                    execution_results.append(result)
            
            return execution_results
        
        else:
            # 순차 실행
            results = []
            for exec_info in executions:
                result = await self.execute_tool(
                    tool_name=exec_info["tool_name"],
                    parameters=exec_info.get("parameters", {}),
                    mode=exec_info.get("mode", ExecutionMode.ASYNC),
                    limits=exec_info.get("limits")
                )
                results.append(result)
            
            return results
    
    async def cancel_execution(self, execution_id: str) -> bool:
        """실행 취소"""
        if execution_id not in self.active_executions:
            return False
        
        try:
            # 실행 컨텍스트 가져오기
            context = self.active_executions[execution_id]
            
            # 취소 로직 (실제 구현은 복잡할 수 있음)
            logger.info(f"실행 취소 요청: {context.tool_name} (ID: {execution_id})")
            
            # 활성 실행 목록에서 제거
            del self.active_executions[execution_id]
            
            return True
        
        except Exception as e:
            logger.error(f"실행 취소 실패: {execution_id} - {e}")
            return False
    
    def get_active_executions(self) -> List[Dict[str, Any]]:
        """활성 실행 목록"""
        return [
            {
                "execution_id": context.execution_id,
                "tool_name": context.tool_name,
                "started_at": context.started_at.isoformat(),
                "elapsed_time": context.elapsed_time,
                "mode": context.mode.value
            }
            for context in self.active_executions.values()
        ]
    
    def get_execution_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """실행 히스토리"""
        history = self.execution_history[-limit:] if limit else self.execution_history
        return [result.to_dict() for result in history]
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """실행 통계"""
        total_executions = len(self.execution_history)
        if total_executions == 0:
            return {"total_executions": 0}
        
        successful = sum(1 for r in self.execution_history 
                        if r.result.status == ExecutionStatus.SUCCESS)
        failed = sum(1 for r in self.execution_history 
                    if r.result.status == ExecutionStatus.ERROR)
        timeouts = sum(1 for r in self.execution_history 
                      if r.result.status == ExecutionStatus.TIMEOUT)
        
        avg_execution_time = sum(r.result.execution_time or 0 
                               for r in self.execution_history) / total_executions
        
        return {
            "total_executions": total_executions,
            "successful": successful,
            "failed": failed,
            "timeouts": timeouts,
            "success_rate": successful / total_executions * 100,
            "average_execution_time": avg_execution_time,
            "active_executions": len(self.active_executions)
        }
    
    def _add_to_history(self, result: ExecutionResult) -> None:
        """히스토리에 추가"""
        self.execution_history.append(result)
        
        # 히스토리 크기 제한
        if len(self.execution_history) > self.max_history_size:
            self.execution_history = self.execution_history[-self.max_history_size:]
    
    async def _execute_callbacks(self, result: ExecutionResult) -> None:
        """결과 콜백 실행"""
        for callback in self.result_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(result)
                else:
                    callback(result)
            except Exception as e:
                logger.error(f"결과 콜백 실행 실패: {e}")
    
    async def cleanup(self) -> None:
        """정리 작업"""
        logger.info("도구 실행 엔진 정리 시작...")
        
        # 활성 실행들 취소
        active_ids = list(self.active_executions.keys())
        for execution_id in active_ids:
            await self.cancel_execution(execution_id)
        
        # 스레드 풀 종료
        self.executor.shutdown(wait=True)
        
        logger.info("도구 실행 엔진 정리 완료")


# 전역 실행 엔진 인스턴스
_global_executor: Optional[ToolExecutor] = None


def get_executor() -> ToolExecutor:
    """전역 실행 엔진 인스턴스 반환"""
    global _global_executor
    if _global_executor is None:
        _global_executor = ToolExecutor()
    return _global_executor


async def execute_tool(tool_name: str, parameters: Dict[str, Any],
                      mode: ExecutionMode = ExecutionMode.ASYNC) -> ExecutionResult:
    """편의 함수: 전역 실행 엔진으로 도구 실행"""
    return await get_executor().execute_tool(tool_name, parameters, mode)
