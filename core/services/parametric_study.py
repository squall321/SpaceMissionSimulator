"""
Parametric Study Service
고도 × 경사각 스윕 — 분석 엔진 없이 해석적 근사로 빠르게 계산
GMAT 없이 수 ms 내 10×10 그리드 생성
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import List, Optional


# ── 상수 ────────────────────────────────────────────────────────
MU      = 398600.4418   # km³/s²  지구 중력 상수
RE      = 6371.0        # km      지구 반경
J2      = 1.08263e-3    # -       J2 섭동 계수
S0      = 1361.0        # W/m²   태양상수
LAMBDA  = 500e-9        # m       Rayleigh λ (가시광)


# ── 결과 데이터클래스 ────────────────────────────────────────────
@dataclass
class ParamPoint:
    altitude_km:              float
    inclination_deg:          float
    # 궤도 기본
    period_min:               float
    velocity_kms:             float
    # 일식
    eclipse_max_min:          float   # 최대 일식 지속시간 (min/orbit)
    sunlight_fraction:        float   # 일조율 (0~1)
    # 접속 (서울 37.5°N 기준)
    contacts_per_day:         float
    contact_time_per_day_min: float
    # 해상도
    gsd_m:                    float   # GSD (m), aperture 15cm
    # 방사선 (3mm Al, 5yr 임무)
    tid_krad:                 float
    # SSO 여부
    is_sso:                   bool
    # 궤도 유지 ΔV
    delta_v_ms_yr:            float
    # 전력 (태양전지 면적 기준 4m²)
    power_margin_pct:         float
    # 재방문 주기 추산 (hr)
    revisit_hr:               float


@dataclass
class ParametricStudyResult:
    grid: List[List[ParamPoint]]    # [inc_idx][alt_idx]
    alt_values: List[float]
    inc_values: List[float]
    alt_steps:  int
    inc_steps:  int


class ParametricStudyService:
    """해석적 근사 기반 고속 파라메트릭 스윕"""

    # 기본 대상 지상국 (서울)
    GS_LAT       = 37.5
    GS_EL_MIN    = 5.0          # deg, 최소 부각
    APERTURE_CM  = 15.0         # cm, 기본 카메라 구경
    SAT_POWER_W  = 800          # W, 위성 총 소비전력
    PANEL_EFF    = 0.30         # 태양전지 효율
    PANEL_AREA   = 4.0          # m², 기본 패널 면적
    MISSION_YEAR = 5.0          # year, 임무 수명

    # 방사선 TID 근사 (3mm Al, AP-8 curve fit)
    # TID(krad/yr) ≈ A * exp(-B*(h-h0)) + C (쌍곡선 간이 맞춤)
    _TID_PARAMS = [
        # (h_min, h_max, A, B, C)
        (300,  800,   2.0,  0.0, 0.0),   # LEO 저선량
        (800, 1200,   8.0,  0.0, 0.0),   # 방사선대 진입
        (1200, 2000, 18.0,  0.0, 0.0),   # 내부 방사선대
    ]

    # ── 공개 API ────────────────────────────────────────────────
    def sweep(self,
              alt_range:   tuple[float, float] = (300, 1200),
              inc_range:   tuple[float, float] = (0,   105),
              alt_steps:   int = 10,
              inc_steps:   int = 10,
              aperture_cm: float = None,
              gs_lat:      float = None) -> ParametricStudyResult:
        """고도 × 경사각 2D 그리드 계산 → ParametricStudyResult 반환"""
        ap  = aperture_cm if aperture_cm else self.APERTURE_CM
        lat = gs_lat      if gs_lat      else self.GS_LAT

        alts = [alt_range[0] + (alt_range[1] - alt_range[0]) / (alt_steps - 1) * i
                for i in range(alt_steps)]
        incs = [inc_range[0] + (inc_range[1] - inc_range[0]) / (inc_steps - 1) * i
                for i in range(inc_steps)]

        grid: list[list[ParamPoint]] = []
        for inc in incs:
            row: list[ParamPoint] = []
            for alt in alts:
                row.append(self._calc_point(alt, inc, ap, lat))
            grid.append(row)

        return ParametricStudyResult(
            grid=grid,
            alt_values=alts,
            inc_values=incs,
            alt_steps=alt_steps,
            inc_steps=inc_steps,
        )

    def single(self, alt_km: float, inc_deg: float,
               aperture_cm: float = None, gs_lat: float = None) -> ParamPoint:
        return self._calc_point(
            alt_km, inc_deg,
            aperture_cm or self.APERTURE_CM,
            gs_lat or self.GS_LAT,
        )

    # ── 내부 계산 ────────────────────────────────────────────────
    def _calc_point(self, h: float, i_deg: float,
                    ap: float, gs_lat: float) -> ParamPoint:
        a = RE + h
        i = math.radians(i_deg)

        # ── 기본 궤도 요소 ───────────────────────────────────────
        period_s  = 2 * math.pi * math.sqrt(a**3 / MU)
        period_m  = period_s / 60.0
        v         = math.sqrt(MU / a)                            # km/s

        # ── 일식 ────────────────────────────────────────────────
        # Earth subtended half-angle ρ = arcsin(RE/a)
        rho = math.asin(RE / a)                                  # rad
        # 최악 beta=0 가정시 최대 일식각 = 2*rho
        eclipse_frac = 2 * rho / (2 * math.pi)
        eclipse_max_m = eclipse_frac * period_m

        # ── 지상국 접속 (해석적 기하 근사) ─────────────────────
        el_min_r = math.radians(self.GS_EL_MIN)
        gs_lat_r = math.radians(gs_lat)

        # Earth central angle for visibility
        # rho_vis = arccos(RE*cos(el_min) / a) - el_min  (정확한 식)
        gamma = math.acos(RE * math.cos(el_min_r) / a) - el_min_r  # rad

        # 접속 가능 경위도 원: 반각 = gamma
        # 접속 가능성 = 지상국이 가시 원 안에 들어오는 확률 × 궤도 수
        n_rev = 86400.0 / period_s     # 일일 궤도 수

        # 경사각에 따른 GS 가시 가중치
        # 극궤도(90°): 모든 위도 커버. 적도궤도(0°): 위도 ≤ 경사각만 커버
        gs_lat_ok = min(abs(math.degrees(gs_lat_r)), abs(i_deg))
        if abs(i_deg) >= abs(gs_lat):
            vis_weight = 1.0
        else:
            # GS 위도가 경사각보다 높으면 접속 불가
            vis_weight = max(0.0, 1.0 - (abs(gs_lat) - abs(i_deg)) / 10.0)
            vis_weight = max(0.0, vis_weight)

        # 접속 횟수/일 ≈ n_rev × (2*gamma/π) × vis_weight
        contacts = max(0.0, n_rev * (2 * gamma / math.pi) * vis_weight)

        # 접속 1건당 평균 지속시간 (단순 기하)
        if contacts > 0:
            # 최대 앙각 > el_min인 접속 호길이 / v_rel
            # 근사: t_contact = 2 * gamma_rad * (RE+h) / v_rel
            v_rel = v  # 대략적인 상대 속도 (회전 무시)
            t_per_contact_s = 2 * gamma * a / v_rel
            t_total_min = min(contacts, n_rev) * t_per_contact_s / 60.0
        else:
            t_total_min = 0.0
        t_total_min = max(0.0, t_total_min)

        # ── GSD (Rayleigh) ───────────────────────────────────────
        # GSD = 1.22 λ h / D
        gsd_m = 1.22 * LAMBDA * (h * 1000) / (ap * 0.01)

        # ── TID 근사 (3mm Al, 5년 임무) ─────────────────────────
        # 고도별 간이 AP-8 curve:
        tid_yr = self._tid_annual(h)
        tid = tid_yr * self.MISSION_YEAR

        # ── SSO 여부 ────────────────────────────────────────────
        # SSO 경사각: i_sso = 97.8 + 0.0016*(h-500)
        i_sso_target = 97.8 + 0.0016 * (h - 500)
        is_sso = abs(i_deg - i_sso_target) < 2.0

        # ── 궤도유지 ΔV ──────────────────────────────────────────
        # 대기 항력 (h < 600km: 유의미, h > 700km: 무시)
        if h < 400:
            dv = 50.0
        elif h < 500:
            dv = 20.0
        elif h < 600:
            dv = 8.0
        elif h < 700:
            dv = 2.0
        else:
            dv = 0.3

        # ── 전력 마진 ─────────────────────────────────────────────
        # 일조 시 발전량 = 패널면적 × S0 × 효율
        gen = self.PANEL_AREA * S0 * self.PANEL_EFF
        # 필요 전력 = SAT_POWER_W / 일조율
        sun_frac = 1.0 - eclipse_frac
        needed = self.SAT_POWER_W / max(0.1, sun_frac)
        pwr_margin = (gen - needed) / needed * 100.0

        # ── 재방문 주기 ──────────────────────────────────────────
        # Sun-synchronous: 회귀 주기 = 1~16 days depending on alt/LTDN
        # 근사: 지구 전체 커버에 필요한 orbits = 360 / (2*gamma_deg)
        gamma_deg = math.degrees(gamma)
        if gamma_deg > 0:
            orbits_to_cover = 360.0 / (2 * gamma_deg) if gamma_deg > 0 else 999
            revisit_hr = (orbits_to_cover / n_rev) * 24.0
        else:
            revisit_hr = 999.0
        revisit_hr = min(revisit_hr, 240.0)

        return ParamPoint(
            altitude_km              = round(h, 1),
            inclination_deg          = round(i_deg, 1),
            period_min               = round(period_m, 2),
            velocity_kms             = round(v, 3),
            eclipse_max_min          = round(eclipse_max_m, 1),
            sunlight_fraction        = round(1.0 - eclipse_frac, 4),
            contacts_per_day         = round(contacts, 1),
            contact_time_per_day_min = round(t_total_min, 1),
            gsd_m                    = round(gsd_m, 2),
            tid_krad                 = round(tid, 1),
            is_sso                   = is_sso,
            delta_v_ms_yr            = round(dv, 1),
            power_margin_pct         = round(pwr_margin, 1),
            revisit_hr               = round(revisit_hr, 1),
        )

    def _tid_annual(self, h: float) -> float:
        """고도별 연간 TID(krad) 간이 추산 (3mm Al, 적도기준 AP-8)"""
        if h < 500:
            return 1.0 + (h - 300) / 200 * 2.0     # 1~3 krad/yr
        elif h < 900:
            return 3.0 + (h - 500) / 400 * 8.0     # 3~11 krad/yr
        elif h < 1200:
            return 11.0 + (h - 900) / 300 * 15.0   # 11~26 krad/yr (내부 방사선대)
        elif h < 1500:
            return 26.0 + (h - 1200) / 300 * 20.0  # 26~46 krad/yr
        else:
            return 18.0 - (h - 1500) / 500 * 5.0   # 체감 (외부 방사선대 빠져나감)
