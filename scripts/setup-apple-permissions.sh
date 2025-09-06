#!/bin/bash

# Apple MCP 권한 설정 자동화 스크립트

echo "🍎 Apple MCP 권한 설정 가이드"
echo "================================"
echo ""

echo "📋 Step 1: 시스템 설정 열기"
echo "다음 명령어를 실행하여 시스템 설정을 엽니다:"
echo "open 'x-apple.systempreferences:com.apple.preference.security?Privacy_Automation'"
echo ""

echo "🔐 Step 2: 필요한 권한 목록"
echo "Privacy & Security > Automation에서 다음 권한들을 활성화하세요:"
echo ""

echo "📱 Terminal (또는 현재 사용 중인 터미널):"
echo "  ☐ Contacts"
echo "  ☐ Notes"
echo "  ☐ Messages"
echo "  ☐ Mail"
echo "  ☐ Reminders"
echo "  ☐ Calendar"
echo "  ☐ Maps"
echo "  ☐ Safari"
echo ""

echo "🏃 Bun (런타임):"
echo "  ☐ 위의 모든 앱들에 대한 권한"
echo ""

echo "🔧 Step 3: 추가 권한 (필요시)"
echo "Privacy & Security > Accessibility:"
echo "  ☐ Terminal"
echo "  ☐ Bun"
echo ""

echo "💾 Privacy & Security > Full Disk Access (필요시):"
echo "  ☐ Terminal"
echo "  ☐ Bun"
echo ""

echo "✅ Step 4: 권한 설정 후 테스트"
echo "권한 설정이 완료되면 다음 명령어로 테스트하세요:"
echo "cd external/apple-mcp"
echo "bun test tests/integration/contacts-simple.test.ts --preload ./tests/setup.ts"
echo ""

echo "🚨 주의사항:"
echo "- 권한 변경 후 터미널을 재시작해야 할 수 있습니다"
echo "- 일부 앱은 처음 실행 시 추가 권한 요청 팝업이 나타날 수 있습니다"
echo "- 권한이 거부되면 해당 기능이 작동하지 않습니다"
echo ""

echo "📞 문제 해결:"
echo "권한 관련 문제가 발생하면 docs/apple-mcp-setup.md를 참조하세요"
