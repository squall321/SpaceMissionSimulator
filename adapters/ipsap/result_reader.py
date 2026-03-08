"""
IPSAP Result Reader
DIAMOND/IPSAP (NASTRAN 호환) 해석 결과 파일(.f06) 파서

파싱 대상 섹션:
  - REAL EIGENVALUES (고유값 해석 → 고유진동수)
  - STRESS IN QUAD4 ELEMENTS (CQUAD4 폰 미세스 응력)
  - DISPLACEMENTS IN SCALAR POINTS (절점 변위)
"""
import re
import math
import logging
from pathlib import Path
from typing import List, Optional, Dict, Tuple

from core.domain.structural import ModeShape, NodeResult, StructuralResult

log = logging.getLogger(__name__)


# ── 정규표현식 패턴 ── ─────────────────────────────────────────

_RE_EIGEN_HEADER = re.compile(
    r"^\s*R\s*E\s*A\s*L\s+E\s*I\s*G\s*E\s*N\s*V\s*A\s*L\s*U\s*E\s*S", re.IGNORECASE
)
_RE_EIGEN_ROW = re.compile(
    r"^\s*(\d+)\s+(\d+)\s+([\d.E+\-]+)\s+([\d.E+\-]+)\s+([\d.E+\-]+)\s+([\d.E+\-]+)"
)
_RE_STRESS_HEADER = re.compile(
    r"S\s*T\s*R\s*E\s*S\s*S\s*E\s*S.+QUAD4", re.IGNORECASE
)
_RE_STRESS_ROW = re.compile(
    r"^\s*(\d+)\s+(\d+)\s+([\d.E+\-]+)\s+([\d.E+\-]+)\s+([\d.E+\-]+)"
    r"\s+([\d.E+\-]+)\s+([\d.E+\-]+)"
)
_RE_DISP_HEADER = re.compile(
    r"D\s*I\s*S\s*P\s*L\s*A\s*C\s*E\s*M\s*E\s*N\s*T\s*S", re.IGNORECASE
)
_RE_DISP_ROW = re.compile(
    r"^\s*(\d+)\s+0\s+([\d.E+\-]+)\s+([\d.E+\-]+)\s+([\d.E+\-]+)"
)


