"""
Structural Domain Model
구조/진동 해석 관련 도메인 데이터 클래스
IPSAP(DIAMOND) 어댑터와 간소 해석 엔진이 공통으로 사용합니다.
"""
from dataclasses import dataclass, field
from typing import List, Optional


# ── 재료 라이브러리 ──────────────────────────────────────────────
MATERIALS = {
    "Al6061-T6": dict(
        E_GPa=68.9, rho_kg_m3=2700, sigma_y_MPa=276, sigma_u_MPa=310,
        nu=0.33, alpha_1e6=23.6, k_W_mK=167, description="알루미늄 합금 (일반 구조재)"
    ),
    "Al7075-T73": dict(
        E_GPa=71.7, rho_kg_m3=2810, sigma_y_MPa=434, sigma_u_MPa=503,
        nu=0.33, alpha_1e6=23.6, k_W_mK=130, description="항공용 고강도 알루미늄"
    ),
    "Ti-6Al-4V": dict(
        E_GPa=113.8, rho_kg_m3=4430, sigma_y_MPa=880, sigma_u_MPa=950,
        nu=0.34, alpha_1e6=8.6, k_W_mK=6.7, description="티타늄 합금 (고하중 브래킷)"
    ),
    "CFRP-Quasi": dict(
        E_GPa=70.0, rho_kg_m3=1550, sigma_y_MPa=500, sigma_u_MPa=600,
        nu=0.30, alpha_1e6=2.0, k_W_mK=5.0, description="CFRP 준등방성 적층"
    ),
    "Invar36": dict(
        E_GPa=148, rho_kg_m3=8080, sigma_y_MPa=276, sigma_u_MPa=480,
        nu=0.26, alpha_1e6=1.3, k_W_mK=10.0, description="인바 합금 (저열팽창 광학 구조)"
    ),
}


@dataclass
class StructuralParams:
    """위성 구조 입력 파라미터"""
    # 제원
    total_mass_kg: float = 30.0           # 발사 질량
    structure_mass_kg: float = 8.0        # 구조체 순 질량
    width_m: float = 0.35                 # X (±2σ 설계 허용 범위)
    depth_m: float = 0.35                 # Y
    height_m: float = 0.45               # Z (발사 방향 기준)
    panel_thickness_mm: float = 3.0       # 사이드 패널 두께
    material: str = "Al6061-T6"           # 기본 구조재

    # 발사 하중 계획 (GEVS / JAXA JERG 기준)
    ql_axial_g: float = 14.0             # 준정적 축방향 (g)
    ql_lateral_g: float = 9.0            # 준정적 측면 (g)
    random_grms: float = 14.1            # 랜덤진동 Grms (GEVS Qual)
    freq_req_hz: float = 50.0            # 최소 1차 고유진동 요구 [Hz]

    # 탑재체/전장품박스 공간 질량
    payload_mass_kg: float = 5.0
    electronics_mass_kg: float = 7.0
    battery_mass_kg: float = 3.0

    # 안전계수
    factor_of_safety: float = 2.0        # 정적 최종 안전계수
    yield_factor: float = 1.25           # 항복 안전계수


@dataclass
class LoadCase:
    """해석 하중 케이스"""
    name: str
    description: str
    axial_g: float = 0.0
    lateral_g: float = 0.0
    torsional_Nm: float = 0.0


@dataclass
class ModeShape:
    """고유 모드 정보"""
    mode_number: int
    freq_hz: float
    modal_mass_fraction: float    # 유효 질량 분율
    direction: str                # "X", "Y", "Z", "RX", "RY", "RZ"
    description: str = ""


@dataclass
class NodeResult:
    """절점 응력/변형 결과"""
    node_id: int
    location: str                  # 설명 (예: "판넬 중앙", "마운트 구석")
    von_mises_MPa: float
    sigma_x_MPa: float = 0.0
    sigma_y_MPa: float = 0.0
    sigma_z_MPa: float = 0.0
    displacement_mm: float = 0.0


@dataclass
class MarginOfSafety:
    """안전 여유 (Margin of Safety)"""
    location: str
    load_case: str
    actual_stress_MPa: float
    allowable_MPa: float
    ms_yield: float               # σ_allow_yield / (σ_actual × YSF) - 1
    ms_ultimate: float            # σ_allow_ult / (σ_actual × FSu) - 1

    @property
    def is_pass(self) -> bool:
        return self.ms_yield >= 0.0 and self.ms_ultimate >= 0.0

    @property
    def status(self) -> str:
        if self.ms_yield < 0 or self.ms_ultimate < 0:
            return "FAIL"
        elif self.ms_yield < 0.1 or self.ms_ultimate < 0.1:
            return "MARGIN"
        return "PASS"


@dataclass
class ThermalStressResult:
    """열응력 간이 평가"""
    delta_T_K: float              # 작동 온도 범위
    material: str
    cte_1e6_per_K: float          # 열팽창계수
    constrained_length_mm: float  # 구속 길이
    thermal_stress_MPa: float     # E × CTE × ΔT
    ms_thermal: float             # 대 항복 마진


@dataclass
class StructuralResult:
    """IPSAP 어댑터 최종 출력"""
    # 상태
    success: bool = False
    error: Optional[str] = None
    mock_mode: bool = True           # True = 내장 간이해석 결과

    # 고유값 해석
    modes: List[ModeShape] = field(default_factory=list)
    first_freq_hz: float = 0.0
    freq_margin_pct: float = 0.0     # (f1 - f_req) / f_req × 100

    # 정적 응력
    node_results: List[NodeResult] = field(default_factory=list)
    max_von_mises_MPa: float = 0.0
    max_displacement_mm: float = 0.0

    # 안전 여유
    margins: List[MarginOfSafety] = field(default_factory=list)
    min_ms_yield: float = 0.0
    min_ms_ultimate: float = 0.0

    # 열응력
    thermal_stress: Optional[ThermalStressResult] = None

    # 랜덤진동 간이 평가
    three_sigma_g: float = 0.0       # 3σ 가속도
    three_sigma_stress_MPa: float = 0.0

    # 종합 판정
    @property
    def overall_status(self) -> str:
        if not self.success:
            return "ERROR"
        if self.first_freq_hz < 1.0:
            return "ERROR"
        freq_ok = self.first_freq_hz >= (self.modes[0].freq_hz if self.modes else 0)
        ms_ok = self.min_ms_yield >= 0 and self.min_ms_ultimate >= 0
        if not ms_ok:
            return "FAIL"
        if self.first_freq_hz < 40 or self.min_ms_yield < 0.05:
            return "MARGIN"
        return "PASS"
