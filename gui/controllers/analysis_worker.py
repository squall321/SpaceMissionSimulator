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

            # Stage 1: 궤도 해석
            self.progress_msg.emit("🌍  Stage 1/4 · Orbit propagation...")
            self.log_msg.emit("Stage 1/4 · Orbit propagation", "stage")
            stations = list(MissionAnalysisService.DEFAULT_STATIONS) + self.extra_stations
            self.log_msg.emit(
                f"  파라미터: h={self.params.altitude_km}km  i={self.params.inclination_deg}°  "
                f"RAAN={self.params.raan_deg}°  T={self.params.duration_days}d", "info"
            )
            self.log_msg.emit(f"  지상국 {len(stations)}개", "info")

            orbit = self.mission_svc.analyze(self.params, stations=stations, sat_config=self.sat_config)
            if orbit.error:
                self.log_msg.emit(f"궤도 해석 오류: {orbit.error}", "error")
                self.error.emit(f"Orbit error: {orbit.error}")
                return

            used_gmat = gmat_ok and not orbit.error and len(orbit.ephemeris_times) > 100
            if used_gmat:
                self.log_msg.emit(
                    f"  ✓ GMAT 완료  에페메리스={len(orbit.ephemeris_times)}pts  "
                    f"주기={orbit.period_min:.1f}min  일식수={len(orbit.eclipse_events)}", "success"
                )
                self.log_msg.emit(
                    f"  접속창={len(orbit.contact_windows)}개  "
                    f"일조율={orbit.sunlight_fraction*100:.1f}%", "gmat"
                )
            else:
                self.log_msg.emit(
                    f"  ✓ 내부엔진 완료  주기={orbit.period_min:.1f}min  "
                    f"일조율={orbit.sunlight_fraction*100:.1f}%", "success"
                )

            # Stage 2: 열해석
            self.progress_msg.emit("🌡  Stage 2/4 · Thermal analysis...")
            self.log_msg.emit("Stage 2/4 · Thermal analysis (노드법)", "stage")
            thermal = self.thermal_svc.analyze(orbit, self.sat_config)
            t_max = max(thermal.node_temps_max.values(), default=0)
            t_min = min(thermal.node_temps_min.values(), default=0)
            self.log_msg.emit(f"  ✓ Tmax={t_max:.1f}°C  Tmin={t_min:.1f}°C", "success")

            # Stage 3: 예산 계산
            self.progress_msg.emit("⚡  Stage 3/4 · Budget calculation...")
            self.log_msg.emit("Stage 3/4 · Power/Mass/Link budget", "stage")
            budget = self.budget_svc.calc_power_budget(
                orbit,
                payload_power_w=self.sat_config.get('total_power_w', 800),
                solar_efficiency=0.30,
                sat_config=self.sat_config
            )
            self.log_msg.emit(
                f"  ✓ 전력마진={budget.power_margin_w:.1f}W  "
                f"배터리DOD={budget.battery_dod_pct:.1f}%  "
                f"데이터={budget.data_per_day_gb:.1f}GB/d", "success"
            )

            # Stage 4: 방사선 + 평가
            self.progress_msg.emit("☢  Stage 4/4 · Radiation & scoring...")
            self.log_msg.emit("Stage 4/4 · Radiation & Design Score", "stage")
            radiation = self.rad_svc.analyze(
                orbit,
                shielding_mm=self.sat_config.get('shielding_mm', 3.0)
            )

            score = self.evaluator.evaluate(orbit, budget, radiation, t_max, t_min)
            self.log_msg.emit(
                f"  ✓ TID={radiation.tid_krad_5yr:.1f}krad  "
                f"종합점수={score.total_score:.0f}  등급={score.grade}", "success"
            )
            self.log_msg.emit("─" * 55, "debug")

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
            self.log_msg.emit(f"파이프라인 예외: {e}", "error")
            print("WORKER ERROR:", err_msg)
            self.error.emit(err_msg)
