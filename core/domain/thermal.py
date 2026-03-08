"""
Thermal & Structural Domain Models
열/구조 관련 도메인 모델
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class ThermalNode:
    """열 노드 (Lumped-Parameter)"""
    node_id: int
    name: str
    mass_kg: float
    cp_jkg: float              # 비열 [J/kg·K]
    area_m2: float             # 방열 면적
    emissivity: float          # 방사율 ε
    absorptivity: float        # 흡수율 α (태양)
    internal_heat_w: float     # 내부 발열 [W]
    initial_temp_c: float = 20.0


@dataclass
class ThermalResult:
    """열해석 결과"""
    # 각 노드의 최고/최저/평균 온도
    node_temps_max: Dict[str, float] = field(default_factory=dict)   # {name: °C}
    node_temps_min: Dict[str, float] = field(default_factory=dict)
    node_temps_avg: Dict[str, float] = field(default_factory=dict)

    # 온도 이력 (시간별)
    time_s: List[float] = field(default_factory=list)
    temp_histories: Dict[str, List[float]] = field(default_factory=dict)  # {name: [°C]}

    # 열플럭스 요약
    q_solar_w: float = 0.0
    q_albedo_w: float = 0.0
    q_ir_w: float = 0.0
    q_internal_w: float = 0.0
    q_radiated_w: float = 0.0

    # 판정
    is_hot_case: bool = True
    margin_hot_c: float = 0.0   # 양수 = 여유
    margin_cold_c: float = 0.0

    # 방열판 요구 면적
    radiator_area_required_m2: float = 0.0
    heater_power_required_w: float = 0.0


@dataclass
class RadiationResult:
    """방사선 환경 분석 결과"""
    # TID (Total Ionizing Dose)
    tid_krad_5yr: float = 0.0          # 5년 임무 기준
    tid_krad_per_year: float = 0.0

    # 차폐 요구
    shielding_required_mm_al: float = 0.0   # 3krad 목표 기준
    shielding_current_mm_al: float = 3.0    # 현재 설계 두께

    # 플럭스
    proton_flux: float = 0.0           # p/cm²/s (>10MeV)
    electron_flux: float = 0.0        # e/cm²/s (>1MeV)

    # SEE rate 추산
    seu_rate_per_day: float = 0.0      # 단일사상 업셋

    # 등급 판정
    component_grade: str = "Commercial"   # Commercial / Mil / Rad-Hard
    is_acceptable: bool = True
    risk_level: str = "LOW"               # LOW / MEDIUM / HIGH


@dataclass
class StructuralResult:
    """구조 간이 검토 결과 (목업용)"""
    # 1차 공진 주파수
    first_freq_hz: float = 0.0
    freq_requirement_hz: float = 35.0
    freq_margin_hz: float = 0.0
    freq_pass: bool = True

    # 준정적 하중
    quasi_static_g: float = 0.0        # 최대 정적 가속도
    stress_max_mpa: float = 0.0        # 최대 응력
    allowable_stress_mpa: float = 0.0  # 허용 응력
    stress_margin: float = 0.0         # (허용/최대) - 1

    # 랜덤진동 응답
    grms_input: float = 0.0            # 입력 Grms
    grms_response: float = 0.0         # 응답 Grms

    overall_pass: bool = True
    mass_structure_kg: float = 0.0


@dataclass
class BudgetResult:
    """예산 계산 결과 전체"""
    # 질량 예산 [kg] (CBE / MEV) — 9 subsystems
    mass_structure_cbe:   float = 0.0
    mass_power_cbe:       float = 0.0
    mass_thermal_cbe:     float = 0.0
    mass_adcs_cbe:        float = 0.0
    mass_cdh_cbe:         float = 0.0
    mass_comms_cbe:       float = 0.0
    mass_propulsion_cbe:  float = 0.0
    mass_payload_cbe:     float = 0.0
    mass_harness_cbe:     float = 0.0
    mass_total_cbe:       float = 0.0
    mass_total_mev:       float = 0.0
    mass_margin_pct:      float = 0.0
    mass_launch_available: float = 100.0

    # 서브시스템별 마진 % (설계 기준값)
    MASS_MARGINS: Dict[str, float] = field(default_factory=lambda: {
        "Structure":  15.0,
        "Power":      10.0,
        "Thermal":    15.0,
        "ADCS":        5.0,
        "C&DH":        5.0,
        "Comms":      10.0,
        "Propulsion": 10.0,
        "Payload":    20.0,
        "Harness":    20.0,
    })

    # 전력 예산 [W]
    power_payload_w:        float = 0.0
    power_bus_w:            float = 0.0
    power_total_w:          float = 0.0
    solar_panel_area_m2:    float = 0.0
    solar_panel_efficiency: float = 0.30
    solar_generated_w:      float = 0.0    # 일조 중 태양전지 발전량
    battery_capacity_wh:    float = 0.0
    battery_dod_pct:        float = 0.0
    power_margin_w:         float = 0.0    # 마진 [W]
    power_margin_pct:       float = 0.0

    # 링크 예산
    downlink_rate_mbps: float = 0.0
    data_per_day_gb:    float = 0.0
    link_margin_db:     float = 0.0
    contact_count:      int   = 0          # 일일 접속 횟수
    contact_time_per_day_min: float = 0.0  # 일일 접속 총 시간
    uplink_rate_mbps:   float = 10.0       # 기본 업링크 100 Mbps의 1/10
    data_volume_stored_tb: float = 0.0     # 일일 저장 대역 추산 (탑재체)


@dataclass
class DesignScoreCard:
    """종합 설계 평가 점수 카드"""
    # 개별 항목 점수 (0~100)
    score_power: float = 0.0
    score_thermal: float = 0.0
    score_radiation: float = 0.0
    score_structure: float = 0.0
    score_contact: float = 0.0
    score_mass: float = 0.0

    # 종합
    total_score: float = 0.0
    grade: str = "N/A"          # A / B / C / D / F

    # 지표 상세
    indicators: Dict[str, dict] = field(default_factory=dict)
    # {
    #   'sunlight_ratio': {'value': 92.3, 'unit': '%', 'limit': 85, 'margin': 7.3, 'pass': True},
    #   ...
    # }
