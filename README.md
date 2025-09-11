# Personal AI Assistant

**에이전틱 AI 기반 지능형 개인 비서** - Discord를 통해 자연어 명령을 받아 ReAct 엔진이 스스로 판단하고 MCP 도구를 활용하여 자율적으로 임무를 완수하는 차세대 AI 시스템

## 🎯 핵심 기능

- **🤖 에이전틱 AI**: Google Gemini 2.5 기반 ReAct 엔진으로 목표 달성까지 자율적 사고-행동-관찰 루프 실행
- **📱 Discord Bot**: 휴대폰으로 언제 어디서나 AI 비서와 자연어로 소통
- **🧠 고급 계획 수립**: 복잡한 목표를 단계별로 분해하고 동적으로 적응하는 Planning Engine
- **🔧 MCP 도구 통합**: Notion, Apple 시스템, 파일시스템 등 다양한 도구를 상황에 맞게 자동 선택 및 실행
- **🧠 장기기억 시스템**: RAG 기반으로 과거 행동 패턴을 학습하여 개인화된 서비스 제공
- **⚡ 실시간 적응**: 실행 중 문제 발생 시 Self-Repair로 자동 오류 수정 및 재시도
- **🕐 24/7 백그라운드**: macOS에서 상시 대기하며 능동적/수동적 작업 처리

## 🛠️ 기술 스택

### 🧠 AI & Machine Learning
- **Google Gemini 2.5 Flash/Pro** - 차세대 멀티모달 AI 엔진
- **ChromaDB** - 벡터 데이터베이스 및 RAG 검색
- **ReAct Framework** - 에이전틱 AI 추론 및 행동 패러다임

### 🐍 Backend & Framework  
- **Python 3.11+** - 주요 개발 언어
- **Discord.py** - Discord Bot 인터페이스
- **Pydantic** - 데이터 검증 및 설정 관리
- **AsyncIO** - 비동기 처리

### 🔧 MCP & 도구 통합
- **Model Context Protocol (MCP)** - 도구 통합 표준
- **Notion API** - 일정/할일 관리
- **Apple Automation** - macOS 시스템 통합
- **TypeScript** - Apple MCP 서버

### 🗄️ 데이터 & 저장소
- **SQLite** - 세션 및 메타데이터 저장  
- **ChromaDB** - 벡터 임베딩 저장소
- **File System** - 로그 및 캐시 관리

### 🛡️ 보안 & 안정성
- **Path Validation** - 파일시스템 접근 제어
- **Rate Limiting** - API 호출 제한
- **Error Handling** - 포괄적 오류 처리
- **Self-Repair** - 자동 오류 복구

## 🤖 에이전틱 모드 정책

### 🎯 핵심 원칙
- **순수 AI 추론**: 키워드 매칭이나 규칙 기반 분류에 의존하지 않고 LLM이 직접 상황을 이해하고 도구를 선택
- **Chain of Thought**: 모든 의사결정 과정을 투명하게 기록하여 추론 과정 추적 가능
- **Self-Repair**: 실행 실패 시 에러 정보와 이전 파라미터를 분석하여 LLM이 스스로 교정 후 재시도

### ⚙️ 환경 변수 제어
```bash
# 에이전틱 AI 동작 모드
PAI_MOCK_MODE=off                    # off/echo/heuristic
PAI_PARAM_NORMALIZATION_MODE=minimal # off/minimal/full  
PAI_SELF_REPAIR_ATTEMPTS=2           # 자동 교정 재시도 횟수

# 성능 최적화
PAI_COMPLEXITY_THRESHOLD=7           # ReAct 엔진 활성화 복잡도 임계값
PAI_MAX_ITERATIONS=15               # 최대 ReAct 루프 반복 횟수
PAI_TIMEOUT_SECONDS=600             # 작업 타임아웃 (초)
```

### 🚀 적응적 라우팅
- **단순 요청** (복잡도 < 7): 기존 효율적인 원샷 방식 활용
- **복잡한 요청** (복잡도 ≥ 7): ReAct 엔진으로 다단계 처리
- **초복잡 요청** (복잡도 ≥ 8): 고급 계획 수립 시스템 활용

## 🚀 에이전틱 AI의 특별함

### ReAct (Reasoning and Acting) 엔진
전통적인 "한 번 호출하고 끝"이 아닌, **사고 → 행동 → 관찰** 루프를 목표 달성까지 반복:

