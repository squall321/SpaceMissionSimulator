"""
Orbit Domain Model
궤도 관련 도메인 모델 (데이터 클래스)
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class OrbitParams:
    """사용자 입력 궤도 파라미터"""
    altitude_km: float = 550.0
    inclination_deg: float = 97.6        # SSO 기본값
    raan_deg: float = 0.0
    eccentricity: float = 0.0
    arg_perigee_deg: float = 0.0
    true_anomaly_deg: float = 0.0
    orbit_type: str = "SSO"              # LEO, SSO, DDSSO
    epoch: str = "2026-03-07T00:00:00"
    duration_days: float = 3.0


@dataclass
class EclipseEvent:
    """일식 이벤트"""
    start_time: float    # 임무 시작 이후 초
    end_time: float
    duration_min: float

    @property
    def is_total(self) -> bool:
        return self.duration_min > 0


@dataclass
class ContactWindow:
    """지상국 접속 윈도우"""
    station_name: str
    start_time: float    # 임무 시작 이후 초
    end_time: float
    max_elevation_deg: float
    range_km: float

    @property
    def duration_min(self) -> float:
        return (self.end_time - self.start_time) / 60.0


@dataclass
class GroundStation:
    """지상국"""
    name: str
    latitude_deg: float
    longitude_deg: float
    altitude_m: float = 0.0
    min_elevation_deg: float = 5.0


@dataclass
class OrbitResult:
    """GMAT/SGP4 궤도 해석 결과 패키지"""
    params: OrbitParams

    # 궤도 기본 파생값
    period_min: float = 0.0
    altitude_min_km: float = 0.0
    altitude_max_km: float = 0.0
    velocity_kms: float = 0.0
    beta_angle_deg: float = 0.0

    # 에페메리스 (시간, x, y, z [km]) - GMAT ReportFile 파싱값
    ephemeris_times: List[float] = field(default_factory=list)    # 초
    ephemeris_x: List[float] = field(default_factory=list)        # km ECI
    ephemeris_y: List[float] = field(default_factory=list)
    ephemeris_z: List[float] = field(default_factory=list)

    # 일식
    eclipse_events: List[EclipseEvent] = field(default_factory=list)
    eclipse_fraction: float = 0.0        # 전체 대비 일식 비율
    sunlight_fraction: float = 0.0       # 일조율

    # 지상국 접속
    contact_windows: List[ContactWindow] = field(default_factory=list)
    contacts_per_day: float = 0.0
    contact_time_per_day_min: float = 0.0

    # 궤도 유지
    delta_v_per_year_ms: float = 0.0

    # 방사선 환경 (고도 기반 초기 추산)
    radiation_flux_proton: float = 0.0   # p/cm²/s
    radiation_flux_electron: float = 0.0

    error: Optional[str] = None
