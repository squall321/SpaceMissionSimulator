"""
Budget & Radiation Services
전력/질량/링크 예산 자동 계산 + 방사선 환경 평가
"""
import math
from core.domain.orbit import OrbitResult
from core.domain.thermal import (
    BudgetResult, RadiationResult, DesignScoreCard
)

SOLAR_CONST = 1361.0  # W/m²


class BudgetService:
    """전력/질량/링크 예산 자동 계산"""

    def calc_power_budget(self, orbit: OrbitResult,
                          payload_power_w: float,
                          solar_efficiency: float = 0.30,
                          sat_config: dict = None) -> BudgetResult:
        res = BudgetResult()
        sat_config = sat_config or {}

        # ── 전력 예산 ──
        sf = orbit.sunlight_fraction
        bus_power = payload_power_w * 0.35           # 버스 = 페이로드의 35%
        res.power_payload_w = payload_power_w
        res.power_bus_w = bus_power
        res.power_total_w = payload_power_w + bus_power

        # 태양전지 필요 면적 (EOL 마진 20% 감출)
        p_required = res.power_total_w / max(sf, 0.5)
        p_eol_factor = 0.80                           # EOL 성능 저하
        area = p_required / (SOLAR_CONST * solar_efficiency * p_eol_factor)
        res.solar_panel_area_m2 = round(area, 2)
        res.solar_panel_efficiency = solar_efficiency

        # 배터리 (일식 전력 커버, DOD 30% 제한)
        eclipse_max_min = max((e.duration_min for e in orbit.eclipse_events), default=0)
        battery_energy = res.power_total_w * eclipse_max_min / 60.0
        res.battery_capacity_wh = battery_energy / 0.30   # DOD 30%
        res.battery_dod_pct = 30.0

        # 전력 마진
        p_available = SOLAR_CONST * solar_efficiency * p_eol_factor * sat_config.get('panel_area_m2', area) * sf
        res.solar_generated_w  = round(p_available, 1)
        res.power_margin_w     = round(p_available - res.power_total_w, 1)
        res.power_margin_pct   = (p_available - res.power_total_w) / res.power_total_w * 100

        # ── 기초 요구량 연동 (`app.py` Starlink-class 경량 설계 기준 적용) ──
        dual_boards = sat_config.get('dual_boards', 20)
        modules = math.ceil(dual_boards / 10.0)
        
        # 컴퓨팅 페이로드
        dual_board_mass = 2.5
        shielding_per_module = 5.0
        compute_mass = dual_boards * dual_board_mass + modules * shielding_per_module
        res.mass_payload_cbe = round(compute_mass, 1)

        # 서브시스템 질량 추산
        total_p_kw = float(res.power_total_w) / 1000.0
        
        mass_power_sys = (sat_config.get('mass_panel_kg', res.solar_panel_area_m2 * 1.5) + 
                          res.battery_capacity_wh / 250.0 +  # 250 Wh/kg 리튬이온 밀도 적용
                          total_p_kw * 0.5) # PCDU
        mass_thermal = sat_config.get('radiator_area_m2', 3.0) * 2.0  # 방열판 밀도 2.0 kg/m2
        
        sub_total = compute_mass + mass_power_sys + mass_thermal
        
        mass_struct = sub_total * 0.08
        mass_adcs = 3.0 + total_p_kw * 0.1
        mass_comms = 5.0 + total_p_kw * 0.2
        mass_cdh = 2.0  # OBC
        mass_prop = 5.0 + sub_total * 0.02
        mass_harness = sub_total * 0.03

        res.mass_structure_cbe = round(float(mass_struct), 1)
        res.mass_power_cbe = round(float(mass_power_sys), 1)
        res.mass_thermal_cbe = round(float(mass_thermal), 1)
        res.mass_adcs_cbe = round(float(mass_adcs), 1)
        res.mass_cdh_cbe = round(float(mass_cdh), 1)
        res.mass_comms_cbe = round(float(mass_comms), 1)
        res.mass_propulsion_cbe = round(float(mass_prop), 1)
        res.mass_harness_cbe = round(float(mass_harness), 1)
        
        res.mass_total_cbe = sum([mass_struct, mass_power_sys, mass_thermal,
                                  mass_adcs, mass_cdh, mass_comms, mass_prop,
                                  compute_mass, mass_harness])
        
        res.mass_total_mev = res.mass_total_cbe * 1.15
        res.mass_launch_available = res.mass_total_mev * 1.5 # 발사체 마진 여유 공간 확보로 임의 설정
        res.mass_margin_pct = (
            (res.mass_launch_available - res.mass_total_mev)
            / res.mass_launch_available * 100
        )

        # ── 링크 예산 ──
        contact_min_day = orbit.contact_time_per_day_min
        res.downlink_rate_mbps       = 100.0                # 100 Mbps 기본
        res.data_per_day_gb          = res.downlink_rate_mbps * contact_min_day * 60 / 8 / 1024
        res.link_margin_db           = 3.0
        res.contact_count            = int(round(orbit.contacts_per_day))
        res.contact_time_per_day_min = contact_min_day
        res.uplink_rate_mbps         = 10.0
        res.data_volume_stored_tb    = res.power_payload_w * 0.001 * 86400 / 1e3  # 간소 추산

        return res


