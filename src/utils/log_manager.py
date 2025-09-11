"""
로그 관리 및 유지보수 모듈
"""
import gzip
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional
from .logger import get_logger

logger = get_logger(__name__)


class LogManager:
    """로그 파일 관리 클래스"""
    
    def __init__(self, logs_dir: Path):
        self.logs_dir = logs_dir
        self.log_files = [
            "personal_ai_assistant.log",
            "discord_bot.log", 
            "ai_engine.log",
            "errors.log"
        ]
    
    def rotate_logs(self, max_size_mb: int = 50, keep_days: int = 30):
        """로그 로테이션 수행"""
        logger.info(f"로그 로테이션 시작: 최대크기={max_size_mb}MB, 보관기간={keep_days}일")
        rotation_start = datetime.now()
        
        rotated_count = 0
        total_size_before = 0
        total_size_after = 0
        
        for log_file in self.log_files:
            log_path = self.logs_dir / log_file
            
            if not log_path.exists():
                logger.debug(f"로그 파일 없음: {log_file}")
                continue
            
            # 파일 크기 확인
            size_mb = log_path.stat().st_size / (1024 * 1024)
            total_size_before += size_mb
            
            logger.debug(f"로그 파일 검사: {log_file} ({size_mb:.2f}MB)")
            
            if size_mb > max_size_mb:
                logger.info(f"로그 파일 로테이션 필요: {log_file} ({size_mb:.2f}MB > {max_size_mb}MB)")
                self._rotate_file(log_path)
                rotated_count += 1
                
                # 로테이션 후 크기 재계산
                if log_path.exists():
                    new_size = log_path.stat().st_size / (1024 * 1024)
                    total_size_after += new_size
                    logger.debug(f"로테이션 후 크기: {log_file} ({new_size:.2f}MB)")
            else:
                total_size_after += size_mb
        
        # 오래된 로그 파일 정리
        cleaned_count = self._cleanup_old_logs(keep_days)
        
        rotation_time = (datetime.now() - rotation_start).total_seconds()
        logger.info(f"로그 로테이션 완료: 로테이션={rotated_count}개, 정리={cleaned_count}개, "
                   f"크기변화={total_size_before:.2f}MB→{total_size_after:.2f}MB, "
                   f"소요시간={rotation_time:.2f}초")
    
    def _rotate_file(self, log_path: Path):
        """개별 로그 파일 로테이션"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        original_size = log_path.stat().st_size
        
        # 압축된 백업 파일 생성
        backup_path = log_path.parent / f"{log_path.stem}_{timestamp}.log.gz"
        
        try:
            logger.debug(f"로그 파일 압축 시작: {log_path} ({original_size} bytes)")
            
            with open(log_path, 'rb') as f_in:
                with gzip.open(backup_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # 압축 결과 확인
            compressed_size = backup_path.stat().st_size
            compression_ratio = (1 - compressed_size / original_size) * 100
            
            # 원본 파일 비우기
            log_path.write_text("")
            
            logger.info(f"로그 파일 로테이션 완료: {log_path} → {backup_path} "
                       f"(압축률: {compression_ratio:.1f}%)")
            
        except Exception as e:
            logger.error(f"로그 파일 로테이션 실패 {log_path}: {e}")
    
    def _cleanup_old_logs(self, keep_days: int) -> int:
        """오래된 로그 파일 정리"""
        logger.debug(f"오래된 로그 파일 정리 시작: {keep_days}일 이전")
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        cleaned_count = 0
        total_freed_space = 0
        
        # .gz 파일들 확인
        for gz_file in self.logs_dir.glob("*.log.gz"):
            try:
                file_time = datetime.fromtimestamp(gz_file.stat().st_mtime)
                
                if file_time < cutoff_date:
                    file_size = gz_file.stat().st_size
                    gz_file.unlink()
                    
                    cleaned_count += 1
                    total_freed_space += file_size
                    logger.debug(f"오래된 로그 파일 삭제: {gz_file} ({file_size} bytes)")
                    
            except Exception as e:
                logger.error(f"로그 파일 삭제 실패 {gz_file}: {e}")
        
        if cleaned_count > 0:
            freed_mb = total_freed_space / (1024 * 1024)
            logger.info(f"오래된 로그 정리 완료: {cleaned_count}개 파일, {freed_mb:.2f}MB 확보")
        else:
            logger.debug("정리할 오래된 로그 파일 없음")
            
        return cleaned_count
    
    def get_log_stats(self) -> dict:
        """로그 파일 통계 반환"""
        logger.debug("로그 파일 통계 수집 중...")
        
        stats = {
            'total_files': 0,
            'total_size_mb': 0,
            'files': {},
            'compressed_files': 0,
            'compressed_size_mb': 0
        }
        
        # 현재 로그 파일들
        for log_file in self.log_files:
            log_path = self.logs_dir / log_file
            
            if log_path.exists():
                size_mb = log_path.stat().st_size / (1024 * 1024)
                stats['files'][log_file] = {
                    'size_mb': round(size_mb, 2),
                    'lines': self._count_lines(log_path)
                }
                stats['total_size_mb'] += size_mb
                stats['total_files'] += 1
        
        # 압축된 백업 파일들
        backup_files = list(self.logs_dir.glob("*.log.gz"))
        if backup_files:
            backup_size = sum(f.stat().st_size for f in backup_files) / (1024 * 1024)
            stats['backup_files'] = len(backup_files)
            stats['backup_size_mb'] = round(backup_size, 2)
        
        stats['total_size_mb'] = round(stats['total_size_mb'], 2)
        
        return stats
    
    def _count_lines(self, file_path: Path) -> int:
        """파일의 라인 수 카운트"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return sum(1 for _ in f)
        except Exception:
            return 0
    
    def compress_logs(self):
        """현재 로그 파일들을 즉시 압축"""
        logger.info("로그 파일 압축 시작")
        
        for log_file in self.log_files:
            log_path = self.logs_dir / log_file
            
            if log_path.exists() and log_path.stat().st_size > 0:
                self._rotate_file(log_path)
        
        logger.info("로그 파일 압축 완료")
    
    def tail_log(self, log_name: str, lines: int = 50) -> List[str]:
        """로그 파일의 마지막 N줄 반환"""
        log_path = self.logs_dir / log_name
        
        if not log_path.exists():
            return []
        
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                return f.readlines()[-lines:]
        except Exception as e:
            logger.error(f"로그 읽기 실패 {log_path}: {e}")
            return []


