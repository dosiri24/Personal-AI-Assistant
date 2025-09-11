import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import sys
import os

# 프로젝트 루트 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from ..base.tool import BaseTool, ToolResult, ExecutionStatus, ToolMetadata, ToolParameter, ParameterType, ToolCategory
from .scheduler import WebCrawlScheduler, CrawlJob


class WebScraperTool(BaseTool):
    """웹 스크래핑 MCP 도구"""
    
    def __init__(self):
        super().__init__()
        self.name = "web_scraper"
        self.description = "인하대 공지사항 크롤링 및 모니터링"
        self.scheduler = WebCrawlScheduler()
        self._initialize()
    
    def _initialize(self):
        """도구 초기화"""
        try:
            # 기존 상태 복원
            self.scheduler.load_state()
            self.logger.info("웹 스크래퍼 도구 초기화 완료")
        except Exception as e:
            self.logger.error(f"웹 스크래퍼 초기화 실패: {e}")
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """도구 실행"""
        try:
            action = parameters.get("action", "crawl_once")
            
            if action == "crawl_once":
                return await self._crawl_once(parameters)
            elif action == "get_latest":
                return await self._get_latest(parameters)
            elif action == "get_status":
                return await self._get_status()
            elif action == "get_changes":
                return await self._get_changes(parameters)
            elif action == "start_monitoring":
                return await self._start_monitoring()
            elif action == "stop_monitoring":
                return await self._stop_monitoring()
            else:
                return {
                    "success": False,
                    "error": f"알 수 없는 액션: {action}",
                    "available_actions": [
                        "crawl_once", "get_latest", "get_status", 
                        "get_changes", "start_monitoring", "stop_monitoring"
                    ]
                }
        
        except Exception as e:
            self.logger.error(f"웹 스크래퍼 실행 오류: {e}")
            return {"success": False, "error": str(e)}
    
    async def _crawl_once(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """한 번 크롤링 실행"""
        try:
            max_pages = parameters.get("max_pages", 2)
            
            # 특정 작업만 실행하도록 임시 설정
            if "job_id" in parameters:
                job_id = parameters["job_id"]
                if job_id in self.scheduler.jobs:
                    job = self.scheduler.jobs[job_id]
                    job.max_pages = max_pages
                    result = await self.scheduler.execute_job(job)
                    
                    return {
                        "success": True,
                        "action": "crawl_once",
                        "job_id": job_id,
                        "data_count": result.data_count,
                        "changes_detected": result.changes_detected,
                        "execution_time": result.execution_time,
                        "timestamp": result.timestamp
                    }
                else:
                    return {"success": False, "error": f"작업을 찾을 수 없음: {job_id}"}
            
            # 모든 작업 실행
            results = await self.scheduler.run_once()
            
            return {
                "success": True,
                "action": "crawl_once",
                "results": [
                    {
                        "job_id": r.job_id,
                        "success": r.success,
                        "data_count": r.data_count,
                        "changes_detected": r.changes_detected,
                        "execution_time": r.execution_time
                    }
                    for r in results
                ],
                "total_jobs": len(results)
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _get_latest(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """최신 크롤링 데이터 조회"""
        try:
            limit = parameters.get("limit", 10)
            job_id = parameters.get("job_id", "inha_notices")
            days = parameters.get("days", 7)
            
            # 최신 파일 찾기
            data_dir = self.scheduler.data_dir
            cutoff_date = datetime.now() - timedelta(days=days)
            
            latest_file = None
            latest_time = None
            
            for file_path in data_dir.glob(f"{job_id}_*.json"):
                try:
                    file_time = datetime.fromisoformat(file_path.stem.split('_', 1)[1])
                    if file_time > cutoff_date and (latest_time is None or file_time > latest_time):
                        latest_time = file_time
                        latest_file = file_path
                except:
                    continue
            
            if latest_file and latest_file.exists():
                with open(latest_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 제한된 수의 항목만 반환
                limited_data = data[:limit] if isinstance(data, list) else data
                
                return {
                    "success": True,
                    "action": "get_latest",
                    "job_id": job_id,
                    "file_timestamp": latest_time.isoformat(),
                    "total_items": len(data) if isinstance(data, list) else 1,
                    "returned_items": len(limited_data) if isinstance(limited_data, list) else 1,
                    "data": limited_data
                }
            else:
                return {
                    "success": False,
                    "error": f"최근 {days}일간 데이터를 찾을 수 없습니다.",
                    "job_id": job_id
                }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _get_status(self) -> Dict[str, Any]:
        """스케줄러 상태 조회"""
        try:
            status = self.scheduler.get_status()
            return {
                "success": True,
                "action": "get_status",
                **status
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _get_changes(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """최근 변경사항 조회"""
        try:
            hours = parameters.get("hours", 24)
            changes = self.scheduler.get_latest_changes(hours)
            
            return {
                "success": True,
                "action": "get_changes",
                "hours": hours,
                "changes_count": len(changes),
                "changes": [
                    {
                        "job_id": c.job_id,
                        "timestamp": c.timestamp,
                        "data_count": c.data_count,
                        "content_hash": c.content_hash[:8]
                    }
                    for c in changes
                ]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _start_monitoring(self) -> Dict[str, Any]:
        """모니터링 시작"""
        try:
            if not self.scheduler.is_running:
                # 백그라운드에서 스케줄러 시작
                asyncio.create_task(self.scheduler.run_scheduler(interval=60))
                return {
                    "success": True,
                    "action": "start_monitoring",
                    "message": "웹 크롤링 모니터링이 시작되었습니다.",
                    "interval": "60초"
                }
            else:
                return {
                    "success": True,
                    "action": "start_monitoring",
                    "message": "모니터링이 이미 실행 중입니다."
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _stop_monitoring(self) -> Dict[str, Any]:
        """모니터링 중지"""
        try:
            if self.scheduler.is_running:
                self.scheduler.stop_scheduler()
                # 상태 저장
                self.scheduler.save_state()
                return {
                    "success": True,
                    "action": "stop_monitoring",
                    "message": "웹 크롤링 모니터링이 중지되었습니다."
                }
            else:
                return {
                    "success": True,
                    "action": "stop_monitoring", 
                    "message": "모니터링이 실행 중이 아닙니다."
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_schema(self) -> Dict[str, Any]:
        """도구 스키마 반환"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "crawl_once", "get_latest", "get_status",
                            "get_changes", "start_monitoring", "stop_monitoring"
                        ],
                        "description": "실행할 액션"
                    },
                    "max_pages": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 2,
                        "description": "크롤링할 최대 페이지 수"
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 10,
                        "description": "반환할 최대 항목 수"
                    },
                    "job_id": {
                        "type": "string",
                        "default": "inha_notices",
                        "description": "크롤링 작업 ID"
                    },
                    "hours": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 168,
                        "default": 24,
                        "description": "조회할 시간 범위 (시간)"
                    },
                    "days": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 30,
                        "default": 7,
                        "description": "조회할 날짜 범위 (일)"
                    }
                },
                "required": ["action"]
            }
        }


# 사용 예시
async def main():
    """웹 스크래퍼 도구 테스트"""
    tool = WebScraperTool()
    
    # 한 번 크롤링
    print("🔄 크롤링 실행...")
    result = await tool.execute({"action": "crawl_once", "max_pages": 1})
    print(f"결과: {result['success']}")
    if result['success']:
        for r in result.get('results', []):
            print(f"- {r['job_id']}: {r['data_count']}개 항목, 변경: {r['changes_detected']}")
    
    # 최신 데이터 조회
    print("\n📋 최신 데이터 조회...")
    latest = await tool.execute({"action": "get_latest", "limit": 3})
    if latest['success']:
        print(f"총 {latest['total_items']}개 중 {latest['returned_items']}개 반환")
        for item in latest['data'][:2]:
            print(f"- {item['title']} ({item['date']})")
    
    # 상태 조회
    print("\n📊 상태 조회...")
    status = await tool.execute({"action": "get_status"})
    if status['success']:
        print(f"활성 작업: {status['active_jobs']}/{status['total_jobs']}")


if __name__ == "__main__":
    asyncio.run(main())
