"""
Orbit Optimization Service
궤도 최적화 및 설계 공간 탐색 서비스
"""
import logging
import math
from typing import List, Tuple, Callable, Optional, Dict, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import random

from core.domain.orbit import OrbitParams, OrbitResult
from core.pipeline.orchestrator import (
    PipelineOrchestrator, PipelineContext, MultiOrbitAnalyzer, generate_orbit_candidates
)

log = logging.getLogger(__name__)


@dataclass
class OptimizationConstraints:
    """최적화 제약 조건"""
    # 고도 제약 (km)
    altitude_min: float = 300.0
    altitude_max: float = 1000.0
    
    # 경사각 제약 (deg)
    inclination_min: float = 0.0
    inclination_max: float = 180.0
    
    # 일식 제약
    max_eclipse_fraction: float = 0.4  # 최대 40% 일식
    
    # 접속 제약
    min_contacts_per_day: float = 4.0
    min_contact_time_per_day_min: float = 30.0
    
    # 방사선 제약
    max_total_dose_krad: float = 100.0


@dataclass
class OptimizationObjectives:
    """최적화 목표"""
    # 최대화 목표
    maximize_sunlight: bool = True      # 일조율 최대화
    maximize_contact: bool = True       # 접속 시간 최대화
    
    # 최소화 목표
    minimize_delta_v: bool = True       # 궤도 유지 ΔV 최소화
    minimize_radiation: bool = True     # 방사선 노출 최소화
    
    # 가중치
    weight_sunlight: float = 1.0
    weight_contact: float = 1.0
    weight_delta_v: float = 0.5
    weight_radiation: float = 0.8


@dataclass
class OptimizationResult:
    """최적화 결과"""
    best_params: Optional[OrbitParams] = None
    best_score: float = 0.0
    best_context: Optional[PipelineContext] = None
    
    # 파레토 프론티어 (다목적 최적화)
    pareto_front: List[Tuple[OrbitParams, float, PipelineContext]] = field(default_factory=list)
    
    # 탐색 통계
    total_evaluated: int = 0
    feasible_count: int = 0
    iterations: int = 0
    convergence_history: List[float] = field(default_factory=list)


