# Personal AI Assistant

Discord를 통해 자연어 명령을 받아 에이전틱 AI가 스스로 판단하고 MCP 도구를 활용하여 임무를 완수하는 지능형 개인 비서

## 🎯 핵심 기능

- **Discord Bot**: 휴대폰으로 언제 어디서나 AI 비서와 소통
- **에이전틱 AI**: Google Gemini 2.5 Pro 기반 자율적 판단 및 도구 선택
- **장기기억 시스템**: RAG 기반으로 과거 행동 패턴을 학습하여 개인화된 서비스 제공
- **MCP 도구 연동**: Notion, 웹 스크래핑, Apple 시스템 등 다양한 도구 자동 실행
- **24/7 백그라운드 실행**: macOS에서 상시 대기하여 능동적/수동적 작업 처리

## 🚀 빠른 시작

### 1. 설치

```bash
# 저장소 클론
git clone https://github.com/dosiri24/Personal-AI-Assistant.git
cd Personal-AI-Assistant

# 의존성 설치
poetry install

# 환경 변수 설정
cp .env.example .env
# .env 파일을 편집하여 필요한 API 키들을 설정하세요
```

### 2. 설정

`.env` 파일에 다음 항목들을 설정하세요:

- `DISCORD_BOT_TOKEN`: Discord Bot 토큰
- `GOOGLE_API_KEY`: Google Gemini API 키
- `NOTION_API_TOKEN`: Notion 통합 토큰
- 기타 필요한 API 키들

추가 환경 변수(에이전틱 모드 제어):

- `PAI_MOCK_MODE` (기본: `off`): Mock LLM 동작 토글
  - `off`: 비활성화(운영 권장)
  - `echo`: 마지막 사용자 메시지를 그대로 반환(디버그용)
  - `heuristic`: 키워드 기반 휴리스틱 응답(데모/테스트용)
- `PAI_PARAM_NORMALIZATION_MODE` (기본: `minimal`): MCP 파라미터 정규화 수준
  - `off`: 정규화 비활성화(LLM 결과 그대로 실행)
  - `minimal`: 비해석적 보정만(키 이름/타임존/기본값)
  - `full`: 동의어 매핑까지 수행(지양)
- `PAI_SELF_REPAIR_ATTEMPTS` (기본: `2`): 도구 실행 실패 시 LLM 자기교정 재시도 횟수

### 3. 실행

```bash
# 개발 모드로 실행
poetry run pai start

# 백그라운드 데몬으로 실행
poetry run pai start --daemon

# 상태 확인
poetry run pai status

# 중지
poetry run pai stop
```

## 📋 주요 명령어

Discord에서 다음과 같은 자연어 명령을 사용할 수 있습니다:

- `내일 오후 3시에 회의 일정 추가해줘`
- `오늘 할 일 목록 보여줘`
- `AI 관련 최신 뉴스 찾아서 요약해줘`
- `중요한 메일이 오면 알려줘`

### CLI 명령어

직접 CLI를 통해서도 도구를 사용할 수 있습니다:

```bash
# Notion 연결 테스트
poetry run pai notion test-connection

# 캘린더 이벤트 생성
poetry run pai notion create-event --title "팀 미팅" --date "tomorrow 14:00"

# Todo 생성
poetry run pai notion create-todo --title "문서 작성" --priority high

# 이벤트 목록 조회
poetry run pai notion list-events

# Todo 목록 조회
poetry run pai notion list-todos --filter pending
```

자세한 Notion 설정은 [NOTION_SETUP.md](NOTION_SETUP.md)를 참조하세요.

## 🏗️ 프로젝트 구조

