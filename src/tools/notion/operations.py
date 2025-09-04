"""
Notion Operations 레이어

TodoTool과 CalendarTool을 통합하여 고수준 작업을 조율하는 operations 레이어입니다.
복잡한 워크플로우, 벌크 작업, 트랜잭션 처리를 담당합니다.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json

from ...utils.logger import get_logger
from ...config import Settings
from .todo_tool import TodoTool
from .calendar_tool import CalendarTool
from .client import NotionClient, NotionError

logger = get_logger(__name__)


class OperationType(Enum):
    """작업 타입"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    BULK_CREATE = "bulk_create"
    BULK_UPDATE = "bulk_update"
    BULK_DELETE = "bulk_delete"
    MIGRATE = "migrate"
    SYNC = "sync"


@dataclass
class OperationContext:
    """작업 컨텍스트"""
    user_id: str
    operation_id: str
    operation_type: OperationType
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OperationResult:
    """작업 결과"""
    success: bool
    operation_id: str
    results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    execution_time: float = 0.0
    items_processed: int = 0
    items_succeeded: int = 0
    items_failed: int = 0


class NotionOperations:
    """
    Notion 통합 Operations 레이어
    
    TodoTool과 CalendarTool을 통합하여 고수준 작업을 제공합니다.
    벌크 작업, 트랜잭션 처리, 복잡한 워크플로우를 담당합니다.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Operations 레이어 초기화
        
        Args:
            settings: 애플리케이션 설정
        """
        if settings is None:
            settings = Settings()
        
        self.settings = settings
        self.todo_tool = TodoTool(settings)
        self.calendar_tool = CalendarTool(settings)
        self.logger = get_logger("notion_operations")
        
        # 작업 상태 추적
        self.active_operations: Dict[str, OperationContext] = {}
        
        self.logger.info("Notion Operations 레이어 초기화 완료")
    
    async def initialize(self) -> bool:
        """Operations 레이어 초기화"""
        try:
            # 개별 도구들 초기화는 각 도구에서 필요시 수행
            self.logger.info("Notion Operations 초기화 성공")
            return True
        except Exception as e:
            self.logger.error(f"Notion Operations 초기화 실패: {e}")
            return False
    
    # =====================================================
    # 벌크 작업 (Bulk Operations)
    # =====================================================
    
    async def bulk_create_todos(
        self,
        todos: List[Dict[str, Any]],
        context: Optional[OperationContext] = None
    ) -> OperationResult:
        """
        여러 할일을 일괄 생성
        
        Args:
            todos: 할일 데이터 목록
            context: 작업 컨텍스트
            
        Returns:
            OperationResult: 벌크 작업 결과
        """
        start_time = datetime.now()
        operation_id = context.operation_id if context else f"bulk_todo_{int(start_time.timestamp())}"
        
        result = OperationResult(
            success=True,
            operation_id=operation_id,
            items_processed=len(todos)
        )
        
        try:
            self.logger.info(f"벌크 할일 생성 시작: {len(todos)}개 항목")
            
            # 각 할일을 개별적으로 생성 (병렬 처리)
            tasks = []
            for i, todo_data in enumerate(todos):
                # action을 create로 강제 설정
                todo_data['action'] = 'create'
                tasks.append(self._create_single_todo(todo_data, f"{operation_id}_item_{i}"))
            
            # 병렬 실행
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 처리
            for i, todo_result in enumerate(results):
                if isinstance(todo_result, Exception):
                    result.errors.append({
                        "index": i,
                        "data": todos[i],
                        "error": str(todo_result)
                    })
                    result.items_failed += 1
                else:
                    # ToolResult 객체인 경우
                    if hasattr(todo_result, 'is_success') and getattr(todo_result, 'is_success', False):
                        result.results.append({
                            "index": i,
                            "data": getattr(todo_result, 'data', None)
                        })
                        result.items_succeeded += 1
                    else:
                        result.errors.append({
                            "index": i,
                            "data": todos[i],
                            "error": getattr(todo_result, 'error_message', str(todo_result))
                        })
                        result.items_failed += 1
            
            # 실행 시간 계산
            end_time = datetime.now()
            result.execution_time = (end_time - start_time).total_seconds()
            
            # 성공 여부 결정 (80% 이상 성공시 성공으로 간주)
            success_rate = result.items_succeeded / result.items_processed if result.items_processed > 0 else 0
            result.success = success_rate >= 0.8
            
            self.logger.info(
                f"벌크 할일 생성 완료: "
                f"{result.items_succeeded}/{result.items_processed} 성공 "
                f"({result.execution_time:.2f}초)"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"벌크 할일 생성 실패: {e}")
            result.success = False
            result.errors.append({"error": str(e)})
            return result
    
    async def _create_single_todo(self, todo_data: Dict[str, Any], item_id: str):
        """단일 할일 생성 (내부 헬퍼)"""
        try:
            return await self.todo_tool.execute(**todo_data)
        except Exception as e:
            self.logger.error(f"할일 생성 실패 ({item_id}): {e}")
            raise e
    
    async def bulk_create_events(
        self,
        events: List[Dict[str, Any]],
        context: Optional[OperationContext] = None
    ) -> OperationResult:
        """
        여러 이벤트를 일괄 생성
        
        Args:
            events: 이벤트 데이터 목록
            context: 작업 컨텍스트
            
        Returns:
            OperationResult: 벌크 작업 결과
        """
        start_time = datetime.now()
        operation_id = context.operation_id if context else f"bulk_event_{int(start_time.timestamp())}"
        
        result = OperationResult(
            success=True,
            operation_id=operation_id,
            items_processed=len(events)
        )
        
        try:
            self.logger.info(f"벌크 이벤트 생성 시작: {len(events)}개 항목")
            
            # 각 이벤트를 개별적으로 생성 (병렬 처리)
            tasks = []
            for i, event_data in enumerate(events):
                # action을 create로 강제 설정
                event_data['action'] = 'create'
                tasks.append(self._create_single_event(event_data, f"{operation_id}_item_{i}"))
            
            # 병렬 실행
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 처리
            for i, event_result in enumerate(results):
                if isinstance(event_result, Exception):
                    result.errors.append({
                        "index": i,
                        "data": events[i],
                        "error": str(event_result)
                    })
                    result.items_failed += 1
                else:
                    # ToolResult 객체인 경우
                    if hasattr(event_result, 'is_success') and getattr(event_result, 'is_success', False):
                        result.results.append({
                            "index": i,
                            "data": getattr(event_result, 'data', None)
                        })
                        result.items_succeeded += 1
                    else:
                        result.errors.append({
                            "index": i,
                            "data": events[i],
                            "error": getattr(event_result, 'error_message', str(event_result))
                        })
                        result.items_failed += 1
            
            # 실행 시간 계산
            end_time = datetime.now()
            result.execution_time = (end_time - start_time).total_seconds()
            
            # 성공 여부 결정
            success_rate = result.items_succeeded / result.items_processed if result.items_processed > 0 else 0
            result.success = success_rate >= 0.8
            
            self.logger.info(
                f"벌크 이벤트 생성 완료: "
                f"{result.items_succeeded}/{result.items_processed} 성공 "
                f"({result.execution_time:.2f}초)"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"벌크 이벤트 생성 실패: {e}")
            result.success = False
            result.errors.append({"error": str(e)})
            return result
    
    async def _create_single_event(self, event_data: Dict[str, Any], item_id: str):
        """단일 이벤트 생성 (내부 헬퍼)"""
        try:
            return await self.calendar_tool.execute(**event_data)
        except Exception as e:
            self.logger.error(f"이벤트 생성 실패 ({item_id}): {e}")
            raise e
    
    # =====================================================
    # 고수준 워크플로우
    # =====================================================
    
    async def create_project_workflow(
        self,
        project_name: str,
        tasks: List[Dict[str, Any]],
        meetings: Optional[List[Dict[str, Any]]] = None,
        context: Optional[OperationContext] = None
    ) -> OperationResult:
        """
        프로젝트 전체 워크플로우 생성
        
        할일과 미팅을 함께 생성하여 완전한 프로젝트 일정을 구성합니다.
        
        Args:
            project_name: 프로젝트 이름
            tasks: 할일 목록
            meetings: 미팅 목록
            context: 작업 컨텍스트
            
        Returns:
            OperationResult: 워크플로우 생성 결과
        """
        start_time = datetime.now()
        operation_id = context.operation_id if context else f"project_{int(start_time.timestamp())}"
        
        result = OperationResult(
            success=True,
            operation_id=operation_id
        )
        
        try:
            self.logger.info(f"프로젝트 워크플로우 생성 시작: {project_name}")
            
            # 1. 할일 일괄 생성
            if tasks:
                # 모든 할일에 프로젝트 태그 추가
                for task in tasks:
                    if 'tags' not in task:
                        task['tags'] = []
                    if isinstance(task['tags'], list):
                        task['tags'].append(project_name)
                    else:
                        task['tags'] = [task['tags'], project_name]
                
                todo_result = await self.bulk_create_todos(tasks, context)
                result.results.append({
                    "type": "todos",
                    "result": todo_result.__dict__
                })
                result.items_processed += todo_result.items_processed
                result.items_succeeded += todo_result.items_succeeded
                result.items_failed += todo_result.items_failed
                result.errors.extend(todo_result.errors)
            
            # 2. 미팅 일괄 생성
            if meetings:
                # 모든 미팅에 프로젝트 카테고리 추가
                for meeting in meetings:
                    if 'category' not in meeting:
                        meeting['category'] = project_name
                
                meeting_result = await self.bulk_create_events(meetings, context)
                result.results.append({
                    "type": "meetings",
                    "result": meeting_result.__dict__
                })
                result.items_processed += meeting_result.items_processed
                result.items_succeeded += meeting_result.items_succeeded
                result.items_failed += meeting_result.items_failed
                result.errors.extend(meeting_result.errors)
            
            # 실행 시간 계산
            end_time = datetime.now()
            result.execution_time = (end_time - start_time).total_seconds()
            
            # 성공 여부 결정
            success_rate = result.items_succeeded / result.items_processed if result.items_processed > 0 else 1.0
            result.success = success_rate >= 0.8
            
            self.logger.info(
                f"프로젝트 워크플로우 생성 완료: {project_name} "
                f"({result.items_succeeded}/{result.items_processed} 성공, "
                f"{result.execution_time:.2f}초)"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"프로젝트 워크플로우 생성 실패: {e}")
            result.success = False
            result.errors.append({"error": str(e)})
            return result
    
    async def sync_todo_to_calendar(
        self,
        todo_ids: Optional[List[str]] = None,
        context: Optional[OperationContext] = None
    ) -> OperationResult:
        """
        할일을 캘린더 이벤트로 동기화
        
        마감일이 있는 할일들을 캘린더 이벤트로 자동 생성합니다.
        
        Args:
            todo_ids: 동기화할 할일 ID 목록 (None시 모든 할일)
            context: 작업 컨텍스트
            
        Returns:
            OperationResult: 동기화 결과
        """
        start_time = datetime.now()
        operation_id = context.operation_id if context else f"sync_{int(start_time.timestamp())}"
        
        result = OperationResult(
            success=True,
            operation_id=operation_id
        )
        
        try:
            self.logger.info("할일→캘린더 동기화 시작")
            
            # 1. 할일 목록 조회
            if todo_ids:
                # 특정 할일들만 조회
                todos = []
                for todo_id in todo_ids:
                    todo_result = await self.todo_tool.execute(action="get", todo_id=todo_id)
                    if todo_result.is_success:
                        todos.append(todo_result.data)
            else:
                # 모든 할일 조회
                list_result = await self.todo_tool.execute(action="list")
                if hasattr(list_result, 'is_success') and list_result.is_success:
                    data = getattr(list_result, 'data', {})
                    if isinstance(data, dict):
                        todos = data.get('todos', [])
                    else:
                        todos = []
                else:
                    error_msg = getattr(list_result, 'error_message', str(list_result))
                    raise Exception(f"할일 목록 조회 실패: {error_msg}")
            
            # 2. 마감일이 있는 할일들을 캘린더 이벤트로 변환
            events_to_create = []
            for todo in todos:
                if todo.get('due_date'):
                    event_data = {
                        'action': 'create',
                        'title': f"📋 {todo.get('title', '할일')}",
                        'start_date': todo.get('due_date'),
                        'description': f"할일 마감: {todo.get('description', '')}",
                        'category': 'Todo Deadline',
                        'priority': todo.get('priority', 'Medium')
                    }
                    events_to_create.append(event_data)
            
            # 3. 이벤트 일괄 생성
            if events_to_create:
                event_result = await self.bulk_create_events(events_to_create, context)
                result.results.append({
                    "type": "calendar_events",
                    "result": event_result.__dict__
                })
                result.items_processed = event_result.items_processed
                result.items_succeeded = event_result.items_succeeded
                result.items_failed = event_result.items_failed
                result.errors.extend(event_result.errors)
            else:
                self.logger.info("동기화할 할일이 없습니다 (마감일이 없는 할일들)")
            
            # 실행 시간 계산
            end_time = datetime.now()
            result.execution_time = (end_time - start_time).total_seconds()
            
            # 성공 여부 결정
            success_rate = result.items_succeeded / result.items_processed if result.items_processed > 0 else 1.0
            result.success = success_rate >= 0.8
            
            self.logger.info(
                f"할일→캘린더 동기화 완료: "
                f"{result.items_succeeded}/{result.items_processed} 성공 "
                f"({result.execution_time:.2f}초)"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"할일→캘린더 동기화 실패: {e}")
            result.success = False
            result.errors.append({"error": str(e)})
            return result
    
    # =====================================================
    # 유틸리티 메서드
    # =====================================================
    
    async def get_operation_status(self, operation_id: str) -> Optional[OperationContext]:
        """작업 상태 조회"""
        return self.active_operations.get(operation_id)
    
    async def cleanup_old_operations(self, max_age_hours: int = 24):
        """오래된 작업 컨텍스트 정리"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        
        to_remove = []
        for op_id, context in self.active_operations.items():
            if context.timestamp < cutoff_time:
                to_remove.append(op_id)
        
        for op_id in to_remove:
            del self.active_operations[op_id]
        
        if to_remove:
            self.logger.info(f"오래된 작업 컨텍스트 {len(to_remove)}개 정리 완료")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Operations 통계 정보"""
        return {
            "active_operations": len(self.active_operations),
            "tools_available": {
                "todo_tool": True,
                "calendar_tool": True
            },
            "last_cleanup": datetime.now(timezone.utc).isoformat()
        }


