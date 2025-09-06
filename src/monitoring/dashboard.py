"""
Step 9.4: 모니터링 대시보드 구현
실시간 시스템 상태 모니터링 및 시각화
"""

import asyncio
import json
import threading
import time
import psutil
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import logging
from pathlib import Path

# 외부 모듈 import
try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

try:
    import dash
    from dash import dcc, html, Input, Output, callback
    import dash_bootstrap_components as dbc
    DASH_AVAILABLE = True
except ImportError:
    DASH_AVAILABLE = False

from ..utils.logger import get_logger
from ..utils.error_handler import error_handler, AISystemError
from ..utils.performance import global_performance_monitor

logger = get_logger(__name__)

@dataclass
class SystemMetrics:
    """시스템 메트릭 데이터 클래스"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_available_gb: float
    disk_usage_percent: float
    network_sent_mb: float
    network_recv_mb: float
    active_threads: int
    process_count: int
    load_average: Optional[float] = None

@dataclass
class AIMetrics:
    """AI 엔진 메트릭 데이터 클래스"""
    timestamp: datetime
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time: float
    cache_hit_rate: float
    active_sessions: int
    queue_size: int
    model_temperature: float
    tokens_processed: int

@dataclass
class AlertRule:
    """알림 규칙 데이터 클래스"""
    name: str
    metric_type: str  # 'system' or 'ai'
    metric_name: str
    threshold: float
    operator: str  # '>', '<', '>=', '<=', '=='
    severity: str  # 'low', 'medium', 'high', 'critical'
    enabled: bool = True
    cooldown_minutes: int = 5

class MetricsCollector:
    """메트릭 수집기"""
    
    def __init__(self, db_path: str = "data/monitoring.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_database()
        self._network_counters = None
        logger.info("메트릭 수집기 초기화 완료")
    
    def _init_database(self):
        """데이터베이스 초기화"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    cpu_percent REAL,
                    memory_percent REAL,
                    memory_available_gb REAL,
                    disk_usage_percent REAL,
                    network_sent_mb REAL,
                    network_recv_mb REAL,
                    active_threads INTEGER,
                    process_count INTEGER,
                    load_average REAL
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS ai_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    total_requests INTEGER,
                    successful_requests INTEGER,
                    failed_requests INTEGER,
                    average_response_time REAL,
                    cache_hit_rate REAL,
                    active_sessions INTEGER,
                    queue_size INTEGER,
                    model_temperature REAL,
                    tokens_processed INTEGER
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    rule_name TEXT,
                    metric_type TEXT,
                    metric_name TEXT,
                    current_value REAL,
                    threshold REAL,
                    severity TEXT,
                    message TEXT,
                    resolved BOOLEAN DEFAULT FALSE
                )
            ''')
    
    @error_handler.handle_errors
    def collect_system_metrics(self) -> SystemMetrics:
        """시스템 메트릭 수집"""
        try:
            # CPU 사용률
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # 메모리 정보
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available_gb = memory.available / (1024 ** 3)
            
            # 디스크 사용률
            disk = psutil.disk_usage('/')
            disk_usage_percent = disk.percent
            
            # 네트워크 정보
            network = psutil.net_io_counters()
            if self._network_counters:
                network_sent_mb = (network.bytes_sent - self._network_counters.bytes_sent) / (1024 ** 2)
                network_recv_mb = (network.bytes_recv - self._network_counters.bytes_recv) / (1024 ** 2)
            else:
                network_sent_mb = network_recv_mb = 0.0
            self._network_counters = network
            
            # 프로세스 정보
            active_threads = threading.active_count()
            process_count = len(psutil.pids())
            
            # 로드 평균 (리눅스/맥OS만)
            try:
                load_average = psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else None
            except:
                load_average = None
            
            return SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_available_gb=memory_available_gb,
                disk_usage_percent=disk_usage_percent,
                network_sent_mb=network_sent_mb,
                network_recv_mb=network_recv_mb,
                active_threads=active_threads,
                process_count=process_count,
                load_average=load_average
            )
        except Exception as e:
            logger.error(f"시스템 메트릭 수집 실패: {e}")
            raise AISystemError(f"시스템 메트릭 수집 실패: {e}")
    
    @error_handler.handle_errors
    def collect_ai_metrics(self) -> AIMetrics:
        """AI 엔진 메트릭 수집"""
        try:
            # 성능 모니터에서 데이터 가져오기
            monitor_stats = global_performance_monitor.get_statistics()
            
            # 캐시 통계
            from ..utils.performance import global_cache
            cache_stats = global_cache.get_statistics()
            
            return AIMetrics(
                timestamp=datetime.now(),
                total_requests=monitor_stats.get('total_requests', 0),
                successful_requests=monitor_stats.get('successful_requests', 0),
                failed_requests=monitor_stats.get('failed_requests', 0),
                average_response_time=monitor_stats.get('avg_response_time', 0.0),
                cache_hit_rate=cache_stats.get('hit_rate', 0.0),
                active_sessions=monitor_stats.get('active_sessions', 0),
                queue_size=monitor_stats.get('queue_size', 0),
                model_temperature=0.7,  # 기본값
                tokens_processed=monitor_stats.get('tokens_processed', 0)
            )
        except Exception as e:
            logger.error(f"AI 메트릭 수집 실패: {e}")
            # 기본값 반환
            return AIMetrics(
                timestamp=datetime.now(),
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                average_response_time=0.0,
                cache_hit_rate=0.0,
                active_sessions=0,
                queue_size=0,
                model_temperature=0.7,
                tokens_processed=0
            )
    
    def save_metrics(self, system_metrics: SystemMetrics, ai_metrics: AIMetrics):
        """메트릭을 데이터베이스에 저장"""
        with sqlite3.connect(self.db_path) as conn:
            # 시스템 메트릭 저장
            conn.execute('''
                INSERT INTO system_metrics 
                (cpu_percent, memory_percent, memory_available_gb, disk_usage_percent,
                 network_sent_mb, network_recv_mb, active_threads, process_count, load_average)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                system_metrics.cpu_percent,
                system_metrics.memory_percent,
                system_metrics.memory_available_gb,
                system_metrics.disk_usage_percent,
                system_metrics.network_sent_mb,
                system_metrics.network_recv_mb,
                system_metrics.active_threads,
                system_metrics.process_count,
                system_metrics.load_average
            ))
            
            # AI 메트릭 저장
            conn.execute('''
                INSERT INTO ai_metrics 
                (total_requests, successful_requests, failed_requests, average_response_time,
                 cache_hit_rate, active_sessions, queue_size, model_temperature, tokens_processed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ai_metrics.total_requests,
                ai_metrics.successful_requests,
                ai_metrics.failed_requests,
                ai_metrics.average_response_time,
                ai_metrics.cache_hit_rate,
                ai_metrics.active_sessions,
                ai_metrics.queue_size,
                ai_metrics.model_temperature,
                ai_metrics.tokens_processed
            ))

class AlertSystem:
    """알림 시스템"""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.alert_rules: List[AlertRule] = []
        self.last_alert_times: Dict[str, datetime] = {}
        self.alert_callbacks: List[Callable] = []
        logger.info("알림 시스템 초기화 완료")
    
    def add_alert_rule(self, rule: AlertRule):
        """알림 규칙 추가"""
        self.alert_rules.append(rule)
        logger.info(f"알림 규칙 추가: {rule.name}")
    
    def add_default_rules(self):
        """기본 알림 규칙 추가"""
        default_rules = [
            AlertRule("높은 CPU 사용률", "system", "cpu_percent", 80.0, ">", "high"),
            AlertRule("높은 메모리 사용률", "system", "memory_percent", 85.0, ">", "high"),
            AlertRule("낮은 메모리 가용량", "system", "memory_available_gb", 1.0, "<", "medium"),
            AlertRule("높은 디스크 사용률", "system", "disk_usage_percent", 90.0, ">", "critical"),
            AlertRule("높은 응답 시간", "ai", "average_response_time", 5.0, ">", "medium"),
            AlertRule("낮은 캐시 히트율", "ai", "cache_hit_rate", 30.0, "<", "low"),
            AlertRule("많은 실패 요청", "ai", "failed_requests", 10, ">", "high"),
        ]
        
        for rule in default_rules:
            self.add_alert_rule(rule)
    
    def add_alert_callback(self, callback: Callable):
        """알림 콜백 함수 추가"""
        self.alert_callbacks.append(callback)
    
    @error_handler.handle_errors
    def check_alerts(self, system_metrics: SystemMetrics, ai_metrics: AIMetrics):
        """알림 규칙 확인"""
        current_time = datetime.now()
        
        for rule in self.alert_rules:
            if not rule.enabled:
                continue
            
            # 쿨다운 확인
            last_alert = self.last_alert_times.get(rule.name)
            if last_alert and (current_time - last_alert).total_seconds() < rule.cooldown_minutes * 60:
                continue
            
            # 메트릭 값 가져오기
            if rule.metric_type == "system":
                current_value = getattr(system_metrics, rule.metric_name, None)
            elif rule.metric_type == "ai":
                current_value = getattr(ai_metrics, rule.metric_name, None)
            else:
                continue
            
            if current_value is None:
                continue
            
            # 임계값 확인
            triggered = False
            if rule.operator == ">":
                triggered = current_value > rule.threshold
            elif rule.operator == "<":
                triggered = current_value < rule.threshold
            elif rule.operator == ">=":
                triggered = current_value >= rule.threshold
            elif rule.operator == "<=":
                triggered = current_value <= rule.threshold
            elif rule.operator == "==":
                triggered = current_value == rule.threshold
            
            if triggered:
                self._trigger_alert(rule, current_value, current_time)
    
    def _trigger_alert(self, rule: AlertRule, current_value: float, timestamp: datetime):
        """알림 발생"""
        message = f"{rule.name}: {rule.metric_name} = {current_value} {rule.operator} {rule.threshold}"
        
        # 데이터베이스에 알림 저장
        with sqlite3.connect(self.metrics_collector.db_path) as conn:
            conn.execute('''
                INSERT INTO alerts 
                (rule_name, metric_type, metric_name, current_value, threshold, severity, message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                rule.name,
                rule.metric_type,
                rule.metric_name,
                current_value,
                rule.threshold,
                rule.severity,
                message
            ))
        
        # 마지막 알림 시간 업데이트
        self.last_alert_times[rule.name] = timestamp
        
        # 콜백 함수 호출
        for callback in self.alert_callbacks:
            try:
                callback(rule, current_value, message)
            except Exception as e:
                logger.error(f"알림 콜백 실행 실패: {e}")
        
        logger.warning(f"🚨 [{rule.severity.upper()}] {message}")

