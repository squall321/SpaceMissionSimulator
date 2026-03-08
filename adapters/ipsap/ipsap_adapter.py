"""
IPSAP Adapter
DIAMOND/IPSAP FEM 해석 파이프라인 메인 진입점.

두 가지 동작 모드:
  1. Mock 모드 (IPSAP 미설치) — 내장 해석 공식으로 빠른 예비 설계 평가
  2. 실행 모드 (IPSAP 설치됨) — BDF 생성 → IPSAP 실행 → f06 파싱

Mock 모드 해석 방법:
  - 1차 고유진동수: 등가 외팔보 공식 (Euler-Bernoulli)
  - 정적 응력: 준정적 굽힘/압축 중첩
  - 랜덤 진동: Miles 공식 (π/2 × fn × Q × PSD)
  - 열응력: E × CTE × ΔT (구속 조건 가정)
"""
import os
import math
import subprocess
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

from core.domain.structural import (
    StructuralParams, StructuralResult,
    ModeShape, NodeResult, MarginOfSafety, ThermalStressResult, MATERIALS
)
from adapters.ipsap.input_generator import IpsapInputGenerator
from adapters.ipsap.result_reader import IpsapResultReader

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
_G = 9.80665   # m/s²


def _find_ipsap_path() -> Optional[str]:
    """
    IPSAP/DIAMOND 실행 경로 탐색 (우선순위 순):
    1. 환경 변수 IPSAP_BIN_DIR (IPSAP.exe or NASTRAN.exe)
    2. DIAMOND 기본 설치 경로 C:/DIAMOND/bin
    3. MSC Nastran 경로 C:/MSC.Software/MSC_Nastran/*/bin
    """
    env = os.environ.get("IPSAP_BIN_DIR")
    if env:
        for exe in ("ipsap.exe", "IPSAP.exe", "nastran.exe", "NASTRAN.exe"):
            if (Path(env) / exe).exists():
                return env

    # DIAMOND 기본 경로
    diamond = Path("C:/DIAMOND/bin")
    if (diamond / "DIAMOND.exe").exists() or (diamond / "ipsap.exe").exists():
        return str(diamond)

    # MSC Nastran 와일드카드 탐색
    msc_root = Path("C:/MSC.Software")
    if msc_root.exists():
        for candidate in sorted(msc_root.glob("MSC_Nastran/*/bin"), reverse=True):
            if any(candidate.glob("nastran*")):
                return str(candidate)

    return None    # 설치 없음 → Mock 모드


