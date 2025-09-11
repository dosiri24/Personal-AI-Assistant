"""
Notion 자연어 파싱 엔진

자연어를 구조화된 데이터로 변환하는 NLP 시스템입니다.
한국어 날짜/시간, 우선순위, 반복 패턴을 인식합니다.
"""

import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass
from enum import Enum

from ...utils.logger import get_logger

logger = get_logger(__name__)


class Priority(Enum):
    """우선순위 열거형"""
    HIGH = "높음"
    MEDIUM = "중간"
    LOW = "낮음"


class RecurrenceType(Enum):
    """반복 타입 열거형"""
    DAILY = "매일"
    WEEKLY = "매주"
    MONTHLY = "매월"
    YEARLY = "매년"
    NONE = "없음"


@dataclass
class ParsedDateTime:
    """파싱된 날짜/시간 정보"""
    datetime: datetime
    is_relative: bool  # 상대적 시간인지 (예: "내일", "다음주")
    original_text: str  # 원본 텍스트
    confidence: float  # 파싱 신뢰도 (0-1)


@dataclass
class ParsedRecurrence:
    """파싱된 반복 정보"""
    type: RecurrenceType
    interval: int  # 간격 (예: 매 2주 = 2)
    days_of_week: Optional[List[int]] = None  # 요일 (0=월요일)
    end_date: Optional[datetime] = None
    original_text: str = ""
    confidence: float = 0.0


@dataclass
class ParsedTodo:
    """파싱된 할일 정보"""
    title: str
    description: Optional[str] = None
    due_date: Optional[ParsedDateTime] = None
    priority: Optional[Priority] = None
    tags: Optional[List[str]] = None
    recurrence: Optional[ParsedRecurrence] = None
    confidence: float = 0.0


