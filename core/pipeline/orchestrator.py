"""
Pipeline Orchestrator
GMAT → 변환 → 해석 → 평가 파이프라인을 조율하는 오케스트레이터
"""
import logging
from typing import List, Optional, Callable, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from core.domain.orbit import OrbitParams, OrbitResult, GroundStation

log = logging.getLogger(__name__)


class StageStatus(Enum):
    """파이프라인 스테이지 상태"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageResult:
    """스테이지 실행 결과"""
    stage_name: str
    status: StageStatus
    duration_sec: float = 0.0
    data: Any = None
    error: Optional[str] = None


@dataclass
class PipelineContext:
    """파이프라인 실행 컨텍스트"""
    orbit_params: OrbitParams
    sat_config: dict = field(default_factory=dict)
    ground_stations: List[GroundStation] = field(default_factory=list)
    
    # 중간 결과 저장
    orbit_result: Optional[OrbitResult] = None
    thermal_result: Any = None
    radiation_result: Any = None
    budget_result: Any = None
    score_card: Any = None
    
    # 실행 메타데이터
    stage_results: List[StageResult] = field(default_factory=list)
    total_duration_sec: float = 0.0
    error: Optional[str] = None


class PipelineStage:
    """파이프라인 스테이지 기본 클래스"""
    
    def __init__(self, name: str):
        self.name = name
    
    def execute(self, context: PipelineContext) -> PipelineContext:
        """스테이지 실행 (서브클래스에서 구현)"""
        raise NotImplementedError
    
    def can_skip(self, context: PipelineContext) -> bool:
        """스킵 가능 여부 확인"""
        return False


class GmatStage(PipelineStage):
    """GMAT 궤도 해석 스테이지"""
    
    def __init__(self):
        super().__init__("GMAT Analysis")
        from core.services.mission_analysis import MissionAnalysisService
        self.service = MissionAnalysisService()
    
    def execute(self, context: PipelineContext) -> PipelineContext:
        result = self.service.analyze(
            context.orbit_params,
            context.ground_stations if context.ground_stations else None,
            context.sat_config if context.sat_config else None
        )
        context.orbit_result = result
        if result.error:
            raise RuntimeError(f"GMAT/Orbit analysis failed: {result.error}")
        return context


class ThermalStage(PipelineStage):
    """열 해석 스테이지"""
    
    def __init__(self):
        super().__init__("Thermal Analysis")
        from core.services.thermal_analysis import ThermalAnalysisService
        self.service = ThermalAnalysisService()
    
    def can_skip(self, context: PipelineContext) -> bool:
        return context.orbit_result is None
    
    def execute(self, context: PipelineContext) -> PipelineContext:
        if context.orbit_result is None:
            raise RuntimeError("Orbit result required for thermal analysis")
        
        result = self.service.analyze(
            context.orbit_result,
            context.sat_config
        )
        context.thermal_result = result
        return context


class RadiationStage(PipelineStage):
    """방사선 해석 스테이지"""
    
    def __init__(self):
        super().__init__("Radiation Analysis")
        from core.services.budget_radiation import RadiationService
        self.service = RadiationService()
    
    def can_skip(self, context: PipelineContext) -> bool:
        return context.orbit_result is None
    
    def execute(self, context: PipelineContext) -> PipelineContext:
        if context.orbit_result is None:
            raise RuntimeError("Orbit result required for radiation analysis")
        
        result = self.service.analyze(
            context.orbit_result.params.altitude_km,
            context.orbit_result.params.inclination_deg,
            mission_years=5.0
        )
        context.radiation_result = result
        return context


class BudgetStage(PipelineStage):
    """예산 계산 스테이지"""
    
    def __init__(self):
        super().__init__("Budget Calculation")
        from core.services.budget_radiation import BudgetService
        self.service = BudgetService()
    
    def execute(self, context: PipelineContext) -> PipelineContext:
        result = self.service.calculate(
            context.sat_config,
            context.orbit_result
        )
        context.budget_result = result
        return context


class EvaluationStage(PipelineStage):
    """설계 평가 스테이지"""
    
    def __init__(self):
        super().__init__("Design Evaluation")
        from core.services.budget_radiation import DesignEvaluator
        self.evaluator = DesignEvaluator()
    
    def execute(self, context: PipelineContext) -> PipelineContext:
        score = self.evaluator.evaluate(
            context.orbit_result,
            context.thermal_result,
            context.budget_result
        )
        context.score_card = score
        return context


class PipelineOrchestrator:
    """
    파이프라인 오케스트레이터
    여러 스테이지를 순차적으로 실행하고 결과를 수집
    """
    
    def __init__(self):
        self.stages: List[PipelineStage] = []
        self.progress_callback: Optional[Callable[[str, float], None]] = None
    
    def add_stage(self, stage: PipelineStage) -> 'PipelineOrchestrator':
        """스테이지 추가"""
        self.stages.append(stage)
        return self
    
    def set_progress_callback(self, callback: Callable[[str, float], None]):
        """진행 상황 콜백 설정"""
        self.progress_callback = callback
    
    def build_default_pipeline(self) -> 'PipelineOrchestrator':
        """기본 파이프라인 구성"""
        self.stages = [
            GmatStage(),
            ThermalStage(),
            RadiationStage(),
            BudgetStage(),
            EvaluationStage()
        ]
        return self
    
    def execute(self, context: PipelineContext) -> PipelineContext:
        """파이프라인 전체 실행"""
        total_stages = len(self.stages)
        start_time = time.time()
        
        log.info(f"Starting pipeline with {total_stages} stages")
        
        for i, stage in enumerate(self.stages):
            stage_start = time.time()
            
            # 진행 상황 콜백
            if self.progress_callback:
                progress = i / total_stages
                self.progress_callback(stage.name, progress)
            
            # 스킵 체크
            if stage.can_skip(context):
                result = StageResult(
                    stage_name=stage.name,
                    status=StageStatus.SKIPPED
                )
                context.stage_results.append(result)
                log.info(f"Stage '{stage.name}' skipped")
                continue
            
            # 스테이지 실행
            try:
                log.info(f"Executing stage '{stage.name}'")
                context = stage.execute(context)
                
                result = StageResult(
                    stage_name=stage.name,
                    status=StageStatus.COMPLETED,
                    duration_sec=time.time() - stage_start
                )
                context.stage_results.append(result)
                log.info(f"Stage '{stage.name}' completed in {result.duration_sec:.2f}s")
                
            except Exception as e:
                log.error(f"Stage '{stage.name}' failed: {e}")
                result = StageResult(
                    stage_name=stage.name,
                    status=StageStatus.FAILED,
                    duration_sec=time.time() - stage_start,
                    error=str(e)
                )
                context.stage_results.append(result)
                context.error = f"Pipeline failed at stage '{stage.name}': {e}"
                break
        
        context.total_duration_sec = time.time() - start_time
        
        # 최종 진행 상황
        if self.progress_callback:
            self.progress_callback("Complete", 1.0)
        
        log.info(f"Pipeline completed in {context.total_duration_sec:.2f}s")
        return context


class MultiOrbitAnalyzer:
    """
    다중 궤도 비교 분석기
    여러 궤도 후보를 병렬로 분석하고 비교
    """
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.progress_callback: Optional[Callable[[int, int, str], None]] = None
    
    def set_progress_callback(self, callback: Callable[[int, int, str], None]):
        """진행 상황 콜백 (current, total, status)"""
        self.progress_callback = callback
    
    def analyze_multiple(
        self,
        orbit_params_list: List[OrbitParams],
        sat_config: dict = None,
        ground_stations: List[GroundStation] = None
    ) -> List[PipelineContext]:
        """
        여러 궤도를 분석하고 결과 반환
        
        Args:
            orbit_params_list: 분석할 궤도 파라미터 목록
            sat_config: 위성 구성
            ground_stations: 지상국 목록
            
        Returns:
            각 궤도에 대한 PipelineContext 목록
        """
        results: List[PipelineContext] = []
        total = len(orbit_params_list)
        
        def analyze_single(idx: int, params: OrbitParams) -> tuple:
            context = PipelineContext(
                orbit_params=params,
                sat_config=sat_config or {},
                ground_stations=ground_stations or []
            )
            
            orchestrator = PipelineOrchestrator().build_default_pipeline()
            result = orchestrator.execute(context)
            return idx, result
        
        # 병렬 실행
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(analyze_single, i, params): i
                for i, params in enumerate(orbit_params_list)
            }
            
            completed = 0
            results = [None] * total
            
            for future in as_completed(futures):
                idx, result = future.result()
                results[idx] = result
                completed += 1
                
                if self.progress_callback:
                    status = "completed" if not result.error else "failed"
                    self.progress_callback(completed, total, status)
        
        return results
    
    def compare_results(
        self,
        results: List[PipelineContext]
    ) -> Dict[str, Any]:
        """
        분석 결과를 비교하고 순위 산출
        
        Returns:
            비교 결과 딕셔너리
        """
        comparison = {
            'total_cases': len(results),
            'successful': 0,
            'failed': 0,
            'rankings': [],
            'best_case': None,
            'summary_stats': {}
        }
        
        # 성공/실패 카운트
        successful_results = []
        for i, ctx in enumerate(results):
            if ctx.error is None and ctx.score_card is not None:
                comparison['successful'] += 1
                successful_results.append((i, ctx))
            else:
                comparison['failed'] += 1
        
        if not successful_results:
            return comparison
        
        # 점수 기반 순위
        scored = []
        for idx, ctx in successful_results:
            score = getattr(ctx.score_card, 'total_score', 0)
            scored.append({
                'index': idx,
                'params': ctx.orbit_params,
                'score': score,
                'orbit_result': ctx.orbit_result,
                'score_card': ctx.score_card
            })
        
        # 점수 내림차순 정렬
        scored.sort(key=lambda x: x['score'], reverse=True)
        comparison['rankings'] = scored
        comparison['best_case'] = scored[0] if scored else None
        
        # 통계 요약
        if successful_results:
            altitudes = [ctx.orbit_params.altitude_km for _, ctx in successful_results]
            inclinations = [ctx.orbit_params.inclination_deg for _, ctx in successful_results]
            scores = [s['score'] for s in scored]
            
            comparison['summary_stats'] = {
                'altitude_range': (min(altitudes), max(altitudes)),
                'inclination_range': (min(inclinations), max(inclinations)),
                'score_range': (min(scores), max(scores)),
                'avg_score': sum(scores) / len(scores)
            }
        
        return comparison


def generate_orbit_candidates(
    altitude_range: tuple = (400, 700),
    altitude_step: float = 50,
    inclination_range: tuple = (90, 98),
    inclination_step: float = 2,
    base_params: OrbitParams = None
) -> List[OrbitParams]:
    """
    궤도 후보 자동 생성
    
    Args:
        altitude_range: 고도 범위 (min, max) km
        altitude_step: 고도 간격 km
        inclination_range: 경사각 범위 (min, max) deg
        inclination_step: 경사각 간격 deg
        base_params: 기본 파라미터 (없으면 기본값 사용)
        
    Returns:
        OrbitParams 목록
    """
    if base_params is None:
        base_params = OrbitParams()
    
    candidates = []
    
    alt = altitude_range[0]
    while alt <= altitude_range[1]:
        inc = inclination_range[0]
        while inc <= inclination_range[1]:
            params = OrbitParams(
                altitude_km=alt,
                inclination_deg=inc,
                raan_deg=base_params.raan_deg,
                eccentricity=base_params.eccentricity,
                arg_perigee_deg=base_params.arg_perigee_deg,
                true_anomaly_deg=base_params.true_anomaly_deg,
                orbit_type=base_params.orbit_type,
                epoch=base_params.epoch,
                duration_days=base_params.duration_days
            )
            candidates.append(params)
            inc += inclination_step
        alt += altitude_step
    
    return candidates