class RadiationService:
    """방사선 환경 평가 서비스 (AP-8/AE-8 간소 모델)"""

    # 차폐 두께별 TID 감쇄 팩터 (Al 등가, 5년 LEO 기준)
    SHIELDING_TID = {
        1.0: 80.0,   # 1mm Al → 80 krad
        2.0: 40.0,
        3.0: 20.0,
        5.0: 10.0,
        7.0:  5.0,
        10.0: 2.0,
    }

    def analyze(self, orbit: OrbitResult,
                shielding_mm: float = 3.0,
                mission_years: float = 5.0) -> RadiationResult:
        res = RadiationResult()
        res.shielding_current_mm_al = shielding_mm
        res.proton_flux = orbit.radiation_flux_proton
        res.electron_flux = orbit.radiation_flux_electron

        # TID 계산 (간소 모델: 고도 + 차폐 두께)
        base_tid = self._base_tid_per_year(orbit.params.altitude_km,
                                           orbit.params.inclination_deg)
        shielding_factor = self._shielding_attenuation(shielding_mm)
        res.tid_krad_per_year = base_tid * shielding_factor
        res.tid_krad_5yr = res.tid_krad_per_year * mission_years

        # 필요 차폐 두께 (부품 등급별 한계선량 기준)
        grade, limit_krad = self._determine_component_grade(res.tid_krad_5yr)
        res.component_grade = grade
        res.shielding_required_mm_al = self._required_shielding(
            base_tid * mission_years, limit_krad)

        # SEE rate (단순 추산)
        res.seu_rate_per_day = orbit.radiation_flux_proton * 1e-12 * 86400

        # 위험도 판정
        if res.tid_krad_5yr < 20 and grade in ("Commercial", "Mil"):
            res.risk_level = "LOW"
            res.is_acceptable = True
        elif res.tid_krad_5yr < 50:
            res.risk_level = "MEDIUM"
            res.is_acceptable = True
        else:
            res.risk_level = "HIGH"
            res.is_acceptable = False

        return res

    def _base_tid_per_year(self, alt_km: float, inc_deg: float) -> float:
        """고도/경사각 기반 연간 기본 TID [krad/yr] (차폐 없음)"""
        if alt_km < 500:
            tid = 10.0
        elif alt_km < 700:
            tid = 20.0
        elif alt_km < 900:
            tid = 50.0
        elif alt_km < 1200:
            tid = 150.0   # 내부 반앨런대 접근
        else:
            tid = 300.0

        # SAA 통과 보정 (경사각 20~70°)
        if 20 < inc_deg < 70:
            tid *= 1.5
        return tid

    def _shielding_attenuation(self, mm: float) -> float:
        """차폐 감쇄 팩터 (0~1, 두께가 클수록 작음)"""
        return max(0.02, math.exp(-0.35 * (mm - 1.0)))

    def _determine_component_grade(self, tid_5yr: float):
        if tid_5yr < 5:
            return "Commercial", 5.0
        elif tid_5yr < 20:
            return "Mil", 20.0
        elif tid_5yr < 100:
            return "Rad-Hard", 100.0
        else:
            return "Rad-Hard+", 300.0

    def _required_shielding(self, total_tid_unshielded: float,
                            limit_krad: float) -> float:
        """목표 TID 달성에 필요한 Al 두께 [mm]"""
        if total_tid_unshielded <= 0 or limit_krad <= 0:
            return 1.0
        factor = limit_krad / total_tid_unshielded
        mm = max(1.0, -math.log(factor) / 0.35 + 1.0)
        return round(float(mm), 1)


