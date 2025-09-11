"""
시스템 시간 정보 도구

현재 시스템의 날짜, 시간, 시간대 정보를 제공하는 MCP 도구입니다.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List
from zoneinfo import ZoneInfo

from ..mcp.base_tool import BaseTool, ToolResult, ExecutionStatus
from ..mcp.base_tool import ToolMetadata, ToolParameter, ParameterType, ToolCategory
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SystemTimeTool(BaseTool):
    """시스템 시간 정보 제공 도구"""
    
    def __init__(self):
        super().__init__()
        self._metadata = ToolMetadata(
            name="system_time",
            version="1.0.0",
            description="현재 시스템의 날짜, 시간, 시간대 정보를 제공합니다",
            category=ToolCategory.SYSTEM,
            parameters=[
                ToolParameter(
                    name="action",
                    type=ParameterType.STRING,
                    description="시간 정보 조회 유형",
                    required=True,
                    choices=["current", "date", "time", "timezone", "formatted"],
                    default="current"
                ),
                ToolParameter(
                    name="timezone",
                    type=ParameterType.STRING,
                    description="시간대 (기본값: Asia/Seoul)",
                    required=False,
                    default="Asia/Seoul"
                ),
                ToolParameter(
                    name="format",
                    type=ParameterType.STRING,
                    description="날짜/시간 출력 형식 (action이 'formatted'일 때 사용)",
                    required=False,
                    default="%Y년 %m월 %d일 %H시 %M분"
                )
            ],
            tags=["시간", "날짜", "시스템", "시간대"]
        )
    
    @property
    def metadata(self) -> ToolMetadata:
        """도구 메타데이터 반환"""
        return self._metadata
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """시스템 시간 정보 조회 실행"""
        try:
            action = parameters.get("action", "current")
            timezone_str = parameters.get("timezone", "Asia/Seoul")
            format_str = parameters.get("format", "%Y년 %m월 %d일 %H시 %M분")
            
            # 시간대 설정
            try:
                tz = ZoneInfo(timezone_str)
            except Exception:
                tz = ZoneInfo("Asia/Seoul")  # 기본값으로 폴백
                logger.warning(f"잘못된 시간대 '{timezone_str}', 기본값 사용")
            
            # 현재 시간 가져오기
            now = datetime.now(tz)
            
            # 액션에 따른 결과 생성
            if action == "current":
                result = {
                    "datetime": now.isoformat(),
                    "date": now.strftime("%Y-%m-%d"),
                    "time": now.strftime("%H:%M:%S"),
                    "timezone": timezone_str,
                    "weekday": now.strftime("%A"),
                    "weekday_kr": self._get_korean_weekday(now.weekday()),
                    "timestamp": int(now.timestamp()),
                    "formatted": now.strftime("%Y년 %m월 %d일 %H시 %M분")
                }
                
            elif action == "date":
                result = {
                    "date": now.strftime("%Y-%m-%d"),
                    "formatted": now.strftime("%Y년 %m월 %d일"),
                    "weekday": now.strftime("%A"),
                    "weekday_kr": self._get_korean_weekday(now.weekday())
                }
                
            elif action == "time":
                result = {
                    "time": now.strftime("%H:%M:%S"),
                    "time_short": now.strftime("%H:%M"),
                    "formatted": now.strftime("%H시 %M분")
                }
                
            elif action == "timezone":
                result = {
                    "timezone": timezone_str,
                    "offset": now.strftime("%z"),
                    "offset_hours": now.utcoffset().total_seconds() / 3600 if now.utcoffset() else 0
                }
                
            elif action == "formatted":
                result = {
                    "formatted": now.strftime(format_str),
                    "raw_datetime": now.isoformat()
                }
                
            else:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"지원하지 않는 액션: {action}"
                )
            
            logger.info(f"시스템 시간 조회 완료: {action}")
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data=result
            )
            
        except Exception as e:
            logger.error(f"시스템 시간 조회 실패: {e}")
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"시스템 시간 조회 중 오류 발생: {str(e)}"
            )
    
    def _get_korean_weekday(self, weekday: int) -> str:
        """영어 요일을 한국어로 변환"""
        korean_weekdays = {
            0: "월요일",
            1: "화요일", 
            2: "수요일",
            3: "목요일",
            4: "금요일",
            5: "토요일",
            6: "일요일"
        }
        return korean_weekdays.get(weekday, "알 수 없음")


# 도구 인스턴스 생성 함수
def create_system_time_tool() -> SystemTimeTool:
    """시스템 시간 도구 인스턴스 생성"""
    return SystemTimeTool()


# 비동기 초기화 함수
async def initialize_system_time_tool() -> SystemTimeTool:
    """시스템 시간 도구 비동기 초기화"""
    tool = create_system_time_tool()
    await tool.initialize()
    return tool
