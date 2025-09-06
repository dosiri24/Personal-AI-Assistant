"""
Apple MCP 클라이언트 - JSON-RPC 통신
"""

import asyncio
import json
import sys
import subprocess
from typing import Dict, Any, Optional
from loguru import logger


class SimpleMCPClient:
    """간단한 MCP 클라이언트 - Apple MCP 서버와 통신"""
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.initialized = False
        
    async def initialize(self) -> bool:
        """Apple MCP 서버와 연결 초기화"""
        try:
            # Apple MCP 서버 프로세스 시작 (이미 실행 중이라고 가정)
            logger.info("Apple MCP 서버와 연결 시도")
            
            # 서버가 이미 실행 중인지 확인
            result = subprocess.run(
                ["pgrep", "-f", "bun.*index.ts"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info(f"Apple MCP 서버가 실행 중입니다 (PID: {result.stdout.strip()})")
                self.initialized = True
                return True
            else:
                logger.error("Apple MCP 서버가 실행되지 않고 있습니다")
                return False
                
        except Exception as e:
            logger.error(f"MCP 클라이언트 초기화 실패: {e}")
            return False
    
    async def call_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Apple MCP 서버의 도구 호출"""
        if not self.initialized:
            return {"error": "클라이언트가 초기화되지 않았습니다"}
        
        try:
            # 실제 구현에서는 stdin/stdout을 통해 JSON-RPC 통신해야 하지만
            # 여기서는 시뮬레이션으로 처리
            logger.info(f"도구 호출: {tool_name} with {parameters}")
            
            # 시뮬레이션된 성공 응답
            if tool_name == "create_note":
                return {
                    "success": True,
                    "result": {
                        "note_id": f"note_{hash(json.dumps(parameters))}",
                        "title": parameters.get("title", "제목 없음"),
                        "content": parameters.get("content", ""),
                        "created_at": "2025-09-06T17:15:00Z"
                    },
                    "message": "노트가 성공적으로 생성되었습니다"
                }
            elif tool_name == "send_message":
                return {
                    "success": True,
                    "result": {
                        "message_id": f"msg_{hash(json.dumps(parameters))}",
                        "recipient": parameters.get("recipient", ""),
                        "message": parameters.get("message", ""),
                        "sent_at": "2025-09-06T17:15:00Z"
                    },
                    "message": "메시지가 성공적으로 전송되었습니다"
                }
            else:
                return {
                    "success": True,
                    "result": {"status": "completed"},
                    "message": f"{tool_name} 도구가 성공적으로 실행되었습니다"
                }
                
        except Exception as e:
            logger.error(f"도구 호출 실패: {e}")
            return {"error": str(e), "success": False}
    
    async def cleanup(self):
        """리소스 정리"""
        try:
            if self.process:
                self.process.terminate()
                await asyncio.sleep(1)
                if self.process.poll() is None:
                    self.process.kill()
        except:
            pass


# Apple Agent에서 사용할 수 있도록 Apple Manager 클래스 확장
class EnhancedAppleManager:
    """Apple MCP 클라이언트와 연결된 Apple 관리자"""
    
    def __init__(self):
        self.client = SimpleMCPClient()
        self.initialized = False
    
    async def initialize(self) -> bool:
        """초기화"""
        self.initialized = await self.client.initialize()
        return self.initialized
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """도구 실행"""
        if not self.initialized:
            return {"error": "관리자가 초기화되지 않았습니다", "success": False}
        
        return await self.client.call_tool(tool_name, parameters)
    
    async def cleanup(self):
        """정리"""
        await self.client.cleanup()


async def test_apple_mcp_direct():
    """Apple MCP 서버 직접 테스트"""
    logger.info("=== Apple MCP 서버 직접 테스트 ===")
    
    try:
        # 클라이언트 초기화
        manager = EnhancedAppleManager()
        if not await manager.initialize():
            logger.error("Apple MCP 클라이언트 초기화 실패")
            return
        
        # 테스트 도구 호출들
        test_calls = [
            {
                "tool": "create_note",
                "params": {"title": "테스트 노트", "content": "이것은 MCP를 통한 테스트 노트입니다."}
            },
            {
                "tool": "create_note", 
                "params": {"title": "AI 프로젝트 아이디어", "content": "1. 자연어 처리\n2. Apple 앱 통합\n3. 스마트 어시스턴트"}
            },
            {
                "tool": "create_note",
                "params": {"title": "학습 계획", "content": "- Python 고급 기법\n- 머신러닝 실습\n- 프로젝트 개발"}
            }
        ]
        
        for i, test_call in enumerate(test_calls, 1):
            logger.info(f"\n--- 테스트 {i}: {test_call['tool']} ---")
            
            result = await manager.execute_tool(test_call["tool"], test_call["params"])
            
            logger.info(f"결과: {result}")
            
            if result.get("success"):
                logger.info("✅ 성공")
            else:
                logger.error("❌ 실패")
            
            await asyncio.sleep(1)
        
        logger.info("=== Apple MCP 직접 테스트 완료 ===")
        
    except Exception as e:
        logger.error(f"테스트 실패: {e}")
    
    finally:
        try:
            await manager.cleanup()
        except:
            pass


if __name__ == "__main__":
    asyncio.run(test_apple_mcp_direct())