class ReportGenerator:
    """보고서 생성기"""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        logger.info("보고서 생성기 초기화 완료")
    
    @error_handler.handle_errors
    def generate_system_report(self, hours: int = 24) -> Dict[str, Any]:
        """시스템 보고서 생성"""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        with sqlite3.connect(self.metrics_collector.db_path) as conn:
            cursor = conn.execute('''
                SELECT * FROM system_metrics 
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp DESC
            ''', (start_time, end_time))
            
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
        
        if not rows:
            return {"error": "데이터가 없습니다"}
        
        # 데이터 분석
        metrics_data = [dict(zip(columns, row)) for row in rows]
        
        report = {
            "period": f"{start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}",
            "total_records": len(metrics_data),
            "summary": {
                "cpu": {
                    "avg": sum(m['cpu_percent'] for m in metrics_data) / len(metrics_data),
                    "max": max(m['cpu_percent'] for m in metrics_data),
                    "min": min(m['cpu_percent'] for m in metrics_data)
                },
                "memory": {
                    "avg": sum(m['memory_percent'] for m in metrics_data) / len(metrics_data),
                    "max": max(m['memory_percent'] for m in metrics_data),
                    "min": min(m['memory_percent'] for m in metrics_data)
                },
                "disk": {
                    "avg": sum(m['disk_usage_percent'] for m in metrics_data) / len(metrics_data),
                    "max": max(m['disk_usage_percent'] for m in metrics_data),
                    "min": min(m['disk_usage_percent'] for m in metrics_data)
                }
            },
            "latest_metrics": metrics_data[0] if metrics_data else None
        }
        
        return report
    
    @error_handler.handle_errors
    def generate_ai_report(self, hours: int = 24) -> Dict[str, Any]:
        """AI 엔진 보고서 생성"""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        with sqlite3.connect(self.metrics_collector.db_path) as conn:
            cursor = conn.execute('''
                SELECT * FROM ai_metrics 
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp DESC
            ''', (start_time, end_time))
            
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
        
        if not rows:
            return {"error": "데이터가 없습니다"}
        
        # 데이터 분석
        metrics_data = [dict(zip(columns, row)) for row in rows]
        
        total_requests = metrics_data[0]['total_requests'] if metrics_data else 0
        successful_requests = metrics_data[0]['successful_requests'] if metrics_data else 0
        failed_requests = metrics_data[0]['failed_requests'] if metrics_data else 0
        
        success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
        
        report = {
            "period": f"{start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}",
            "total_records": len(metrics_data),
            "summary": {
                "requests": {
                    "total": total_requests,
                    "successful": successful_requests,
                    "failed": failed_requests,
                    "success_rate": success_rate
                },
                "performance": {
                    "avg_response_time": sum(m['average_response_time'] for m in metrics_data) / len(metrics_data),
                    "cache_hit_rate": sum(m['cache_hit_rate'] for m in metrics_data) / len(metrics_data),
                    "tokens_processed": sum(m['tokens_processed'] for m in metrics_data)
                }
            },
            "latest_metrics": metrics_data[0] if metrics_data else None
        }
        
        return report

