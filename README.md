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
│   ├── main.py                 # CLI 메인 엔트리포인트
│   ├── cli/                    # CLI 명령어 정의
│   ├── discord_bot/            # Discord Bot 구현
│   ├── ai_engine/              # AI 비서 엔진
│   ├── memory/                 # 장기기억 시스템 (RAG + 임베딩)
│   ├── mcp/                    # MCP 프로토콜 구현
│   ├── tools/                  # MCP 도구들
│   ├── automation/             # 자동화 시스템
│   ├── data/                   # 데이터 관리 (SQLite)
│   └── utils/                  # 유틸리티 함수
├── tests/                      # 테스트
├── logs/                       # 로그 파일
└── data/                       # 로컬 데이터베이스 파일
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
