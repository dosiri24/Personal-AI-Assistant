"""
Phase 3: 멀티 에이전트 시스템

여러 전문화된 AI 에이전트들이 협력하여 복잡한 작업을 수행하는 시스템입니다.
각 에이전트는 특정 역할에 특화되어 있으며, CoordinatorAgent가 전체를 조율합니다.
"""

import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Type, Union
from datetime import datetime
from enum import Enum

from .llm_provider import LLMProvider, ChatMessage
from .agent_state import AgentContext, AgentResult
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AgentRole(Enum):
    """에이전트 역할 정의"""
    COORDINATOR = "coordinator"    # 전체 조율
    PLANNER = "planner"           # 계획 수립
    ANALYZER = "analyzer"         # 분석 전문
    EXECUTOR = "executor"         # 실행 전문
    COMMUNICATOR = "communicator" # 소통 전문


class TaskStatus(Enum):
    """작업 상태"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    DELEGATED = "delegated"


@dataclass
class AgentTask:
    """에이전트 작업 정의"""
    task_id: str
    description: str
    assigned_agent: AgentRole
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 5  # 1(높음) ~ 10(낮음)
    dependencies: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class AgentMessage:
    """에이전트 간 메시지"""
    message_id: str
    from_agent: AgentRole
    to_agent: AgentRole
    message_type: str  # "request", "response", "notification", "question"
    content: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    requires_response: bool = False


class BaseAgent(ABC):
    """기본 에이전트 클래스"""
    
    def __init__(self, role: AgentRole, llm_provider: LLMProvider):
        self.role = role
        self.llm_provider = llm_provider
        self.agent_id = f"{role.value}_{uuid.uuid4().hex[:8]}"
        self.inbox: List[AgentMessage] = []
        self.outbox: List[AgentMessage] = []
        self.current_tasks: List[AgentTask] = []
        
        # 에이전트별 전문성 정의
        self.specialties = self._define_specialties()
        self.capabilities = self._define_capabilities()
        
        logger.info(f"{self.role.value.title()} 에이전트 초기화 완료: {self.agent_id}")
    
    @abstractmethod
    def _define_specialties(self) -> List[str]:
        """에이전트의 전문 분야 정의"""
        pass
    
    @abstractmethod
    def _define_capabilities(self) -> List[str]:
        """에이전트의 능력 정의"""
        pass
    
    @abstractmethod
    async def process_task(self, task: AgentTask) -> AgentTask:
        """작업 처리"""
        pass
    
    async def receive_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """메시지 수신 및 처리"""
        self.inbox.append(message)
        logger.debug(f"{self.agent_id} 메시지 수신: {message.message_type} from {message.from_agent.value}")
        
        # 메시지 타입별 처리
        if message.message_type == "task_assignment":
            return await self._handle_task_assignment(message)
        elif message.message_type == "collaboration_request":
            return await self._handle_collaboration_request(message)
        elif message.message_type == "status_inquiry":
            return await self._handle_status_inquiry(message)
        
        return None
    
    async def _handle_task_assignment(self, message: AgentMessage) -> Optional[AgentMessage]:
        """작업 할당 처리"""
        task_data = message.content.get("task")
        if task_data:
            task = AgentTask(**task_data)
            self.current_tasks.append(task)
            
            # 응답 메시지 생성
            response = AgentMessage(
                message_id=f"resp_{uuid.uuid4().hex[:8]}",
                from_agent=self.role,
                to_agent=message.from_agent,
                message_type="task_accepted",
                content={"task_id": task.task_id, "estimated_time": "30분"}
            )
            return response
        
        return None
    
    async def _handle_collaboration_request(self, message: AgentMessage) -> Optional[AgentMessage]:
        """협업 요청 처리"""
        # 기본적으로 협업에 동의
        response = AgentMessage(
            message_id=f"collab_{uuid.uuid4().hex[:8]}",
            from_agent=self.role,
            to_agent=message.from_agent,
            message_type="collaboration_accepted",
            content={"collaboration_id": message.content.get("collaboration_id")}
        )
        return response
    
    async def _handle_status_inquiry(self, message: AgentMessage) -> Optional[AgentMessage]:
        """상태 조회 처리"""
        status = {
            "agent_id": self.agent_id,
            "current_tasks": len(self.current_tasks),
            "specialties": self.specialties,
            "availability": len(self.current_tasks) < 3  # 3개 미만이면 사용 가능
        }
        
        response = AgentMessage(
            message_id=f"status_{uuid.uuid4().hex[:8]}",
            from_agent=self.role,
            to_agent=message.from_agent,
            message_type="status_response",
            content=status
        )
        return response
    
    def get_status(self) -> Dict[str, Any]:
        """에이전트 상태 반환"""
        return {
            "agent_id": self.agent_id,
            "role": self.role.value,
            "specialties": self.specialties,
            "capabilities": self.capabilities,
            "current_tasks": len(self.current_tasks),
            "inbox_messages": len(self.inbox),
            "outbox_messages": len(self.outbox)
        }


class CoordinatorAgent(BaseAgent):
    """조율 에이전트 - 전체 작업 분배 및 조율"""
    
    def _define_specialties(self) -> List[str]:
        return [
            "작업 분배", "프로젝트 관리", "리소스 할당", 
            "팀 조율", "의사결정", "우선순위 설정"
        ]
    
    def _define_capabilities(self) -> List[str]:
        return [
            "복잡한 작업 분해", "에이전트 선택", "일정 관리",
            "품질 관리", "리스크 관리", "성과 모니터링"
        ]
    
    async def process_task(self, task: AgentTask) -> AgentTask:
        """작업 분해 및 분배"""
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now()
        
        try:
            # LLM을 통한 작업 분해
            breakdown = await self._analyze_and_breakdown_task(task.description)
            
            # 각 하위 작업을 적절한 에이전트에게 할당
            subtasks = await self._create_subtasks(breakdown)
            
            task.result = {
                "breakdown": breakdown,
                "subtasks": subtasks,
                "assigned_agents": [st["agent"] for st in subtasks]
            }
            
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            
            logger.info(f"작업 분해 완료: {task.task_id} -> {len(subtasks)}개 하위작업")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            logger.error(f"작업 분해 실패: {task.task_id} - {e}")
        
        return task
    
    async def _analyze_and_breakdown_task(self, description: str) -> Dict[str, Any]:
        """작업 분석 및 분해"""
        prompt = f"""복잡한 작업을 분석하고 적절한 하위 작업으로 분해해주세요.

