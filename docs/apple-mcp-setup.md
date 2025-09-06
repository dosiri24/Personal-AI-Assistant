# Apple MCP 서버 설치 및 설정 가이드

# Apple MCP 서버 설치 및 설정 가이드

## 📋 설치 상태

### ✅ 완료된 단계 (Step 8.1)
1. **Apple MCP 서버 다운로드 완료**
   - 리포지토리: `external/apple-mcp/`
   - 소스: https://github.com/supermemoryai/apple-mcp
   - 모든 의존성 설치 완료

2. **CLI 명령어 시스템 구축 완료**
   ```bash
   # 사용 가능한 명령어들
   python src/main.py apple --help
   python src/main.py apple start [--background]
   python src/main.py apple stop
   python src/main.py apple status
   python src/main.py apple tools
   python src/main.py apple setup-permissions
   python src/main.py apple test [--app APP_NAME]
   ```

3. **서버 실행 확인 완료**
   ```bash
   # 백그라운드 실행
   python src/main.py apple start --background
   
   # 상태 확인
   python src/main.py apple status
   # 🟢 Apple MCP 서버: 실행 중 (PID: 93734)
   #    메모리 사용량: 50.4 MB
   #    CPU 사용량: 0.0%
   ```

4. **권한 설정 자동화 스크립트 완료**
   - `scripts/setup-apple-permissions.sh` 생성
   - 자동 권한 설정 가이드 제공

## 🚨 다음 필요 단계: macOS 권한 설정

Apple MCP 서버가 macOS 앱들에 접근하려면 다음 권한들이 필요합니다:

### 1. 시스템 설정 열기
```bash
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation"
```

### 2. 필요한 권한 목록
**Privacy & Security > Automation**에서 다음 앱들에 대한 권한을 부여해야 합니다:

- **Terminal** (또는 사용 중인 터미널 앱)
  - [ ] Contacts
  - [ ] Notes  
  - [ ] Messages
  - [ ] Mail
  - [ ] Reminders
  - [ ] Calendar
  - [ ] Maps
  - [ ] Safari

- **Bun** (런타임)
  - [ ] 모든 위 앱들에 대한 권한

### 3. 추가 권한
**Privacy & Security > Accessibility**
- [ ] Terminal
- [ ] Bun

**Privacy & Security > Full Disk Access** (필요시)
- [ ] Terminal
- [ ] Bun

## 🔧 권한 설정 후 테스트

권한 설정 완료 후 다음 명령어로 테스트:

```bash
cd external/apple-mcp
bun test tests/integration/contacts-simple.test.ts --preload ./tests/setup.ts
```

## 📱 지원되는 Apple 앱 기능

### 1. **Messages (메시지)**
- 메시지 전송/읽기/예약
- 읽지 않은 메시지 확인

### 2. **Notes (노트)**
- 노트 생성/검색/조회
- 폴더별 관리

### 3. **Contacts (연락처)**
- 연락처 검색/조회
- 전화번호 찾기

### 4. **Mail (메일)**
- 메일 전송/검색
- 읽지 않은 메일 확인
- 계정/메일박스별 관리

### 5. **Reminders (미리 알림)**
- 미리 알림 생성/검색
- 목록별 관리

### 6. **Calendar (캘린더)**
- 이벤트 생성/검색
- 일정 조회

### 7. **Maps (지도)**
- 위치 검색/저장
- 길찾기/가이드 관리

## 🐛 문제 해결

### Q: "Module not found" 오류
A: 올바른 경로에서 실행하는지 확인 (`external/apple-mcp/` 폴더 내)

### Q: 권한 관련 오류
A: System Settings에서 모든 필요 권한이 활성화되어 있는지 확인

### Q: 서버가 응답하지 않음
A: 터미널을 재시작하고 권한을 다시 확인

## 📝 참고 자료

- [Apple MCP GitHub](https://github.com/supermemoryai/apple-mcp)
- [MCP 프로토콜 문서](https://modelcontextprotocol.io/)
- [macOS 권한 설정 가이드](https://support.apple.com/guide/mac-help/allow-accessibility-apps-to-access-your-mac-mh43185/mac)