class PerformanceOptimizer:
    """성능 최적화 관리 클래스"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
    
    def cleanup_temp_files(self):
        """임시 파일 정리"""
        logger.info("임시 파일 정리 시작")
        
        temp_patterns = [
            "*.tmp",
            "*.temp", 
            "*.cache",
            "*.pid.old"
        ]
        
        cleaned_count = 0
        
        for pattern in temp_patterns:
            for temp_file in self.data_dir.glob(pattern):
                try:
                    # 1시간 이상 된 파일만 삭제
                    file_age = datetime.now() - datetime.fromtimestamp(temp_file.stat().st_mtime)
                    
                    if file_age > timedelta(hours=1):
                        temp_file.unlink()
                        cleaned_count += 1
                        logger.debug(f"임시 파일 삭제: {temp_file}")
                        
                except Exception as e:
                    logger.warning(f"임시 파일 삭제 실패 {temp_file}: {e}")
        
        logger.info(f"임시 파일 정리 완료: {cleaned_count}개 삭제")
    
    def optimize_data_directory(self):
        """데이터 디렉토리 최적화"""
        logger.info("데이터 디렉토리 최적화 시작")
        
        # 임시 파일 정리
        self.cleanup_temp_files()
        
        # TODO: 데이터베이스 최적화 (향후 구현)
        # TODO: 캐시 파일 정리 (향후 구현)
        
        logger.info("데이터 디렉토리 최적화 완료")
    
    def get_disk_usage(self) -> dict:
        """디스크 사용량 정보 반환"""
        try:
            total_size = 0
            file_count = 0
            
            for item in self.data_dir.rglob("*"):
                if item.is_file():
                    total_size += item.stat().st_size
                    file_count += 1
            
            return {
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'file_count': file_count,
                'directory': str(self.data_dir)
            }
            
        except Exception as e:
            logger.error(f"디스크 사용량 계산 실패: {e}")
            return {'error': str(e)}