```
Personal-AI-Assistant/
├── main.py                         # Discord 런처(PID/인증서/Apple MCP 자동시작 옵션)
├── src/
│   ├── main.py                     # CLI 엔트리포인트 (Click)
│   ├── config.py                   # Pydantic Settings(.env) + 에이전틱 토글
│   ├── daemon.py / log_manager.py / process_monitor.py
│   ├── cli/
│   │   ├── main.py                 # 명령군 등록
│   │   └── commands/
│   │       ├── service.py          # start/stop/restart/status/health
│   │       ├── monitoring.py       # logs/queue/sessions/process-message
│   │       ├── tools.py            # tools list/info/execute/discover/stats
│   │       ├── notion.py           # Notion CLI 도우미
│   │       ├── apple_commands.py / apple_apps_commands.py
│   │       └── utils.py
│   ├── discord_bot/
│   │   ├── bot.py                  # 권한/세션/중복방지/명령어
│   │   ├── ai_handler.py           # LLM↔MCP 브리지(템플릿 기반 도구선택, 키워드 폴백 없음)
│   │   ├── parser.py / router.py / session.py / message_queue.py
│   ├── ai_engine/
│   │   ├── llm_provider.py         # Gemini Provider, Mock(ENV: PAI_MOCK_MODE)
│   │   ├── decision_engine.py      # 에이전틱 의사결정/자연어→파라미터 변환
│   │   ├── prompt_templates.py     # command_analysis/tool_selection/context_aware_planning 등
│   │   ├── natural_language.py     # intent_category/urgency 기반, 키워드 분류 제거
│   │   ├── response_generator.py   # 진행/완료/오류 보고 프롬프트
│   ├── mcp/
│   │   ├── base_tool.py / registry.py / executor.py / protocol.py
│   │   ├── mcp_integration.py      # AI 의사결정→도구 실행 + Self-Repair 재시도(ENV)
│   │   ├── apple_tools.py / apple_client.py / apple_agent_v2.py
│   ├── tools/
│   │   ├── calculator_tool.py
│   │   ├── notion/                 # client.py / todo_tool.py / calendar_tool.py / operations.py / nlp_parser.py
│   │   └── apple/                  # notes_tool.py / notification_monitor.py / auto_responder.py
│   │   └── web_scraper/            # (실험적) 크롤러/스케줄러/검증 유틸
│   ├── memory/                     # 장기기억/RAG/벡터(준비됨)
│   │   ├── vector_store.py / rag_engine.py / memory_manager.py / simple_memory_manager.py / models.py / enhanced_models.py / embedding_provider.py
│   ├── integration/                # event_bus / container / interfaces
│   ├── monitoring/                 # dashboard.py (실험적)
│   ├── utils/                      # logger / error_handler / performance
│   └── __init__.py
├── external/
│   └── apple-mcp/                  # Apple MCP TypeScript 서버(선택)
├── docs/                           # 설치/가이드 문서
├── scripts/                        # 권한/설정 스크립트
├── data/                           # 런타임 DB/벡터 저장소
├── logs/                           # 런타임 로그
├── .env / .env.example             # 환경변수(에이전틱 토글 포함)
├── PROJECT_PLAN.md / DEVELOPMENT_LOG.md / NOTION_SETUP.md
└── README.md
```

## 🛠️ 기술 스택

- **Python 3.11+**
- **Google Gemini 2.5 Pro API** - AI 엔진
- **Discord.py** - Discord Bot
- **ChromaDB** - 벡터 데이터베이스
- **Notion API** - 일정/할일 관리

## 🤖 에이전틱 모드 정책

- 기본값은 “엄격한 에이전틱 모드”입니다. 키워드 매칭/동의어 매핑에 의존하지 않고, LLM이 도구 선택과 파라미터를 직접 생성합니다.
- 실행 실패 시에는 에러/스키마/이전 파라미터를 근거로 LLM이 스스로 파라미터를 교정(Self-Repair)하여 재시도합니다(`PAI_SELF_REPAIR_ATTEMPTS`).
- 필요 시 `.env`로 Mock/정규화 수준을 일시적으로 조절할 수 있습니다.
- **Beautiful Soup / Scrapy** - 웹 스크래핑
- **Click/Typer** - CLI 프레임워크

## 🧰 사용 가능한 MCP 도구

본 프로젝트에서 AI가 실시간으로 선택·실행하는 MCP 도구들을 정리했습니다. 각 도구는 레지스트리 이름과 지원 액션, 파라미터 규격, 동작 원리와 LLM 사용 규격(예시 JSON)을 함께 제공합니다.

### Notion - Todo 도구 (`notion_todo`)
- 기능: Notion 할일 데이터베이스에서 할일 생성/수정/삭제/조회/완료 처리
- 지원 액션: `create`, `update`, `delete`, `get`, `list`, `complete`
- 주요 파라미터:
  - `title`(str, 생성/수정), `description`(str), `due_date`(ISO 또는 자연어), `priority`(낮음/중간/높음), `todo_id`(대상 항목), `limit`(조회 개수)
- 우선순위 표준화: LLM이 `High/Medium/Low/urgent/중요` 등으로 내려도 실행 전 자동으로 한국어 표준값(높음/중간/낮음)으로 정규화됩니다.
- 날짜 파싱: ISO 권장. 자연어 키워드(오늘/내일/다음 주)는 마감 시각을 23:59로 설정합니다.
- LLM 사용 규격(예시):
```json
{
  "selected_tools": ["notion_todo"],
  "execution_plan": [
    {
      "tool": "notion_todo",
      "action": "create",
      "parameters": {
        "title": "회의 준비",
        "due_date": "2025-09-08T09:00+09:00",
        "priority": "High"
      }
    }
  ]
}
```