class KoreanNLPParser:
    """
    한국어 자연어 파싱 엔진
    
    자연어 텍스트에서 날짜, 시간, 우선순위, 반복 패턴 등을
    인식하여 구조화된 데이터로 변환합니다.
    """
    
    def __init__(self):
        """파서 초기화"""
        self._init_patterns()
        
    def _init_patterns(self):
        """정규표현식 패턴 초기화"""
        
        # 날짜/시간 패턴들
        self.datetime_patterns = {
            # 절대 날짜
            'absolute_date': [
                r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일',
                r'(\d{1,2})월\s*(\d{1,2})일',
                r'(\d{4})-(\d{1,2})-(\d{1,2})',
                r'(\d{1,2})/(\d{1,2})',
            ],
            
            # 상대 날짜
            'relative_date': [
                r'오늘',
                r'내일',
                r'모레',
                r'다음\s*주',
                r'이번\s*주',
                r'다음\s*달',
                r'이번\s*달',
                r'(\d+)일\s*후',
                r'(\d+)주\s*후',
                r'(\d+)개월\s*후',
            ],
            
            # 요일
            'weekday': [
                r'월요일', r'화요일', r'수요일', r'목요일', 
                r'금요일', r'토요일', r'일요일',
                r'월', r'화', r'수', r'목', r'금', r'토', r'일'
            ],
            
            # 시간
            'time': [
                r'(오전|오후|저녁|밤|새벽)\s*(\d{1,2})시(?:\s*(\d{1,2})분)?',
                r'(\d{1,2})시(?:\s*(\d{1,2})분)?(?:까지)?',
                r'(\d{1,2}):(\d{2})'
            ]
        }
        
        # 우선순위 패턴
        self.priority_patterns = {
            'high': [r'급한?', r'중요한?', r'높음', r'high', r'urgent', r'긴급한?'],
            'medium': [r'보통', r'중간', r'medium', r'normal'],
            'low': [r'낮음', r'천천히', r'나중에', r'low']
        }
        
        # 반복 패턴
        self.recurrence_patterns = {
            'daily': [r'매일', r'날마다', r'하루마다'],
            'weekly': [r'매주', r'주마다', r'일주일마다'],
            'monthly': [r'매월', r'달마다', r'한달마다'],
            'yearly': [r'매년', r'해마다', r'일년마다']
        }
        
        # 태그 패턴
        self.tag_patterns = [
            r'#(\w+)',  # 해시태그
            r'@(\w+)',  # 멘션
            r'\[([^\]]+)\]',  # 대괄호 태그
        ]
        
    def parse_todo(self, text: str) -> ParsedTodo:
        """
        자연어 텍스트를 파싱하여 Todo 정보 추출
        
        Args:
            text: 파싱할 자연어 텍스트
            
        Returns:
            ParsedTodo: 파싱된 할일 정보
        """
        logger.info(f"Todo 파싱 시작: {text}")
        
        # 기본 정보 초기화
        title = text.strip()
        description = None
        due_date = None
        priority = None
        tags = []
        recurrence = None
        confidence = 0.0
        
        # 태그 추출
        tags = self._extract_tags(text)
        
        # 날짜/시간 추출 (날짜와 시간 모두 처리)
        due_date, remaining_text = self._extract_datetime(text)
        if due_date:
            confidence += 0.3
            
        # 우선순위 추출
        priority, remaining_text = self._extract_priority(remaining_text)
        if priority:
            confidence += 0.2
            
        # 반복 패턴 추출
        recurrence, remaining_text = self._extract_recurrence(remaining_text)
        if recurrence:
            confidence += 0.2
            
        # 제목과 설명 분리
        title, description = self._extract_title_description(remaining_text)
        confidence += 0.3  # 기본 제목 추출
        
        result = ParsedTodo(
            title=title,
            description=description,
            due_date=due_date,
            priority=priority,
            tags=tags,
            recurrence=recurrence,
            confidence=confidence
        )
        
        logger.info(f"Todo 파싱 완료: {result.title} (신뢰도: {result.confidence:.2f})")
        return result
        
    def _extract_datetime(self, text: str) -> Tuple[Optional[ParsedDateTime], str]:
        """날짜/시간 정보 추출"""
        logger.debug(f"날짜/시간 추출 시작: {text}")
        
        now = datetime.now(timezone.utc)
        remaining_text = text
        chosen_dt: Optional[ParsedDateTime] = None
        
        # 절대 날짜 패턴 확인
        for pattern in self.datetime_patterns['absolute_date']:
            match = re.search(pattern, text)
            if match:
                try:
                    parsed_dt = self._parse_absolute_date(match, now)
                    if parsed_dt:
                        remaining_text = re.sub(pattern, '', text, count=1).strip()
                        logger.debug(f"절대 날짜 파싱 성공: {parsed_dt.datetime}")
                        chosen_dt = parsed_dt
                        text = remaining_text
                        break
                except Exception as e:
                    logger.warning(f"절대 날짜 파싱 실패: {e}")
        if chosen_dt is None:
            # 상대 날짜 패턴 확인
            for pattern in self.datetime_patterns['relative_date']:
                match = re.search(pattern, text)
                if match:
                    try:
                        parsed_dt = self._parse_relative_date(match, now)
                        if parsed_dt:
                            remaining_text = re.sub(pattern, '', text, count=1).strip()
                            logger.debug(f"상대 날짜 파싱 성공: {parsed_dt.datetime}")
                            chosen_dt = parsed_dt
                            text = remaining_text
                            break
                    except Exception as e:
                        logger.warning(f"상대 날짜 파싱 실패: {e}")
                    
        if chosen_dt is None:
            # 요일 패턴 확인
            for i, weekday in enumerate(['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']):
                if weekday in text or weekday[0] in text:
                    try:
                        parsed_dt = self._parse_weekday(i, now)
                        remaining_text = text.replace(weekday, '').replace(weekday[0], '').strip()
                        logger.debug(f"요일 파싱 성공: {parsed_dt.datetime}")
                        chosen_dt = parsed_dt
                        text = remaining_text
                        break
                    except Exception as e:
                        logger.warning(f"요일 파싱 실패: {e}")

        # 시간 패턴 추출 및 적용
        hour, minute, time_expr = self._extract_time_components(text)
        if hour is not None:
            # 텍스트에서 시간 표현 제거
            if time_expr:
                remaining_text = text.replace(time_expr, '').strip()
            else:
                remaining_text = text
            base = chosen_dt.datetime if chosen_dt else now
            dt = base.replace(hour=hour, minute=minute or 0, second=0, microsecond=0)
            chosen_dt = ParsedDateTime(
                datetime=dt,
                is_relative=chosen_dt.is_relative if chosen_dt else True,
                original_text=time_expr or '',
                confidence=(chosen_dt.confidence if chosen_dt else 0.5) + 0.2
            )

        if chosen_dt is not None:
            return chosen_dt, remaining_text
        else:
            return None, remaining_text

    def _extract_time_components(self, text: str) -> Tuple[Optional[int], Optional[int], Optional[str]]:
        """시간 성분 추출: (hour, minute, matched_text)"""
        # 1) 오전/오후/저녁/밤/새벽 + 시/분
        m = re.search(r'(오전|오후|저녁|밤|새벽)\s*(\d{1,2})시(?:\s*(\d{1,2})분)?', text)
        if m:
            meridiem = m.group(1)
            h = int(m.group(2))
            mi = int(m.group(3)) if m.group(3) else 0
            if meridiem in ['오후', '저녁', '밤'] and h < 12:
                h += 12
            if meridiem == '새벽' and h == 12:
                h = 0
            return h, mi, m.group(0)
        # 2) HH:MM
        m = re.search(r'(\d{1,2}):(\d{2})', text)
        if m:
            h = int(m.group(1))
            mi = int(m.group(2))
            return h, mi, m.group(0)
        # 3) HH시 / HH시MM분 (Optional '까지')
        m = re.search(r'(\d{1,2})시(?:\s*(\d{1,2})분)?(?:까지)?', text)
        if m:
            h = int(m.group(1))
            mi = int(m.group(2)) if m.group(2) else 0
            return h, mi, m.group(0)
        return None, None, None
        
    def _parse_absolute_date(self, match: re.Match, now: datetime) -> Optional[ParsedDateTime]:
        """절대 날짜 파싱"""
        groups = match.groups()
        
        if len(groups) == 3:  # 년월일
            year = int(groups[0])
            month = int(groups[1])
            day = int(groups[2])
        elif len(groups) == 2:  # 월일
            year = now.year
            month = int(groups[0])
            day = int(groups[1])
        else:
            return None
            
        try:
            dt = datetime(year, month, day, 23, 59, 0, tzinfo=timezone.utc)
            return ParsedDateTime(
                datetime=dt,
                is_relative=False,
                original_text=match.group(0),
                confidence=0.9
            )
        except ValueError:
            return None
            
    def _parse_relative_date(self, match: re.Match, now: datetime) -> Optional[ParsedDateTime]:
        """상대 날짜 파싱"""
        text = match.group(0)
        
        if '오늘' in text:
            dt = now.replace(hour=23, minute=59, second=0, microsecond=0)
        elif '내일' in text:
            dt = (now + timedelta(days=1)).replace(hour=23, minute=59, second=0, microsecond=0)
        elif '모레' in text:
            dt = (now + timedelta(days=2)).replace(hour=23, minute=59, second=0, microsecond=0)
        elif '다음' in text and '주' in text:
            dt = (now + timedelta(weeks=1)).replace(hour=23, minute=59, second=0, microsecond=0)
        elif '이번' in text and '주' in text:
            # 이번 주 일요일
            days_until_sunday = (6 - now.weekday()) % 7
            dt = (now + timedelta(days=days_until_sunday)).replace(hour=23, minute=59, second=0, microsecond=0)
        elif '다음' in text and '달' in text:
            dt = (now + timedelta(days=30)).replace(hour=23, minute=59, second=0, microsecond=0)
        elif '일 후' in text:
            days_match = re.search(r'(\d+)일', text)
            if days_match:
                days = int(days_match.group(1))
                dt = (now + timedelta(days=days)).replace(hour=23, minute=59, second=0, microsecond=0)
            else:
                return None
        elif '주 후' in text:
            weeks_match = re.search(r'(\d+)주', text)
            if weeks_match:
                weeks = int(weeks_match.group(1))
                dt = (now + timedelta(weeks=weeks)).replace(hour=23, minute=59, second=0, microsecond=0)
            else:
                return None
        elif '개월 후' in text:
            months_match = re.search(r'(\d+)개월', text)
            if months_match:
                months = int(months_match.group(1))
                dt = (now + timedelta(days=months*30)).replace(hour=23, minute=59, second=0, microsecond=0)
            else:
                return None
        else:
            return None
            
        return ParsedDateTime(
            datetime=dt,
            is_relative=True,
            original_text=text,
            confidence=0.8
        )
        
    def _parse_weekday(self, weekday_index: int, now: datetime) -> ParsedDateTime:
        """요일 파싱 (다음 해당 요일로)"""
        current_weekday = now.weekday()
        days_ahead = weekday_index - current_weekday
        
        if days_ahead <= 0:  # 같은 날이거나 이미 지난 경우
            days_ahead += 7
            
        dt = (now + timedelta(days=days_ahead)).replace(hour=23, minute=59, second=0, microsecond=0)
        
        return ParsedDateTime(
            datetime=dt,
            is_relative=True,
            original_text=f"다음 {['월', '화', '수', '목', '금', '토', '일'][weekday_index]}요일",
            confidence=0.7
        )
        
    def _extract_priority(self, text: str) -> Tuple[Optional[Priority], str]:
        """우선순위 추출"""
        remaining_text = text
        
        for priority_level, patterns in self.priority_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    remaining_text = re.sub(pattern, '', text, flags=re.IGNORECASE).strip()
                    if priority_level == 'high':
                        return Priority.HIGH, remaining_text
                    elif priority_level == 'medium':
                        return Priority.MEDIUM, remaining_text
                    elif priority_level == 'low':
                        return Priority.LOW, remaining_text
                        
        return None, remaining_text
        
    def _extract_recurrence(self, text: str) -> Tuple[Optional[ParsedRecurrence], str]:
        """반복 패턴 추출"""
        remaining_text = text
        
        for recur_type, patterns in self.recurrence_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    remaining_text = re.sub(pattern, '', text).strip()
                    
                    if recur_type == 'daily':
                        return ParsedRecurrence(
                            type=RecurrenceType.DAILY,
                            interval=1,
                            original_text=pattern,
                            confidence=0.8
                        ), remaining_text
                    elif recur_type == 'weekly':
                        return ParsedRecurrence(
                            type=RecurrenceType.WEEKLY,
                            interval=1,
                            original_text=pattern,
                            confidence=0.8
                        ), remaining_text
                    elif recur_type == 'monthly':
                        return ParsedRecurrence(
                            type=RecurrenceType.MONTHLY,
                            interval=1,
                            original_text=pattern,
                            confidence=0.8
                        ), remaining_text
                    elif recur_type == 'yearly':
                        return ParsedRecurrence(
                            type=RecurrenceType.YEARLY,
                            interval=1,
                            original_text=pattern,
                            confidence=0.8
                        ), remaining_text
                        
        return None, remaining_text
        
    def _extract_tags(self, text: str) -> List[str]:
        """태그 추출"""
        tags = []
        
        for pattern in self.tag_patterns:
            matches = re.findall(pattern, text)
            tags.extend(matches)
            
        return list(set(tags))  # 중복 제거
        
    def _extract_title_description(self, text: str) -> Tuple[str, Optional[str]]:
        """제목과 설명 분리"""
        # 불필요한 어미/명령어/키워드 제거
        clean = text
        # 일반적인 부탁/명령 표현 제거
        clean = re.sub(r'(해줄래|해줘|부탁해|주세요)$', '', clean).strip()
        # todo/투두 같은 키워드 제거
        clean = re.sub(r'\b(todo|투두)\b', '', clean, flags=re.IGNORECASE).strip()
        # 설정/추가/등록 등의 동사 제거 (문장 끝 위주)
        clean = re.sub(r'(설정|추가|등록)(해줄래|해줘)?$', '', clean).strip()
        # 잔여 접미사 '까지' 제거(시간 표현 제거 후 남은 경우)
        clean = re.sub(r'까지$', '', clean).strip()

        # 줄바꿈이나 특정 구분자로 제목과 설명 분리
        lines = clean.split('\n')
        title = lines[0].strip()
        
        if len(lines) > 1:
            description = '\n'.join(lines[1:]).strip()
            return title, description if description else None
        
        # 단일 라인에서 구분자로 분리 (예: " - ", " : ")
        separators = [' - ', ' : ', ' | ']
        for sep in separators:
            if sep in clean:
                parts = clean.split(sep, 1)
                return parts[0].strip(), parts[1].strip()
                
        return title, None


