"""
프롬프트 최적화 관련 명령어들 (create-ab-test, analyze-ab-test, optimize-prompts)
"""

import asyncio
import click
from src.utils.logger import get_logger
from .utils import async_command, handle_errors


@click.command(name="create-ab-test")
@click.option("--test-name", default="response_quality_test", help="A/B 테스트 이름")
@click.option("--duration", default=7, help="테스트 기간 (일)")
def create_ab_test(test_name, duration):
    """프롬프트 A/B 테스트 생성 및 시작"""
    from src.ai_engine.prompt_optimizer import PromptOptimizer, PromptVariant, MetricType
    
    logger = get_logger("cli")
    
    try:
        click.echo("🧪 A/B 테스트 생성 중...")
        
        optimizer = PromptOptimizer()
        
        # 테스트 변형 생성
        variant_a = PromptVariant(
            id="variant_a_formal",
            name="formal_response",
            template="""다음 사용자 요청에 대해 공식적이고 전문적인 톤으로 응답해주세요:

사용자 요청: $user_request

응답은 다음 구조를 따르세요:
1. 요청 이해 확인
2. 구체적인 해결책 제시
3. 추가 필요사항 안내

전문적이고 정확한 정보를 제공해주세요.""",
            description="공식적이고 전문적인 톤의 응답"
        )
        
        variant_b = PromptVariant(
            id="variant_b_casual",
            name="casual_response", 
            template="""다음 사용자 요청에 대해 친근하고 대화적인 톤으로 응답해주세요:

사용자 요청: $user_request

친구처럼 편안하게 대화하면서도 도움이 되는 정보를 제공해주세요.
이해하기 쉽고 실용적인 조언을 해주세요.""",
            description="친근하고 대화적인 톤의 응답"
        )
        
        # A/B 테스트 생성
        test = optimizer.create_ab_test(
            name=test_name,
            description="응답 품질과 사용자 만족도 개선을 위한 톤 비교 테스트",
            variants=[variant_a, variant_b],
            traffic_split={"variant_a_formal": 0.5, "variant_b_casual": 0.5},
            target_metrics=[MetricType.USER_SATISFACTION, MetricType.USER_ENGAGEMENT],
            min_sample_size=50
        )
        
        # 테스트 시작
        success = optimizer.start_test(test.id)
        
        if success:
            click.echo(f"✅ A/B 테스트 생성 및 시작 완료")
            click.echo(f"테스트 ID: {test.id}")
            click.echo(f"테스트 이름: {test.name}")
            click.echo(f"변형 수: {len(test.variants)}")
            click.echo(f"최소 샘플 크기: {test.min_sample_size}")
            click.echo(f"대상 지표: {[m.value for m in test.target_metrics]}")
        else:
            click.echo("❌ A/B 테스트 시작 실패")
            
    except Exception as e:
        logger.error(f"A/B 테스트 생성 실패: {e}", exc_info=True)
        click.echo(f"❌ A/B 테스트 생성 실패: {e}")


@click.command(name="analyze-ab-test")
@click.option("--test-id", help="분석할 테스트 ID (없으면 모든 활성 테스트)")
def analyze_ab_test(test_id):
    """A/B 테스트 결과 분석"""
    from src.ai_engine.prompt_optimizer import PromptOptimizer
    
    logger = get_logger("cli")
    
    try:
        click.echo("📊 A/B 테스트 결과 분석 중...")
        
        optimizer = PromptOptimizer()
        
        if test_id:
            # 특정 테스트 분석
            analysis = optimizer.analyze_test_results(test_id)
            
            if "error" in analysis:
                click.echo(f"❌ 분석 실패: {analysis['error']}")
                return
                
            click.echo(f"\n📋 테스트 분석 결과: {analysis['test_name']}")
            click.echo(f"상태: {analysis['status']}")
            click.echo(f"총 샘플: {analysis['total_samples']}")
            
            # 변형별 결과
            for variant_id, variant_data in analysis["variants"].items():
                click.echo(f"\n🔬 변형: {variant_data['name']}")
                click.echo(f"샘플 크기: {variant_data['sample_size']}")
                
                for metric, stats in variant_data["metrics"].items():
                    click.echo(f"  {metric}:")
                    click.echo(f"    평균: {stats['mean']:.3f}")
                    click.echo(f"    표준편차: {stats['std']:.3f}")
                    click.echo(f"    범위: {stats['min']:.3f} - {stats['max']:.3f}")
            
            # 통계적 유의성
            significance = analysis.get("statistical_significance", {})
            if significance:
                click.echo(f"\n📈 통계적 유의성:")
                for metric, data in significance.items():
                    if data.get("significant", False):
                        click.echo(f"  {metric}: ✅ 유의미 (승자: {data['winner']})")
                        click.echo(f"    효과 크기: {data['effect_size']:.1%}")
                    else:
                        click.echo(f"  {metric}: ❌ 유의하지 않음")
            
            # 추천사항
            recommendations = analysis.get("recommendations", [])
            if recommendations:
                click.echo(f"\n💡 추천사항:")
                for rec in recommendations:
                    click.echo(f"  - {rec}")
                    
        else:
            # 모든 활성 테스트 분석
            if not optimizer.active_tests:
                click.echo("활성 A/B 테스트가 없습니다.")
                return
                
            for test_id, test in optimizer.active_tests.items():
                click.echo(f"\n📊 테스트: {test.name} ({test_id})")
                analysis = optimizer.analyze_test_results(test_id)
                click.echo(f"샘플 수: {analysis.get('total_samples', 0)}")
                click.echo(f"상태: {analysis.get('status', 'unknown')}")
                
        click.echo("\n✅ A/B 테스트 분석 완료")
        
    except Exception as e:
        logger.error(f"A/B 테스트 분석 실패: {e}", exc_info=True)
        click.echo(f"❌ A/B 테스트 분석 실패: {e}")


@click.command(name="optimize-prompts")
def optimize_prompts():
    """프롬프트 성능 최적화 실행"""
    from src.config import get_settings
    from src.ai_engine.natural_language import NaturalLanguageProcessor
    
    logger = get_logger("cli")
    
    async def run_optimization():
        try:
            click.echo("⚡ 프롬프트 성능 최적화 시작...")
            
            settings = get_settings()
            nlp = NaturalLanguageProcessor(settings)
            await nlp.initialize()
            
            # 최적화 실행
            result = await nlp.optimize_prompt_performance()
            
            if result["status"] == "success":
                click.echo(f"✅ 최적화 완료")
                click.echo(f"적용된 최적화: {result['optimizations_applied']}개")
                
                for test_id, analysis in result["results"].items():
                    click.echo(f"\n📊 {analysis.get('test_name', test_id)}:")
                    click.echo(f"  샘플 수: {analysis.get('total_samples', 0)}")
                    
                    significance = analysis.get("statistical_significance", {})
                    for metric, data in significance.items():
                        if data.get("significant", False):
                            click.echo(f"  ✅ {metric}: {data['winner']} 승리 ({data['effect_size']:.1%} 개선)")
                            
            else:
                click.echo(f"❌ 최적화 실패: {result.get('error', '알 수 없는 오류')}")
                
        except Exception as e:
            logger.error(f"프롬프트 최적화 실패: {e}", exc_info=True)
            click.echo(f"❌ 프롬프트 최적화 실패: {e}")
    
    asyncio.run(run_optimization())


# 최적화 명령어들을 리스트로 export
optimization_commands = [
    create_ab_test,
    analyze_ab_test,
    optimize_prompts
]
