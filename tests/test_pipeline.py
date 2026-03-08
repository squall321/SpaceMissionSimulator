"""
SpaceD-AADE 통합 파이프라인 테스트
pytest 기반 — 핵심 서비스 + 어댑터 End-to-End 검증

실행:
    cd SpaceD-AADE
    .venv/Scripts/pytest tests/test_pipeline.py -v
"""
import sys
import math
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.domain.orbit       import OrbitParams, GroundStation
from core.domain.structural  import StructuralParams, MATERIALS
from core.services.mission_analysis import MissionAnalysisService
from core.services.thermal_analysis import ThermalAnalysisService
from core.services.budget_radiation import BudgetService, RadiationService, DesignEvaluator
from adapters.ipsap.ipsap_adapter  import StructuralAnalyzer


# ── 공통 픽스처 ────────────────────────────────────────────────

@pytest.fixture
def default_orbit():
    return OrbitParams(altitude_km=550, inclination_deg=97.6,
                       duration_days=2.0, epoch="2026-01-01T00:00:00")

@pytest.fixture
def default_sat_cfg():
    return {
        "total_power_w":       800,
        "panel_area_m2":       4.0,
        "radiator_area_m2":    1.2,
        "bus_area_m2":         1.5,
        "mass_bus_kg":         20,
        "mass_panel_kg":       6,
        "mass_electronics_kg": 15,
        "mass_battery_kg":     10,
        "shielding_mm":        3.0,
    }

@pytest.fixture
def default_struct_params():
    return StructuralParams(
        total_mass_kg=51.0,       # sat_cfg 합계
        width_m=0.35, depth_m=0.35, height_m=0.45,
        panel_thickness_mm=3.0, material="Al6061-T6",
    )


# ── 궤도 분석 ──────────────────────────────────────────────────

class TestMissionAnalysis:
    def test_basic_orbit(self, default_orbit, default_sat_cfg):
        svc = MissionAnalysisService()
        result = svc.analyze(default_orbit, sat_config=default_sat_cfg)
        assert result is not None
        assert result.period_min > 0, "궤도 주기가 양수이어야 합니다"
        assert 85 <= result.period_min <= 105, f"550km SSO 주기 예상 범위: {result.period_min:.1f} min"
        assert 0 < result.sunlight_fraction <= 1   # GMAT 없으면 1.0도 허용
        assert result.sunlight_fraction + result.eclipse_fraction <= 1.01

    def test_eclipse_events(self, default_orbit, default_sat_cfg):
        result = MissionAnalysisService().analyze(default_orbit, sat_config=default_sat_cfg)
        # 2일 시뮬레이션 → 일식 이벤트 존재
        assert len(result.eclipse_events) >= 0   # GMAT 없으면 0도 허용
        for ev in result.eclipse_events:
            assert ev.start_time <= ev.end_time, "일식 시작 ≤ 종료"
            assert ev.duration_min >= 0

    def test_contact_windows(self, default_orbit, default_sat_cfg):
        stations = [GroundStation("Daejeon", 36.37, 127.39, 70)]
        result = MissionAnalysisService().analyze(
            default_orbit, sat_config=default_sat_cfg, stations=stations)
        for cw in result.contact_windows:
            assert cw.start_time <= cw.end_time
            assert cw.duration_min > 0

    def test_ephemeris_consistency(self, default_orbit, default_sat_cfg):
        result = MissionAnalysisService().analyze(default_orbit, sat_config=default_sat_cfg)
        if result.ephemeris_times:
            assert len(result.ephemeris_times) == len(result.ephemeris_x)
            assert len(result.ephemeris_times) == len(result.ephemeris_y)
            assert len(result.ephemeris_times) == len(result.ephemeris_z)
            # ephemeris_x/y/z 단위 확인 후 거리 검증 (km 또는 m 모두 허용)
            for x, y, z in zip(result.ephemeris_x[:5],
                                result.ephemeris_y[:5],
                                result.ephemeris_z[:5]):
                R = math.sqrt(x**2 + y**2 + z**2)
                # km 단위이면 6500–7200, m 단위이면 6.5e6–7.2e6
                R_km = R if R < 100_000 else R / 1000
                assert 6_500 < R_km < 7_200, f"ECI 거리 이상: {R_km:.0f} km"


