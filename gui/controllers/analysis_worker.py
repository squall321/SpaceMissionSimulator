"""
Analysis Worker
백그라운드 스레드에서 해석 실행 (UI 블로킹 방지)
"""
from PySide6.QtCore import QThread, Signal

from core.domain.orbit   import OrbitParams
from core.services.mission_analysis import MissionAnalysisService
from core.services.thermal_analysis  import ThermalAnalysisService
from core.services.budget_radiation  import BudgetService, RadiationService, DesignEvaluator


class AnalysisWorker(QThread):
    finished    = Signal(dict)
    progress_msg = Signal(str)
    error        = Signal(str)

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
                 sat_config: dict = None):
        super().__init__()
        self.params      = params
        self.mission_svc = mission_svc
        self.thermal_svc = thermal_svc
        self.budget_svc  = budget_svc
        self.rad_svc     = rad_svc
        self.evaluator   = evaluator
        self.sat_config  = sat_config or self.DEFAULT_SAT_CONFIG

    def run(self):
        try:
            # Stage 1: 궤도 해석
            self.progress_msg.emit("🌍  Stage 1/4 · Orbit propagation...")
            orbit = self.mission_svc.analyze(self.params, sat_config=self.sat_config)
            if orbit.error:
                self.error.emit(f"Orbit error: {orbit.error}")
                return

            # Stage 2: 열해석
            self.progress_msg.emit("🌡  Stage 2/4 · Thermal analysis...")
            thermal = self.thermal_svc.analyze(orbit, self.sat_config)

            # Stage 3: 예산 계산
            self.progress_msg.emit("⚡  Stage 3/4 · Budget calculation...")
            budget = self.budget_svc.calc_power_budget(
                orbit,
                payload_power_w=self.sat_config.get('total_power_w', 800),
                solar_efficiency=0.30,
                sat_config=self.sat_config
            )

            # Stage 4: 방사선 + 평가
            self.progress_msg.emit("☢  Stage 4/4 · Radiation & scoring...")
            radiation = self.rad_svc.analyze(
                orbit,
                shielding_mm=self.sat_config.get('shielding_mm', 3.0)
            )

            t_max = max(thermal.node_temps_max.values(), default=60.0)
            t_min = min(thermal.node_temps_min.values(), default=-10.0)
            score = self.evaluator.evaluate(orbit, budget, radiation, t_max, t_min)

            self.finished.emit({
                'orbit':     orbit,
                'thermal':   thermal,
                'budget':    budget,
                'radiation': radiation,
                'score':     score,
            })

        except Exception as e:
            import traceback
            err_msg = traceback.format_exc()
            print("WORKER ERROR:", err_msg)
            self.error.emit(err_msg)