```
1. 🤔 Thought: "사용자가 일정 추가를 원한다. 먼저 Notion 캘린더를 확인해보자"
2. 🔧 Action: notion_calendar.list() 실행
3. 👀 Observation: "기존 일정 확인 완료. 이제 새 일정을 추가하자"
4. 🔧 Action: notion_calendar.create() 실행
5. 📋 Final Answer: "회의 일정이 성공적으로 추가되었습니다"
```

### 고급 계획 수립 시스템
복잡한 요청을 자동으로 여러 단계로 분해하고 각 단계의 의존성을 관리:
- **목표 분해**: "프레젠테이션 준비"를 "자료 수집 → 구조 설계 → 슬라이드 작성 → 리허설" 단계로 분해
- **동적 적응**: 중간 단계 실패 시 대안 전략 자동 생성
- **병렬 처리**: 독립적인 작업들을 동시 실행으로 효율성 극대화

### Self-Repair 시스템
도구 실행 실패 시 에러 분석 후 매개변수를 자동 수정하여 재시도:
```python
# 매개변수 오류 자동 수정 예시
"source" → "src" 자동 변환
"destination" → "dst" 자동 변환
누락된 "action" 매개변수 기본값 자동 추가
```

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

## 📋 주요 명령어 예시

Discord에서 다음과 같은 자연어 명령을 사용할 수 있습니다:

### 🗓️ 일정 관리
- `내일 오후 3시에 팀 회의 일정 추가해줘`
- `이번 주 금요일에 뭐 있는지 확인해줘`
- `다음 주 월요일 회의를 화요일로 변경해줘`

### ✅ 할일 관리  
- `오늘 할 일 목록 보여줘`
- `중요한 프로젝트 마감일 임박한 것들 알려줘`
- `"보고서 작성" 할일을 완료로 표시해줘`

### 📁 파일 관리
- `바탕화면에 "프로젝트" 폴더 만들고 관련 파일들 정리해줘`
- `문서 폴더에서 PDF 파일들만 찾아서 새 폴더로 이동시켜줘`

### 📝 메모 작성
- `오늘 회의 내용을 Apple Notes에 정리해줘`
- `아이디어 메모 찾아서 보여줘`

### 🔍 정보 검색 & 분석
- `AI 관련 최신 뉴스 찾아서 요약해줘`
- `중요한 메일이 오면 알려줘`

### 🧮 계산 & 분석
- `프로젝트 예산 계산해줘: 기획 500만원, 개발 2000만원, 마케팅 300만원`
- `월 지출 대비 수입 비율 계산해줘`

**특징**: 단순 명령뿐만 아니라 복잡한 **멀티스텝 작업**도 자동으로 분해하여 처리합니다!

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

## 🏗️ 시스템 아키텍처

### 📊 시스템 구성도

```mermaid
graph TB
    subgraph "사용자 인터페이스"
        A[Discord Bot] --> B[AI Handler]
        A --> C[Session Manager]
        A --> D[Message Queue]
    end
    
    subgraph "에이전틱 AI 엔진"
        B --> E[ReAct Engine]
        E --> F[Planning Engine]
        E --> G[Goal Manager]
        E --> H[Dynamic Adapter]
        E --> I[LLM Provider]
    end
    
    subgraph "MCP 도구 생태계"
        J[Tool Registry] --> K[Notion Tools]
        J --> L[Apple Tools]
        J --> M[Filesystem Tools]
        J --> N[Calculator Tools]
        J --> O[Other Tools]
    end
    
    subgraph "통합 제어층"
        P[Agentic Controller] --> E
        P --> J
        Q[Event Bus] --> P
        R[Container] --> P
    end
    
    subgraph "메모리 & 학습"
        S[Vector Store] --> T[RAG Engine]
        S --> U[Memory Manager]
        S --> V[Embedding Provider]
    end
    
    subgraph "외부 서비스"
        W[Google Gemini API]
        X[Notion API]
        Y[Apple MCP Server]
        Z[ChromaDB]
    end
    
    B --> P
    I --> W
    K --> X
    L --> Y
    S --> Z
    
    style A fill:#e1f5fe
    style E fill:#f3e5f5
    style J fill:#e8f5e8
    style P fill:#fff3e0
    style S fill:#fce4ec
```

### 🔄 데이터 흐름도