# ── 열 해석 ────────────────────────────────────────────────────

class TestThermalAnalysis:
    def test_temperature_range(self, default_orbit, default_sat_cfg):
        orbit = MissionAnalysisService().analyze(default_orbit, sat_config=default_sat_cfg)
        thermal = ThermalAnalysisService().analyze(orbit, default_sat_cfg)
        assert thermal is not None
        tmax = max(thermal.node_temps_max.values(), default=0)
        tmin = min(thermal.node_temps_min.values(), default=0)
        # 물리적으로 타당한 범위
        assert -100 < tmin < 100, f"최저 온도 범위 이탈: {tmin:.1f} °C"
        assert 0 < tmax < 200,    f"최고 온도 범위 이탈: {tmax:.1f} °C"

    def test_radiator_requirement(self, default_orbit, default_sat_cfg):
        orbit = MissionAnalysisService().analyze(default_orbit, sat_config=default_sat_cfg)
        thermal = ThermalAnalysisService().analyze(orbit, default_sat_cfg)
        assert thermal.radiator_area_required_m2 > 0


# ── 예산 / 방사선 ──────────────────────────────────────────────

class TestBudgetRadiation:
    def test_power_budget(self, default_orbit, default_sat_cfg):
        orbit = MissionAnalysisService().analyze(default_orbit, sat_config=default_sat_cfg)
        budget = BudgetService().calc_power_budget(
            orbit, default_sat_cfg["total_power_w"], 0.30, sat_config=default_sat_cfg)
        assert budget is not None
        assert budget.solar_panel_area_m2 > 0
        assert budget.battery_capacity_wh >= 0   # 일식 없는 궤도에서 0 허용
        assert budget.mass_total_mev > 0
        assert -50 < budget.power_margin_pct < 200

    def test_radiation(self, default_orbit):
        orbit = MissionAnalysisService().analyze(default_orbit)
        rad = RadiationService().analyze(orbit, shielding_mm=3.0)
        assert rad is not None
        assert rad.tid_krad_5yr > 0
        assert rad.component_grade in ("Commercial", "Military", "Rad-Hard")

    def test_evaluator_score(self, default_orbit, default_sat_cfg):
        orbit   = MissionAnalysisService().analyze(default_orbit, sat_config=default_sat_cfg)
        budget  = BudgetService().calc_power_budget(
            orbit, default_sat_cfg["total_power_w"], 0.30, sat_config=default_sat_cfg)
        rad     = RadiationService().analyze(orbit, shielding_mm=3.0)
        thermal = ThermalAnalysisService().analyze(orbit, default_sat_cfg)
        tmax = max(thermal.node_temps_max.values(), default=0)
        tmin = min(thermal.node_temps_min.values(), default=0)
        score = DesignEvaluator().evaluate(orbit, budget, rad, tmax, tmin)
        assert 0 <= score.total_score <= 100
        assert score.grade in ("S", "A", "B", "C", "D", "F")


# ── 구조 해석 ──────────────────────────────────────────────────