작업 설명: {description}

다음 형식으로 응답해주세요:
1. 작업 복잡도 (1-10점)
2. 필요한 전문 분야들
3. 하위 작업 목록 (각각 담당할 에이전트 타입 포함)

사용 가능한 에이전트 타입:
- planner: 계획 수립 전문
- analyzer: 분석 및 연구 전문  
- executor: 실행 및 도구 사용 전문
- communicator: 사용자 소통 전문"""

        messages = [ChatMessage(role="user", content=prompt)]
        
        response = await self.llm_provider.generate_response(
            messages=messages,
            temperature=0.3,
            max_tokens=32768
        )
        
        # 응답 파싱 (실제로는 더 정교한 파싱 필요)
        content = response.content.strip()
        
        return {
            "analysis": content,
            "complexity": 7,  # 임시값
            "domains": ["planning", "analysis", "execution"],
            "estimated_time": "60분"
        }
    
    async def _create_subtasks(self, breakdown: Dict[str, Any]) -> List[Dict[str, Any]]:
        """하위 작업 생성"""
        # 임시 구현 - 실제로는 breakdown 분석해서 동적 생성
        return [
            {
                "task_id": f"subtask_{uuid.uuid4().hex[:8]}",
                "description": "작업 계획 수립",
                "agent": AgentRole.PLANNER,
                "priority": 1
            },
            {
                "task_id": f"subtask_{uuid.uuid4().hex[:8]}",
                "description": "관련 정보 분석",
                "agent": AgentRole.ANALYZER,
                "priority": 2
            },
            {
                "task_id": f"subtask_{uuid.uuid4().hex[:8]}",
                "description": "실제 작업 실행",
                "agent": AgentRole.EXECUTOR,
                "priority": 3
            }
        ]


class PlannerAgent(BaseAgent):
    """계획 에이전트 - 전략 수립 및 계획 전문"""
    
    def _define_specialties(self) -> List[str]:
        return [
            "전략 수립", "일정 계획", "리소스 계획",
            "리스크 분석", "목표 설정", "마일스톤 정의"
        ]
    
    def _define_capabilities(self) -> List[str]:
        return [
            "SMART 목표 설정", "간트 차트 작성", "리스크 매트릭스",
            "의존성 분석", "타임라인 최적화", "대안 계획 수립"
        ]
    
    async def process_task(self, task: AgentTask) -> AgentTask:
        """계획 수립 작업 처리"""
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now()
        
        try:
            # 계획 수립 프롬프트
            plan = await self._create_detailed_plan(task.description)
            
            task.result = {
                "plan": plan,
                "timeline": "2-3일",
                "resources_needed": ["문서 작성 도구", "프레젠테이션 소프트웨어"],
                "risks": ["시간 부족", "자료 부족"]
            }
            
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            
            logger.info(f"계획 수립 완료: {task.task_id}")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            logger.error(f"계획 수립 실패: {task.task_id} - {e}")
        
        return task
    
    async def _create_detailed_plan(self, description: str) -> str:
        """상세 계획 생성"""
        prompt = f"""다음 작업에 대한 상세한 실행 계획을 수립해주세요:

