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
├── src/
│   ├── main.py                       # CLI 엔트리포인트 (Click)
│   ├── daemon.py                     # 데몬 실행 유틸리티
│   ├── config.py                     # 환경설정(.env)
│   ├── log_manager.py                # 로그 관리
│   ├── process_monitor.py            # 프로세스/리소스 모니터링
│   ├── cli/
│   │   ├── main.py                   # pai 스크립트 엔트리(모듈형)
│   │   └── commands/
│   │       ├── __init__.py
│   │       ├── service.py            # 서비스 시작/중지/상태
│   │       ├── testing.py            # 테스트 유틸리티
│   │       ├── monitoring.py         # 모니터링/통계 확인
│   │       ├── optimization.py       # 최적화 관련 명령
│   │       ├── tools.py              # 도구 관련 진단/실행
│   │       ├── notion.py             # Notion CLI
│   │       ├── apple_commands.py     # Apple MCP 서버 관리
│   │       ├── apple_apps_commands.py# Apple 앱 별 테스트/도움말
│   │       └── utils.py
│   ├── discord_bot/
│   │   ├── bot.py                    # Discord Bot 본체(이벤트/권한/세션)
│   │   ├── ai_handler.py             # 메시지 → 도구/LLM 실행 허브
│   │   ├── parser.py                 # 메시지 파서(선택적)
│   │   ├── router.py                 # 라우팅(선택적)
│   │   ├── message_queue.py          # 메시지 큐
│   │   ├── session.py                # 대화 세션 관리
│   │   └── __init__.py
│   ├── ai_engine/
│   │   ├── decision_engine.py        # 에이전틱 의사결정(도구선택/계획)
│   │   ├── llm_provider.py           # Gemini/Mock LLM 프로바이더/매니저
│   │   ├── natural_language.py       # NL 처리 유틸/파이프라인
│   │   ├── response_generator.py     # 응답 생성 로직
│   │   ├── prompt_templates.py       # 프롬프트 템플릿
│   │   ├── prompt_optimizer.py       # 프롬프트 최적화
│   │   ├── mcp_integration.py        # MCP 연계 유틸
│   │   └── __init__.py
│   ├── memory/                       # 장기기억/임베딩/RAG
│   │   ├── embedding_provider.py
│   │   ├── enhanced_models.py
│   │   ├── memory_manager.py
│   │   ├── models.py
│   │   ├── rag_engine.py
│   │   ├── simple_memory_manager.py
│   │   ├── vector_store.py
│   │   └── __init__.py
│   ├── mcp/                          # MCP 프로토콜/도구 런타임
│   │   ├── base_tool.py              # Tool 인터페이스/Result/메타데이터
│   │   ├── protocol.py               # MCP 프로토콜 정의
│   │   ├── executor.py               # 도구 실행기
│   │   ├── registry.py               # 도구 레지스트리(발견/등록/활성화)
│   │   ├── mcp_integration.py
│   │   ├── simple_apple_client.py    # 간이 Apple 클라이언트
│   │   ├── apple_client.py
│   │   ├── apple_agent_v2.py         # Apple 에이전트(V2)
│   │   ├── apple_tools.py            # Apple 도구 모음
│   ├── tools/                        # 실제 실행 도구(앱/서비스)
│   │   ├── calculator_tool.py        # 계산기
│   │   ├── echo_tool.py              # 에코
│   │   ├── apple/
│   │   │   ├── auto_responder.py     # 알림 자동응답(에이전틱)
│   │   │   ├── notification_monitor.py# macOS 알림 모니터
│   │   │   └── notes_tool.py         # Apple Notes MCP 도구(시뮬레이션)
│   │   ├── notion/
│   │   │   ├── client.py             # Notion API 클라이언트
│   │   │   ├── todo_tool.py          # Notion 할일 도구
│   │   │   ├── calendar_tool.py      # Notion 캘린더 도구
│   │   │   ├── operations.py         # 공통 연산/유틸
│   │   │   └── nlp_parser.py         # 자연어 → Notion 파라미터 보조
│   │   └── web_scraper/
│   │       ├── web_scraper_tool.py   # 범용 스크래퍼 도구
│   │       ├── scheduler.py          # 스케줄러
│   │       ├── code_validator.py     # 코드 검증
│   │       ├── crawler_generator.py  # 크롤러 생성기
│   │       ├── html_analyzer.py      # HTML 분석
│   │       ├── enhanced_inha_crawler.py
│   │       ├── inha_notice_crawler.py
│   │       └── notice_summary_test.py
│   ├── automation/                   # (현재 비어있음)
│   ├── monitoring/
│   │   ├── dashboard.py              # 메트릭/대시보드
│   │   └── __init__.py
│   ├── utils/
│   │   ├── logger.py                 # 로깅 시스템(loguru)
│   │   ├── error_handler.py          # 오류/재시도/분류
│   │   └── performance.py            # 캐시/리소스풀/모니터링
│   └── data/                         # (현재 비어있음)
├── tests/                            # (현재 비어있음)
├── logs/                             # 런타임 로그
├── data/                             # 로컬 DB/벡터 저장소
├── scripts/
│   └── setup-apple-permissions.sh    # macOS 권한 안내 스크립트
├── docs/
│   └── apple-mcp-setup.md            # Apple MCP 설정 가이드
├── external/
│   └── apple-mcp/                    # Apple MCP 서버(필요 시 설치)
├── .env
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 🛠️ 기술 스택

- **Python 3.11+**
- **Google Gemini 2.5 Pro API** - AI 엔진
- **Discord.py** - Discord Bot
- **ChromaDB** - 벡터 데이터베이스
- **Notion API** - 일정/할일 관리
- **Beautiful Soup / Scrapy** - 웹 스크래핑
- **Click/Typer** - CLI 프레임워크

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