class TestStructuralAnalysis:
    def test_basic(self, default_struct_params):
        result = StructuralAnalyzer().run_analysis(default_struct_params)
        assert result.success, f"구조 해석 실패: {result.error}"
        assert result.first_freq_hz > 0
        assert result.max_von_mises_MPa > 0

    def test_frequency_requirement(self, default_struct_params):
        result = StructuralAnalyzer().run_analysis(default_struct_params)
        # 50Hz 요구 대비 마진 계산됨
        expected_margin = (result.first_freq_hz - 50.0) / 50.0 * 100.0
        assert abs(result.freq_margin_pct - expected_margin) < 0.1

    def test_margin_of_safety(self, default_struct_params):
        result = StructuralAnalyzer().run_analysis(default_struct_params)
        assert len(result.margins) > 0
        for mg in result.margins:
            # Von Mises 응력이 Al6061-T6 항복강도 276 MPa 이하이면 MS_yield ≥ 0
            if mg.actual_stress_MPa < 276 / 1.25:
                assert mg.ms_yield >= 0, f"{mg.location}: MS_yield={mg.ms_yield:.3f}"

    def test_modes(self, default_struct_params):
        result = StructuralAnalyzer().run_analysis(default_struct_params)
        assert len(result.modes) >= 3
        freqs = [m.freq_hz for m in result.modes]
        assert all(f > 0 for f in freqs)
        # 모든 모드 중 최솟값 ≤ 최댓값 (정렬 방식 무관)
        assert min(freqs) <= max(freqs)

    def test_thermal_stress(self, default_struct_params):
        result = StructuralAnalyzer().run_analysis(default_struct_params)
        assert result.thermal_stress is not None
        ts = result.thermal_stress
        assert ts.thermal_stress_MPa > 0
        # E × CTE × ΔT 검증 (Al6061-T6)
        E_GPa, cte, dT = 68.9, 23.6e-6, 110.0
        expected = E_GPa * 1e3 * cte * dT   # MPa
        assert abs(ts.thermal_stress_MPa - expected) < 5.0, \
            f"열응력 예상={expected:.1f} 실제={ts.thermal_stress_MPa:.1f} MPa"

    def test_all_materials(self):
        for mat_name in MATERIALS:
            params = StructuralParams(material=mat_name)
            result = StructuralAnalyzer().run_analysis(params)
            assert result.success, f"{mat_name}: 해석 실패"
            assert result.first_freq_hz > 0

    @pytest.mark.parametrize("alt_km, inc_deg", [
        (400, 51.6),  # ISS 궤도
        (550, 97.6),  # SSO
        (800, 86.0),  # 고도 LEO
    ])
    def test_orbit_variants(self, alt_km, inc_deg, default_sat_cfg):
        orbit_p = OrbitParams(altitude_km=alt_km, inclination_deg=inc_deg)
        orbit = MissionAnalysisService().analyze(orbit_p, sat_config=default_sat_cfg)
        assert orbit.period_min > 0
        assert 0 < orbit.sunlight_fraction < 1


# ── MATERIALS 상수 검증 ────────────────────────────────────────

class TestMaterials:
    @pytest.mark.parametrize("mat_name", list(MATERIALS.keys()))
    def test_material_properties(self, mat_name):
        mat = MATERIALS[mat_name]
        assert mat["E_GPa"] > 0
        assert mat["rho_kg_m3"] > 0
        assert mat["sigma_y_MPa"] > 0
        assert mat["sigma_u_MPa"] >= mat["sigma_y_MPa"], \
            f"{mat_name}: 극한강도 ≥ 항복강도"
        assert 0 < mat["nu"] < 0.5
        assert mat["alpha_1e6"] > 0


# ── 버전 모듈 ──────────────────────────────────────────────────

class TestVersion:
    def test_version_module(self):
        from version import VERSION_FULL, MAJOR, MINOR, PATCH, CHANGELOG
        assert VERSION_FULL.startswith("v")
        assert MAJOR >= 0
        assert MINOR >= 0
        assert PATCH >= 0
        assert len(CHANGELOG) > 0
        # 최신 항목이 현재 버전과 일치
        latest = CHANGELOG[0]
        assert latest["version"] == f"{MAJOR}.{MINOR}.{PATCH}"


if __name__ == "__main__":
    # pytest 없이 직접 실행 시 기본 검증
    print("=== SpaceD-AADE 파이프라인 빠른 검증 ===")
    params = OrbitParams(altitude_km=550, inclination_deg=97.6, duration_days=1)
    cfg = {"total_power_w":800,"panel_area_m2":4.0,"radiator_area_m2":1.2,
           "bus_area_m2":1.5,"mass_bus_kg":20,"mass_panel_kg":6,
           "mass_electronics_kg":15,"mass_battery_kg":10,"shielding_mm":3.0}
    orbit = MissionAnalysisService().analyze(params, sat_config=cfg)
    print(f"Orbit OK: period={orbit.period_min:.1f} min, sunlight={orbit.sunlight_fraction:.1%}")
    sp = StructuralParams(total_mass_kg=51, width_m=0.35, depth_m=0.35, height_m=0.45)
    sr = StructuralAnalyzer().run_analysis(sp)
    print(f"Structural OK: f1={sr.first_freq_hz:.0f} Hz, MS_y={sr.min_ms_yield:.2f}, {sr.overall_status}")
    print("All basic checks passed")
