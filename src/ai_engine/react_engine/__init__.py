"""
ReAct Engine 모듈

Reasoning and Acting (ReAct) 패러다임을 구현하는 모듈화된 엔진
🌟 자연어 기반 시스템으로 전환: JSON 구조 강제 없이 순수 LLM 추론 활용
"""

def __getattr__(name: str):
    """Lazy attribute access to avoid import cycles during package init."""
    if name == 'ReactEngine':
        # 🌟 기본적으로 자연어 기반 엔진 사용
        from .natural_adapter import NaturalReactEngine as _NaturalReactEngine
        return _NaturalReactEngine
    if name == 'PlanningExecutor':
        # 🌟 자연어 기반 실행기 사용
        from .natural_planning import NaturalPlanningExecutor as _NaturalPlanningExecutor
        return _NaturalPlanningExecutor
    if name == 'NaturalReactEngine':
        from .natural_adapter import NaturalReactEngine as _NaturalReactEngine
        return _NaturalReactEngine
    if name == 'NaturalPlanningExecutor':
        from .natural_planning import NaturalPlanningExecutor as _NaturalPlanningExecutor
        return _NaturalPlanningExecutor
    if name == 'LegacyReactEngine':
        # 기존 구조화된 엔진 (필요시 사용)
        from .core import ReactEngine as _LegacyReactEngine
        return _LegacyReactEngine
    if name == 'LegacyPlanningExecutor':
        # 기존 구조화된 실행기 (필요시 사용)
        from .planning import PlanningExecutor as _LegacyPlanningExecutor
        return _LegacyPlanningExecutor
    raise AttributeError(name)
