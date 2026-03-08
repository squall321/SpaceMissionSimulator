"""
Analysis Worker — v0.8.0
백그라운드 스레드에서 Pipeline Orchestrator를 통해 해석 실행 (UI 블로킹 방지)
"""
from PySide6.QtCore import QThread, Signal

from core.domain.orbit import OrbitParams
from core.domain.structural import StructuralParams
from core.services.mission_analysis import MissionAnalysisService
from core.services.thermal_analysis  import ThermalAnalysisService
from core.services.budget_radiation  import BudgetService, RadiationService, DesignEvaluator
from adapters.ipsap.ipsap_adapter import StructuralAnalyzer
from core.pipeline.orchestrator import (
    PipelineOrchestrator, PipelineContext,
    GmatStage, ThermalStage, BudgetStage, RadiationStage, EvaluationStage,
)


class AnalysisWorker(QThread):
    finished     = Signal(dict)
    progress_msg = Signal(str)
    error        = Signal(str)
    log_msg      = Signal(str, str)    # (message, level)  level: stage|gmat|success|warn|error|info

    # 기본 위성 구성 (100kg급 우주DC)
    DEFAULT_SAT_CONFIG = {
        'total_power_w':       800,     # 전체 소비전력 (컴퓨팅 550W 포함)
        'panel_area_m2':       4.0,     # 태양전지판 면적
        'radiator_area_m2':    1.2,     # 라디에이터 면적
        'bus_area_m2':         1.5,     # 버스 외표면 면적
        'mass_bus_kg':         20,
        'mass_panel_kg':       6,
        'mass_electronics_kg': 15,
        'mass_battery_kg':     10,
        'shielding_mm':        3.0,
    }

    def __init__(self, params: OrbitParams,
                 mission_svc, thermal_svc, budget_svc, rad_svc, evaluator,
                 sat_config: dict = None, extra_stations: list = None):
        super().__init__()
        self.params         = params
        self.mission_svc    = mission_svc
        self.thermal_svc    = thermal_svc
        self.budget_svc     = budget_svc
        self.rad_svc        = rad_svc
        self.evaluator      = evaluator
        self.sat_config     = sat_config or self.DEFAULT_SAT_CONFIG
        self.extra_stations = extra_stations or []

    def run(self):
        try:
            from adapters.gmat.gmat_adapter import GmatAdapter
            _gmat = GmatAdapter()
            gmat_ok = _gmat.is_available()
            gmat_console = _gmat.is_console_available()

            if gmat_ok:
                mode = "GmatConsole.exe" if gmat_console else "GMAT.exe"
                self.log_msg.emit(f"GMAT 사용: {mode}  ({_gmat.gmat_exe})", "gmat")
            else:
                self.log_msg.emit("GMAT 없음 → 내장 해석 엔진 사용", "warn")

            # ── 파이프라인 컨텍스트 구성 ──────────────────────────────────
            from core.services.mission_analysis import MissionAnalysisService
            stations = list(MissionAnalysisService.DEFAULT_STATIONS) + self.extra_stations

            ctx = PipelineContext(
                orbit_params=self.params,
                sat_config=self.sat_config,
                stations=stations,
                log_fn=lambda msg, lv: self.log_msg.emit(msg, lv),
                progress_fn=lambda msg: self.progress_msg.emit(msg),
            )

            # ── 오케스트레이터 구성 (서비스 DI) ──────────────────────────
            orch = PipelineOrchestrator([
                GmatStage(self.mission_svc),
                ThermalStage(self.thermal_svc),
                BudgetStage(self.budget_svc),
                RadiationStage(self.rad_svc),
                EvaluationStage(self.evaluator),
            ])

            # ── 실행 ──────────────────────────────────────────────────────
            ctx = orch.execute(ctx)

            if not ctx.succeeded:
                fail_msgs = [r.message for r in ctx.failed_stages]
                err = ctx.error or "; ".join(fail_msgs) or "파이프라인 실패"
                self.error.emit(err)
                return

            # ── 구조 해석 (v1.0) ──────────────────────────────────────
            result_dict = ctx.as_result_dict()
            try:
                sc = self.sat_config
                struct_params = StructuralParams(
                    total_mass_kg=(
                        sc.get("mass_bus_kg", 20) +
                        sc.get("mass_panel_kg", 6) +
                        sc.get("mass_electronics_kg", 15) +
                        sc.get("mass_battery_kg", 10)
                    ),
                    structure_mass_kg=sc.get("mass_bus_kg", 20),
                    payload_mass_kg=sc.get("mass_electronics_kg", 15) * 0.3,
                    electronics_mass_kg=sc.get("mass_electronics_kg", 15) * 0.7,
                    battery_mass_kg=sc.get("mass_battery_kg", 10),
                )
                struct_result = StructuralAnalyzer().run_analysis(struct_params)
                result_dict["structural"] = struct_result
                self.log_msg.emit(
                    f"구조 해석: f1={struct_result.first_freq_hz:.0f} Hz  "
                    f"σ_max={struct_result.max_von_mises_MPa:.1f} MPa  "
                    f"MS_y={struct_result.min_ms_yield:.2f}  [{struct_result.overall_status}]",
                    "success"
                )
            except Exception as se:
                self.log_msg.emit(f"구조 해석 생략: {se}", "warn")
                result_dict["structural"] = None

            self.finished.emit(result_dict)

        except Exception as e:
            import traceback
            err_msg = traceback.format_exc()
            self.log_msg.emit(f"파이프라인 예외: {e}", "error")
            print("WORKER ERROR:", err_msg)
            self.error.emit(err_msg)