class IpsapResultReader:
    """
    IPSAP/NASTRAN .f06 결과 파일 파서.

    사용 예::

        reader = IpsapResultReader()
        result = reader.parse(Path("satellite_structure.f06"), params)
    """

    def parse(self, f06_path: Path,
              params=None) -> StructuralResult:
        """
        .f06 파일을 파싱하여 StructuralResult 를 반환합니다.
        파일이 없거나 파싱 실패 시 error 필드를 설정합니다.
        """
        result = StructuralResult(mock_mode=False)
        if not f06_path.exists():
            result.error = f"결과 파일 없음: {f06_path}"
            return result

        try:
            text = f06_path.read_text(encoding="utf-8", errors="replace")
            modes, stresses, displacements = self._parse_sections(text)

            result.modes = modes
            result.first_freq_hz = modes[0].freq_hz if modes else 0.0
            if params and result.first_freq_hz > 0:
                req = getattr(params, "freq_req_hz", 50.0)
                result.freq_margin_pct = (result.first_freq_hz - req) / req * 100.0

            result.node_results = stresses
            if stresses:
                result.max_von_mises_MPa = max(n.von_mises_MPa for n in stresses)
                result.max_displacement_mm = max(n.displacement_mm for n in stresses)

            if params:
                result.margins = self._compute_margins(stresses, params)
                if result.margins:
                    result.min_ms_yield    = min(m.ms_yield    for m in result.margins)
                    result.min_ms_ultimate = min(m.ms_ultimate for m in result.margins)

            result.success = True
            log.info("f06 parsed: %d modes, %d stress nodes", len(modes), len(stresses))

        except Exception as exc:
            result.error = f"f06 파싱 오류: {exc}"
            log.exception("f06 parse error")

        return result

    # ── 내부 파서 ─────────────────────────────────────────────

    def _parse_sections(self, text: str
                        ) -> Tuple[List[ModeShape], List[NodeResult], List[dict]]:
        lines = text.splitlines()
        modes: List[ModeShape] = []
        stresses: List[NodeResult] = []
        displacements: List[dict] = []

        i = 0
        n = len(lines)
        while i < n:
            line = lines[i]

            # ── 고유값 섹션 ───────────────────────────────
            if _RE_EIGEN_HEADER.search(line):
                i += 3  # 헤더 스킵
                while i < n:
                    m = _RE_EIGEN_ROW.match(lines[i])
                    if not m:
                        break
                    mode_n = int(m.group(1))
                    freq_hz = float(m.group(4))
                    mmf = float(m.group(6)) if m.lastindex >= 6 else 0.0
                    direction = _guess_direction(mode_n)
                    modes.append(ModeShape(
                        mode_number=mode_n, freq_hz=freq_hz,
                        modal_mass_fraction=mmf, direction=direction,
                        description=f"Mode {mode_n}"
                    ))
                    i += 1
                continue

            # ── 응력 섹션 ─────────────────────────────────
            if _RE_STRESS_HEADER.search(line):
                i += 4
                while i < n:
                    m = _RE_STRESS_ROW.match(lines[i])
                    if not m:
                        break
                    eid  = int(m.group(1))
                    sx   = float(m.group(3))
                    sy   = float(m.group(4))
                    txy  = float(m.group(5))
                    smax = float(m.group(6))
                    smin = float(m.group(7))
                    vm   = math.sqrt(sx**2 - sx*sy + sy**2 + 3*txy**2)
                    stresses.append(NodeResult(
                        node_id=eid, location=f"EL-{eid}",
                        von_mises_MPa=vm / 1e6,
                        sigma_x_MPa=sx / 1e6, sigma_y_MPa=sy / 1e6,
                    ))
                    i += 1
                continue

            # ── 변위 섹션 ─────────────────────────────────
            if _RE_DISP_HEADER.search(line):
                i += 3
                while i < n:
                    m = _RE_DISP_ROW.match(lines[i])
                    if not m:
                        break
                    nid = int(m.group(1))
                    d = math.sqrt(float(m.group(2))**2
                                  + float(m.group(3))**2
                                  + float(m.group(4))**2)
                    displacements.append(dict(nid=nid, disp_m=d))
                    i += 1
                continue

            i += 1

        # 변위를 스트레스 데이터에 병합
        disp_map = {d["nid"]: d["disp_m"] for d in displacements}
        for nr in stresses:
            nr.displacement_mm = disp_map.get(nr.node_id, 0.0) * 1000.0

        return modes, stresses, displacements

    def _compute_margins(self, stresses: List[NodeResult], params) -> list:
        from core.domain.structural import MarginOfSafety, MATERIALS
        mat_name = getattr(params, "material", "Al6061-T6")
        mat = MATERIALS.get(mat_name, MATERIALS["Al6061-T6"])
        sy  = mat["sigma_y_MPa"]
        su  = mat["sigma_u_MPa"]
        ysf = getattr(params, "yield_factor",    1.25)
        fos = getattr(params, "factor_of_safety", 2.0)

        margins = []
        for nr in stresses:
            if nr.von_mises_MPa <= 0:
                continue
            ms_y = sy  / (nr.von_mises_MPa * ysf) - 1.0
            ms_u = su  / (nr.von_mises_MPa * fos) - 1.0
            margins.append(MarginOfSafety(
                location=nr.location, load_case="combined",
                actual_stress_MPa=nr.von_mises_MPa,
                allowable_MPa=sy,
                ms_yield=ms_y, ms_ultimate=ms_u,
            ))
        return margins


def _guess_direction(mode_n: int) -> str:
    dirs = {1: "Z", 2: "X", 3: "Y", 4: "RZ", 5: "RX", 6: "RY"}
    return dirs.get(mode_n, "MIXED")