class MonitoringDashboard:
    """모니터링 대시보드"""
    
    def __init__(self, port: int = 8050):
        self.port = port
        self.metrics_collector = MetricsCollector()
        self.alert_system = AlertSystem(self.metrics_collector)
        self.report_generator = ReportGenerator(self.metrics_collector)
        
        # 기본 알림 규칙 추가
        self.alert_system.add_default_rules()
        
        # 모니터링 스레드
        self.monitoring_thread = None
        self.is_running = False
        
        # 실시간 데이터 저장
        self.real_time_data = {
            'system': deque(maxlen=100),
            'ai': deque(maxlen=100)
        }
        
        logger.info(f"모니터링 대시보드 초기화 완료 (포트: {port})")
    
    def start_monitoring(self, interval: int = 30):
        """모니터링 시작"""
        if self.is_running:
            logger.warning("모니터링이 이미 실행 중입니다")
            return
        
        self.is_running = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(interval,),
            daemon=True
        )
        self.monitoring_thread.start()
        logger.info(f"모니터링 시작 (수집 간격: {interval}초)")
    
    def stop_monitoring(self):
        """모니터링 중지"""
        self.is_running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("모니터링 중지")
    
    def _monitoring_loop(self, interval: int):
        """모니터링 루프"""
        while self.is_running:
            try:
                # 메트릭 수집
                system_metrics = self.metrics_collector.collect_system_metrics()
                ai_metrics = self.metrics_collector.collect_ai_metrics()
                
                # 데이터베이스에 저장
                self.metrics_collector.save_metrics(system_metrics, ai_metrics)
                
                # 실시간 데이터 업데이트
                self.real_time_data['system'].append(asdict(system_metrics))
                self.real_time_data['ai'].append(asdict(ai_metrics))
                
                # 알림 확인
                self.alert_system.check_alerts(system_metrics, ai_metrics)
                
                time.sleep(interval)
                
            except Exception as e:
                logger.error(f"모니터링 루프 오류: {e}")
                time.sleep(interval)
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """대시보드 데이터 반환"""
        return {
            'real_time_system': list(self.real_time_data['system'])[-20:],  # 최근 20개
            'real_time_ai': list(self.real_time_data['ai'])[-20:],
            'system_report': self.report_generator.generate_system_report(hours=1),
            'ai_report': self.report_generator.generate_ai_report(hours=1)
        }
    
    def create_dash_app(self):
        """Dash 웹 앱 생성"""
        if not DASH_AVAILABLE:
            logger.error("Dash가 설치되지 않았습니다. pip install dash plotly 를 실행하세요")
            return None
        
        app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
        
        app.layout = dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.H1("🤖 Personal AI Assistant - 모니터링 대시보드", className="text-center mb-4")
                ])
            ]),
            
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("시스템 메트릭", className="card-title"),
                            dcc.Graph(id="system-metrics-graph")
                        ])
                    ])
                ], width=6),
                
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("AI 엔진 메트릭", className="card-title"),
                            dcc.Graph(id="ai-metrics-graph")
                        ])
                    ])
                ], width=6)
            ], className="mb-4"),
            
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("시스템 상태", className="card-title"),
                            html.Div(id="system-status")
                        ])
                    ])
                ], width=6),
                
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("최근 알림", className="card-title"),
                            html.Div(id="recent-alerts")
                        ])
                    ])
                ], width=6)
            ]),
            
            dcc.Interval(
                id='interval-component',
                interval=10*1000,  # 10초마다 업데이트
                n_intervals=0
            )
        ], fluid=True)
        
        @app.callback(
            [Output('system-metrics-graph', 'figure'),
             Output('ai-metrics-graph', 'figure'),
             Output('system-status', 'children'),
             Output('recent-alerts', 'children')],
            [Input('interval-component', 'n_intervals')]
        )
        def update_dashboard(n):
            return self._update_dashboard_callback()
        
        return app
    
    def _update_dashboard_callback(self):
        """대시보드 업데이트 콜백"""
        try:
            data = self.get_dashboard_data()
            
            # 시스템 메트릭 그래프
            system_fig = self._create_system_graph(data['real_time_system'])
            
            # AI 메트릭 그래프
            ai_fig = self._create_ai_graph(data['real_time_ai'])
            
            # 시스템 상태
            system_status = self._create_system_status(data['system_report'])
            
            # 최근 알림
            recent_alerts = self._create_alerts_display()
            
            return system_fig, ai_fig, system_status, recent_alerts
            
        except Exception as e:
            logger.error(f"대시보드 업데이트 오류: {e}")
            return {}, {}, f"오류: {e}", "알림을 불러올 수 없습니다"
    
    def _create_system_graph(self, data: List[Dict]):
        """시스템 메트릭 그래프 생성"""
        if not data or not PLOTLY_AVAILABLE:
            return {}
        
        timestamps = [item['timestamp'] for item in data]
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('CPU 사용률', '메모리 사용률', '디스크 사용률', '활성 스레드'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}]]
        )
        
        # CPU 사용률
        fig.add_trace(
            go.Scatter(x=timestamps, y=[item['cpu_percent'] for item in data],
                      mode='lines+markers', name='CPU %', line=dict(color='red')),
            row=1, col=1
        )
        
        # 메모리 사용률
        fig.add_trace(
            go.Scatter(x=timestamps, y=[item['memory_percent'] for item in data],
                      mode='lines+markers', name='Memory %', line=dict(color='blue')),
            row=1, col=2
        )
        
        # 디스크 사용률
        fig.add_trace(
            go.Scatter(x=timestamps, y=[item['disk_usage_percent'] for item in data],
                      mode='lines+markers', name='Disk %', line=dict(color='green')),
            row=2, col=1
        )
        
        # 활성 스레드
        fig.add_trace(
            go.Scatter(x=timestamps, y=[item['active_threads'] for item in data],
                      mode='lines+markers', name='Threads', line=dict(color='purple')),
            row=2, col=2
        )
        
        fig.update_layout(height=400, showlegend=False, title_text="시스템 메트릭")
        return fig
    
    def _create_ai_graph(self, data: List[Dict]):
        """AI 메트릭 그래프 생성"""
        if not data or not PLOTLY_AVAILABLE:
            return {}
        
        timestamps = [item['timestamp'] for item in data]
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('요청 수', '응답 시간', '캐시 히트율', '활성 세션'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}]]
        )
        
        # 총 요청 수
        fig.add_trace(
            go.Scatter(x=timestamps, y=[item['total_requests'] for item in data],
                      mode='lines+markers', name='Total Requests', line=dict(color='orange')),
            row=1, col=1
        )
        
        # 평균 응답 시간
        fig.add_trace(
            go.Scatter(x=timestamps, y=[item['average_response_time'] for item in data],
                      mode='lines+markers', name='Response Time', line=dict(color='red')),
            row=1, col=2
        )
        
        # 캐시 히트율
        fig.add_trace(
            go.Scatter(x=timestamps, y=[item['cache_hit_rate'] for item in data],
                      mode='lines+markers', name='Cache Hit Rate', line=dict(color='green')),
            row=2, col=1
        )
        
        # 활성 세션
        fig.add_trace(
            go.Scatter(x=timestamps, y=[item['active_sessions'] for item in data],
                      mode='lines+markers', name='Active Sessions', line=dict(color='blue')),
            row=2, col=2
        )
        
        fig.update_layout(height=400, showlegend=False, title_text="AI 엔진 메트릭")
        return fig
    
    def _create_system_status(self, report: Dict) -> html.Div:
        """시스템 상태 표시 생성"""
        if 'error' in report:
            return html.Div([
                dbc.Alert("데이터를 불러올 수 없습니다", color="warning")
            ])
        
        latest = report.get('latest_metrics', {})
        if not latest:
            return html.Div([
                dbc.Alert("최신 데이터가 없습니다", color="info")
            ])
        
        cpu_color = "danger" if latest['cpu_percent'] > 80 else "warning" if latest['cpu_percent'] > 60 else "success"
        memory_color = "danger" if latest['memory_percent'] > 85 else "warning" if latest['memory_percent'] > 70 else "success"
        
        return html.Div([
            dbc.Row([
                dbc.Col([
                    dbc.Badge(f"CPU: {latest['cpu_percent']:.1f}%", color=cpu_color, className="me-2")
                ]),
                dbc.Col([
                    dbc.Badge(f"메모리: {latest['memory_percent']:.1f}%", color=memory_color, className="me-2")
                ])
            ]),
            html.Hr(),
            html.P([
                html.Strong("활성 스레드: "), f"{latest['active_threads']}개",
                html.Br(),
                html.Strong("프로세스 수: "), f"{latest['process_count']}개",
                html.Br(),
                html.Strong("가용 메모리: "), f"{latest['memory_available_gb']:.1f}GB"
            ])
        ])
    
    def _create_alerts_display(self) -> html.Div:
        """최근 알림 표시 생성"""
        try:
            with sqlite3.connect(self.metrics_collector.db_path) as conn:
                cursor = conn.execute('''
                    SELECT timestamp, severity, message 
                    FROM alerts 
                    WHERE timestamp >= datetime('now', '-24 hours')
                    ORDER BY timestamp DESC 
                    LIMIT 5
                ''')
                alerts = cursor.fetchall()
            
            if not alerts:
                return html.Div([
                    dbc.Alert("최근 24시간 동안 알림이 없습니다", color="success")
                ])
            
            alert_items = []
            for timestamp, severity, message in alerts:
                color = {
                    'low': 'info',
                    'medium': 'warning', 
                    'high': 'danger',
                    'critical': 'danger'
                }.get(severity, 'secondary')
                
                alert_items.append(
                    dbc.Alert([
                        html.Strong(f"[{severity.upper()}] "),
                        message,
                        html.Small(f" - {timestamp}", className="text-muted d-block")
                    ], color=color, className="py-2")
                )
            
            return html.Div(alert_items)
            
        except Exception as e:
            return html.Div([
                dbc.Alert(f"알림 데이터 로드 오류: {e}", color="danger")
            ])
    
    def run_dashboard(self):
        """대시보드 실행"""
        app = self.create_dash_app()
        if app:
            logger.info(f"대시보드 서버 시작: http://localhost:{self.port}")
            app.run_server(debug=False, host='0.0.0.0', port=self.port)
        else:
            logger.error("대시보드를 시작할 수 없습니다")

# 전역 모니터링 대시보드 인스턴스
global_dashboard = MonitoringDashboard()

def start_monitoring():
    """전역 모니터링 시작"""
    global_dashboard.start_monitoring()

def stop_monitoring():
    """전역 모니터링 중지"""
    global_dashboard.stop_monitoring()

def get_monitoring_status() -> Dict[str, Any]:
    """모니터링 상태 반환"""
    return {
        "is_running": global_dashboard.is_running,
        "dashboard_data": global_dashboard.get_dashboard_data()
    }

logger.info("모니터링 대시보드 시스템이 초기화되었습니다.")