### Notion - Calendar 도구 (`notion_calendar`)
- 기능: Notion 캘린더에서 일정 생성/수정/삭제/조회
- 지원 액션: `create`, `update`, `delete`, `get`, `list`
- 주요 파라미터:
  - `title`(str), `start_date`(ISO/자연어), `end_date`(ISO/자연어), `description`(str), `location`(str), `attendees`([]), `priority`(High/Medium/Low), `is_all_day`(bool)
- 날짜/시간 파싱: “오전/오후 N시”, “HH:MM”, “오늘/내일/다음 주” 등 일부 자연어 지원. ISO(+타임존) 입력 권장.
- LLM 사용 규격(예시):
```json
{
  "selected_tools": ["notion_calendar"],
  "execution_plan": [
    {
      "tool": "notion_calendar",
      "action": "create",
      "parameters": {
        "title": "팀 미팅",
        "start_date": "2025-09-08T14:00+09:00",
        "end_date": "2025-09-08T15:00+09:00",
        "description": "주간 진행 점검"
      }
    }
  ]
}
```

### 계산기 도구 (`calculator`)
- 기능: 기본 사칙연산
- 지원 액션: 없음(파라미터 기반 수행)
- 주요 파라미터: `operation`(+, -, *, /), `a`(number), `b`(number), `precision`(int, 기본 2)
- LLM 사용 규격(예시):
```json
{
  "selected_tools": ["calculator"],
  "execution_plan": [
    {
      "tool": "calculator",
      "parameters": {"operation": "+", "a": 2, "b": 3, "precision": 0}
    }
  ]
}
```

### 에코 도구 (`echo`)
- 기능: 입력 텍스트를 그대로(옵션 적용) 반환
- 지원 액션: 없음(파라미터 기반 수행)
- 주요 파라미터: `message`(str), `delay`(sec, 선택), `uppercase`(bool, 선택)
- LLM 사용 규격(예시):
```json
{
  "selected_tools": ["echo"],
  "execution_plan": [
    {
      "tool": "echo",
      "parameters": {"message": "안녕하세요!", "uppercase": false}
    }
  ]
}
```

### Apple MCP 도구들 (macOS + 외부 서버 필요)
Apple 앱 제어 도구는 `external/apple-mcp` 서버가 실행 중이어야 합니다. `pai apple install` → `pai apple start -b`로 백그라운드 실행 후 사용하세요.

- 연락처 (`apple_contacts`)
  - 액션: `search`(name), `find_by_phone`(phone)
  - 예시:
  ```json
  {"selected_tools":["apple_contacts"],"execution_plan":[{"tool":"apple_contacts","action":"search","parameters":{"name":"홍길동"}}]}
  ```

- 메모 (`apple_notes`)
  - 액션: `create`(title, body, folder_name), `search`(search_text), `list`(folder_name)
  - 예시:
  ```json
  {"selected_tools":["apple_notes"],"execution_plan":[{"tool":"apple_notes","action":"create","parameters":{"title":"회의 메모","body":"안건 정리","folder_name":"Claude"}}]}
  ```

- 메시지 (`apple_messages`)
  - 액션: `send`(phone_number, message), `read`(phone_number, limit), `unread`(limit), `schedule`(phone_number, message, scheduled_time)

- 메일 (`apple_mail`)
  - 액션: `send`(to, subject, body, cc?, bcc?), `unread`(account?, mailbox?, limit), `search`(search_term, account?, limit), `accounts`, `mailboxes`(account)

- 미리 알림 (`apple_reminders`)
  - 액션: `create`(name, list_name?, notes?, due_date?), `search`(search_text), `list`, `open`(search_text)

- 캘린더 (`apple_calendar`)
  - 액션: `create`(title, start_date, end_date, ...), `search`(search_text, from_date?, to_date?, limit?), `list`(from_date?, to_date?, limit?), `open`(event_id)

- 지도 (`apple_maps`)
  - 액션: `search`(query, limit?), `save`(name, address), `directions`(from_address, to_address, transport_type?), `pin`(name, address), `create_guide`(guide_name), `add_to_guide`(guide_name, address)

> 주의: Apple 도구는 macOS 권한 설정이 필요할 수 있습니다. `pai apple setup-permissions` 참고.

### (참고) 웹 스크래퍼 도구
- `src/tools/web_scraper`에 실험적 도구가 포함되어 있으나, 현재 MCP 통합 경로에서는 비활성화되어 있습니다.

