# MCP 도구 안내서

본 문서는 Personal AI Assistant에서 에이전틱 AI가 사용하는 MCP 도구들을 정리합니다. 각 도구의 지원 액션, 주요 파라미터, 사용 예시(JSON)를 제공합니다.

도구 호출은 내부적으로 LLM이 다음과 같은 계획(JSON)을 생성해 실행됩니다.

```json
{
  "selected_tools": ["tool_name"],
  "execution_plan": [
    { "tool": "tool_name", "action": "...", "parameters": { /* ... */ } }
  ]
}
```

주의: 날짜/시간은 ISO(+타임존) 권장. 자연어(오늘/내일/오후 3시 등)도 일부 지원되며, 기본 타임존은 설정값(`default_timezone`)을 따릅니다.

---

## Notion 도구

### notion_todo — Notion 할일 관리
- 설명: Notion 할일 DB에서 할일 생성/수정/삭제/조회/완료 처리
- 액션: `create`, `update`, `delete`, `get`, `list`, `complete`
- 파라미터(주요):
  - 공통: `action`(필수)
  - 식별/검색: `todo_id`, `target_title`
  - 생성/수정: `title`, `description`, `due_date`(ISO/자연어), `priority`(높음/중간/낮음), `category`, `tags[]`, `status`, `assignee`, `estimated_hours`
  - 조회: `filter`(all/pending/completed/overdue), `limit`(기본 5, 최대 100)

예시
```json
{
  "selected_tools": ["notion_todo"],
  "execution_plan": [
    {
      "tool": "notion_todo",
      "action": "create",
      "parameters": {
        "title": "프로젝트 문서 작성",
        "description": "서론/결론 정리",
        "priority": "높음",
        "due_date": "2025-09-09T18:00+09:00",
        "tags": ["doc", "v1"]
      }
    }
  ]
}
```
```json
{
  "selected_tools": ["notion_todo"],
  "execution_plan": [
    {
      "tool": "notion_todo",
      "action": "list",
      "parameters": { "filter": "overdue", "limit": 10 }
    }
  ]
}
```
```json
{
  "selected_tools": ["notion_todo"],
  "execution_plan": [
    {
      "tool": "notion_todo",
      "action": "update",
      "parameters": {
        "todo_id": "<PAGE_ID>",
        "due_date": "2025-09-10T09:00+09:00",
        "priority": "중간"
      }
    }
  ]
}
```
```json
{
  "selected_tools": ["notion_todo"],
  "execution_plan": [
    {
      "tool": "notion_todo",
      "action": "complete",
      "parameters": { "todo_id": "<PAGE_ID>", "completed": true }
    }
  ]
}
```

---

### notion_calendar — Notion 캘린더 관리
- 설명: Notion 캘린더 DB에서 일정 생성/수정/삭제/조회
- 액션: `create`, `update`, `delete`, `get`, `list`
- 파라미터(주요):
  - 공통: `action`
  - 생성/수정: `title`, `start_date`(ISO/자연어), `end_date`(ISO/자연어), `description`, `location`, `attendees[]`, `priority`(High/Medium/Low), `category`, `is_all_day`, `reminder_minutes`
  - 식별: `event_id`
  - 조회: `date_range`(today/week/month/특정일)

예시
```json
{
  "selected_tools": ["notion_calendar"],
  "execution_plan": [
    {
      "tool": "notion_calendar",
      "action": "create",
      "parameters": {
        "title": "팀 미팅",
        "start_date": "2025-09-09T14:00+09:00",
        "end_date": "2025-09-09T15:00+09:00",
        "description": "주간 진행 점검",
        "reminder_minutes": 10
      }
    }
  ]
}
```

---

## Apple 도구 (MCP)

아래 도구들은 `external/apple-mcp` 서버 및 macOS 권한 설정이 필요합니다.

### apple_contacts — 연락처
- 액션: `search`(name), `find_by_phone`(phone)
- 예시
```json
{
  "selected_tools": ["apple_contacts"],
  "execution_plan": [
    { "tool": "apple_contacts", "action": "search", "parameters": { "name": "홍길동" } }
  ]
}
```

### apple_notes — 메모
- 액션: `create`(title, body, folder_name?), `search`(search_text), `list`(folder_name?)
- 기본 폴더: `Claude`
- 예시
```json
{
  "selected_tools": ["apple_notes"],
  "execution_plan": [
    {
      "tool": "apple_notes",
      "action": "create",
      "parameters": { "title": "회의 메모", "body": "안건 정리", "folder_name": "Inbox" }
    }
  ]
}
```

### apple_messages — 메시지
- 액션: `send`(phone_number, message), `read`(phone_number, limit?), `unread`(limit?), `schedule`(phone_number, message, scheduled_time)
- 예시
```json
{
  "selected_tools": ["apple_messages"],
  "execution_plan": [
    {
      "tool": "apple_messages",
      "action": "schedule",
      "parameters": {
        "phone_number": "+821012345678",
        "message": "내일 2시 회의 링크 공유",
        "scheduled_time": "2025-09-09T13:55+09:00"
      }
    }
  ]
}
```

### apple_mail — 메일
- 액션: `send`(to, subject, body, cc?, bcc?), `unread`(account?, mailbox?, limit?), `search`(search_term, account?, limit?), `accounts`, `mailboxes`(account)
- 예시
```json
{
  "selected_tools": ["apple_mail"],
  "execution_plan": [
    {
      "tool": "apple_mail",
      "action": "send",
      "parameters": {
        "to": "user@example.com",
        "subject": "주간 보고",
        "body": "첨부 참조 부탁드립니다.",
        "cc": "lead@example.com"
      }
    }
  ]
}
```

