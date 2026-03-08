"""
Mission Analysis Service
SGP4 기반 궤도 전파 + 간소 일식/접속/열플럭스 계산
실제 GMAT 없이도 동작하는 내장 해석 엔진 (목업/빠른 평가용)
"""
import os
import subprocess
import logging
import math
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List, Tuple

from core.domain.orbit import (
    OrbitParams, OrbitResult, EclipseEvent, ContactWindow, GroundStation
)
from adapters.gmat.gmat_adapter import GmatAdapter

# 지구 상수
MU = 398600.4418       # km³/s²
R_EARTH = 6371.0       # km
J2 = 1.08263e-3
SOLAR_CONST = 1361.0   # W/m²
DEG = math.pi / 180.0


class MissionAnalysisService:
    """
    내장 궤도 해석 서비스
    - SGP4 간소화 버전 (원형 궤도 가정으로 빠른 계산)
    - 일식, 접속, 열플럭스 자동 산출
    """

    DEFAULT_STATIONS = [
        GroundStation("Seoul",    37.5665,  126.9780, 30.0,  5.0),
        GroundStation("Daejeon",  36.3504,  127.3845, 70.0,  5.0),
        GroundStation("Svalbard", 78.2292,   15.4080, 45.0,  5.0),
        GroundStation("Fairbanks",64.8401, -147.7200, 100.0, 5.0),
    ]

    def __init__(self):
        self.gmat_adapter = GmatAdapter()

    def analyze(self, params: OrbitParams,
                stations: List[GroundStation] = None,
                sat_config: dict = None) -> OrbitResult:
        """궤도 파라미터 → 전체 해석 결과 반환"""
        if stations is None:
            stations = self.DEFAULT_STATIONS
        if sat_config is None:
            sat_config = {}

        # 1. GMAT 연동 시도
        if self.gmat_adapter.is_available():
            result = self.gmat_adapter.run_analysis(params, sat_config, stations)
            if not result.error:
                # GMAT 성공 시 추가로 필요한 연간 dV 등 잔여 계산만 채움
                result.delta_v_per_year_ms = self._calc_station_keeping_dv(params.altitude_km)
                return result

        # 2. GMAT이 없거나 실패 시 내부 Fallback 모델 사용
        result = OrbitResult(params=params)

        try:
            # 1. 기본 궤도 요소 계산
            a = R_EARTH + params.altitude_km          # 반장축 km
            result.period_min = 2 * math.pi * math.sqrt(a**3 / MU) / 60.0
            result.velocity_kms = math.sqrt(MU / a)
            result.altitude_min_km = params.altitude_km
            result.altitude_max_km = params.altitude_km  # 원형 궤도 가정
            result.beta_angle_deg = self._calc_beta_angle(
                params.inclination_deg, params.raan_deg)

            # 2. 에페메리스 생성 (원형 궤도)
            result.ephemeris_times, result.ephemeris_x, \
                result.ephemeris_y, result.ephemeris_z = \
                self._propagate_circular(params, result.period_min)

            # 3. 일식 계산
            result.eclipse_events = self._calc_eclipses(
                result.ephemeris_times, result.ephemeris_x,
                result.ephemeris_y, result.ephemeris_z, params)
            result.eclipse_fraction = self._eclipse_fraction(
                result.eclipse_events, params.duration_days * 86400)
            result.sunlight_fraction = 1.0 - result.eclipse_fraction

            # 4. 접속 계산
            result.contact_windows = self._calc_contacts(
                result.ephemeris_times, result.ephemeris_x,
                result.ephemeris_y, result.ephemeris_z, stations, params)
            total_contact = sum(w.duration_min for w in result.contact_windows)
            result.contacts_per_day = len(result.contact_windows) / params.duration_days
            result.contact_time_per_day_min = total_contact / params.duration_days

            # 5. 궤도 유지 ΔV (대기 항력 근사)
            result.delta_v_per_year_ms = self._calc_station_keeping_dv(
                params.altitude_km)

            # 6. 방사선 환경 (고도 기반 간소 모델)
            result.radiation_flux_proton, result.radiation_flux_electron = \
                self._calc_radiation_flux(params.altitude_km, params.inclination_deg)

        except Exception as e:
            result.error = str(e)

        return result

    # ─────────────────────────────────────────────
    # 내부 계산 메서드
    # ─────────────────────────────────────────────

    def _propagate_circular(self, params: OrbitParams, period_min: float):
        """원형 궤도 에페메리스 생성"""
        a = R_EARTH + params.altitude_km
        inc = params.inclination_deg * DEG
        raan = params.raan_deg * DEG

        n = 2 * math.pi / (period_min * 60)   # rad/s
        dt = 60.0  # 1분 스텝
        total_steps = int(params.duration_days * 86400 / dt)

        times, xs, ys, zs = [], [], [], []
        for i in range(min(total_steps, 4320)):  # 최대 3일
            t = i * dt
            M = n * t   # 평균 근점이각
            # 궤도면 내 위치
            x_orb = a * math.cos(M)
            y_orb = a * math.sin(M)
            # ECI 변환 (경사각, RAAN 적용)
            x = (math.cos(raan)*math.cos(M) -
                 math.sin(raan)*math.sin(M)*math.cos(inc)) * a
            y = (math.sin(raan)*math.cos(M) +
                 math.cos(raan)*math.sin(M)*math.cos(inc)) * a
            z = math.sin(inc) * math.sin(M) * a
            times.append(t)
            xs.append(x)
            ys.append(y)
            zs.append(z)

        return times, xs, ys, zs

    def _calc_beta_angle(self, inc_deg: float, raan_deg: float) -> float:
        """Beta 각 근사 계산 (태양 황위 ≈ 0 가정)"""
        # 태양 방향 (춘분점 기준 단순화)
        sun_lon = 0.0  # 실제는 날짜 기반
        beta = math.asin(
            math.cos(inc_deg * DEG) * math.cos(sun_lon * DEG) +
            math.sin(inc_deg * DEG) * math.sin(sun_lon * DEG) *
            math.sin(raan_deg * DEG)
        ) / DEG
        return beta

    def _calc_eclipses(self, times, xs, ys, zs, params) -> List[EclipseEvent]:
        """원통 그림자 모델로 일식 감지"""
        events = []
        in_eclipse = False
        start_t = 0.0

        sun_dir = np.array([1.0, 0.0, 0.0])  # 태양 방향 (단순화)

        for i, (t, x, y, z) in enumerate(zip(times, xs, ys, zs)):
            pos = np.array([x, y, z])
            # 원통 그림자 판별
            proj = np.dot(pos, sun_dir)
            perp2 = np.dot(pos, pos) - proj**2
            in_shadow = (proj < 0) and (math.sqrt(max(perp2, 0)) < R_EARTH)

            if in_shadow and not in_eclipse:
                in_eclipse = True
                start_t = t
            elif not in_shadow and in_eclipse:
                in_eclipse = False
                dur = (t - start_t) / 60.0
                if dur > 0.5:
                    events.append(EclipseEvent(start_t, t, dur))

        if in_eclipse and times:
            dur = (times[-1] - start_t) / 60.0
            if dur > 0.5:
                events.append(EclipseEvent(start_t, times[-1], dur))

        return events

    def _eclipse_fraction(self, events: List[EclipseEvent], total_s: float) -> float:
        if total_s <= 0:
            return 0.0
        total_eclipse = sum(e.duration_min * 60 for e in events)
        return min(total_eclipse / total_s, 1.0)

    def _calc_contacts(self, times, xs, ys, zs,
                       stations: List[GroundStation],
                       params: OrbitParams) -> List[ContactWindow]:
        """각 지상국과의 접속 윈도우 계산"""
        windows = []

        for gs in stations:
            lat = gs.latitude_deg * DEG
            lon = gs.longitude_deg * DEG
            min_el = gs.min_elevation_deg * DEG

            in_contact = False
            start_t = 0.0
            max_el = 0.0
            min_range = 1e9

            for t, x, y, z in zip(times, xs, ys, zs):
                # 지구 자전 반영 (15°/hr)
                earth_rot = (t / 3600.0) * 15.0 * DEG
                gs_lon = lon + earth_rot
                gs_x = R_EARTH * math.cos(lat) * math.cos(gs_lon)
                gs_y = R_EARTH * math.cos(lat) * math.sin(gs_lon)
                gs_z = R_EARTH * math.sin(lat)

                # 위성-지상국 벡터
                dp = np.array([x - gs_x, y - gs_y, z - gs_z])
                gs_vec = np.array([gs_x, gs_y, gs_z])
                gs_norm = gs_vec / (np.linalg.norm(gs_vec) + 1e-9)
                dp_norm = dp / (np.linalg.norm(dp) + 1e-9)

                el = math.asin(np.clip(np.dot(dp_norm, gs_norm), -1, 1))
                rng = np.linalg.norm(dp)

                if el >= min_el:
                    if not in_contact:
                        in_contact = True
                        start_t = t
                        max_el = el
                        min_range = rng
                    else:
                        max_el = max(max_el, el)
                        min_range = min(min_range, rng)
                else:
                    if in_contact:
                        in_contact = False
                        dur = t - start_t
                        if dur > 30:  # 30초 이상
                            windows.append(ContactWindow(
                                station_name=gs.name,
                                start_time=start_t,
                                end_time=t,
                                max_elevation_deg=max_el / DEG,
                                range_km=min_range
                            ))

        windows.sort(key=lambda w: w.start_time)
        return windows

    def _calc_station_keeping_dv(self, altitude_km: float) -> float:
        """대기 항력에 의한 연간 ΔV 추산 (m/s/yr)"""
        # 고도별 대기 밀도 근사
        if altitude_km < 400:
            rho = 1e-11
        elif altitude_km < 500:
            rho = 5e-12
        elif altitude_km < 600:
            rho = 1e-12
        elif altitude_km < 700:
            rho = 2e-13
        else:
            rho = 1e-14

        v = math.sqrt(MU / (R_EARTH + altitude_km)) * 1000  # m/s
        cd = 2.2
        area_mass = 0.01  # m²/kg 기준
        dv_per_s = 0.5 * rho * v**2 * cd * area_mass
        return dv_per_s * 3.154e7   # 연간 m/s

    def _calc_radiation_flux(self, altitude_km: float,
                             inclination_deg: float) -> Tuple[float, float]:
        """AP-8/AE-8 간소 모델 - 고도별 방사선 플럭스 추산"""
        # 양성자 플럭스 > 10 MeV (p/cm²/s)
        if altitude_km < 600:
            p_flux = 1e3
        elif altitude_km < 800:
            p_flux = 5e3
        elif altitude_km < 1200:
            p_flux = 5e4    # SAA 영향
        elif altitude_km < 1600:
            p_flux = 2e5    # 내부 반앨런대 접근
        else:
            p_flux = 5e4

        # 경사각에 따른 SAA 통과 빈도 보정
        if 20 < inclination_deg < 70:
            p_flux *= 2.0   # SAA 자주 통과

        # 전자 플럭스 > 1 MeV (e/cm²/s)
        if altitude_km < 600:
            e_flux = 1e5
        elif altitude_km < 1000:
            e_flux = 5e5
        else:
            e_flux = 2e6

        return p_flux, e_flux