### 동작 원리와 규격 요약
- 선택: 에이전틱 의사결정 엔진이 LLM 응답(JSON)으로 `selected_tools`와 `execution_plan`을 생성합니다.
- 정규화: `MCPIntegration`이 액션/우선순위/날짜 등을 표준 형태로 보정합니다.
- 실행: `ToolExecutor`가 리소스 제한(시간/메모리/CPU)을 적용해 안전 실행 후 결과/통계를 기록합니다.
- 요약: 성공/실패 메시지를 사용자가 읽기 쉬운 한국어로 요약하여 반환합니다.


## 🔧 개발

### 테스트 실행

```bash
poetry run pytest
```

## 🔧 개발 도구

### GitHub Copilot MCP 연동

이 프로젝트는 GitHub Copilot과 MCP (Model Context Protocol)를 통해 연동되어 있습니다.

#### MCP 서버 설정
`.vscode/settings.json`에 다음과 같은 MCP 서버가 구성되어 있습니다:

- **Codex CLI**: 고급 코드 분석, 생성, 리팩토링 기능

#### MCP 서버 사용법
GitHub Copilot Chat에서 다음과 같이 요청할 수 있습니다:

```
@codex 현재 코드베이스를 분석하고 개선점을 찾아줘
@codex 이 함수를 더 효율적으로 리팩토링해줘
@codex 현재 프로젝트의 복잡한 쉘 스크립트를 생성해줘
```

자세한 MCP 설정은 [.vscode/README.md](.vscode/README.md)를 참조하세요.

### 개발 명령어

```bash
# 프로젝트 빌드
poetry run pai build

# 테스트 실행
poetry run pytest

# 로그 확인
poetry run pai logs --follow

# 시스템 상태 확인
poetry run pai health
```

### 코드 포맷팅

```bash
poetry run black src/
poetry run isort src/
```

### 타입 체크

```bash
poetry run mypy src/
```

## 📖 문서

자세한 문서는 [PROJECT_PLAN.md](PROJECT_PLAN.md)를 참조하세요.

## 🤝 기여

이슈와 풀 리퀘스트를 환영합니다!

## 📄 라이센스

MIT License

## 🧠 에이전틱 아키텍처 개요

이 프로젝트는 “에이전틱 AI 개인 비서”를 목표로 설계되었습니다. 핵심은 LLM이 사용자의 자연어를 그대로 이해하고, 중간의 규칙/분류기 없이 필요한 도구를 스스로 선택·실행하는 흐름입니다.

- 에이전틱 의사결정: LLM이 도구 선택·실행계획(JSON)까지 산출 → 실행
- 도구 실행: MCP 스타일의 도구 인터페이스로 실제 시스템/서비스 연동
- 상호작용 채널: Discord Bot(메인), CLI, macOS 알림 기반 트리거(Apple)
- 관측/운영: 로깅/모니터링/오류처리/성능관리 유틸리티 포함

관련 파일
- `src/ai_engine/decision_engine.py:1`: 에이전틱 의사결정(도구 선택/계획/신뢰도)
- `src/ai_engine/llm_provider.py:1`: Gemini/Mock LLM 프로바이더 통합
- `src/discord_bot/ai_handler.py:1`: Discord 메시지 → 도구/LLM 처리 허브
- `src/mcp/registry.py:1`: MCP 도구 레지스트리(발견/등록/활성화)
- `src/integration/event_bus.py:1`: 비동기 이벤트 버스(컴포넌트 decoupling)
- `src/tools/notion/todo_tool.py:1`: Notion Todo MCP 도구
- `src/tools/notion/calendar_tool.py:1`: Notion Calendar MCP 도구
- `src/tools/apple/notes_tool.py:1`: Apple Notes MCP 도구(시뮬레이션)
- `src/tools/apple/notification_monitor.py:1`: macOS 알림 모니터
- `src/tools/apple/auto_responder.py:1`: 알림 자동응답(Apple 에이전트/스크립트 연계)
- `src/monitoring/dashboard.py:1`: 대시보드/메트릭 수집
- `src/config.py:1`: 환경설정(.env)

## 🔗 모듈 간 관계와 데이터 흐름

1) Discord 대화 흐름(요청 → 도구/AI 응답)
- 입력: Discord 메시지
- 흐름: `src/discord_bot/bot.py:1` → `src/discord_bot/ai_handler.py:200`(process_message)
  - 도구 판단·실행: `AIMessageHandler._check_and_execute_tools` → 필요 시 각 MCP 도구의 `execute`
  - 에이전틱 판단: LLM(Gemini/Mock)이 선택/계획 JSON을 생성(`src/ai_engine/decision_engine.py:120` 파싱 로직 참조)
  - 도구 결과 타입: `ToolResult(status, data, error_message)`(`src/mcp/base_tool.py` 정의)
  - 응답: 도구 실행 결과가 있으면 우선 반환, 없으면 LLM 일반 응답