class IpsapAdapter:
    """
    IPSAP/DIAMOND FEM 해석 어댑터.

    Parameters
    ----------
    ipsap_bin_dir : str, optional
        IPSAP/NASTRAN 실행 파일 디렉터리.
        None 이면 자동 탐색하고, 찾지 못하면 Mock 모드로 전환.
    work_dir : str, optional
        BDF/f06 작업 디렉터리. None 이면 임시 폴더 사용.
    """

    def __init__(self, ipsap_bin_dir: str = None, work_dir: str = None):
        self._bin_dir = ipsap_bin_dir or _find_ipsap_path()
        self._work_dir = Path(work_dir) if work_dir else None
        self._reader = IpsapResultReader()

    # ── 공개 API ──────────────────────────────────────────────

    def is_available(self) -> bool:
        """IPSAP/DIAMOND 실행 파일 사용 가능 여부"""
        if not self._bin_dir:
            return False
        bin_path = Path(self._bin_dir)
        return any((bin_path / exe).exists()
                   for exe in ("ipsap.exe","IPSAP.exe","nastran.exe","NASTRAN.exe",
                                "DIAMOND.exe","diamond.exe"))

    @property
    def mode(self) -> str:
        return "IPSAP" if self.is_available() else "Mock"

    def run_analysis(self, params: StructuralParams) -> StructuralResult:
        """
        구조 해석 실행.
        IPSAP 가 설치되어 있으면 실제 FEM, 없으면 Mock 해석.
        """
        if self.is_available():
            return self._run_ipsap(params)
        else:
            log.info("IPSAP not found — Mock 해석 모드 사용")
            return self._run_mock(params)

    # ── 실제 IPSAP 실행 ────────────────────────────────────────

    def _run_ipsap(self, params: StructuralParams) -> StructuralResult:
        gen = IpsapInputGenerator(params)
        work = self._work_dir or Path(TemporaryDirectory().name)
        work.mkdir(parents=True, exist_ok=True)

        bdf_path = gen.generate(work)
        f06_path = bdf_path.with_suffix(".f06")

        exe = self._find_exe()
        cmd = [exe, str(bdf_path)]
        log.info("IPSAP 실행: %s", " ".join(cmd))
        try:
            proc = subprocess.run(
                cmd, cwd=str(work),
                capture_output=True, text=True, timeout=300
            )
            if proc.returncode != 0:
                result = StructuralResult()
                result.error = f"IPSAP exit {proc.returncode}: {proc.stderr[:200]}"
                return result
        except subprocess.TimeoutExpired:
            result = StructuralResult()
            result.error = "IPSAP 실행 타임아웃 (300s)"
            return result
        except Exception as exc:
            result = StructuralResult()
            result.error = f"IPSAP 실행 실패: {exc}"
            return result

        result = self._reader.parse(f06_path, params)
        result.mock_mode = False
        return result

    def _find_exe(self) -> str:
        bin_path = Path(self._bin_dir)
        for exe in ("ipsap.exe","IPSAP.exe","nastran.exe","NASTRAN.exe",
                    "DIAMOND.exe","diamond.exe"):
            p = bin_path / exe
            if p.exists():
                return str(p)
        raise FileNotFoundError(f"IPSAP 실행 파일 없음: {self._bin_dir}")

    # ── Mock (내장 간이 해석) ──────────────────────────────────

    def _run_mock(self, params: StructuralParams) -> StructuralResult:
        """
        해석 공식 기반 예비 설계 평가.
        실제 FEM 대비 ±30% 오차 범위 내 결과 제공.
        """
        result = StructuralResult(mock_mode=True)
        mat = MATERIALS.get(params.material, MATERIALS["Al6061-T6"])
        E   = mat["E_GPa"] * 1e9          # Pa
        rho = mat["rho_kg_m3"]            # kg/m³
        sy  = mat["sigma_y_MPa"]          # MPa
        su  = mat["sigma_u_MPa"]          # MPa
        nu  = mat["nu"]
        cte = mat["alpha_1e6"] * 1e-6     # 1/K

        W, D, H = params.width_m, params.depth_m, params.height_m
        t = params.panel_thickness_mm / 1000.0   # m
        m = params.total_mass_kg

        try:
            # ── 1. 고유진동수 (등가 외팔보 Euler-Bernoulli) ──────────
            #   f1 = (λ1²)/(2π·L²) · √(EI/ρ_lin)
            #   L = H (발사 방향 == 보 길이)
            #   단면 (XY평면): W × D 박스 단면, 두께 t
            #   λ1 = 1.875  (외팔보 1차 모드)
            # 단면 2차 모멘트 (박스 단면 — 벽두께 t)
            Ixx = (D * W**3 - (D - 2*t) * (W - 2*t)**3) / 12.0   # Y-Z 굽힘
            Iyy = (W * D**3 - (W - 2*t) * (D - 2*t)**3) / 12.0   # X-Z 굽힘
            I_min = min(Ixx, Iyy)                               # 취약 방향

            # 유효 선밀도 [kg/m]: 구조 껍질 + 내부 집중 질량 균등 분포
            m_int   = (params.payload_mass_kg
                       + params.electronics_mass_kg
                       + params.battery_mass_kg)
            rho_lin = (m - m_int) / H + m_int / H   # ≈ m_total / H
            A_panel = 2*(W + D) * H * t + 2*W*D*t   # 전체 면적(정보용)

            lam1 = 1.875
            f1_z = (lam1**2 / (2 * math.pi * H**2)) * math.sqrt(E * I_min / rho_lin)
            # 축방향(Z) 고유진동 (스프링–질량 근사)
            k_axial = E * (2*W*D - (W-2*t)*(D-2*t)) / H       # N/m
            f1_ax   = (1/(2*math.pi)) * math.sqrt(k_axial / m)

            modes = [
                ModeShape(1, f1_z,  0.65, "X", "1차 횡방향 X"),
                ModeShape(2, f1_z,  0.65, "Y", "1차 횡방향 Y"),
                ModeShape(3, f1_ax, 0.75, "Z", "1차 축방향 Z"),
            ]
            # 상위 모드 추정 (배수 근사)
            for k in range(4, 11):
                fk = f1_z * (k - 1)**0.6 * 2.0
                modes.append(ModeShape(k, fk, 0.02, "MIXED", f"고차 모드 {k}"))

            result.modes       = modes
            result.first_freq_hz = f1_z
            result.freq_margin_pct = (f1_z - params.freq_req_hz) / params.freq_req_hz * 100.0

            # ── 2. 준정적 굽힘 응력 ─────────────────────────────────
            #   σ_bending = M·c/I  where M = F_lat × H/2, c = W/2
            F_ax  = m * params.ql_axial_g   * _G    # N
            F_lat = m * params.ql_lateral_g * _G    # N
            M_base = F_lat * H / 2.0                # N·m  (기저 모멘트)
            c = max(W, D) / 2.0
            sigma_bend = M_base * c / I_min         # Pa   (굽힘)
            sigma_axial= F_ax / (2*(W+D)*t)         # Pa   (압축)
            # Von Mises (축+굽힘 조합)
            sigma_vm   = math.sqrt(sigma_axial**2 + sigma_bend**2
                                   - sigma_axial * sigma_bend) / 1e6   # MPa

            node_cnt = 6  # 면당 대표 절점 모의
            node_results = []
            locations = ["기저 모서리 ±X", "기저 모서리 ±Y",
                         "패널 중앙 +X", "패널 중앙 -X",
                         "패널 중앙 +Y", "패널 중앙 -Y"]
            stress_factors = [1.0, 0.95, 0.55, 0.55, 0.52, 0.50]
            for i, (loc, sf) in enumerate(zip(locations, stress_factors)):
                node_results.append(NodeResult(
                    node_id=i+1, location=loc,
                    von_mises_MPa=round(sigma_vm * sf, 2),
                    sigma_x_MPa=round((sigma_axial/1e6) * sf, 2),
                    sigma_y_MPa=round((sigma_bend/1e6) * sf, 2),
                    displacement_mm=round(F_lat / (E * I_min / H**3) * 1000 * sf, 3),
                ))

            result.node_results      = node_results
            result.max_von_mises_MPa = round(sigma_vm, 2)
            result.max_displacement_mm = round(F_lat / (E * I_min / H**3) * 1000, 3)

            # ── 3. 안전 여유 ──────────────────────────────────────
            ysf = params.yield_factor
            fos = params.factor_of_safety
            margins = []
            for nr in node_results:
                if nr.von_mises_MPa <= 0:
                    continue
                ms_y = sy / (nr.von_mises_MPa * ysf) - 1.0
                ms_u = su / (nr.von_mises_MPa * fos)  - 1.0
                margins.append(MarginOfSafety(
                    location=nr.location, load_case="LC3-Combined",
                    actual_stress_MPa=nr.von_mises_MPa,
                    allowable_MPa=sy,
                    ms_yield=round(ms_y, 3), ms_ultimate=round(ms_u, 3),
                ))
            result.margins          = margins
            result.min_ms_yield     = min(m.ms_yield    for m in margins) if margins else 0.0
            result.min_ms_ultimate  = min(m.ms_ultimate for m in margins) if margins else 0.0

            # ── 4. 랜덤 진동 (Miles 공식 3σ 응력) ─────────────────
            #   σ_rms = sqrt(π/2 · fn · Q · W_in)
            #   여기서 W_in = (Grms)² / fn  (ASD 근사), Q=10
            Q_factor = 10.0
            Grms     = params.random_grms
            W_in     = (Grms * _G)**2 / f1_z      # (m/s²)² / Hz = m²/s³
            a_rms    = math.sqrt(math.pi / 2 * f1_z * Q_factor * W_in)  # m/s²
            # 3σ 가속도, 대응 응력 (낮은 정밀도)
            F_random = m * a_rms * 3.0
            sigma_rnd= (F_random * H/2 * c / I_min) / 1e6    # MPa

            result.three_sigma_g          = round(a_rms * 3.0 / _G, 1)
            result.three_sigma_stress_MPa = round(sigma_rnd, 1)

            # ── 5. 열응력 (ΔT = 고온90°C - 저온-20°C = 110K) ─────
            delta_T = 110.0
            sigma_th = E * cte * delta_T / 1e6    # MPa (완전 구속 가정)
            ms_th    = sy / (sigma_th * ysf) - 1.0
            result.thermal_stress = ThermalStressResult(
                delta_T_K=delta_T, material=params.material,
                cte_1e6_per_K=mat["alpha_1e6"],
                constrained_length_mm=max(W, D) * 1000.0,
                thermal_stress_MPa=round(sigma_th, 2),
                ms_thermal=round(ms_th, 3),
            )

            result.success = True
            log.info("Mock 구조 해석 완료: f1=%.1f Hz, σ_max=%.1f MPa, MS_y=%.2f",
                     f1_z, sigma_vm, result.min_ms_yield)

        except Exception as exc:
            result.error = f"Mock 해석 오류: {exc}"
            log.exception("Mock structural analysis error")

        return result
