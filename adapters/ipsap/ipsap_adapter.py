"""
StructuralAnalyzer — 내장 간이 구조 해석기
DIAMOND/IPSAP 없이 실행되는 예비 설계용 해석 엔진.

해석 방법:
  - 1차 고유진동수: Euler-Bernoulli 외팔보 등가 공식
  - 정적 응력:     준정적 굽힘+압축 중첩, Von Mises
  - 안전 여유:     MS_yield / MS_ultimate
  - 랜덤 진동:     Miles 공식 (pi/2 * fn * Q * PSD)
  - 열응력:        E * CTE * DeltaT (완전 구속 가정)

실제 FEM 연동은 추후 외부 NASTRAN 호환 솔버를 통해 확장 예정.
"""
import math
import logging
from typing import List

from core.domain.structural import (
    StructuralParams, StructuralResult,
    ModeShape, NodeResult, MarginOfSafety,
    ThermalStressResult, MATERIALS,
)

log = logging.getLogger(__name__)

_G = 9.80665   # m/s^2


class StructuralAnalyzer:
    """
    내장 간이 구조 해석기.

    예비 설계 단계에서 위성 구조 응력/고유진동/안전 여유를
    실시간으로 평가합니다. 공식 정밀도 ±30%.

    Examples
    --------
    >>> from adapters.ipsap.ipsap_adapter import StructuralAnalyzer
    >>> from core.domain.structural import StructuralParams
    >>> result = StructuralAnalyzer().run_analysis(StructuralParams(total_mass_kg=30))
    >>> print(result.first_freq_hz, result.overall_status)
    """

    def run_analysis(self, params: StructuralParams) -> StructuralResult:
        """내장 공식 기반 예비 설계 구조 평가"""
        result = StructuralResult(mock_mode=True)
        mat = MATERIALS.get(params.material, MATERIALS["Al6061-T6"])
        E   = mat["E_GPa"] * 1e9
        sy  = mat["sigma_y_MPa"]
        su  = mat["sigma_u_MPa"]
        cte = mat["alpha_1e6"] * 1e-6

        W, D, H = params.width_m, params.depth_m, params.height_m
        t = params.panel_thickness_mm / 1000.0
        m = params.total_mass_kg

        try:
            # ── 1. 고유진동수 (Euler-Bernoulli 외팔보) ──────────────────
            # 박스 단면 2차 모멘트
            Ixx   = (D * W**3 - (D - 2*t) * (W - 2*t)**3) / 12.0
            Iyy   = (W * D**3 - (W - 2*t) * (D - 2*t)**3) / 12.0
            I_min = min(Ixx, Iyy)
            lam1  = 1.875
            f1_x  = (lam1**2 / (2 * math.pi * H**2)) * math.sqrt(E * I_min / (m / H))
            A_wall = 2 * (W + D) * t
            f1_z   = (1 / (2 * math.pi)) * math.sqrt(E * A_wall / H / m)

            modes: List[ModeShape] = [
                ModeShape(1, round(f1_x, 1), 0.65, "X", "1차 횡방향 X"),
                ModeShape(2, round(f1_x, 1), 0.65, "Y", "1차 횡방향 Y"),
                ModeShape(3, round(f1_z, 1), 0.75, "Z", "1차 축방향 Z"),
            ]
            for k in range(4, 11):
                modes.append(ModeShape(k, round(f1_x * (k - 1) ** 0.6 * 2.0, 1),
                                       0.02, "MIXED", f"고차 모드 {k}"))
            result.modes = modes
            result.first_freq_hz = f1_x
            result.freq_margin_pct = (f1_x - params.freq_req_hz) / params.freq_req_hz * 100.0

            # ── 2. 준정적 응력 ─────────────────────────────────────────
            F_ax  = m * params.ql_axial_g   * _G
            F_lat = m * params.ql_lateral_g * _G
            c           = max(W, D) / 2.0
            sigma_bend  = (F_lat * H / 2.0) * c / I_min    # Pa
            sigma_axial = F_ax / A_wall                      # Pa
            sigma_vm    = math.sqrt(sigma_axial ** 2 + sigma_bend ** 2
                                    - sigma_axial * sigma_bend) / 1e6  # MPa
            disp_max    = F_lat * H ** 3 / (3 * E * I_min) * 1000.0   # mm

            locations = ["기저 모서리 ±X", "기저 모서리 ±Y",
                         "패널 중앙 +X", "패널 중앙 -X",
                         "패널 중앙 +Y", "패널 중앙 -Y"]
            factors = [1.00, 0.95, 0.55, 0.55, 0.52, 0.50]
            node_results = [
                NodeResult(
                    node_id=i + 1, location=loc,
                    von_mises_MPa=round(sigma_vm * sf, 2),
                    sigma_x_MPa=round((sigma_axial / 1e6) * sf, 2),
                    sigma_y_MPa=round((sigma_bend  / 1e6) * sf, 2),
                    displacement_mm=round(disp_max * sf, 3),
                )
                for i, (loc, sf) in enumerate(zip(locations, factors))
            ]
            result.node_results        = node_results
            result.max_von_mises_MPa   = round(sigma_vm, 2)
            result.max_displacement_mm = round(disp_max, 3)

            # ── 3. 안전 여유 ───────────────────────────────────────────
            ysf = params.yield_factor
            fos = params.factor_of_safety
            margins = [
                MarginOfSafety(
                    location=nr.location, load_case="LC3-Combined",
                    actual_stress_MPa=nr.von_mises_MPa, allowable_MPa=sy,
                    ms_yield    = round(sy / (nr.von_mises_MPa * ysf) - 1.0, 3),
                    ms_ultimate = round(su / (nr.von_mises_MPa * fos) - 1.0, 3),
                )
                for nr in node_results if nr.von_mises_MPa > 0
            ]
            result.margins         = margins
            result.min_ms_yield    = min(mg.ms_yield    for mg in margins) if margins else 0.0
            result.min_ms_ultimate = min(mg.ms_ultimate for mg in margins) if margins else 0.0

            # ── 4. 랜덤 진동 Miles 공식 ────────────────────────────────
            Q     = 10.0
            W_in  = (params.random_grms * _G) ** 2 / f1_x
            a_rms = math.sqrt(math.pi / 2 * f1_x * Q * W_in)
            result.three_sigma_g          = round(a_rms * 3.0 / _G, 1)
            result.three_sigma_stress_MPa = round(
                (m * a_rms * 3.0 * H / 2 * c / I_min) / 1e6, 1)

            # ── 5. 열응력 (ΔT = 110 K) ─────────────────────────────────
            sigma_th = E * cte * 110.0 / 1e6
            result.thermal_stress = ThermalStressResult(
                delta_T_K=110.0, material=params.material,
                cte_1e6_per_K=mat["alpha_1e6"],
                constrained_length_mm=max(W, D) * 1000.0,
                thermal_stress_MPa=round(sigma_th, 2),
                ms_thermal=round(sy / (sigma_th * ysf) - 1.0, 3),
            )

            result.success = True
            log.info("구조 해석 완료: f1=%.1f Hz, sigma_max=%.1f MPa, MS_y=%.2f",
                     f1_x, sigma_vm, result.min_ms_yield)

        except Exception as exc:
            result.error = f"구조 해석 오류: {exc}"
            log.exception("StructuralAnalyzer error")

        return result


# 하위 호환 별칭
IpsapAdapter = StructuralAnalyzer
