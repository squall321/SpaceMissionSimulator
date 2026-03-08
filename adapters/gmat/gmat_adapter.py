"""
GMAT Adapter
GMAT 파이프라인의 메인 진입점. 스크립트 생성, 외부 GMAT 실행, 결과 파싱 등을 조율합니다.
"""
import os
import math
import subprocess
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from core.domain.orbit import OrbitParams, OrbitResult
from adapters.gmat.script_factory import GmatScriptFactory
from adapters.gmat.result_parser import GmatResultParser

log = logging.getLogger(__name__)

# 프로젝트 루트 경로 (adapters/gmat/gmat_adapter.py 기준)
PROJECT_ROOT = Path(__file__).parent.parent.parent


def _find_gmat_path() -> str:
    """
    GMAT 경로를 다음 순서로 탐색:
    1. 환경 변수 GMAT_BIN_DIR
    2. 프로젝트 내 tools/GMAT/bin
    3. 시스템 기본 경로 C:/GMAT/bin
    """
    # 1. 환경 변수
    env_path = os.environ.get("GMAT_BIN_DIR")
    if env_path and os.path.exists(os.path.join(env_path, "GMAT.exe")):
        return env_path
    
    # 2. 프로젝트 내장 GMAT (권장)
    local_gmat = PROJECT_ROOT / "tools" / "GMAT" / "bin"
    if local_gmat.exists() and (local_gmat / "GMAT.exe").exists():
        return str(local_gmat)
    
    # 3. 시스템 기본 경로
    system_default = "C:\\GMAT\\bin"
    if os.path.exists(os.path.join(system_default, "GMAT.exe")):
        return system_default
    
    # GMAT이 없으면 프로젝트 내장 경로 반환 (나중에 설치될 수 있음)
    return str(local_gmat)