# 편의 함수들
async def create_daily_workflow(
    date: datetime,
    todos: List[Dict[str, Any]],
    meetings: List[Dict[str, Any]],
    settings: Optional[Settings] = None
) -> OperationResult:
    """하루 일정 워크플로우 생성"""
    operations = NotionOperations(settings)
    await operations.initialize()
    
    context = OperationContext(
        user_id="default",
        operation_id=f"daily_{date.strftime('%Y%m%d')}",
        operation_type=OperationType.CREATE
    )
    
    return await operations.create_project_workflow(
        project_name=f"Daily_{date.strftime('%Y-%m-%d')}",
        tasks=todos,
        meetings=meetings,
        context=context
    )


async def bulk_import_from_json(
    json_file_path: str,
    settings: Optional[Settings] = None
) -> OperationResult:
    """JSON 파일에서 데이터 일괄 가져오기"""
    operations = NotionOperations(settings)
    await operations.initialize()
    
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        todos = data.get('todos', [])
        events = data.get('events', [])
        
        context = OperationContext(
            user_id="import",
            operation_id=f"import_{int(datetime.now().timestamp())}",
            operation_type=OperationType.BULK_CREATE
        )
        
        # 할일과 이벤트를 프로젝트로 처리
        return await operations.create_project_workflow(
            project_name=data.get('project_name', 'Imported_Data'),
            tasks=todos,
            meetings=events,
            context=context
        )
        
    except Exception as e:
        logger.error(f"JSON 가져오기 실패: {e}")
        return OperationResult(
            success=False,
            operation_id="import_failed",
            errors=[{"error": str(e)}]
        )