```mermaid
sequenceDiagram
    participant U as 사용자
    participant D as Discord Bot
    participant A as AI Handler
    participant R as ReAct Engine
    participant T as MCP Tools
    participant L as LLM Provider
    
    U->>D: 자연어 명령
    D->>A: 메시지 전달
    A->>R: 에이전틱 처리 요청
    
    loop ReAct 루프
        R->>L: 사고 생성 요청
        L->>R: 현재 상황 분석
        R->>T: 도구 실행
        T->>R: 실행 결과
        R->>L: 관찰 및 다음 행동 결정
    end
    
    R->>A: 최종 결과
    A->>D: 응답 메시지
    D->>U: 결과 전달
```

### 📁 완전한 프로젝트 구조

```
Personal-AI-Assistant/
├── 🚀 main.py                           # Discord Bot 메인 런처
├── 📋 pyproject.toml                     # Poetry 프로젝트 설정
├── ⚙️ .env                              # 환경 변수 설정
├── 📄 README.md                         # 프로젝트 문서
├── 📄 PROJECT_PLAN.md                   # 개발 로드맵
├── 📄 DEVELOPMENT_LOG.md                # 개발 일지
├── 📄 requirements.txt                  # pip 의존성 (Poetry 백업)
│
├── 📁 src/                              # 메인 소스코드
│   ├── 📄 __init__.py
│   ├── ⚙️ config.py                     # 전역 설정 관리
│   ├── 🛠️ daemon.py                     # 데몬 프로세스 관리
│   ├── 📊 log_manager.py                # 통합 로깅 시스템
│   ├── 📋 main.py                       # CLI 진입점
│   ├── 🔍 process_monitor.py            # 프로세스 모니터링
│   │
│   ├── 🧠 ai_engine/                    # 에이전틱 AI 코어
│   │   ├── 📄 __init__.py
│   │   ├── 🧠 agent_state.py            # Agent 상태 관리 (Scratchpad)
│   │   ├── 🎯 decision_engine.py        # 의사결정 및 도구 선택 엔진
│   │   ├── 🔄 dynamic_adapter.py        # 동적 적응 및 Self-Repair
│   │   ├── 📝 goal_manager.py           # 목표 분해 및 계층 관리
│   │   ├── 🤖 llm_provider.py           # Google Gemini API 연동
│   │   ├── 📊 mcp_integration.py        # MCP 프로토콜 통합
│   │   ├── 🎯 multi_agent_system.py     # 멀티 에이전트 조정
│   │   ├── 🗣️ natural_language.py       # 자연어 이해 및 의도 분석
│   │   ├── 📋 planning_engine.py        # 고급 계획 수립 시스템
│   │   ├── 🎨 prompt_optimizer.py       # 프롬프트 최적화
│   │   ├── 📝 prompt_templates.py       # 에이전틱 전용 템플릿
│   │   ├── 🔄 react_engine.py           # ReAct 루프 실행 엔진
│   │   └── 📋 response_generator.py     # 응답 생성 및 포맷팅
│   │
│   ├── 🛠️ mcp/                         # MCP 프로토콜 구현
│   │   ├── 📄 __init__.py
│   │   ├── 🍎 apple_agent_v2.py         # Apple 시스템 에이전트
│   │   ├── 🍎 apple_client.py           # Apple MCP 클라이언트
│   │   ├── 🍎 apple_mcp_manager.py      # Apple MCP 매니저
│   │   ├── 🍎 apple_tools.py            # Apple 도구 모음
│   │   ├── 🔧 base_tool.py              # 기본 도구 인터페이스
│   │   ├── ⚡ executor.py                # 도구 실행 및 Self-Repair
│   │   ├── 🔗 mcp_integration.py        # MCP 통합 레이어
│   │   ├── 📡 protocol.py               # MCP 프로토콜 정의
│   │   └── 📋 registry.py               # 도구 등록 및 메타데이터
│   │
│   ├── 🔧 tools/                        # 구체적 도구 구현체
│   │   ├── 🍎 apple/                    # Apple 시스템 통합
│   │   │   ├── 📄 __init__.py
│   │   │   ├── 🤖 auto_responder.py     # 지능형 자동 응답
│   │   │   ├── 📅 calendar_tool.py      # Apple 캘린더
│   │   │   ├── 👥 contacts_tool.py      # Apple 연락처
│   │   │   ├── 📧 mail_tool.py          # Apple 메일
│   │   │   ├── 🗺️ maps_tool.py          # Apple 지도
│   │   │   ├── 💬 messages_tool.py      # Apple 메시지
│   │   │   ├── 📝 notes_tool.py         # Apple Notes
│   │   │   ├── 🔔 notification_monitor.py # 알림 모니터링
│   │   │   └── ⏰ reminders_tool.py     # Apple 미리 알림
│   │   │
│   │   ├── 📝 notion/                   # Notion 통합
│   │   │   ├── 📄 __init__.py
│   │   │   ├── 📅 calendar_tool.py      # Notion 캘린더
│   │   │   ├── 🔗 client.py             # Notion API 클라이언트
│   │   │   └── ✅ todo_tool.py          # Notion 할일 관리
│   │   │
│   │   ├── 🧮 calculator_tool.py        # 계산 도구
│   │   ├── 📁 filesystem_tool.py        # 안전한 파일시스템 작업
│   │   └── 🕐 system_time_tool.py       # 시간 조회 도구
│   │
│   ├── 💬 discord_bot/                  # Discord 인터페이스
│   │   ├── 📄 __init__.py
│   │   ├── 🤖 ai_handler.py             # AI 엔진 연동 브리지
│   │   ├── 🤖 bot.py                    # Discord Bot 메인
│   │   ├── 📜 handlers_deprecated.py    # 레거시 핸들러 (삭제 예정)
│   │   ├── 📨 message_queue.py          # 비동기 메시지 처리
│   │   ├── 📝 parser.py                 # 명령어 파싱
│   │   ├── 🔀 router.py                 # 요청 라우팅
│   │   └── 💾 session.py                # 대화 세션 관리
│   │
│   ├── 🎮 integration/                  # 시스템 통합 레이어
│   │   ├── 📄 __init__.py
│   │   ├── 🎯 agentic_controller.py     # 에이전틱 AI 통합 컨트롤러
│   │   ├── 📦 container.py              # 의존성 주입 컨테이너
│   │   ├── 📡 event_bus.py              # 비동기 이벤트 버스
│   │   ├── 🔌 interfaces.py             # 시스템 인터페이스 정의
│   │   └── 🔄 legacy_adapter.py         # 레거시 시스템 어댑터
│   │
│   ├── 🧠 memory/                       # 장기기억 시스템
│   │   ├── 📄 __init__.py
│   │   ├── 🔍 embedding_provider.py     # 임베딩 생성 및 관리
│   │   ├── 💾 memory_manager.py         # 장기기억 관리
│   │   ├── 🔍 rag_engine.py             # RAG 기반 검색 엔진
│   │   └── 📊 vector_store.py           # ChromaDB 벡터 저장소
│   │
│   ├── 📊 monitoring/                   # 모니터링 & 대시보드
│   │   ├── 📄 __init__.py
│   │   └── 📊 dashboard.py              # 실시간 모니터링 대시보드
│   │
│   ├── ⚙️ utils/                        # 유틸리티 모듈
│   │   ├── 📄 __init__.py
│   │   ├── ❌ error_handler.py          # 포괄적 오류 처리
│   │   ├── 📝 logger.py                 # 고급 로깅 시스템
│   │   └── ⚡ performance.py            # 성능 최적화 및 리소스 관리
│   │
│   ├── 🎯 cli/                          # CLI 명령어 인터페이스
│   │   ├── 📄 __init__.py
│   │   ├── 📋 main.py                   # CLI 메인 진입점
│   │   └── 📁 commands/                 # CLI 명령어 모음
│   │       ├── 📄 __init__.py
│   │       ├── 🍎 apple.py              # Apple 관련 CLI
│   │       ├── 🧠 memory.py             # 메모리 관리 CLI
│   │       ├── 📊 monitoring.py         # 모니터링 CLI
│   │       ├── 📝 notion.py             # Notion 관련 CLI
│   │       └── 🔧 tools.py              # 도구 관리 CLI
│   │
│   ├── 📁 automation/                   # 자동화 스크립트
│   └── 📁 data/                         # 데이터 처리 모듈
│
├── 📁 external/                         # 외부 의존성
│   └── 🍎 apple-mcp/                    # Apple MCP 서버 (TypeScript)
│       ├── 📄 package.json
│       ├── 📄 tsconfig.json
│       ├── 📄 index.ts                  # MCP 서버 메인
│       ├── 📄 tools.ts                  # Apple 도구 정의
│       ├── 📄 test-runner.ts            # 테스트 러너
│       ├── 📄 manifest.json             # MCP 매니페스트
│       ├── 📄 bun.lockb                 # Bun 패키지 잠금
│       ├── 📁 tests/                    # 테스트 파일
│       └── 📁 utils/                    # 유틸리티 함수
│
├── 📁 data/                             # 런타임 데이터
│   ├── 💾 discord_bot.pid               # Discord Bot PID
│   ├── 💾 message_queue.db              # 메시지 큐 데이터베이스
│   ├── 💾 prompt_optimization.db        # 프롬프트 최적화 DB
│   ├── 💾 sessions.db                   # 세션 데이터베이스
│   ├── 📁 crawl_results/                # 웹 크롤링 결과
│   └── 📁 chroma_db/                    # ChromaDB 벡터 저장소
│
├── 📁 logs/                             # 시스템 로그
│   ├── 📄 personal_ai_assistant.log     # 메인 시스템 로그
│   ├── 📄 discord_bot.log               # Discord Bot 로그
│   ├── 📄 discord_service.log           # Discord 서비스 로그
│   ├── 📄 ai_engine.log                 # AI 엔진 로그
│   └── 📄 errors.log                    # 오류 전용 로그
│
├── 📁 docs/                             # 프로젝트 문서
│   ├── 📄 Agentic_AI.md                 # 에이전틱 AI 개념 설명
│   ├── 📄 Agentic_AI_Transformation_Plan.md # AI 전환 계획서
│   ├── 📄 apple-mcp-setup.md            # Apple MCP 설정 가이드
│   └── 📄 MCP_TOOLS.md                  # MCP 도구 상세 문서
│
├── 📁 scripts/                          # 설정 및 유틸리티 스크립트
│   ├── 📄 setup-apple-permissions.sh    # Apple 권한 설정
│   ├── 📄 gemini_json_probe.py          # Gemini API 테스트
│   └── 📄 gemini_minimal_text.py        # Gemini 최소 텍스트 테스트
│
└── 📁 tests/                            # 테스트 디렉토리 (미래 확장용)
```

