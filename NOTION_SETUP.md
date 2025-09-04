# Notion 통합 설정 가이드

이 가이드는 Personal AI Assistant의 Notion 통합 기능을 설정하고 사용하는 방법을 설명합니다.

## 1. Notion API 토큰 생성

1. [Notion Developers](https://developers.notion.com/)에 접속
2. "New integration" 클릭
3. 통합 이름 설정 (예: "Personal AI Assistant")
4. 워크스페이스 선택
5. "Submit" 클릭
6. "Internal Integration Token" 복사

## 2. 환경 변수 설정

환경 변수 또는 `.env` 파일에 토큰을 설정합니다:

```bash
export NOTION_API_TOKEN="secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

또는 `.env` 파일에 추가:
```
NOTION_API_TOKEN=secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## 3. 데이터베이스 생성 및 공유

### 캘린더 데이터베이스
1. Notion에서 새 페이지 생성
2. 데이터베이스 추가 (Table 선택)
3. 필수 속성 설정:
   - **Title** (제목): 기본으로 있음
   - **Date** (날짜): Date 타입
   - **Description** (설명): Text 타입 (선택사항)
   - **Location** (장소): Text 타입 (선택사항)
   - **Priority** (우선순위): Select 타입 (High, Medium, Low)

### Todo 데이터베이스
1. Notion에서 새 페이지 생성
2. 데이터베이스 추가 (Table 선택)
3. 필수 속성 설정:
   - **Title** (제목): 기본으로 있음
   - **Status** (상태): Checkbox 타입
   - **Priority** (우선순위): Select 타입 (High, Medium, Low)
   - **Due Date** (마감일): Date 타입 (선택사항)
   - **Description** (설명): Text 타입 (선택사항)

### 통합 권한 부여
1. 데이터베이스 페이지에서 오른쪽 상단 "..." 메뉴 클릭
2. "Connect to" 선택
3. 생성한 통합 선택 ("Personal AI Assistant")

## 4. CLI 명령어 사용법

### 연결 테스트
```bash
# 환경변수에서 토큰 사용
python -m src.cli.main notion test-connection

# 직접 토큰 제공
python -m src.cli.main notion test-connection --token "secret_xxxxxxxx"
```

### 캘린더 이벤트 관리

#### 이벤트 생성
```bash
python -m src.cli.main notion create-event \
  --title "팀 미팅" \
  --date "2024-01-15 14:00" \
  --description "주간 팀 미팅"
```

#### 이벤트 목록 조회
```bash
python -m src.cli.main notion list-events --limit 5
```

### Todo 관리

#### Todo 생성
```bash
python -m src.cli.main notion create-todo \
  --title "문서 작성" \
  --priority high \
  --due-date "2024-01-20" \
  --description "프로젝트 문서 작성"
```

#### Todo 목록 조회
```bash
# 모든 Todo
python -m src.cli.main notion list-todos

# 미완료 Todo만
python -m src.cli.main notion list-todos --filter pending

# 완료된 Todo만
python -m src.cli.main notion list-todos --filter completed

# 기한 지난 Todo만
python -m src.cli.main notion list-todos --filter overdue
```

## 5. 자연어 날짜 지원

날짜는 다양한 형식으로 입력할 수 있습니다:

- ISO 형식: `2024-01-15` 또는 `2024-01-15T14:00:00`
- 상대 날짜: `tomorrow`, `next week`, `in 3 days`
- 한국어: `내일`, `다음주`, `3일 후`

## 6. 문제 해결

### 토큰 오류
- 토큰이 올바른지 확인
- 통합이 워크스페이스에 추가되었는지 확인

### 데이터베이스 접근 오류
- 데이터베이스에 통합 권한이 부여되었는지 확인
- 데이터베이스 ID가 올바른지 확인

### 속성 오류
- 데이터베이스의 속성 이름과 타입이 올바른지 확인
- 필수 속성이 모두 존재하는지 확인

## 7. 추가 기능 (예정)

- 이벤트 수정/삭제
- Todo 상태 변경
- 반복 이벤트 지원
- 알림 설정
- 태그 및 카테고리 관리

## 8. 지원되는 MCP 도구

현재 구현된 MCP 도구들:
- `CalendarTool`: 캘린더 이벤트 관리
- `TodoTool`: Todo 항목 관리

이 도구들은 Discord 봇을 통해서도 자연어로 사용할 수 있습니다.