class GmatAdapter:
    def __init__(self, gmat_bin_dir: str = None):
        """
        :param gmat_bin_dir: GMAT 실행 파일(GMAT.exe 등)이 있는 디렉토리
                             자동 탐색 순서: 환경변수 → 프로젝트 내장 → 시스템 기본
        """
        self.gmat_bin_dir = gmat_bin_dir or _find_gmat_path()
        self.gmat_exe = os.path.join(self.gmat_bin_dir, "GMAT.exe")
        # GmatConsole.exe: GUI 없이 배치 실행하는 전용 CLI 버전 (R2022a+)
        self.gmat_console = os.path.join(self.gmat_bin_dir, "GmatConsole.exe")
        # GMAT output directory - use GMAT's own output/ dir to avoid SPICE path issues
        self.gmat_output_dir = str(Path(self.gmat_bin_dir).parent / "output" / "spaced_analysis")
        os.makedirs(self.gmat_output_dir, exist_ok=True)
        self.factory = GmatScriptFactory()
        self.parser = GmatResultParser()
        
        log.info(f"GmatAdapter initialized with GMAT path: {self.gmat_bin_dir}")
        log.info(f"GMAT available: {self.is_available()}")
        log.info(f"GmatConsole available: {self.is_console_available()}")

    def is_available(self) -> bool:
        """GMAT 실행 파일이 존재하는지 확인"""
        return os.path.exists(self.gmat_exe) or os.path.exists(self.gmat_console)

    def is_console_available(self) -> bool:
        """GmatConsole.exe (헤드리스 배치 실행)이 존재하는지 확인"""
        return os.path.exists(self.gmat_console)

    def _get_run_exe(self) -> str:
        """배치 실행에 사용할 실행 파일 반환 (GmatConsole 우선)"""
        if os.path.exists(self.gmat_console):
            return self.gmat_console
        return self.gmat_exe

    def run_analysis(self, 
                     params: OrbitParams, 
                     sat_config: dict, 
                     ground_stations: list) -> OrbitResult:
        """
        전체 GMAT 해석 파이프라인 실행
        1. 임시 디렉토리 생성
        2. 스크립트 동적 렌더링
        3. GMAT.exe 호출
        4. 결과 리포트 파싱
        5. OrbitResult 도메인 객체로 매핑
        """
        result = OrbitResult(params=params)
        
        if not self.is_available():
            result.error = f"GMAT executable not found at {self.gmat_exe}. Please set GMAT_BIN_DIR."
            return result

        # 임시 디렉토리 (스크립트용), 리포트는 GMAT output/ 디렉토리 사용
        with TemporaryDirectory(prefix="spaced_gmat_") as tmp_dir:
            script_path = os.path.join(tmp_dir, "run_orbit.script")
            output_dir = self.gmat_output_dir
            
            # 1. 스크립트 생성
            try:
                self.factory.generate_script(
                    orbit_params=params,
                    sat_config=sat_config,
                    ground_stations=ground_stations,
                    output_dir=output_dir,
                    script_path=script_path
                )
            except Exception as e:
                result.error = f"Failed to generate GMAT script: {e}"
                return result

            # 2. GMAT 실행 (GmatConsole.exe 배치 모드 우선)
            try:
                run_exe = self._get_run_exe()
                # GmatConsole: GmatConsole.exe <script>
                # GMAT GUI:    GMAT.exe --minimize --run <script>
                if run_exe == self.gmat_console:
                    cmd = [run_exe, script_path]
                else:
                    cmd = [run_exe, "--minimize", "--run", script_path]
                
                log.info(f"Running GMAT: {' '.join(cmd)}")
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding='cp949',
                    errors='replace',
                    timeout=300,
                    cwd=self.gmat_bin_dir   # GMAT 데이터 파일 참조를 위해 bin 디렉토리에서 실행
                )
                
                log.info(f"GMAT returncode: {process.returncode}")
                if process.stdout:
                    log.debug(f"GMAT stdout: {process.stdout[:500]}")
                if process.stderr:
                    log.debug(f"GMAT stderr: {process.stderr[:500]}")
                
                if process.returncode != 0:
                    result.error = f"GMAT execution failed (code {process.returncode}): {process.stderr[:300]}"
                    return result
            except subprocess.TimeoutExpired:
                result.error = "GMAT execution timed out (300s)."
                return result
            except Exception as e:
                result.error = f"Failed to execute GMAT: {e}"
                return result

            # 3. 결과 파싱
            ephem_file   = os.path.join(output_dir, "Ephemeris.txt")
            eclipse_file = os.path.join(output_dir, "Eclipse_Report.txt")
            contact_file = os.path.join(output_dir, "Contact_Report.txt")

            try:
                # 에퍼메리스 (시간=미션 시작 이후 초, X, Y, Z, Lat, Lon)
                times, xs, ys, zs, lats, lons = self.parser.parse_ephemeris(ephem_file, params.epoch)
                if not times:
                    result.error = "GMAT Ephemeris report empty or failed to parse."
                    return result
                    
                result.ephemeris_times = times
                result.ephemeris_x = xs
                result.ephemeris_y = ys
                result.ephemeris_z = zs
                # 기초 궤도 특성 계산 (원궤도 근사, 간소화)
                import numpy as np
                r_mags = np.sqrt(np.array(xs)**2 + np.array(ys)**2 + np.array(zs)**2)
                avg_r = np.mean(r_mags)
                mu = 398600.4418
                result.period_min = 2 * np.pi * np.sqrt(avg_r**3 / mu) / 60.0
                
                # 이벤트 파싱
                result.eclipse_events = self.parser.parse_eclipse(eclipse_file, params.epoch)
                result.contact_windows = self.parser.parse_contact(contact_file, params.epoch)
                
                # 통계량 파생
                total_duration_days = params.duration_days
                total_duration_min = total_duration_days * 24 * 60
                
                eclipse_min = sum(e.duration_min for e in result.eclipse_events)
                result.eclipse_fraction = min(1.0, eclipse_min / total_duration_min)
                result.sunlight_fraction = 1.0 - result.eclipse_fraction
                
                result.contacts_per_day = len(result.contact_windows) / total_duration_days
                result.contact_time_per_day_min = sum(c.duration_min for c in result.contact_windows) / total_duration_days
                
                # Radiation/Thermal 용 간소화 Beta Angle 유지
                result.beta_angle_deg = 23.44 * math.sin(math.radians(params.inclination_deg)) # 단순 추정치
                result.radiation_flux_proton = 1.5e5 * (params.altitude_km / 500)
                result.radiation_flux_electron = 5.2e6 * (params.altitude_km / 500)
                
            except Exception as e:
                result.error = f"Failed to parse GMAT results: {e}"
                return result
                
        return result