### 🧠 AI Engine (에이전틱 AI 코어)
### 🧠 AI Engine (에이전틱 AI 코어)
- **react_engine.py**: ReAct 루프 실행 엔진 (사고-행동-관찰)
- **planning_engine.py**: 고급 계획 수립 및 목표 분해
- **goal_manager.py**: 목표 계층 관리 및 의존성 처리
- **dynamic_adapter.py**: 실행 중 동적 적응 및 오류 복구
- **llm_provider.py**: Google Gemini API 연동

### 🛠️ MCP 도구 생태계
- **registry.py**: 도구 등록 및 메타데이터 관리
- **executor.py**: 도구 실행 및 Self-Repair
- **notion/**: Notion API (할일/일정)
- **apple/**: Apple 시스템 통합
- **filesystem_tool.py**: 안전한 파일시스템 작업

### 🎮 통합 제어층
- **agentic_controller.py**: 에이전틱 AI 통합 컨트롤러
- **event_bus.py**: 비동기 이벤트 처리
- **container.py**: 의존성 주입 컨테이너

### 💬 Discord Bot Interface
- **bot.py**: Discord Bot 메인
- **ai_handler.py**: AI 엔진 연동 브리지
- **session.py**: 대화 세션 관리
- **message_queue.py**: 비동기 메시지 처리

### 🧠 메모리 & 학습 시스템
- **vector_store.py**: ChromaDB 벡터 저장소
- **rag_engine.py**: RAG 기반 검색
- **memory_manager.py**: 장기기억 관리
- **embedding_provider.py**: 임베딩 생성

## 🧰 사용 가능한 MCP 도구

### 🛠️ MCP 도구 생태계
```
src/mcp/ & src/tools/
├── registry.py              # 도구 등록 및 메타데이터 관리
├── executor.py              # 도구 실행 및 Self-Repair
├── base_tool.py             # 통합 도구 인터페이스
├── notion/                  # Notion API (할일/일정)
├── apple/                   # Apple 시스템 통합
├── filesystem_tool.py       # 안전한 파일시스템 작업
└── calculator_tool.py       # 계산 도구
```

### 🎮 통합 제어층
```
src/integration/
├── agentic_controller.py    # 에이전틱 AI 통합 컨트롤러
├── container.py             # 의존성 주입 컨테이너  
├── event_bus.py             # 비동기 이벤트 처리
└── interfaces.py            # 시스템 인터페이스 정의
```

### 💬 Discord Bot Interface
```
src/discord_bot/
├── bot.py                   # Discord Bot 메인
├── ai_handler.py            # AI 엔진 연동 브리지
├── session.py               # 대화 세션 관리
├── message_queue.py         # 비동기 메시지 처리
├── parser.py                # 명령어 파싱
└── router.py                # 요청 라우팅
```

### 🧠 메모리 & 학습 시스템
```
src/memory/
├── vector_store.py          # ChromaDB 벡터 저장소
├── rag_engine.py            # RAG 기반 검색
├── memory_manager.py        # 장기기억 관리
└── embedding_provider.py    # 임베딩 생성
```

## 🧰 사용 가능한 MCP 도구

AI가 자율적으로 선택하여 실행하는 도구들입니다. 각 도구는 특정 상황에서 자동으로 호출됩니다.
```
src/memory/
├── vector_store.py          # ChromaDB 벡터 저장소
├── rag_engine.py            # RAG 기반 검색
├── memory_manager.py        # 장기기억 관리
└── embedding_provider.py    # 임베딩 생성
```

### 📁 전체 프로젝트 구조
```
Personal-AI-Assistant/
├── 🚀 main.py                      # Discord Bot 런처
├── 📁 src/
│   ├── 🧠 ai_engine/               # 에이전틱 AI 코어
│   ├── 🛠️ mcp/                     # MCP 프로토콜 구현
│   ├── 🔧 tools/                   # 구체적 도구 구현
│   ├── 💬 discord_bot/             # Discord 인터페이스
│   ├── 🎮 integration/             # 시스템 통합 레이어
│   ├── 🧠 memory/                  # 장기기억 시스템
│   ├── 📊 monitoring/              # 모니터링 & 대시보드
│   ├── ⚙️ utils/                   # 유틸리티 (로깅, 성능, 오류처리)
│   └── 🎯 cli/                     # CLI 명령어 인터페이스
├── 📁 external/
│   └── 🍎 apple-mcp/               # Apple MCP 서버 (TypeScript)
├── 📁 data/                        # 런타임 데이터
│   ├── 💾 *.db                     # SQLite 데이터베이스
│   └── 🔍 chroma_db/               # 벡터 저장소
├── 📁 logs/                        # 시스템 로그
├── 📁 docs/                        # 문서 및 가이드
├── 📁 scripts/                     # 설정 스크립트
├── ⚙️ .env                         # 환경 설정
├── 📋 pyproject.toml               # Python 프로젝트 설정
└── 📄 README.md                    # 프로젝트 문서
```
```
src/memory/
├── vector_store.py          # ChromaDB 벡터 저장소
├── rag_engine.py            # RAG 기반 검색
├── memory_manager.py        # 장기기억 관리
└── embedding_provider.py    # 임베딩 생성
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

AI가 자율적으로 선택하여 실행하는 도구들입니다. 각 도구는 특정 상황에서 자동으로 호출됩니다.

### 📝 Notion 통합
- **`notion_todo`**: 할일 생성/수정/완료/삭제, 우선순위 관리, 마감일 설정
- **`notion_calendar`**: 일정 생성/수정/삭제, 시간대 처리, 참석자 관리

### 🗂️ 파일시스템 관리  
- **`filesystem`**: 안전한 파일/폴더 작업 (생성/이동/복사/삭제/목록조회)
- 허용 경로 내에서만 작업, 자동 백업 및 권한 검증

### 🍎 Apple 시스템 통합
- **`apple_notes`**: Apple Notes 메모 생성/검색/수정
- **`apple_calendar`**: Apple 캘린더 일정 관리
- **`apple_contacts`**: 연락처 검색 및 관리
- **`apple_messages`**: 메시지 전송 및 읽기
- **`apple_reminders`**: 미리 알림 생성 및 관리

### 🧮 유틸리티
- **`calculator`**: 수식 계산 및 단위 변환
- **`system_time`**: 현재 시간 조회 (일정/할일 날짜 계산용)

### 🔍 정보 검색 (개발 중)
- **`web_scraper`**: 웹 정보 수집 및 요약 (실험적)
- **`email_monitor`**: 이메일 모니터링 및 알림 (계획 중)

**특징**: AI가 상황에 맞는 도구를 자동 선택하고, 실패 시 Self-Repair로 매개변수를 수정하여 재시도합니다.

##  고급 설정

### 환경 변수 설정
`.env` 파일에서 다음 항목들을 설정할 수 있습니다:

```bash
# AI 엔진 설정
GOOGLE_AI_API_KEY=your_gemini_api_key
AI_MODEL=gemini-2.5-flash                # 또는 gemini-2.5-pro
AI_TEMPERATURE=0.7
AI_MAX_TOKENS=8192

# Discord Bot 설정  
DISCORD_BOT_TOKEN=your_discord_bot_token
ALLOWED_USER_IDS=123456789,987654321    # 허용된 사용자 ID
ADMIN_USER_IDS=123456789               # 관리자 사용자 ID

# Notion 통합
NOTION_API_TOKEN=your_notion_token
NOTION_TODO_DATABASE_ID=your_database_id

# 에이전틱 AI 제어
PAI_SELF_REPAIR_ATTEMPTS=2             # 자동 재시도 횟수
PAI_MAX_ITERATIONS=15                  # 최대 ReAct 루프 반복
PAI_TIMEOUT_SECONDS=600               # 작업 타임아웃 (초)
PAI_COMPLEXITY_THRESHOLD=7            # ReAct 활성화 임계값

# Apple 시스템 통합 (macOS 전용)
APPLE_MCP_AUTOSTART=false             # 자동 시작 여부
APPLE_MCP_PORT=3001                   # MCP 서버 포트

# 메모리 & 성능
MAX_MEMORY_USAGE=8192                 # 최대 메모리 사용량(MB)
VECTOR_DB_PATH=data/chroma_db         # 벡터 DB 경로
```

### 고급 CLI 명령어
```bash
# 시스템 상태 모니터링
poetry run pai monitoring dashboard
poetry run pai monitoring logs --tail
poetry run pai monitoring process-message "test message"

# 도구 관리
poetry run pai tools list              # 사용 가능한 도구 목록
poetry run pai tools info notion_todo  # 특정 도구 정보
poetry run pai tools stats             # 도구 사용 통계

# Apple 시스템 관리 (macOS)
poetry run pai apple install           # Apple MCP 서버 설치
poetry run pai apple start --background # 백그라운드 실행
poetry run pai apple setup-permissions # 권한 설정

# 메모리 관리
poetry run pai memory status           # 메모리 사용량 확인
poetry run pai memory cleanup          # 메모리 정리
```

## 📊 모니터링 & 로깅

### 실시간 모니터링
- **성능 지표**: 응답 시간, 도구 호출 성공률, 메모리 사용량
- **에이전틱 통계**: ReAct 루프 반복 횟수, Self-Repair 성공률
- **사용자 활동**: 명령어 빈도, 세션 지속 시간

### 로그 시스템
```bash
logs/
├── personal_ai_assistant.log  # 메인 시스템 로그
├── discord_bot.log           # Discord 관련 로그
├── ai_engine.log            # AI 엔진 및 ReAct 로그
└── errors.log               # 오류 전용 로그
```

## 🤝 기여하기

1. 이 저장소를 포크합니다
2. 새로운 기능 브랜치를 생성합니다 (`git checkout -b feature/amazing-feature`)
3. 변경사항을 커밋합니다 (`git commit -m 'Add amazing feature'`)
4. 브랜치에 푸시합니다 (`git push origin feature/amazing-feature`)
5. Pull Request를 생성합니다

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 🆘 지원 & 문제 해결

### 자주 묻는 질문
- **Q: ReAct 엔진이 너무 느려요**
  - A: `PAI_COMPLEXITY_THRESHOLD`를 높여서 단순한 요청은 원샷 방식으로 처리하세요
  
- **Q: 도구 실행이 자꾸 실패해요**
  - A: `PAI_SELF_REPAIR_ATTEMPTS`를 늘리거나 로그를 확인해서 권한 문제를 해결하세요

- **Q: Apple 도구가 작동하지 않아요**
  - A: `poetry run pai apple setup-permissions`로 권한을 설정하고 MCP 서버를 실행하세요

### 문제 신고
- [GitHub Issues](https://github.com/dosiri24/Personal-AI-Assistant/issues)에서 버그를 신고하거나 기능을 제안하세요
- 로그 파일과 함께 구체적인 재현 방법을 제공해주세요

---

**Made with ❤️ by AI & Human Collaboration**

