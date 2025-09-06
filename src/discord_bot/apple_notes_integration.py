"""
Discord Bot용 Apple Notes 연동 모듈

Discord에서 받은 자연어 명령을 Apple Notes 메모로 저장하는 기능을 제공합니다.
"""

import asyncio
import subprocess
import re
from typing import Optional, Dict, Any
from pathlib import Path
import sys

# AI 엔진 모듈 가져오기
sys.path.append(str(Path(__file__).parent.parent))
from ai_engine.llm_provider import GeminiProvider, ChatMessage

class AppleNotesIntegration:
    """Discord Bot용 Apple Notes 연동 클래스"""
    
    def __init__(self):
        self.llm_provider = GeminiProvider()
        
    async def process_memo_command(self, user_message: str) -> Dict[str, Any]:
        """
        사용자 메시지에서 메모 저장 명령을 처리
        
        Args:
            user_message: Discord에서 받은 사용자 메시지
            
        Returns:
            처리 결과 딕셔너리
        """
        try:
            # AI로 메모 저장 명령인지 분석
            analysis = await self._analyze_memo_command(user_message)
            
            if analysis["is_memo_command"]:
                # Apple Notes에 메모 저장
                success = await self._save_to_apple_notes(
                    title=analysis["title"],
                    content=analysis["content"]
                )
                
                if success:
                    return {
                        "success": True,
                        "message": f"✅ '{analysis['title']}' 메모가 Apple Notes에 저장되었습니다!",
                        "title": analysis["title"],
                        "content": analysis["content"]
                    }
                else:
                    return {
                        "success": False,
                        "message": "❌ Apple Notes에 메모 저장에 실패했습니다.",
                        "error": "AppleScript 실행 오류"
                    }
            else:
                return {
                    "success": False,
                    "message": "메모 저장 명령이 아닙니다.",
                    "is_memo_command": False
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 오류가 발생했습니다: {str(e)}",
                "error": str(e)
            }
    
    async def _analyze_memo_command(self, user_message: str) -> Dict[str, Any]:
        """
        사용자 메시지가 메모 저장 명령인지 AI로 분석
        
        Args:
            user_message: 사용자 메시지
            
        Returns:
            분석 결과
        """
        system_prompt = """
당신은 사용자 메시지를 분석하여 Apple Notes 메모 저장 명령인지 판단하는 AI입니다.

메모 저장 관련 키워드: "메모", "저장", "기록", "적어줘", "메모해줘", "노트" 등

사용자 입력을 분석하여 다음 JSON 형식으로 응답하세요:

{
    "is_memo_command": true/false,
    "confidence": 0.0-1.0,
    "title": "메모 제목 (간단하게)",
    "content": "메모 내용 (사용자가 요청한 그대로)",
    "reasoning": "판단 근거"
}

중요: 사용자가 요청한 내용을 있는 그대로 저장하세요. 불필요한 부가 정보나 체크리스트를 추가하지 마세요.

예시:
- "사과 5개 사기 메모로 저장해줘" → {"is_memo_command": true, "title": "사과 5개 사기", "content": "사과 5개 구입하기"}
- "오늘 날씨 어때?" → {"is_memo_command": false}
"""
        
        try:
            messages = [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=f"사용자 메시지: {user_message}")
            ]
            
            response = await self.llm_provider.generate_response(
                messages=messages,
                temperature=0.1
            )
            
            # JSON 응답 파싱
            response_text = response.content if hasattr(response, 'content') else str(response)
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                import json
                result = json.loads(json_match.group())
                return result
            
            # JSON 파싱 실패 시 기본값
            return {
                "is_memo_command": False,
                "confidence": 0.0,
                "title": "",
                "content": "",
                "reasoning": "JSON 파싱 실패"
            }
            
        except Exception as e:
            return {
                "is_memo_command": False,
                "confidence": 0.0,
                "title": "",
                "content": "",
                "reasoning": f"AI 분석 오류: {e}"
            }
    
    async def _save_to_apple_notes(self, title: str, content: str) -> bool:
        """
        Apple Notes에 메모 저장
        
        Args:
            title: 메모 제목
            content: 메모 내용
            
        Returns:
            저장 성공 여부
        """
        try:
            # AppleScript로 Notes에 메모 생성
            applescript = f'''
            tell application "Notes"
                make new note with properties {{name:"{title}", body:"{content}"}}
            end tell
            '''
            
            # AppleScript 실행
            process = subprocess.run(
                ["osascript", "-e", applescript],
                capture_output=True,
                text=True
            )
            
            return process.returncode == 0
            
        except Exception as e:
            print(f"Apple Notes 저장 오류: {e}")
            return False
    
    async def list_recent_notes(self, limit: int = 5) -> list[str]:
        """
        최근 생성된 메모 목록 조회
        
        Args:
            limit: 조회할 메모 수
            
        Returns:
            메모 제목 목록
        """
        try:
            applescript = f'''
            tell application "Notes"
                set recentNotes to {{}}
                set allNotes to every note
                repeat with i from 1 to (count of allNotes)
                    if i > {limit} then exit repeat
                    set end of recentNotes to name of item i of allNotes
                end repeat
                return recentNotes as string
            end tell
            '''
            
            process = subprocess.run(
                ["osascript", "-e", applescript],
                capture_output=True,
                text=True
            )
            
            if process.returncode == 0:
                notes_str = process.stdout.strip()
                return notes_str.split(", ") if notes_str else []
            
            return []
            
        except Exception as e:
            print(f"메모 목록 조회 오류: {e}")
            return []
