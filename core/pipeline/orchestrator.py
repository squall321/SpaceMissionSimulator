"""
SpaceD-AADE Pipeline Orchestrator — v0.8.0
GMAT → Transform → Analysis → Evaluate 4-Stage 파이프라인

패턴: Pipeline (Chain) + Strategy + Mediator
서비스는 생성자에서 주입받는 방식(DI)으로 외부 의존성을 격리한다.
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum, auto
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional

from core.domain.orbit import OrbitParams, OrbitResult, GroundStation

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  StageStatus / StageResult
# ─────────────────────────────────────────────────────────────────────────────

class StageStatus(Enum):
    PENDING   = auto()
    RUNNING   = auto()
    SUCCESS   = auto()
    FAILED    = auto()
    SKIPPED   = auto()


@dataclass
class StageResult:
    stage_name:   str
    status:       StageStatus
    duration_sec: float               = 0.0
    message:      str                 = ""
    error:        Optional[Exception] = None

    @property
    def ok(self) -> bool:
        return self.status == StageStatus.SUCCESS


# ─────────────────────────────────────────────────────────────────────────────
#  PipelineContext — 공유 상태 컨테이너
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PipelineContext:
    """파이프라인 전 단계를 흐르는 공유 상태 컨테이너"""
    orbit_params: OrbitParams
    sat_config:   dict = field(default_factory=dict)
    stations:     list = field(default_factory=list)   # GroundStation 목록

    # ── 단계별 결과 ──────────────────────────────────────────────────────────
    orbit_result:     Optional[OrbitResult] = None
    thermal_result:   Any                   = None  # ThermalResult
    budget_result:    Any                   = None  # BudgetResult
    radiation_result: Any                   = None  # RadiationResult
    score_result:     Any                   = None  # DesignScoreCard

    # ── 콜백 ─────────────────────────────────────────────────────────────────
    log_fn:      Optional[Callable[[str, str], None]] = None   # (msg, level) -> None
    progress_fn: Optional[Callable[[str], None]]      = None   # (msg,) -> None

    # ── 실행 메타데이터 ───────────────────────────────────────────────────────
    stage_results:     List[StageResult] = field(default_factory=list)
    total_duration_sec: float             = 0.0
    metadata:          dict               = field(default_factory=dict)
    # 하위 호환 — 예전 코드에서 context.error 를 읽을 수 있도록 유지
    error: Optional[str] = None

    # ── 편의 메서드 ───────────────────────────────────────────────────────────
    def log(self, msg: str, level: str = "info") -> None:
        if self.log_fn:
            self.log_fn(msg, level)
        else:
            log.info("[%s] %s", level, msg)

    def progress(self, msg: str) -> None:
        if self.progress_fn:
            self.progress_fn(msg)

    def as_result_dict(self) -> dict:
        return {
            "orbit":     self.orbit_result,
            "thermal":   self.thermal_result,
            "budget":    self.budget_result,
            "radiation": self.radiation_result,
            "score":     self.score_result,
        }

    @property
    def succeeded(self) -> bool:
        return all([
            self.orbit_result     is not None,
            self.thermal_result   is not None,
            self.budget_result    is not None,
            self.radiation_result is not None,
            self.score_result     is not None,
        ])

    @property
    def failed_stages(self) -> List[StageResult]:
        return [r for r in self.stage_results if r.status == StageStatus.FAILED]

    # 하위 호환: 예전 코드가 ctx.score_card 를 읽을 경우
    @property
    def score_card(self):
        return self.score_result

    # 하위 호환: ground_stations 속성
    @property
    def ground_stations(self) -> list:
        return self.stations


# ─────────────────────────────────────────────────────────────────────────────
#  PipelineStage — 추상 기반
# ─────────────────────────────────────────────────────────────────────────────

class PipelineStage(ABC):
    """모든 파이프라인 단계의 추상 기반 클래스 (서비스는 DI로 주입)"""
    name: str = "unnamed"

    @abstractmethod
    def execute(self, ctx: PipelineContext) -> StageResult:
        ...

    def can_skip(self, ctx: PipelineContext) -> bool:   # 하위 호환
        return False

    # ── 헬퍼 ─────────────────────────────────────────────────────────────────
    def _ok(self, ctx: PipelineContext, msg: str = "", dur: float = 0.0) -> StageResult:
        r = StageResult(self.name, StageStatus.SUCCESS, dur, msg)
        ctx.stage_results.append(r)
        return r

    def _fail(self, ctx: PipelineContext, msg: str,
              error: Exception = None, dur: float = 0.0) -> StageResult:
        r = StageResult(self.name, StageStatus.FAILED, dur, msg, error)
        ctx.stage_results.append(r)
        return r

    def _skip(self, ctx: PipelineContext, msg: str = "", dur: float = 0.0) -> StageResult:
        r = StageResult(self.name, StageStatus.SKIPPED, dur, msg)
        ctx.stage_results.append(r)
        return r


# ─────────────────────────────────────────────────────────────────────────────
#  Stage 1: GMAT / Orbit Analysis
# ─────────────────────────────────────────────────────────────────────────────

class GmatStage(PipelineStage):
    """궤도 해석 (GMAT Console 또는 내장 엔진 자동 선택)"""
    name = "GmatStage"

    def __init__(self, mission_svc=None):
        if mission_svc is None:
            from core.services.mission_analysis import MissionAnalysisService
            mission_svc = MissionAnalysisService()
        self._svc = mission_svc

    def execute(self, ctx: PipelineContext) -> StageResult:
        t0 = time.perf_counter()
        ctx.progress("🌍  Stage 1/4 · Orbit propagation...")
        ctx.log("Stage 1/4 · Orbit propagation", "stage")
        ctx.log(
            f"  파라미터: h={ctx.orbit_params.altitude_km:.0f}km  "
            f"i={ctx.orbit_params.inclination_deg:.1f}°  "
            f"RAAN={ctx.orbit_params.raan_deg:.1f}°  "
            f"T={ctx.orbit_params.duration_days}d", "info"
        )
        ctx.log(f"  지상국 {len(ctx.stations)}개", "info")
        try:
            orbit = self._svc.analyze(ctx.orbit_params,
                                      stations=ctx.stations,
                                      sat_config=ctx.sat_config)
            if orbit.error:
                ctx.log(f"궤도 해석 오류: {orbit.error}", "error")
                ctx.error = orbit.error
                return self._fail(ctx, orbit.error, dur=time.perf_counter() - t0)

            ctx.orbit_result = orbit
            used_gmat = len(orbit.ephemeris_times) > 100
            ctx.metadata["used_gmat"] = used_gmat
            if used_gmat:
                ctx.log(
                    f"  ✓ GMAT 완료  에페메리스={len(orbit.ephemeris_times)}pts  "
                    f"주기={orbit.period_min:.1f}min  일식={len(orbit.eclipse_events)}건", "success"
                )
                ctx.log(
                    f"  접속창={len(orbit.contact_windows)}개  "
                    f"일조율={orbit.sunlight_fraction * 100:.1f}%", "gmat"
                )
            else:
                ctx.log(
                    f"  ✓ 내부엔진 완료  주기={orbit.period_min:.1f}min  "
                    f"일조율={orbit.sunlight_fraction * 100:.1f}%", "success"
                )
            return self._ok(ctx, f"주기={orbit.period_min:.1f}min", time.perf_counter() - t0)
        except Exception as e:
            ctx.log(f"GmatStage 예외: {e}", "error")
            ctx.error = str(e)
            return self._fail(ctx, str(e), error=e, dur=time.perf_counter() - t0)


# ─────────────────────────────────────────────────────────────────────────────
#  Stage 2: Thermal Analysis
# ─────────────────────────────────────────────────────────────────────────────

class ThermalStage(PipelineStage):
    """노드 열해석 (Lumped-Parameter)"""
    name = "ThermalStage"

    def __init__(self, thermal_svc=None):
        if thermal_svc is None:
            from core.services.thermal_analysis import ThermalAnalysisService
            thermal_svc = ThermalAnalysisService()
        self._svc = thermal_svc

    def can_skip(self, ctx: PipelineContext) -> bool:
        return ctx.orbit_result is None

    def execute(self, ctx: PipelineContext) -> StageResult:
        t0 = time.perf_counter()
        ctx.progress("🌡  Stage 2/4 · Thermal analysis...")
        ctx.log("Stage 2/4 · Thermal analysis (노드법)", "stage")
        if ctx.orbit_result is None:
            return self._skip(ctx, "orbit 결과 없음 — skip")
        try:
            thermal = self._svc.analyze(ctx.orbit_result, ctx.sat_config)
            t_max = max(thermal.node_temps_max.values(), default=0.0)
            t_min = min(thermal.node_temps_min.values(), default=0.0)
            ctx.thermal_result = thermal
            ctx.metadata["t_max"] = t_max
            ctx.metadata["t_min"] = t_min
            ctx.log(f"  ✓ Tmax={t_max:.1f}°C  Tmin={t_min:.1f}°C", "success")
            return self._ok(ctx, f"Tmax={t_max:.1f} Tmin={t_min:.1f}", time.perf_counter() - t0)
        except Exception as e:
            ctx.log(f"ThermalStage 예외: {e}", "error")
            return self._fail(ctx, str(e), error=e, dur=time.perf_counter() - t0)


# ─────────────────────────────────────────────────────────────────────────────
#  Stage 3: Budget Calculation
# ─────────────────────────────────────────────────────────────────────────────

class BudgetStage(PipelineStage):
    """전력/질량/링크 예산 자동 계산"""
    name = "BudgetStage"

    def __init__(self, budget_svc=None):
        if budget_svc is None:
            from core.services.budget_radiation import BudgetService
            budget_svc = BudgetService()
        self._svc = budget_svc

    def execute(self, ctx: PipelineContext) -> StageResult:
        t0 = time.perf_counter()
        ctx.progress("⚡  Stage 3/4 · Budget calculation...")
        ctx.log("Stage 3/4 · Power/Mass/Link budget", "stage")
        if ctx.orbit_result is None:
            return self._skip(ctx, "orbit 없음")
        try:
            payload_w = ctx.sat_config.get("total_power_w", 800)
            budget    = self._svc.calc_power_budget(
                ctx.orbit_result,
                payload_power_w=payload_w,
                solar_efficiency=0.30,
                sat_config=ctx.sat_config,
            )
            ctx.budget_result = budget
            ctx.log(
                f"  ✓ 발전={budget.solar_generated_w:.0f}W  "
                f"마진={budget.power_margin_w:.0f}W  "
                f"배터리DOD={budget.battery_dod_pct:.0f}%  "
                f"데이터={budget.data_per_day_gb:.1f}GB/d", "success"
            )
            return self._ok(ctx, f"마진={budget.power_margin_w:.0f}W", time.perf_counter() - t0)
        except Exception as e:
            ctx.log(f"BudgetStage 예외: {e}", "error")
            return self._fail(ctx, str(e), error=e, dur=time.perf_counter() - t0)


# ─────────────────────────────────────────────────────────────────────────────
#  Stage 4: Radiation + Design Evaluation
# ─────────────────────────────────────────────────────────────────────────────

class RadiationStage(PipelineStage):
    """방사선 환경 평가 (AP-8/AE-8 TID 계산)"""
    name = "RadiationStage"

    def __init__(self, rad_svc=None):
        if rad_svc is None:
            from core.services.budget_radiation import RadiationService
            rad_svc = RadiationService()
        self._svc = rad_svc

    def can_skip(self, ctx: PipelineContext) -> bool:
        return ctx.orbit_result is None

    def execute(self, ctx: PipelineContext) -> StageResult:
        t0 = time.perf_counter()
        if ctx.orbit_result is None:
            return self._skip(ctx, "orbit 없음")
        try:
            rad = self._svc.analyze(
                ctx.orbit_result,
                shielding_mm=ctx.sat_config.get("shielding_mm", 3.0),
            )
            ctx.radiation_result = rad
            ctx.metadata["tid_krad"] = rad.tid_krad_5yr
            ctx.log(
                f"  ✓ TID={rad.tid_krad_5yr:.1f}krad (5yr)  "
                f"proton={rad.proton_flux:.2e} p/cm²/s", "success"
            )
            return self._ok(ctx, f"TID={rad.tid_krad_5yr:.1f}krad", time.perf_counter() - t0)
        except Exception as e:
            ctx.log(f"RadiationStage 예외: {e}", "error")
            return self._fail(ctx, str(e), error=e, dur=time.perf_counter() - t0)


class EvaluationStage(PipelineStage):
    """종합 설계 평가 (DesignScoreCard 산출)"""
    name = "EvaluationStage"

    def __init__(self, evaluator=None):
        if evaluator is None:
            from core.services.budget_radiation import DesignEvaluator
            evaluator = DesignEvaluator()
        self._ev = evaluator

    def execute(self, ctx: PipelineContext) -> StageResult:
        t0 = time.perf_counter()
        ctx.progress("☢  Stage 4/4 · Radiation & scoring...")
        ctx.log("Stage 4/4 · Design Score evaluation", "stage")
        if any(r is None for r in [ctx.orbit_result, ctx.budget_result, ctx.radiation_result]):
            return self._skip(ctx, "선행 단계 결과 없음")
        try:
            t_max = ctx.metadata.get("t_max", 60.0)
            t_min = ctx.metadata.get("t_min", -20.0)
            score = self._ev.evaluate(
                ctx.orbit_result, ctx.budget_result, ctx.radiation_result, t_max, t_min
            )
            ctx.score_result = score
            ctx.log(
                f"  ✓ TID={ctx.radiation_result.tid_krad_5yr:.1f}krad  "
                f"종합점수={score.total_score:.0f}  등급={score.grade}", "success"
            )
            ctx.log("─" * 55, "debug")
            return self._ok(ctx, f"점수={score.total_score:.0f} 등급={score.grade}", time.perf_counter() - t0)
        except Exception as e:
            ctx.log(f"EvaluationStage 예외: {e}", "error")
            return self._fail(ctx, str(e), error=e, dur=time.perf_counter() - t0)


# ─────────────────────────────────────────────────────────────────────────────
#  PipelineOrchestrator — 메인 조율자
# ─────────────────────────────────────────────────────────────────────────────

class PipelineOrchestrator:
    """
    파이프라인 실행 조율자 (Mediator 패턴).
    stages를 순서대로 실행하며 첫 FAILED stage에서 중단한다.
    """

    def __init__(self, stages: List[PipelineStage] = None):
        self._stages: List[PipelineStage] = stages or []
        # 하위 호환 — 예전 코드가 .stages 를 직접 읽을 경우
        self.stages = self._stages

    def add_stage(self, stage: PipelineStage) -> "PipelineOrchestrator":
        self._stages.append(stage)
        return self

    def set_progress_callback(self, cb: Callable) -> None:
        """하위 호환 no-op (콜백은 PipelineContext에서 관리)"""
        pass

    @classmethod
    def default(cls,
                mission_svc=None, thermal_svc=None,
                budget_svc=None, rad_svc=None,
                evaluator=None) -> "PipelineOrchestrator":
        """표준 4(+1)-Stage 파이프라인 factory (서비스 선택적 주입)"""
        return cls([
            GmatStage(mission_svc),
            ThermalStage(thermal_svc),
            BudgetStage(budget_svc),
            RadiationStage(rad_svc),
            EvaluationStage(evaluator),
        ])

    def build_default_pipeline(self) -> "PipelineOrchestrator":
        """하위 호환: 기본 파이프라인 자가 구성"""
        self._stages = [
            GmatStage(), ThermalStage(), BudgetStage(),
            RadiationStage(), EvaluationStage(),
        ]
        self.stages = self._stages
        return self

    def run(self, ctx: PipelineContext) -> PipelineContext:
        return self.execute(ctx)

    def execute(self, ctx: PipelineContext) -> PipelineContext:
        """파이프라인 전체 실행"""
        t0 = time.perf_counter()
        ctx.log(f"파이프라인 시작 ({len(self._stages)}단계)", "stage")

        for stage in self._stages:
            if stage.can_skip(ctx):
                ctx.stage_results.append(
                    StageResult(stage.name, StageStatus.SKIPPED, 0.0, "can_skip=True")
                )
                ctx.log(f"  [{stage.name}] SKIPPED", "warn")
                continue

            result = stage.execute(ctx)
            if result.status == StageStatus.FAILED:
                ctx.error = ctx.error or result.message
                ctx.log(f"파이프라인 중단: [{stage.name}] {result.message}", "error")
                break

        ctx.total_duration_sec = time.perf_counter() - t0
        if ctx.succeeded:
            ctx.log(f"파이프라인 완료 ({ctx.total_duration_sec:.1f}s)", "success")
        else:
            n_fail = len(ctx.failed_stages)
            ctx.log(f"파이프라인 종료 ({ctx.total_duration_sec:.1f}s, 실패={n_fail})", "warn")
        return ctx


# ─────────────────────────────────────────────────────────────────────────────
#  MultiOrbitAnalyzer — 파라메트릭 스윕
# ─────────────────────────────────────────────────────────────────────────────

class MultiOrbitAnalyzer:
    """
    동일 위성 설정으로 여러 궤도를 분석 (병렬 지원).
    ParametricStudyPanel 또는 OrbitOptimizationDialog에서 활용.
    """

    def __init__(self, orchestrator: PipelineOrchestrator = None, max_workers: int = 4):
        self._orch       = orchestrator or PipelineOrchestrator.default()
        self.max_workers = max_workers
        self.progress_callback: Optional[Callable] = None

    def set_progress_callback(self, cb: Callable) -> None:
        self.progress_callback = cb

    def sweep(
        self,
        base_ctx: PipelineContext,
        orbit_candidates: List[Any],
        log_fn: Callable = None,
        progress_fn: Callable = None,
    ) -> List[PipelineContext]:
        """순차 스윕 (GUI 스레드 친화적)"""
        results: List[PipelineContext] = []
        n = len(orbit_candidates)
        for i, params in enumerate(orbit_candidates):
            ctx = deepcopy(base_ctx)
            ctx.orbit_params   = params
            ctx.stage_results  = []
            ctx.metadata       = {}
            ctx.error          = None
            ctx.orbit_result   = ctx.thermal_result   = None
            ctx.budget_result  = ctx.radiation_result = ctx.score_result = None
            if log_fn:
                ctx.log_fn = log_fn
            if progress_fn:
                ctx.progress_fn = progress_fn
                progress_fn(f"  스윕 {i+1}/{n}: h={params.altitude_km}km i={params.inclination_deg}°")
            ctx = self._orch.execute(ctx)
            results.append(ctx)
            if self.progress_callback:
                self.progress_callback(i + 1, n, "ok" if ctx.succeeded else "fail")
        return results

    def analyze_multiple(
        self,
        orbit_params_list: List[OrbitParams],
        sat_config: dict = None,
        ground_stations: List[GroundStation] = None,
    ) -> List[PipelineContext]:
        """병렬 분석 (ThreadPoolExecutor)"""
        results: list = [None] * len(orbit_params_list)
        total   = len(orbit_params_list)

        def _run(idx: int, params: OrbitParams) -> tuple:
            ctx = PipelineContext(
                orbit_params=params,
                sat_config=sat_config or {},
                stations=ground_stations or [],
            )
            return idx, PipelineOrchestrator.default().execute(ctx)

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(_run, i, p): i
                       for i, p in enumerate(orbit_params_list)}
            done = 0
            for fut in as_completed(futures):
                idx, ctx = fut.result()
                results[idx] = ctx
                done += 1
                if self.progress_callback:
                    self.progress_callback(done, total, "ok" if ctx.succeeded else "fail")
        return results

    def compare_results(self, results: List[PipelineContext]) -> Dict[str, Any]:
        """분석 결과 비교 및 순위 산출"""
        successful = [(i, c) for i, c in enumerate(results)
                      if c.succeeded and c.score_result is not None]
        scored  = sorted(
            [{"index": i, "params": c.orbit_params,
              "score": c.score_result.total_score, "ctx": c}
             for i, c in successful],
            key=lambda x: x["score"], reverse=True,
        )
        return {
            "total_cases": len(results),
            "successful": len(successful),
            "failed": len(results) - len(successful),
            "rankings": scored,
            "best_case": scored[0] if scored else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
#  편의 함수
# ─────────────────────────────────────────────────────────────────────────────

def generate_orbit_candidates(
    altitudes_km:     List[float] = None,
    inclinations_deg: List[float] = None,
    base_params: OrbitParams = None,
    # 하위 호환 — range+step 방식
    altitude_range:    tuple = None,
    altitude_step:     float = 50,
    inclination_range: tuple = None,
    inclination_step:  float = 2,
) -> List[OrbitParams]:
    """
    고도 × 경사각 그리드 → OrbitParams 목록 생성.
    두 가지 호출 방식 지원:
      1. generate_orbit_candidates(altitudes_km=[400,500], inclinations_deg=[97,98])
      2. generate_orbit_candidates(altitude_range=(400,700), altitude_step=50,
                                   inclination_range=(90,98), inclination_step=2)
    """
    # ── 리스트 방식 ──
    if altitudes_km is not None and inclinations_deg is not None:
        alts = altitudes_km
        incs = inclinations_deg
    # ── range+step 방식 (하위 호환) ──
    elif altitude_range and inclination_range:
        alts = []
        a = altitude_range[0]
        while a <= altitude_range[1]:
            alts.append(float(a)); a += altitude_step
        incs = []
        i = inclination_range[0]
        while i <= inclination_range[1]:
            incs.append(float(i)); i += inclination_step
    else:
        return []

    bp = base_params or OrbitParams(altitude_km=500, inclination_deg=97.6)
    candidates: List[OrbitParams] = []
    for alt in alts:
        for inc in incs:
            p = deepcopy(bp)
            p.altitude_km     = float(alt)
            p.inclination_deg = float(inc)
            candidates.append(p)
    return candidates