class NLPIntegration:
    """
    TodoTool과 NLP 파서 통합 클래스
    
    자연어 입력을 받아 TodoTool에서 사용할 수 있는
    구조화된 데이터로 변환합니다.
    """
    
    def __init__(self):
        """통합 클래스 초기화"""
        self.parser = KoreanNLPParser()
        
    def parse_todo_command(self, command: str) -> Dict[str, Any]:
        """
        자연어 Todo 명령을 파싱하여 TodoTool 파라미터로 변환
        
        Args:
            command: 자연어 Todo 명령
            
        Returns:
            Dict: TodoTool에서 사용할 수 있는 파라미터 딕셔너리
        """
        logger.info(f"Todo 명령 파싱: {command}")
        
        parsed = self.parser.parse_todo(command)
        
        # TodoTool 파라미터 형식으로 변환
        params: Dict[str, Any] = {
            "action": "create",
            "title": parsed.title
        }
        
        if parsed.description:
            params["description"] = parsed.description
            
        if parsed.due_date:
            params["due_date"] = parsed.due_date.datetime.isoformat()
            
        if parsed.priority:
            params["priority"] = parsed.priority.value
            
        if parsed.tags:
            # 태그 리스트를 그대로 전달 (TodoTool이 List[str]을 받음)
            params["tags"] = parsed.tags
            
        logger.info(f"파싱 결과: {params}")
        return params
        
    def analyze_parsing_quality(self, command: str) -> Dict[str, Any]:
        """
        파싱 품질 분석
        
        Args:
            command: 분석할 명령
            
        Returns:
            Dict: 파싱 품질 정보
        """
        parsed = self.parser.parse_todo(command)
        
        analysis = {
            "confidence": parsed.confidence,
            "extracted_elements": [],
            "suggestions": []
        }
        
        if parsed.due_date:
            analysis["extracted_elements"].append("날짜/시간")
        if parsed.priority:
            analysis["extracted_elements"].append("우선순위")
        if parsed.tags:
            analysis["extracted_elements"].append("태그")
        if parsed.recurrence:
            analysis["extracted_elements"].append("반복패턴")
            
        if parsed.confidence < 0.5:
            analysis["suggestions"].append("더 구체적인 정보를 제공해주세요")
        if not parsed.due_date:
            analysis["suggestions"].append("마감일을 명시하면 더 정확합니다")
        if not parsed.priority:
            analysis["suggestions"].append("우선순위를 지정해주세요")
            
        return analysis