작업: {description}

계획에 포함할 요소:
1. 목표 및 성공 기준
2. 단계별 실행 계획
3. 필요한 리소스
4. 예상 소요 시간
5. 잠재적 리스크 및 대응 방안
6. 체크포인트 및 마일스톤

구체적이고 실행 가능한 계획을 작성해주세요."""

        messages = [ChatMessage(role="user", content=prompt)]
        
        response = await self.llm_provider.generate_response(
            messages=messages,
            temperature=0.4,
            max_tokens=32768
        )
        
        return response.content.strip()


# 다른 에이전트들도 유사하게 구현...
# (AnalyzerAgent, ExecutorAgent, CommunicatorAgent)

class MultiAgentSystem:
    """멀티 에이전트 시스템 메인 클래스"""
    
    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider
        self.agents: Dict[AgentRole, BaseAgent] = {}
        self.message_bus: List[AgentMessage] = []
        self.task_queue: List[AgentTask] = []
        
        # 에이전트 초기화
        self._initialize_agents()
        
        logger.info("멀티 에이전트 시스템 초기화 완료")
    
    def _initialize_agents(self):
        """에이전트들 초기화"""
        self.agents[AgentRole.COORDINATOR] = CoordinatorAgent(AgentRole.COORDINATOR, self.llm_provider)
        self.agents[AgentRole.PLANNER] = PlannerAgent(AgentRole.PLANNER, self.llm_provider)
        # 다른 에이전트들도 추가...
    
    async def process_request(self, user_request: str, user_id: str) -> Dict[str, Any]:
        """사용자 요청 처리"""
        logger.info(f"멀티 에이전트 시스템 요청 처리 시작: {user_request}")
        
        # 1. 코디네이터에게 작업 할당
        main_task = AgentTask(
            task_id=f"main_{uuid.uuid4().hex[:8]}",
            description=user_request,
            assigned_agent=AgentRole.COORDINATOR
        )
        
        # 2. 코디네이터가 작업 분해
        coordinator = self.agents[AgentRole.COORDINATOR]
        processed_task = await coordinator.process_task(main_task)
        
        # 3. 결과 반환
        return {
            "task_id": processed_task.task_id,
            "status": processed_task.status.value,
            "result": processed_task.result,
            "processing_time": (processed_task.completed_at - processed_task.started_at).total_seconds()
            if processed_task.completed_at and processed_task.started_at else None
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """시스템 전체 상태"""
        return {
            "agents": {role.value: agent.get_status() for role, agent in self.agents.items()},
            "active_tasks": len(self.task_queue),
            "message_queue": len(self.message_bus)
        }
