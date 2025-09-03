"""프롬프트 최적화 및 A/B 테스트 시스템

프롬프트의 효과를 측정하고 최적화하는 시스템
"""

import json
import sqlite3
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import uuid

from loguru import logger


class TestStatus(Enum):
    """A/B 테스트 상태"""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class MetricType(Enum):
    """측정 지표 타입"""
    SUCCESS_RATE = "success_rate"
    USER_SATISFACTION = "user_satisfaction"
    RESPONSE_TIME = "response_time"
    TASK_COMPLETION_TIME = "task_completion_time"
    ERROR_RATE = "error_rate"
    USER_ENGAGEMENT = "user_engagement"
    CLARIFICATION_REQUESTS = "clarification_requests"


@dataclass
class PromptVariant:
    """프롬프트 변형"""
    id: str
    name: str
    template: str
    description: str
    version: str = "1.0"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class TestResult:
    """테스트 결과"""
    id: str
    test_id: str
    variant_id: str
    user_id: str
    timestamp: datetime
    metrics: Dict[MetricType, float]
    context: Dict[str, Any] = field(default_factory=dict)
    feedback: Optional[str] = None


@dataclass
class ABTest:
    """A/B 테스트"""
    id: str
    name: str
    description: str
    status: TestStatus
    variants: List[PromptVariant]
    traffic_split: Dict[str, float]  # variant_id: percentage
    target_metrics: List[MetricType]
    start_date: datetime
    end_date: Optional[datetime] = None
    min_sample_size: int = 100
    significance_level: float = 0.05
    results: List[TestResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class PromptOptimizer:
    """프롬프트 최적화 관리자"""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path("data/prompt_optimization.db")
        self.db_path.parent.mkdir(exist_ok=True)
        self.active_tests: Dict[str, ABTest] = {}
        self._initialize_database()
        self._load_active_tests()
        
    def _initialize_database(self):
        """데이터베이스 초기화"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS ab_tests (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        status TEXT NOT NULL,
                        variants TEXT NOT NULL,  -- JSON
                        traffic_split TEXT NOT NULL,  -- JSON
                        target_metrics TEXT NOT NULL,  -- JSON
                        start_date TEXT NOT NULL,
                        end_date TEXT,
                        min_sample_size INTEGER,
                        significance_level REAL,
                        metadata TEXT,  -- JSON
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS test_results (
                        id TEXT PRIMARY KEY,
                        test_id TEXT NOT NULL,
                        variant_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        metrics TEXT NOT NULL,  -- JSON
                        context TEXT,  -- JSON
                        feedback TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (test_id) REFERENCES ab_tests (id)
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_test_results_test_id 
                    ON test_results (test_id)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_test_results_timestamp 
                    ON test_results (timestamp)
                """)
                
                conn.commit()
                logger.debug("프롬프트 최적화 데이터베이스 초기화 완료")
                
        except Exception as e:
            logger.error(f"데이터베이스 초기화 중 오류: {e}")
            raise
            
    def _load_active_tests(self):
        """활성 테스트 로드"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT * FROM ab_tests 
                    WHERE status IN ('active', 'paused')
                """)
                
                for row in cursor.fetchall():
                    test = self._row_to_ab_test(row)
                    self.active_tests[test.id] = test
                    
                logger.info(f"활성 테스트 로드 완료: {len(self.active_tests)}개")
                
        except Exception as e:
            logger.error(f"활성 테스트 로드 중 오류: {e}")
            
    def create_ab_test(self, 
                      name: str,
                      description: str,
                      variants: List[PromptVariant],
                      traffic_split: Dict[str, float],
                      target_metrics: List[MetricType],
                      min_sample_size: int = 100,
                      significance_level: float = 0.05) -> ABTest:
        """A/B 테스트 생성"""
        try:
            # 트래픽 분할 검증
            if abs(sum(traffic_split.values()) - 1.0) > 0.001:
                raise ValueError("트래픽 분할의 합이 1.0이 되어야 합니다")
                
            # 변형 ID 검증
            variant_ids = {v.id for v in variants}
            split_ids = set(traffic_split.keys())
            if variant_ids != split_ids:
                raise ValueError("변형 ID와 트래픽 분할 ID가 일치하지 않습니다")
                
            test = ABTest(
                id=str(uuid.uuid4()),
                name=name,
                description=description,
                status=TestStatus.DRAFT,
                variants=variants,
                traffic_split=traffic_split,
                target_metrics=target_metrics,
                start_date=datetime.now(),
                min_sample_size=min_sample_size,
                significance_level=significance_level
            )
            
            self._save_ab_test(test)
            logger.info(f"A/B 테스트 생성 완료: {test.name} ({test.id})")
            return test
            
        except Exception as e:
            logger.error(f"A/B 테스트 생성 중 오류: {e}")
            raise
            
    def start_test(self, test_id: str) -> bool:
        """테스트 시작"""
        try:
            test = self.get_test(test_id)
            if not test:
                raise ValueError(f"테스트를 찾을 수 없습니다: {test_id}")
                
            if test.status != TestStatus.DRAFT:
                raise ValueError(f"드래프트 상태의 테스트만 시작할 수 있습니다: {test.status}")
                
            test.status = TestStatus.ACTIVE
            test.start_date = datetime.now()
            self._save_ab_test(test)
            self.active_tests[test_id] = test
            
            logger.info(f"A/B 테스트 시작: {test.name}")
            return True
            
        except Exception as e:
            logger.error(f"테스트 시작 중 오류: {e}")
            return False
            
    def record_result(self, 
                     test_id: str,
                     user_id: str,
                     variant_id: str,
                     metrics: Dict[MetricType, float],
                     context: Optional[Dict[str, Any]] = None,
                     feedback: Optional[str] = None) -> bool:
        """테스트 결과 기록"""
        try:
            if test_id not in self.active_tests:
                logger.warning(f"활성 테스트가 아닙니다: {test_id}")
                return False
                
            test = self.active_tests[test_id]
            if test.status != TestStatus.ACTIVE:
                logger.warning(f"활성 상태가 아닌 테스트: {test.status}")
                return False
                
            result = TestResult(
                id=str(uuid.uuid4()),
                test_id=test_id,
                variant_id=variant_id,
                user_id=user_id,
                timestamp=datetime.now(),
                metrics=metrics,
                context=context or {},
                feedback=feedback
            )
            
            self._save_test_result(result)
            test.results.append(result)
            
            # 자동 완료 확인
            self._check_test_completion(test_id)
            
            logger.debug(f"테스트 결과 기록: {test_id}")
            return True
            
        except Exception as e:
            logger.error(f"테스트 결과 기록 중 오류: {e}")
            return False
            
    def get_variant_for_user(self, test_id: str, user_id: str) -> Optional[PromptVariant]:
        """사용자에게 할당할 변형 선택"""
        try:
            if test_id not in self.active_tests:
                return None
                
            test = self.active_tests[test_id]
            if test.status != TestStatus.ACTIVE:
                return None
                
            # 사용자 ID를 기반으로 결정적 할당
            user_hash = hash(f"{test_id}:{user_id}") % 1000000
            normalized = user_hash / 1000000
            
            cumulative = 0.0
            for variant_id, percentage in test.traffic_split.items():
                cumulative += percentage
                if normalized <= cumulative:
                    for variant in test.variants:
                        if variant.id == variant_id:
                            return variant
                            
            # 폴백: 첫 번째 변형 반환
            return test.variants[0] if test.variants else None
            
        except Exception as e:
            logger.error(f"변형 선택 중 오류: {e}")
            return None
            
    def analyze_test_results(self, test_id: str) -> Dict[str, Any]:
        """테스트 결과 분석"""
        try:
            test = self.get_test(test_id)
            if not test:
                raise ValueError(f"테스트를 찾을 수 없습니다: {test_id}")
                
            # 결과 로드
            results = self._load_test_results(test_id)
            
            analysis = {
                "test_id": test_id,
                "test_name": test.name,
                "status": test.status.value,
                "total_samples": len(results),
                "variants": {},
                "statistical_significance": {},
                "recommendations": []
            }
            
            # 변형별 분석
            for variant in test.variants:
                variant_results = [r for r in results if r.variant_id == variant.id]
                variant_analysis = self._analyze_variant_results(variant_results, test.target_metrics)
                analysis["variants"][variant.id] = {
                    "name": variant.name,
                    "sample_size": len(variant_results),
                    "metrics": variant_analysis
                }
                
            # 통계적 유의성 검정
            if len(test.variants) == 2:
                significance = self._calculate_statistical_significance(
                    analysis["variants"], test.target_metrics, test.significance_level
                )
                analysis["statistical_significance"] = significance
                
            # 추천사항 생성
            analysis["recommendations"] = self._generate_recommendations(analysis)
            
            return analysis
            
        except Exception as e:
            logger.error(f"테스트 결과 분석 중 오류: {e}")
            return {"error": str(e)}
            
    def _analyze_variant_results(self, results: List[TestResult], target_metrics: List[MetricType]) -> Dict[str, Any]:
        """변형별 결과 분석"""
        if not results:
            return {}
            
        analysis = {}
        for metric in target_metrics:
            values = [r.metrics.get(metric, 0.0) for r in results if metric in r.metrics]
            if values:
                analysis[metric.value] = {
                    "mean": statistics.mean(values),
                    "median": statistics.median(values),
                    "std": statistics.stdev(values) if len(values) > 1 else 0.0,
                    "min": min(values),
                    "max": max(values),
                    "count": len(values)
                }
                
        return analysis
        
    def _calculate_statistical_significance(self, variants: Dict[str, Any], 
                                          target_metrics: List[MetricType],
                                          significance_level: float) -> Dict[str, Any]:
        """통계적 유의성 계산 (간단한 t-test)"""
        # 실제 구현에서는 scipy.stats를 사용하는 것이 좋습니다
        significance = {}
        
        variant_ids = list(variants.keys())
        if len(variant_ids) != 2:
            return significance
            
        v1_id, v2_id = variant_ids
        v1_data = variants[v1_id]
        v2_data = variants[v2_id]
        
        for metric in target_metrics:
            metric_name = metric.value
            if metric_name in v1_data["metrics"] and metric_name in v2_data["metrics"]:
                v1_mean = v1_data["metrics"][metric_name]["mean"]
                v2_mean = v2_data["metrics"][metric_name]["mean"]
                
                # 간단한 효과 크기 계산
                effect_size = abs(v1_mean - v2_mean) / max(v1_mean, v2_mean) if max(v1_mean, v2_mean) > 0 else 0
                
                significance[metric_name] = {
                    "variant_1_mean": v1_mean,
                    "variant_2_mean": v2_mean,
                    "effect_size": effect_size,
                    "significant": effect_size > 0.05,  # 5% 이상 차이면 유의미
                    "winner": v1_id if v1_mean > v2_mean else v2_id
                }
                
        return significance
        
    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """분석 결과 기반 추천사항 생성"""
        recommendations = []
        
        # 샘플 크기 확인
        total_samples = analysis["total_samples"]
        if total_samples < 100:
            recommendations.append("더 많은 샘플이 필요합니다 (현재: {}, 권장: 100+)".format(total_samples))
            
        # 유의미한 차이가 있는 경우
        significance = analysis.get("statistical_significance", {})
        for metric, data in significance.items():
            if data.get("significant", False):
                winner = data["winner"]
                effect_size = data["effect_size"]
                recommendations.append(
                    f"{metric}에서 {winner} 변형이 {effect_size:.1%} 더 우수합니다"
                )
                
        # 기본 추천사항
        if not recommendations:
            recommendations.append("현재까지 유의미한 차이가 발견되지 않았습니다. 더 오래 테스트를 진행하거나 변형을 조정해보세요.")
            
        return recommendations
        
    def get_test(self, test_id: str) -> Optional[ABTest]:
        """테스트 정보 조회"""
        # 활성 테스트에서 먼저 찾기
        if test_id in self.active_tests:
            return self.active_tests[test_id]
            
        # 데이터베이스에서 찾기
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT * FROM ab_tests WHERE id = ?", (test_id,))
                row = cursor.fetchone()
                if row:
                    return self._row_to_ab_test(row)
                    
        except Exception as e:
            logger.error(f"테스트 조회 중 오류: {e}")
            
        return None
        
    def _save_ab_test(self, test: ABTest):
        """A/B 테스트 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                now = datetime.now().isoformat()
                conn.execute("""
                    INSERT OR REPLACE INTO ab_tests 
                    (id, name, description, status, variants, traffic_split, 
                     target_metrics, start_date, end_date, min_sample_size, 
                     significance_level, metadata, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    test.id, test.name, test.description, test.status.value,
                    json.dumps([{
                        "id": v.id, "name": v.name, "template": v.template,
                        "description": v.description, "version": v.version,
                        "metadata": v.metadata, "created_at": v.created_at.isoformat()
                    } for v in test.variants]),
                    json.dumps(test.traffic_split),
                    json.dumps([m.value for m in test.target_metrics]),
                    test.start_date.isoformat(),
                    test.end_date.isoformat() if test.end_date else None,
                    test.min_sample_size, test.significance_level,
                    json.dumps(test.metadata), now, now
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"A/B 테스트 저장 중 오류: {e}")
            raise
            
    def _save_test_result(self, result: TestResult):
        """테스트 결과 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO test_results 
                    (id, test_id, variant_id, user_id, timestamp, metrics, context, feedback, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result.id, result.test_id, result.variant_id, result.user_id,
                    result.timestamp.isoformat(),
                    json.dumps({k.value: v for k, v in result.metrics.items()}),
                    json.dumps(result.context),
                    result.feedback,
                    datetime.now().isoformat()
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"테스트 결과 저장 중 오류: {e}")
            raise
            
    def _load_test_results(self, test_id: str) -> List[TestResult]:
        """테스트 결과 로드"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT * FROM test_results WHERE test_id = ?
                    ORDER BY timestamp
                """, (test_id,))
                
                results = []
                for row in cursor.fetchall():
                    metrics_data = json.loads(row[5])
                    metrics = {MetricType(k): v for k, v in metrics_data.items()}
                    
                    result = TestResult(
                        id=row[0],
                        test_id=row[1], 
                        variant_id=row[2],
                        user_id=row[3],
                        timestamp=datetime.fromisoformat(row[4]),
                        metrics=metrics,
                        context=json.loads(row[6]) if row[6] else {},
                        feedback=row[7]
                    )
                    results.append(result)
                    
                return results
                
        except Exception as e:
            logger.error(f"테스트 결과 로드 중 오류: {e}")
            return []
            
    def _row_to_ab_test(self, row) -> ABTest:
        """데이터베이스 행을 ABTest 객체로 변환"""
        variants_data = json.loads(row[4])
        variants = [
            PromptVariant(
                id=v["id"], name=v["name"], template=v["template"],
                description=v["description"], version=v["version"],
                metadata=v["metadata"], 
                created_at=datetime.fromisoformat(v["created_at"])
            ) for v in variants_data
        ]
        
        return ABTest(
            id=row[0], name=row[1], description=row[2],
            status=TestStatus(row[3]), variants=variants,
            traffic_split=json.loads(row[5]),
            target_metrics=[MetricType(m) for m in json.loads(row[6])],
            start_date=datetime.fromisoformat(row[7]),
            end_date=datetime.fromisoformat(row[8]) if row[8] else None,
            min_sample_size=row[9], significance_level=row[10],
            metadata=json.loads(row[11]) if row[11] else {}
        )
        
    def _check_test_completion(self, test_id: str):
        """테스트 완료 조건 확인"""
        try:
            test = self.active_tests.get(test_id)
            if not test or test.status != TestStatus.ACTIVE:
                return
                
            # 최소 샘플 크기 확인
            results = self._load_test_results(test_id)
            if len(results) >= test.min_sample_size:
                # 통계적 유의성 확인
                analysis = self.analyze_test_results(test_id)
                significance = analysis.get("statistical_significance", {})
                
                # 유의미한 결과가 있으면 테스트 완료
                for metric_data in significance.values():
                    if metric_data.get("significant", False):
                        test.status = TestStatus.COMPLETED
                        test.end_date = datetime.now()
                        self._save_ab_test(test)
                        logger.info(f"테스트 자동 완료: {test.name}")
                        break
                        
        except Exception as e:
            logger.error(f"테스트 완료 확인 중 오류: {e}")