### apple_reminders — 미리 알림
- 액션: `create`(name, list_name?, notes?, due_date?), `search`(search_text), `list`, `open`(search_text)
- 예시
```json
{
  "selected_tools": ["apple_reminders"],
  "execution_plan": [
    {
      "tool": "apple_reminders",
      "action": "create",
      "parameters": {
        "name": "치과 예약",
        "list_name": "개인",
        "notes": "보험증 지참",
        "due_date": "2025-09-10T09:00+09:00"
      }
    }
  ]
}
```

### apple_calendar — 캘린더
- 액션: `create`(title, start_date, end_date, location?, notes?, is_all_day?, calendar_name?), `search`(search_text, from_date?, to_date?, limit?), `list`(from_date?, to_date?, limit?), `open`(event_id)
- 예시
```json
{
  "selected_tools": ["apple_calendar"],
  "execution_plan": [
    {
      "tool": "apple_calendar",
      "action": "create",
      "parameters": {
        "title": "프로젝트 킥오프",
        "start_date": "2025-09-11T10:00+09:00",
        "end_date": "2025-09-11T11:00+09:00",
        "location": "회의실 A",
        "is_all_day": false
      }
    }
  ]
}
```

### apple_maps — 지도
- 액션: `search`(query, limit?), `save`(name, address), `directions`(from_address, to_address, transport_type?), `pin`(name, address), `create_guide`(guide_name), `add_to_guide`(guide_name, address)
- 예시
```json
{
  "selected_tools": ["apple_maps"],
  "execution_plan": [
    {
      "tool": "apple_maps",
      "action": "directions",
      "parameters": {
        "from_address": "서울역",
        "to_address": "인천국제공항",
        "transport_type": "transit"
      }
    }
  ]
}
```

---

## 계산/기타 도구

### filesystem — 로컬 파일 관리(가드레일 적용)
- 설명: 허용된 루트 디렉토리 내에서 안전하게 파일/디렉토리를 조회·이동·복사·삭제합니다. 기본 허용 루트: `~/Documents`, `~/Downloads`, `~/Desktop`, 프로젝트 `data/`, `logs/`. 환경변수 `PAI_FS_ALLOWED_DIRS`로 추가 지정(구분자: macOS `:` / Windows `;`).
- 액션: `list`, `stat`, `move`, `copy`, `mkdir`, `trash_delete`, `delete`
- 파라미터(일부):
  - 공통: `action`
  - list: `path`(dir), `include_hidden`(bool), `max_items`(int, 기본 200), `recursive`(bool)
  - stat: `path`
  - move/copy: `src`, `dst`, `overwrite`(bool), `recursive`(bool; 디렉토리 필수). 복사 용량 제한(`PAI_FS_MAX_COPY_MB`, 기본 50MB)
  - mkdir: `path`, `parents`(bool)
  - trash_delete: `path`, `recursive`(bool)
  - delete: `path`, `recursive`(bool), `force`(bool; 필수)
- 예시
```json
{
  "selected_tools": ["filesystem"],
  "execution_plan": [
    {"tool": "filesystem", "action": "list", "parameters": {"path": "~/Documents", "max_items": 50}},
    {"tool": "filesystem", "action": "copy", "parameters": {"src": "~/Downloads/a.pdf", "dst": "~/Documents/a.pdf", "overwrite": true}},
    {"tool": "filesystem", "action": "trash_delete", "parameters": {"path": "~/Documents/old", "recursive": true}}
  ]
}
```

### calculator — 기본 계산기
- 설명: 사칙연산 수행
- 파라미터: `operation`("+"|"-"|"*"|"/"), `a`(number), `b`(number), `precision`(int, 기본 2)
- 예시
```json
{
  "selected_tools": ["calculator"],
  "execution_plan": [
    {
      "tool": "calculator",
      "parameters": { "operation": "+", "a": 2, "b": 3, "precision": 0 }
    }
  ]
}
```

---

## (실험적) Web Scraper
- 모듈: `src/tools/web_scraper/web_scraper_tool.py`
- 상태: 실험적/데모용, 기본 MCP 레지스트리 자동 등록 대상 아님(메타데이터 미정의)
- 액션: `crawl_once`, `get_latest`, `get_status`, `get_changes`, `start_monitoring`, `stop_monitoring`
- 용도: 특정 웹 공지(예: 대학 공지) 크롤링/모니터링

---

## 결과/오류 규격(요약)
- 모든 MCP 도구는 `ToolResult`를 반환
  - `status`: `success` | `error`
  - `data`: 도구별 결과 데이터(예: id, url, message 등)
  - `error_message`: 오류 시 메시지

## 참고
- Notion 설정: `NOTION_API_TOKEN`, `NOTION_TODO_DATABASE_ID` 필요. 자세한 설정은 `NOTION_SETUP.md` 참조.
- Apple 도구: `external/apple-mcp` 서버 실행 및 macOS 권한 필요. `README.md`의 Apple MCP 섹션 참조.
- 타임존/날짜 처리: 입력이 타임존 없이 오면 기본 타임존을 적용하여 ISO로 보정될 수 있습니다.
