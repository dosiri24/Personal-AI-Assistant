"""
외부 진행상황 관리 시스템 (LLM Canvas)
사용자 요청에 대한 계획과 진행상황을 외부 파일로 관리하여
세션 간 연속성을 보장하고 중복 작업을 방지합니다.
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

class TaskStatus(Enum):
    PENDING = "⏳"
    IN_PROGRESS = "🔄"
    COMPLETED = "✅"
    FAILED = "❌"
    SKIPPED = "⏭️"

@dataclass
class TaskStep:
    id: str
    title: str
    description: str
    status: TaskStatus
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    tool_calls: List[Dict] = None
    
    def __post_init__(self):
        if self.tool_calls is None:
            self.tool_calls = []

@dataclass
class TaskCanvas:
    canvas_id: str
    user_request: str
    created_at: str
    updated_at: str
    status: TaskStatus
    steps: List[TaskStep]
    summary: Optional[str] = None
    completion_percentage: float = 0.0
    
    def __post_init__(self):
        if isinstance(self.status, str):
            self.status = TaskStatus(self.status)
        for i, step in enumerate(self.steps):
            if isinstance(step, dict):
                if isinstance(step.get('status'), str):
                    step['status'] = TaskStatus(step['status'])
                self.steps[i] = TaskStep(**step)
            elif isinstance(step.status, str):
                step.status = TaskStatus(step.status)

class ExternalTaskCanvas:
    """외부 파일로 관리되는 작업 진행상황 캔버스"""
    
    def __init__(self, canvas_dir: str = "data/task_canvas"):
        self.canvas_dir = canvas_dir
        os.makedirs(canvas_dir, exist_ok=True)
    
    def _get_canvas_path(self, canvas_id: str) -> str:
        """캔버스 파일 경로 생성"""
        return os.path.join(self.canvas_dir, f"{canvas_id}.json")
    
    def _generate_canvas_id(self, user_request: str) -> str:
        """사용자 요청 기반 캔버스 ID 생성"""
        # 요청의 핵심 키워드 추출하여 ID 생성
        import hashlib
        request_hash = hashlib.md5(user_request.encode()).hexdigest()[:8]
        timestamp = str(int(time.time()))
        return f"canvas_{request_hash}_{timestamp}"
    
    def create_canvas(self, user_request: str, steps: List[Dict]) -> TaskCanvas:
        """새로운 작업 캔버스 생성"""
        canvas_id = self._generate_canvas_id(user_request)
        now = datetime.now().isoformat()
        
        task_steps = []
        for i, step_data in enumerate(steps):
            step = TaskStep(
                id=f"step_{i+1}",
                title=step_data.get('title', f'단계 {i+1}'),
                description=step_data.get('description', ''),
                status=TaskStatus.PENDING
            )
            task_steps.append(step)
        
        canvas = TaskCanvas(
            canvas_id=canvas_id,
            user_request=user_request,
            created_at=now,
            updated_at=now,
            status=TaskStatus.PENDING,
            steps=task_steps
        )
        
        self._save_canvas(canvas)
        return canvas
    
    def find_existing_canvas(self, user_request: str) -> Optional[TaskCanvas]:
        """기존 캔버스 검색 (유사한 요청)"""
        if not os.path.exists(self.canvas_dir):
            return None
        
        # 키워드 기반 유사도 검사
        request_keywords = set(user_request.lower().split())
        
        for filename in os.listdir(self.canvas_dir):
            if not filename.endswith('.json'):
                continue
                
            try:
                canvas = self.load_canvas(filename[:-5])  # .json 제거
                if canvas and canvas.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    canvas_keywords = set(canvas.user_request.lower().split())
                    similarity = len(request_keywords & canvas_keywords) / len(request_keywords | canvas_keywords)
                    if similarity > 0.6:  # 60% 이상 유사하면 기존 캔버스 사용
                        return canvas
            except:
                continue
        
        return None
    
    def load_canvas(self, canvas_id: str) -> Optional[TaskCanvas]:
        """캔버스 로드"""
        canvas_path = self._get_canvas_path(canvas_id)
        if not os.path.exists(canvas_path):
            return None
        
        try:
            with open(canvas_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return TaskCanvas(**data)
        except Exception as e:
            print(f"캔버스 로드 실패: {e}")
            return None
    
    def _save_canvas(self, canvas: TaskCanvas):
        """캔버스 저장"""
        canvas.updated_at = datetime.now().isoformat()
        canvas_path = self._get_canvas_path(canvas.canvas_id)
        
        # TaskStatus enum을 문자열로 변환
        data = asdict(canvas)
        data['status'] = canvas.status.value
        for step_data in data['steps']:
            step_data['status'] = step_data['status'].value if hasattr(step_data['status'], 'value') else step_data['status']
        
        try:
            with open(canvas_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"캔버스 저장 실패: {e}")
    
    def update_step_status(self, canvas: TaskCanvas, step_id: str, status: TaskStatus, 
                          result: Optional[str] = None, error: Optional[str] = None,
                          tool_call: Optional[Dict] = None):
        """단계 상태 업데이트"""
        now = datetime.now().isoformat()
        
        for step in canvas.steps:
            if step.id == step_id:
                old_status = step.status
                step.status = status
                
                if status == TaskStatus.IN_PROGRESS and not step.started_at:
                    step.started_at = now
                elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED]:
                    step.completed_at = now
                
                if result:
                    step.result = result
                if error:
                    step.error = error
                if tool_call:
                    step.tool_calls.append(tool_call)
                
                break
        
        # 전체 진행률 계산
        completed_steps = sum(1 for step in canvas.steps if step.status in [TaskStatus.COMPLETED, TaskStatus.SKIPPED])
        canvas.completion_percentage = (completed_steps / len(canvas.steps)) * 100
        
        # 전체 상태 업데이트
        if all(step.status in [TaskStatus.COMPLETED, TaskStatus.SKIPPED] for step in canvas.steps):
            canvas.status = TaskStatus.COMPLETED
        elif any(step.status == TaskStatus.FAILED for step in canvas.steps):
            canvas.status = TaskStatus.FAILED
        elif any(step.status == TaskStatus.IN_PROGRESS for step in canvas.steps):
            canvas.status = TaskStatus.IN_PROGRESS
        
        self._save_canvas(canvas)
    
    def get_next_pending_step(self, canvas: TaskCanvas) -> Optional[TaskStep]:
        """다음 대기 중인 단계 반환"""
        for step in canvas.steps:
            if step.status == TaskStatus.PENDING:
                return step
        return None
    
    def is_step_completed(self, canvas: TaskCanvas, step_id: str) -> bool:
        """단계 완료 여부 확인"""
        for step in canvas.steps:
            if step.id == step_id:
                return step.status in [TaskStatus.COMPLETED, TaskStatus.SKIPPED]
        return False
    
    def generate_progress_summary(self, canvas: TaskCanvas) -> str:
        """진행상황 요약 생성"""
        total_steps = len(canvas.steps)
        completed_steps = sum(1 for step in canvas.steps if step.status in [TaskStatus.COMPLETED, TaskStatus.SKIPPED])
        failed_steps = sum(1 for step in canvas.steps if step.status == TaskStatus.FAILED)
        
        summary = f"📋 **작업 진행상황** ({completed_steps}/{total_steps} 완료)\n\n"
        
        for step in canvas.steps:
            status_icon = step.status.value
            title = step.title
            summary += f"{status_icon} **{title}**"
            
            if step.description:
                summary += f": {step.description}"
            
            if step.result:
                summary += f"\n   └─ {step.result}"
            elif step.error:
                summary += f"\n   └─ ❌ {step.error}"
            
            summary += "\n"
        
        if canvas.status == TaskStatus.COMPLETED:
            summary += "\n🎉 **모든 작업이 완료되었습니다!**"
        elif failed_steps > 0:
            summary += f"\n⚠️ **{failed_steps}개의 단계가 실패했습니다.**"
        
        return summary
    
    def cleanup_old_canvases(self, days: int = 7):
        """오래된 캔버스 정리"""
        if not os.path.exists(self.canvas_dir):
            return
        
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        
        for filename in os.listdir(self.canvas_dir):
            if not filename.endswith('.json'):
                continue
            
            file_path = os.path.join(self.canvas_dir, filename)
            if os.path.getmtime(file_path) < cutoff_time:
                try:
                    os.remove(file_path)
                except:
                    pass