class OrbitOptimizer:
    """
    궤도 최적화기
    그리드 탐색, 랜덤 탐색, 간단한 진화 알고리즘 지원
    """
    
    def __init__(
        self,
        constraints: OptimizationConstraints = None,
        objectives: OptimizationObjectives = None
    ):
        self.constraints = constraints or OptimizationConstraints()
        self.objectives = objectives or OptimizationObjectives()
        self.progress_callback: Optional[Callable[[int, int, float], None]] = None
        
    def set_progress_callback(self, callback: Callable[[int, int, float], None]):
        """진행 상황 콜백 (current, total, best_score)"""
        self.progress_callback = callback
    
    def _check_constraints(self, ctx: PipelineContext) -> bool:
        """제약 조건 만족 여부 확인"""
        if ctx.error or ctx.orbit_result is None:
            return False
        
        result = ctx.orbit_result
        params = ctx.orbit_params
        c = self.constraints
        
        # 고도 제약
        if not (c.altitude_min <= params.altitude_km <= c.altitude_max):
            return False
        
        # 경사각 제약
        if not (c.inclination_min <= params.inclination_deg <= c.inclination_max):
            return False
        
        # 일식 제약
        if result.eclipse_fraction > c.max_eclipse_fraction:
            return False
        
        # 접속 제약
        if result.contacts_per_day < c.min_contacts_per_day:
            return False
        if result.contact_time_per_day_min < c.min_contact_time_per_day_min:
            return False
        
        # 방사선 제약 (간소 체크)
        if ctx.radiation_result:
            total_dose = getattr(ctx.radiation_result, 'total_dose_krad', 0)
            if total_dose > c.max_total_dose_krad:
                return False
        
        return True
    
    def _calculate_objective(self, ctx: PipelineContext) -> float:
        """목적 함수 계산 (높을수록 좋음)"""
        if ctx.error or ctx.orbit_result is None:
            return -float('inf')
        
        result = ctx.orbit_result
        obj = self.objectives
        score = 0.0
        
        # 일조율 (0~1, 높을수록 좋음)
        if obj.maximize_sunlight:
            score += obj.weight_sunlight * result.sunlight_fraction
        
        # 접속 시간 (정규화, 높을수록 좋음)
        if obj.maximize_contact:
            # 일일 60분을 최대로 정규화
            contact_norm = min(1.0, result.contact_time_per_day_min / 60.0)
            score += obj.weight_contact * contact_norm
        
        # ΔV (낮을수록 좋음 → 반전)
        if obj.minimize_delta_v:
            # 연간 100 m/s를 최대로 정규화
            dv_norm = min(1.0, result.delta_v_per_year_ms / 100.0)
            score += obj.weight_delta_v * (1.0 - dv_norm)
        
        # 방사선 (낮을수록 좋음 → 반전)
        if obj.minimize_radiation and ctx.radiation_result:
            total_dose = getattr(ctx.radiation_result, 'total_dose_krad', 50)
            # 100 krad를 최대로 정규화
            rad_norm = min(1.0, total_dose / 100.0)
            score += obj.weight_radiation * (1.0 - rad_norm)
        
        return score
    
    def grid_search(
        self,
        altitude_range: Tuple[float, float] = (400, 700),
        altitude_step: float = 50,
        inclination_range: Tuple[float, float] = (90, 98),
        inclination_step: float = 2,
        sat_config: dict = None,
        max_workers: int = 4
    ) -> OptimizationResult:
        """
        그리드 탐색 최적화
        
        고도와 경사각 범위를 격자로 탐색
        """
        # 후보 생성
        candidates = generate_orbit_candidates(
            altitude_range=altitude_range,
            altitude_step=altitude_step,
            inclination_range=inclination_range,
            inclination_step=inclination_step
        )
        
        return self._evaluate_candidates(candidates, sat_config, max_workers)
    
    def random_search(
        self,
        n_samples: int = 50,
        sat_config: dict = None,
        max_workers: int = 4
    ) -> OptimizationResult:
        """
        랜덤 탐색 최적화
        
        제약 범위 내에서 무작위 샘플링
        """
        c = self.constraints
        candidates = []
        
        for _ in range(n_samples):
            params = OrbitParams(
                altitude_km=random.uniform(c.altitude_min, c.altitude_max),
                inclination_deg=random.uniform(c.inclination_min, c.inclination_max),
                duration_days=1.0
            )
            candidates.append(params)
        
        return self._evaluate_candidates(candidates, sat_config, max_workers)
    
    def evolutionary_search(
        self,
        population_size: int = 20,
        generations: int = 10,
        mutation_rate: float = 0.2,
        sat_config: dict = None,
        max_workers: int = 4
    ) -> OptimizationResult:
        """
        간단한 진화 알고리즘 최적화
        
        선택, 교차, 돌연변이를 통한 최적화
        """
        c = self.constraints
        result = OptimizationResult()
        
        # 초기 집단 생성
        population = []
        for _ in range(population_size):
            params = OrbitParams(
                altitude_km=random.uniform(c.altitude_min, c.altitude_max),
                inclination_deg=random.uniform(c.inclination_min, c.inclination_max),
                duration_days=1.0
            )
            population.append(params)
        
        best_score = -float('inf')
        best_params = None
        best_context = None
        
        for gen in range(generations):
            # 현재 집단 평가
            gen_result = self._evaluate_candidates(population, sat_config, max_workers)
            
            result.total_evaluated += gen_result.total_evaluated
            result.feasible_count += gen_result.feasible_count
            result.iterations = gen + 1
            
            # 최고 점수 업데이트
            if gen_result.best_score > best_score:
                best_score = gen_result.best_score
                best_params = gen_result.best_params
                best_context = gen_result.best_context
            
            result.convergence_history.append(best_score)
            
            if self.progress_callback:
                self.progress_callback(gen + 1, generations, best_score)
            
            # 마지막 세대면 종료
            if gen == generations - 1:
                break
            
            # 다음 세대 생성
            # 상위 50% 선택
            ranked = gen_result.pareto_front[:population_size // 2]
            if len(ranked) < 2:
                continue
            
            new_population = [p[0] for p in ranked]
            
            # 교차 및 돌연변이로 나머지 채움
            while len(new_population) < population_size:
                p1 = random.choice(ranked)[0]
                p2 = random.choice(ranked)[0]
                
                # 교차
                child_alt = (p1.altitude_km + p2.altitude_km) / 2
                child_inc = (p1.inclination_deg + p2.inclination_deg) / 2
                
                # 돌연변이
                if random.random() < mutation_rate:
                    child_alt += random.gauss(0, 50)
                    child_alt = max(c.altitude_min, min(c.altitude_max, child_alt))
                
                if random.random() < mutation_rate:
                    child_inc += random.gauss(0, 5)
                    child_inc = max(c.inclination_min, min(c.inclination_max, child_inc))
                
                child = OrbitParams(
                    altitude_km=child_alt,
                    inclination_deg=child_inc,
                    duration_days=1.0
                )
                new_population.append(child)
            
            population = new_population
        
        result.best_params = best_params
        result.best_score = best_score
        result.best_context = best_context
        
        return result
    
    def _evaluate_candidates(
        self,
        candidates: List[OrbitParams],
        sat_config: dict = None,
        max_workers: int = 4
    ) -> OptimizationResult:
        """후보들을 평가하고 결과 반환"""
        result = OptimizationResult()
        result.total_evaluated = len(candidates)
        
        analyzer = MultiOrbitAnalyzer(max_workers=max_workers)
        contexts = analyzer.analyze_multiple(candidates, sat_config)
        
        # 각 결과 평가
        scored = []
        for ctx in contexts:
            if self._check_constraints(ctx):
                result.feasible_count += 1
                score = self._calculate_objective(ctx)
                scored.append((ctx.orbit_params, score, ctx))
        
        # 점수 기준 정렬
        scored.sort(key=lambda x: x[1], reverse=True)
        result.pareto_front = scored
        
        if scored:
            result.best_params = scored[0][0]
            result.best_score = scored[0][1]
            result.best_context = scored[0][2]
        
        return result


# SSO (태양동기궤도) 경사각 계산
def calculate_sso_inclination(altitude_km: float) -> float:
    """
    주어진 고도에서 태양동기궤도 경사각 계산
    
    Args:
        altitude_km: 궤도 고도 (km)
        
    Returns:
        SSO 경사각 (deg)
    """
    # 지구 상수
    R_E = 6378.137  # km
    J2 = 1.08263e-3
    MU = 398600.4418  # km³/s²
    
    # 태양 평균 운동 (rad/s)
    n_sun = 2 * math.pi / (365.25 * 86400)
    
    # 반장축
    a = R_E + altitude_km
    
    # 위성 평균 운동
    n = math.sqrt(MU / a**3)
    
    # SSO 조건: dΩ/dt = n_sun
    # dΩ/dt = -3/2 * n * J2 * (R_E/a)^2 * cos(i)
    # cos(i) = -2 * n_sun * a^2 / (3 * n * J2 * R_E^2)
    
    cos_i = -2 * n_sun * a**2 / (3 * n * J2 * R_E**2)
    
    # 유효한 범위 확인
    if abs(cos_i) > 1:
        log.warning(f"SSO not achievable at {altitude_km} km")
        return 97.0  # 기본값 반환
    
    inc_rad = math.acos(cos_i)
    inc_deg = math.degrees(inc_rad)
    
    return inc_deg