class DesignEvaluator:
    """종합 설계 평가 점수 산출"""

    def evaluate(self, orbit: OrbitResult,
                 budget: BudgetResult,
                 radiation: RadiationResult,
                 thermal_max_c: float,
                 thermal_min_c: float) -> DesignScoreCard:
        sc = DesignScoreCard()
        inds = {}

        # 1. 일조율 (목표: >85%)
        sf_pct = orbit.sunlight_fraction * 100
        inds['sunlight_ratio'] = self._ind(
            sf_pct, '%', limit_lo=85, is_lo_limit=True)

        # 2. 최대 일식 (목표: <30분)
        max_ecl = max((e.duration_min for e in orbit.eclipse_events), default=0)
        inds['max_eclipse'] = self._ind(
            max_ecl, 'min', limit_hi=30, is_hi_limit=True)

        # 3. 배터리 DOD (목표: <35%)
        inds['battery_dod'] = self._ind(
            budget.battery_dod_pct, '%', limit_hi=35, is_hi_limit=True)

        # 4. 최고 온도 (목표: <70°C)
        inds['temp_max'] = self._ind(
            thermal_max_c, '°C', limit_hi=70, is_hi_limit=True)

        # 5. 최저 온도 (목표: >-20°C)
        inds['temp_min'] = self._ind(
            thermal_min_c, '°C', limit_lo=-20, is_lo_limit=True)

        # 6. TID 5년 (목표: <20 krad @3mm)
        inds['tid_5yr'] = self._ind(
            radiation.tid_krad_5yr, 'krad', limit_hi=20, is_hi_limit=True)

        # 7. 접속 횟수 (목표: >4회/일)
        inds['contacts_per_day'] = self._ind(
            orbit.contacts_per_day, '회/일', limit_lo=4, is_lo_limit=True)

        # 8. 질량 마진 (목표: >15%)
        inds['mass_margin'] = self._ind(
            budget.mass_margin_pct, '%', limit_lo=15, is_lo_limit=True)

        # 9. 전력 마진 (목표: >10%)
        inds['power_margin'] = self._ind(
            budget.power_margin_pct, '%', limit_lo=10, is_lo_limit=True)

        sc.indicators = inds

        # 점수 계산 (항목별 통과 여부 + 마진 크기)
        scores = [self._score(v) for v in inds.values()]
        sc.total_score = round(float(sum(scores) / len(scores) if scores else 0.0), 1)

        if sc.total_score >= 90:
            sc.grade = 'A+'
        elif sc.total_score >= 80:
            sc.grade = 'A'
        elif sc.total_score >= 70:
            sc.grade = 'B'
        elif sc.total_score >= 60:
            sc.grade = 'C'
        else:
            sc.grade = 'F'

        return sc

    def _ind(self, value, unit, limit_lo=None, limit_hi=None,
             is_lo_limit=False, is_hi_limit=False):
        if is_lo_limit and limit_lo is not None:
            margin = value - limit_lo
            passed = margin >= 0
        elif is_hi_limit and limit_hi is not None:
            margin = limit_hi - value
            passed = margin >= 0
        else:
            margin = 0
            passed = True
        return {'value': round(value, 2), 'unit': unit,
                'margin': round(margin, 2), 'pass': passed}

    def _score(self, ind: dict) -> float:
        if not ind['pass']:
            return max(0.0, 50.0 + ind['margin'] * 2)
        return min(100.0, 75.0 + ind['margin'] * 1.5)
