"""
GMAT Result Parser
GMAT이 내보낸 텍스트 기반 결과 리포트(이클립스, 컨택, 에퍼메리스 등)를 파싱하여 Domain 객체로 변환.
"""
import os
import re
from datetime import datetime, timedelta
import math
from core.domain.orbit import EclipseEvent, ContactWindow

# GMAT UTCGregorian timestamp format
_GMAT_FMT = "%d %b %Y %H:%M:%S.%f"


def _parse_gmat_utc(s: str) -> datetime:
    """Parse a GMAT UTCGregorian timestamp (e.g. '01 Jan 2026 12:00:00.000')"""
    return datetime.strptime(s.strip(), _GMAT_FMT)


def _to_mission_seconds(dt: datetime, epoch_dt: datetime) -> float:
    """Convert a datetime to seconds since mission epoch"""
    return (dt - epoch_dt).total_seconds()


class GmatResultParser:
    
    @staticmethod
    def parse_ephemeris(file_path: str, mission_epoch_iso: str = None):
        """
        GMAT 에페메리스 리포트 파싱.
        반환하는 times는 미션 시작 이후 경과 초(float) - 폴백 알고리즘과 동일한 타입.
        mission_epoch_iso 미지정 시 파일 첫 행 시각을 epoch 0으로 사용.
        """
        if not os.path.exists(file_path):
            return [], [], [], [], [], []

        epoch_dt = None
        if mission_epoch_iso:
            try:
                epoch_dt = datetime.fromisoformat(mission_epoch_iso.replace('Z', ''))
            except Exception:
                epoch_dt = None

        times, x_list, y_list, z_list, lat_list, lon_list = [], [], [], [], [], []

        with open(file_path, 'r') as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line or line.startswith('Sat.') or line.startswith('%'):
                continue

            # Format: 01 Jan 2026 12:00:00.000  X  Y  Z  VX  VY  VZ  Lat  Lon  Alt
            # parts:  [0]  [1]  [2]    [3]      [4][5][6] [7] [8] [9] [10] [11] [12]
            parts = [p for p in line.split() if p]
            if len(parts) >= 13:
                dt_str = " ".join(parts[0:4])
                try:
                    dt = _parse_gmat_utc(dt_str)

                    # epoch_dt 자동 설정 (첫 행 기준)
                    if epoch_dt is None:
                        epoch_dt = dt

                    elapsed_s = _to_mission_seconds(dt, epoch_dt)
                    x, y, z = float(parts[4]), float(parts[5]), float(parts[6])
                    lat, lon = float(parts[10]), float(parts[11])

                    times.append(elapsed_s)
                    x_list.append(x)
                    y_list.append(y)
                    z_list.append(z)
                    lat_list.append(lat)
                    lon_list.append(lon)
                except Exception:
                    pass

        return times, x_list, y_list, z_list, lat_list, lon_list

    @staticmethod
    def parse_eclipse(file_path: str, mission_epoch_iso: str = None):
        """
        일식 리포트 파싱 - start/end 을 미션 시작 이후 초(float)로 반환
        """
        events = []
        if not os.path.exists(file_path):
            return events

        epoch_dt = None
        if mission_epoch_iso:
            try:
                epoch_dt = datetime.fromisoformat(mission_epoch_iso.replace('Z', ''))
            except Exception:
                epoch_dt = None

        with open(file_path, 'r') as f:
            lines = f.readlines()

        data_started = False
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if 'Start Time' in line and 'Stop Time' in line:
                data_started = True
                continue
            if '-------' in line:
                data_started = True
                continue

            if data_started:
                # GMAT Eclipse Locator format:
                # 01 Jan 2026 12:01:23.456  01 Jan 2026 12:30:45.678  1762.22  Umbra
                parts = [p for p in line.split() if p]
                if len(parts) >= 9:
                    start_str = " ".join(parts[0:4])
                    end_str = " ".join(parts[4:8])
                    try:
                        t1 = _parse_gmat_utc(start_str)
                        t2 = _parse_gmat_utc(end_str)
                        dur_s = float(parts[8])

                        if epoch_dt:
                            s1 = _to_mission_seconds(t1, epoch_dt)
                            s2 = _to_mission_seconds(t2, epoch_dt)
                        else:
                            s1 = t1.timestamp()
                            s2 = t2.timestamp()

                        events.append(EclipseEvent(
                            start_time=s1,
                            end_time=s2,
                            duration_min=dur_s / 60.0
                        ))
                    except Exception:
                        pass
        return events

    @staticmethod
    def parse_contact(file_path: str, mission_epoch_iso: str = None):
        """
        접속 리포트 파싱 - start/end 을 미션 시작 이후 초(float)로 반환
        """
        windows = []
        if not os.path.exists(file_path):
            return windows

        epoch_dt = None
        if mission_epoch_iso:
            try:
                epoch_dt = datetime.fromisoformat(mission_epoch_iso.replace('Z', ''))
            except Exception:
                epoch_dt = None

        with open(file_path, 'r') as f:
            lines = f.readlines()

        data_started = False
        current_gs = "Unknown"
        for line in lines:
            line = line.strip()
            if not line:
                continue

            if 'Observer:' in line:
                current_gs = line.split(':')[1].strip()
                data_started = False
                continue

            if 'Start Time' in line and 'Stop Time' in line:
                data_started = True
                continue
            if '-------' in line:
                data_started = True
                continue

            if data_started and len(line) > 30 and 'Number of events' not in line:
                # Format: 01 Jan 2026 20:32:41.301    01 Jan 2026 20:39:40.792      419.49092082
                parts = [p for p in line.split() if p]
                if len(parts) >= 9:
                    start_str = " ".join(parts[0:4])
                    end_str = " ".join(parts[4:8])
                    try:
                        t1 = _parse_gmat_utc(start_str)
                        t2 = _parse_gmat_utc(end_str)
                        dur_s = float(parts[8])

                        if epoch_dt:
                            s1 = _to_mission_seconds(t1, epoch_dt)
                            s2 = _to_mission_seconds(t2, epoch_dt)
                        else:
                            s1 = t1.timestamp()
                            s2 = t2.timestamp()

                        windows.append(ContactWindow(
                            station_name=current_gs,
                            start_time=s1,
                            end_time=s2,
                            max_elevation_deg=45.0,
                            range_km=0.0
                        ))
                    except Exception:
                        pass
        return windows

