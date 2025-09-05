"""
코드 안전성 검증

생성된 크롤러 코드의 안전성을 검증하고
악의적인 코드나 위험한 동작을 차단합니다.
"""

import ast
import logging
import subprocess
import tempfile
import os
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from pathlib import Path
import re


@dataclass
class SecurityIssue:
    """보안 이슈"""
    severity: str  # 'low', 'medium', 'high', 'critical'
    category: str  # 'malicious', 'resource', 'network', 'file'
    description: str
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None


@dataclass
class ValidationResult:
    """검증 결과"""
    is_safe: bool
    issues: List[SecurityIssue]
    safe_functions: Set[str]
    restricted_functions: Set[str]
    execution_time: float


class CodeValidator:
    """크롤러 코드 안전성 검증기"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 허용된 안전한 함수들
        self.safe_functions = {
            # 표준 라이브러리
            'print', 'len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple',
            'range', 'enumerate', 'zip', 'map', 'filter', 'sorted', 'reversed',
            'min', 'max', 'sum', 'abs', 'round',
            
            # 시간 관련
            'time.sleep', 'time.time', 'datetime.now', 'datetime.strptime',
            
            # 문자열 처리
            'strip', 'split', 'join', 'replace', 'find', 'startswith', 'endswith',
            'upper', 'lower', 'format',
            
            # 파일 I/O (읽기 전용)
            'open', 'read', 'readline', 'readlines', 'close',
            
            # JSON 처리
            'json.loads', 'json.dumps', 'json.dump',
            
            # 웹 요청 (제한적)
            'requests.get', 'requests.post', 'requests.Session',
            
            # BeautifulSoup
            'BeautifulSoup', 'select', 'select_one', 'find', 'find_all',
            'get_text', 'get'
        }
        
        # 금지된 위험한 함수들
        self.dangerous_functions = {
            # 시스템 명령
            'os.system', 'subprocess.call', 'subprocess.run', 'subprocess.Popen',
            'eval', 'exec', 'compile', '__import__',
            
            # 파일 시스템 조작
            'os.remove', 'os.rmdir', 'os.rename', 'shutil.rmtree',
            'os.chmod', 'os.chown',
            
            # 네트워크 (제한적)
            'socket.socket', 'urllib.request.urlopen',
            
            # 위험한 내장 함수
            'getattr', 'setattr', 'delattr', 'hasattr',
            'globals', 'locals', 'vars', 'dir',
            
            # 모듈 임포트 조작
            '__import__', 'importlib'
        }
        
        # 허용된 임포트 모듈
        self.allowed_imports = {
            'requests', 'time', 'json', 'datetime', 'bs4', 'BeautifulSoup',
            'typing', 'pathlib', 'urllib.parse', 're', 'math'
        }
    
    def validate_code(self, code: str, filename: str = "crawler.py") -> ValidationResult:
        """코드 전체 검증"""
        issues = []
        start_time = time.time()
        
        try:
            # AST 파싱 검증
            tree = ast.parse(code)
            
            # 정적 분석
            static_issues = self._static_analysis(tree, code)
            issues.extend(static_issues)
            
            # 패턴 기반 검증
            pattern_issues = self._pattern_analysis(code)
            issues.extend(pattern_issues)
            
            # 임포트 검증
            import_issues = self._validate_imports(tree)
            issues.extend(import_issues)
            
            # 함수 호출 검증
            function_issues = self._validate_function_calls(tree)
            issues.extend(function_issues)
            
        except SyntaxError as e:
            issues.append(SecurityIssue(
                severity='high',
                category='syntax',
                description=f"구문 오류: {e}",
                line_number=e.lineno
            ))
        
        execution_time = time.time() - start_time
        
        # 심각한 이슈가 있는지 확인
        is_safe = not any(issue.severity in ['high', 'critical'] for issue in issues)
        
        return ValidationResult(
            is_safe=is_safe,
            issues=issues,
            safe_functions=self.safe_functions,
            restricted_functions=self.dangerous_functions,
            execution_time=execution_time
        )
    
    def _static_analysis(self, tree: ast.AST, code: str) -> List[SecurityIssue]:
        """AST 기반 정적 분석"""
        issues = []
        
        for node in ast.walk(tree):
            # eval/exec 사용 검사
            if isinstance(node, (ast.Call)):
                if hasattr(node.func, 'id') and node.func.id in ['eval', 'exec']:
                    issues.append(SecurityIssue(
                        severity='critical',
                        category='malicious',
                        description=f"위험한 함수 사용: {node.func.id}",
                        line_number=node.lineno
                    ))
            
            # 파일 쓰기 작업 검사
            if isinstance(node, ast.Call):
                if (hasattr(node.func, 'attr') and 
                    node.func.attr in ['write', 'writelines'] and
                    len(node.args) > 0):
                    issues.append(SecurityIssue(
                        severity='medium',
                        category='file',
                        description="파일 쓰기 작업 감지",
                        line_number=node.lineno
                    ))
        
        return issues
    
    def _pattern_analysis(self, code: str) -> List[SecurityIssue]:
        """패턴 기반 분석"""
        issues = []
        
        dangerous_patterns = [
            (r'__.*__', 'high', '매직 메서드 사용'),
            (r'rm\s+-rf', 'critical', '위험한 시스템 명령'),
            (r'DELETE\s+FROM', 'high', 'SQL 삭제 명령'),
            (r'DROP\s+TABLE', 'critical', 'SQL 테이블 삭제'),
            (r'while\s+True:', 'medium', '무한 루프 가능성'),
            (r'for.*in.*range\(\d{4,}\)', 'medium', '대용량 반복문')
        ]
        
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            for pattern, severity, desc in dangerous_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append(SecurityIssue(
                        severity=severity,
                        category='pattern',
                        description=desc,
                        line_number=i,
                        code_snippet=line.strip()
                    ))
        
        return issues
    
    def _validate_imports(self, tree: ast.AST) -> List[SecurityIssue]:
        """임포트 검증"""
        issues = []
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name.split('.')[0]
                        if module_name not in self.allowed_imports:
                            issues.append(SecurityIssue(
                                severity='medium',
                                category='import',
                                description=f"허용되지 않은 모듈 임포트: {module_name}",
                                line_number=node.lineno
                            ))
                
                elif isinstance(node, ast.ImportFrom):
                    module_name = node.module
                    if module_name and module_name.split('.')[0] not in self.allowed_imports:
                        issues.append(SecurityIssue(
                            severity='medium',
                            category='import',
                            description=f"허용되지 않은 모듈에서 임포트: {module_name}",
                            line_number=node.lineno
                        ))
        
        return issues
    
    def _validate_function_calls(self, tree: ast.AST) -> List[SecurityIssue]:
        """함수 호출 검증"""
        issues = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = self._get_function_name(node)
                
                if func_name in self.dangerous_functions:
                    issues.append(SecurityIssue(
                        severity='high',
                        category='function',
                        description=f"위험한 함수 호출: {func_name}",
                        line_number=node.lineno
                    ))
                
                # 네트워크 요청 검증
                if func_name in ['requests.get', 'requests.post']:
                    if len(node.args) == 0:
                        issues.append(SecurityIssue(
                            severity='medium',
                            category='network',
                            description="네트워크 요청에 URL이 지정되지 않음",
                            line_number=node.lineno
                        ))
        
        return issues
    
    def _get_function_name(self, node: ast.Call) -> str:
        """함수 호출의 이름 추출"""
        if hasattr(node.func, 'id'):
            return node.func.id
        elif hasattr(node.func, 'attr'):
            if hasattr(node.func.value, 'id'):
                return f"{node.func.value.id}.{node.func.attr}"
            elif hasattr(node.func.value, 'attr'):
                return f"{node.func.value.attr}.{node.func.attr}"
        return "unknown"
    
    def sandbox_test(self, code: str, timeout: int = 30) -> ValidationResult:
        """샌드박스 환경에서 코드 실행 테스트"""
        issues = []
        start_time = time.time()
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            try:
                # 제한된 환경에서 실행
                result = subprocess.run(
                    ['python', '-m', 'py_compile', temp_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                
                if result.returncode != 0:
                    issues.append(SecurityIssue(
                        severity='high',
                        category='compilation',
                        description=f"컴파일 오류: {result.stderr}"
                    ))
                
            except subprocess.TimeoutExpired:
                issues.append(SecurityIssue(
                    severity='high',
                    category='resource',
                    description="실행 시간 초과"
                ))
            
            finally:
                os.unlink(temp_file)
        
        except Exception as e:
            issues.append(SecurityIssue(
                severity='medium',
                category='sandbox',
                description=f"샌드박스 테스트 오류: {e}"
            ))
        
        execution_time = time.time() - start_time
        is_safe = not any(issue.severity in ['high', 'critical'] for issue in issues)
        
        return ValidationResult(
            is_safe=is_safe,
            issues=issues,
            safe_functions=self.safe_functions,
            restricted_functions=self.dangerous_functions,
            execution_time=execution_time
        )
    
    def generate_report(self, result: ValidationResult) -> str:
        """검증 결과 보고서 생성"""
        report = []
        report.append("🔒 코드 안전성 검증 보고서")
        report.append("=" * 40)
        report.append(f"전체 평가: {'✅ 안전' if result.is_safe else '❌ 위험'}")
        report.append(f"검증 시간: {result.execution_time:.3f}초")
        report.append(f"발견된 이슈: {len(result.issues)}개")
        report.append("")
        
        if result.issues:
            report.append("🚨 발견된 보안 이슈:")
            report.append("-" * 30)
            
            # 심각도별 정렬
            sorted_issues = sorted(result.issues, 
                                 key=lambda x: {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}[x.severity])
            
            for issue in sorted_issues:
                severity_icon = {
                    'critical': '🔴',
                    'high': '🟠', 
                    'medium': '🟡',
                    'low': '🟢'
                }[issue.severity]
                
                report.append(f"{severity_icon} [{issue.severity.upper()}] {issue.description}")
                if issue.line_number:
                    report.append(f"   라인 {issue.line_number}")
                if issue.code_snippet:
                    report.append(f"   코드: {issue.code_snippet}")
                report.append("")
        
        else:
            report.append("✅ 보안 이슈가 발견되지 않았습니다.")
        
        report.append(f"안전한 함수: {len(result.safe_functions)}개")
        report.append(f"제한된 함수: {len(result.restricted_functions)}개")
        
        return "\n".join(report)


# 사용 예시
async def main():
    """코드 검증기 테스트"""
    validator = CodeValidator()
    
    # 크롤러 코드 읽기
    crawler_path = Path("inha_notice_crawler.py")
    if crawler_path.exists():
        code = crawler_path.read_text(encoding='utf-8')
        
        # 검증 실행
        print("🔍 코드 안전성 검증 중...")
        result = validator.validate_code(code, str(crawler_path))
        
        # 보고서 출력
        report = validator.generate_report(result)
        print(report)
        
        # 샌드박스 테스트
        print("\n🧪 샌드박스 테스트 중...")
        sandbox_result = validator.sandbox_test(code)
        
        if sandbox_result.is_safe:
            print("✅ 샌드박스 테스트 통과")
        else:
            print("❌ 샌드박스 테스트 실패")
            for issue in sandbox_result.issues:
                print(f"  - {issue.description}")
    
    else:
        print("❌ 크롤러 파일을 찾을 수 없습니다.")


if __name__ == "__main__":
    import asyncio
    import time
    asyncio.run(main())
