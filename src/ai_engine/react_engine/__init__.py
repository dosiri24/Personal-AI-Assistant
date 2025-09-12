"""
ReAct Engine 모듈

Reasoning and Acting (ReAct) 패러다임을 구현하는 모듈화된 엔진

중복/누락된 모듈 정리: 현재 저장소에는 core.py, planning.py만 존재하므로
이들만 외부로 노출합니다. (thought/observation/execution/adaptation은 추후 추가 시 복원)
"""

def __getattr__(name: str):
    """Lazy attribute access to avoid import cycles during package init."""
    if name == 'ReactEngine':
        from .core import ReactEngine as _ReactEngine
        return _ReactEngine
    if name == 'PlanningExecutor':
        from .planning import PlanningExecutor as _PlanningExecutor
        return _PlanningExecutor
    raise AttributeError(name)

__all__ = ['ReactEngine', 'PlanningExecutor']