- 출력: Discord 채널로 텍스트/임베드 응답

2) 에이전틱 의사결정(도구 선택/계획)
- 입력: `DecisionContext(user_message, user_id, available_tools, ...)`
- 처리: LLM에게 도구 목록/지침/대화요약을 포함한 프롬프트 전달 → JSON 응답 파싱
- 산출: `Decision(selected_tools, execution_plan[], confidence_score, reasoning ...)`
- 파일: `src/ai_engine/decision_engine.py:68`(데이터클래스), `src/ai_engine/decision_engine.py:164`(프롬프트), `src/ai_engine/decision_engine.py:228`(JSON 파싱)

3) MCP 도구 실행(Notion/Apple/Web/기타)
- 인터페이스: `BaseTool.execute(parameters: Dict) -> ToolResult`
- Notion 예시: `src/tools/notion/todo_tool.py:140`(create), `src/tools/notion/todo_tool.py:248`(list)
- Apple 예시: `src/tools/apple/notes_tool.py:60`(create), 알림 자동응답은 `src/tools/apple/auto_responder.py:150`에서 액션 생성 후 실행
- 동적 등록/발견: `src/mcp/registry.py:74`(register_tool), `src/mcp/registry.py:258`(discover_tools)

4) Apple 알림 기반 흐름(능동적 트리거)
- 입력: macOS 알림 → `src/tools/apple/notification_monitor.py:34`
- 분석: 키워드/간단 규칙 또는 Apple 에이전트 기반 분석 → 응답 액션 제안
- 실행: Notes 생성/캘린더 리마인더/메시지 드래프트 등(`src/tools/apple/auto_responder.py:204`)

5) 운영 컴포넌트
- 이벤트 버스: `src/integration/event_bus.py:1`(컴포넌트 간 비동기 decoupling)
- 로깅: `src/utils/logger.py:115`(바인딩된 로거 제공)
- 오류/재시도: `src/utils/error_handler.py:1`
- 성능/캐시: `src/utils/performance.py:1`
- 모니터링: `src/monitoring/dashboard.py:1`

## 🧩 핵심 컴포넌트 역할 요약

- Discord Bot: 수신/권한/세션 관리, 메시지 라우팅(`src/discord_bot/bot.py:1`)
- AI Handler: 도구 실행/LLM 호출을 조율(`src/discord_bot/ai_handler.py:1`)
- Decision Engine: 자연어 → 도구선택/계획 JSON(`src/ai_engine/decision_engine.py:1`)
- LLM Provider: Gemini/Mock 통합(`src/ai_engine/llm_provider.py:1`)
- MCP Registry: 도구 등록/발견/활성화 관리(`src/mcp/registry.py:1`)
- Notion/Apple Tools: 실제 작업 실행(`src/tools/notion/*`, `src/tools/apple/*`)
- Event Bus: 비동기 이벤트 기반 통신(`src/integration/event_bus.py:1`)
- Monitoring: 시스템/AI 메트릭 수집 및 대시보드(`src/monitoring/dashboard.py:1`)

## ⚙️ 설정(환경변수)

- Discord: `discord_bot_token`, `allowed_user_ids`, `admin_user_ids`
- AI(Gemini): `google_ai_api_key`, `ai_model`, `ai_temperature`
- Notion: `notion_api_token`, `notion_todo_database_id`, `notion_api_rate_limit`
- Apple MCP: `apple_mcp_server_url`
- 파일: `src/config.py:26` 설정 스키마 참고

## 🧪 예시 시나리오

- “내일 3시에 회의 일정 추가해줘”
  - Discord 수신 → AI Handler → LLM이 `notion_calendar` 선택/계획 → `CalendarTool.execute({action: create, ...})` → 성공 응답 반환
- “메모 남겨줘: 점심에 연구실 방문”
  - Discord 수신 → 도구 판단에서 `apple_notes` 또는 `notion_todo` 결정 → 해당 도구 실행 결과 반환
- Mail/Calendar 알림
  - Notification Monitor → Auto Responder 분석 → Notes 생성/캘린더 리마인더 액션 실행(확인 흐름 포함)

## 📚 추가 문서

- Apple MCP 설정 가이드: `docs/apple-mcp-setup.md:1`
- Notion 설정 가이드: `NOTION_SETUP.md:1`
