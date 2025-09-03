"""AI 엔진 모듈

Google Gemini 2.5 Pro 기반 자연어 이해 및 생성 엔진
"""

# 지연 import를 통한 순환 의존성 방지
def get_gemini_provider():
    from .llm_provider import GeminiProvider
    return GeminiProvider

def get_llm_provider():
    from .llm_provider import LLMProvider
    return LLMProvider

def get_prompt_template():
    from .prompt_templates import PromptTemplate
    return PromptTemplate

def get_prompt_manager():
    from .prompt_templates import PromptManager
    return PromptManager

def get_natural_language_processor():
    from .natural_language import NaturalLanguageProcessor
    return NaturalLanguageProcessor

__all__ = [
    "get_gemini_provider",
    "get_llm_provider", 
    "get_prompt_template",
    "get_prompt_manager",
    "get_natural_language_processor",
]
