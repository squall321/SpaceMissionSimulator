"""
IPSAP Input Generator
위성 구조 파라미터 → DIAMOND/IPSAP FEM 입력 파일 자동 생성

IPSAP은 NASTRAN 호환 Bulk Data 형식을 지원합니다.
이 모듈은 간소화된 Equivalent Shell 모델을 자동 생성합니다.
"""
import math
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import logging

from core.domain.structural import StructuralParams, LoadCase, MATERIALS

log = logging.getLogger(__name__)


# ── NASTRAN/IPSAP 카드 포매터 ──────────────────────────────────

def _fmt_f8(v: float) -> str:
    """8-char NASTRAN free-field float formatting"""
    s = f"{v:.6g}"
    return s[:8].ljust(8)


def _nastran_grid(nid: int, x: float, y: float, z: float) -> str:
    return f"GRID    {nid:<8d}{0:<8d}{x:<8.4f}{y:<8.4f}{z:<8.4f}\n"


def _nastran_cquad4(eid: int, pid: int, g1: int, g2: int, g3: int, g4: int) -> str:
    return f"CQUAD4  {eid:<8d}{pid:<8d}{g1:<8d}{g2:<8d}{g3:<8d}{g4:<8d}\n"


def _nastran_pshell(pid: int, mid: int, t: float) -> str:
    return f"PSHELL  {pid:<8d}{mid:<8d}{_fmt_f8(t)}{mid:<8d}\n"


def _nastran_mat1(mid: int, E_Pa: float, nu: float, rho: float, alpha: float) -> str:
    E_s = f"{E_Pa:.6e}"[:8].ljust(8)
    G_s = "".ljust(8)
    nu_s = f"{nu:.4f}"[:8].ljust(8)
    rho_s = f"{rho:.4f}"[:8].ljust(8)
    al_s = f"{alpha:.3e}"[:8].ljust(8)
    return f"MAT1    {mid:<8d}{E_s}{G_s}{nu_s}{rho_s}{al_s}\n"


def _nastran_load(sid: int, gid: int, dir_n: int, value: float) -> str:
    """방향별 집중하중 (CID=0, 기본좌표계)"""
    return f"FORCE   {sid:<8d}{gid:<8d}{0:<8d}{_fmt_f8(value)}{_nastran_dir_vec(dir_n)}\n"


def _nastran_dir_vec(dir_n: int) -> str:
    dirs = {1: "1.0     0.0     0.0     ", 2: "0.0     1.0     0.0     ",
            3: "0.0     0.0     1.0     "}
    return dirs.get(dir_n, "0.0     0.0     1.0     ")


def _nastran_spc1(sid: int, dof: str, nodes: List[int]) -> str:
    node_str = " ".join(str(n) for n in nodes[:4])
    return f"SPC1    {sid:<8d}{dof:<8s}{node_str}\n"


def _nastran_eigrl(sid: int, nd: int) -> str:
    return f"EIGRL   {sid:<8d}{''.ljust(8)}{''.ljust(8)}{nd:<8d}\n"


# ── 위성 Equivalent Box 모델 생성기 ──────────────────────────────

class IpsapInputGenerator:
    """
    StructuralParams → IPSAP Bulk Data (.bdf) 자동 생성

    모델 설명:
    - 6면체 Equivalent Shell Model (박스 위성)
    - 각 면: CQUAD4 요소 격자 (n×n)
    - 내부 질량 = 탑재체/전자 질량 집중 CONM2 절점
    - 발사 하중: NASTRAN SUBCASE (축방향/측방향)
    - 경계조건: 하단 4모서리 절점 고정 (SPC)
    """

    GRID_N = 4   # 면당 격자 분할 수 (n×n → 16 QUAD4 per face)

    def __init__(self, params: StructuralParams):
        self.p = params
        self.mat = MATERIALS.get(params.material, MATERIALS["Al6061-T6"])
        self._nodes: dict = {}   # id -> (x, y, z)
        self._next_nid = 1
        self._elems: List[tuple] = []  # (eid, pid, g1,g2,g3,g4)
        self._next_eid = 1

    # ── 공개 API ────────────────────────────────────────────────

    def generate(self, output_path: Path) -> Path:
        """
        bdf 파일을 생성하고 경로를 반환합니다.
        output_path 가 폴더이면 satellite_structure.bdf 로 저장합니다.
        """
        output_path = Path(output_path)
        if output_path.is_dir():
            bdf_path = output_path / "satellite_structure.bdf"
        else:
            bdf_path = output_path
        bdf_path.parent.mkdir(parents=True, exist_ok=True)

        self._build_mesh()
        content = self._build_bulk_data()
        bdf_path.write_text(content, encoding="utf-8")
        log.info("IPSAP input written: %s  (nodes=%d, elems=%d)",
                 bdf_path, len(self._nodes), len(self._elems))
        return bdf_path

    def generate_load_cases(self) -> List[LoadCase]:
        """표준 발사 하중 케이스 목록 반환"""
        p = self.p
        g = 9.80665
        return [
            LoadCase("LC1-Axial",   "축방향 준정적",  axial_g=p.ql_axial_g,   lateral_g=0.0),
            LoadCase("LC2-Lateral", "측방향 준정적",  axial_g=0.0,             lateral_g=p.ql_lateral_g),
            LoadCase("LC3-Combined","축+측 동시",      axial_g=p.ql_axial_g,   lateral_g=p.ql_lateral_g),
        ]

    # ── 내부 메시 생성 ──────────────────────────────────────────

    def _next_node(self, x: float, y: float, z: float) -> int:
        nid = self._next_nid
        self._nodes[nid] = (x, y, z)
        self._next_nid += 1
        return nid

    def _next_elem(self, pid: int, g1: int, g2: int, g3: int, g4: int):
        eid = self._next_eid
        self._elems.append((eid, pid, g1, g2, g3, g4))
        self._next_eid += 1
        return eid

    def _build_mesh(self):
        """위성 박스 6면에 CQUAD4 격자 생성"""
        W, D, H = self.p.width_m, self.p.depth_m, self.p.height_m
        n = self.GRID_N

        # 면별 격자 생성 헬퍼
        def face_grid(ax0, ax1, ax2, val):
            """ax0=행축, ax1=열축, ax2=법선축(고정값=val)"""
            ranges = [(0, W, n), (0, D, n), (0, H, n)]
            ids = []
            row = []
            r0, r1 = ranges[ax0], ranges[ax1]
            for i in range(n + 1):
                r = []
                for j in range(n + 1):
                    coords = [0.0, 0.0, 0.0]
                    coords[ax0] = r0[0] + i * (r0[1] - r0[0]) / n
                    coords[ax1] = r1[0] + j * (r1[1] - r1[0]) / n
                    coords[ax2] = val
                    r.append(self._next_node(*coords))
                row.append(r)
            for i in range(n):
                for j in range(n):
                    self._next_elem(1, row[i][j], row[i][j+1],
                                    row[i+1][j+1], row[i+1][j])

        # +X, -X, +Y, -Y, +Z, -Z
        face_grid(1, 2, 0, W)    # +X 면
        face_grid(1, 2, 0, 0.0)  # -X 면
        face_grid(0, 2, 1, D)    # +Y 면
        face_grid(0, 2, 1, 0.0)  # -Y 면
        face_grid(0, 1, 2, H)    # +Z 면 (상단)
        face_grid(0, 1, 2, 0.0)  # -Z 면 (하단, SPC 예정)

    def _bottom_nodes(self) -> List[int]:
        """하단면(Z=0) 4모서리 절점 ID 수집 (경계조건용)"""
        W, D = self.p.width_m, self.p.depth_m
        corners = {(0.0,0.0,0.0),(W,0.0,0.0),(0.0,D,0.0),(W,D,0.0)}
        ids = []
        for nid, (x,y,z) in self._nodes.items():
            if abs(z) < 1e-6 and (round(x,4), round(y,4), round(z,4)) in {
                    (round(c[0],4), round(c[1],4), round(c[2],4)) for c in corners}:
                ids.append(nid)
        return ids or [1, 2, 3, 4]   # fallback

    def _conm2_lines(self) -> str:
        """내부 질량 집중 (탑재체+전장품+배터리) — CONM2 카드"""
        cx, cy, cz = self.p.width_m/2, self.p.depth_m/2, self.p.height_m/2
        total_internal = (self.p.payload_mass_kg
                          + self.p.electronics_mass_kg
                          + self.p.battery_mass_kg)
        # 내부 집중 질량 절점 생성
        cg_nid = self._next_node(cx, cy, cz)
        return f"CONM2   9999    {cg_nid:<8d}{0:<8d}{total_internal:.4f}\n"

    def _build_bulk_data(self) -> str:
        p = self.p
        mat = self.mat
        g = 9.80665
        t_m = p.panel_thickness_mm / 1000.0
        E_Pa = mat["E_GPa"] * 1e9
        rho = mat["rho_kg_m3"]
        nu = mat["nu"]
        alpha = mat["alpha_1e6"] * 1e-6

        F_axial   = p.total_mass_kg * p.ql_axial_g   * g
        F_lateral = p.total_mass_kg * p.ql_lateral_g * g

        spc_nodes = self._bottom_nodes()

        lines = []
        lines.append("$ IPSAP/NASTRAN Bulk Data — Auto-generated by SpaceD-AADE\n")
        lines.append(f"$ Material: {p.material}  |  Mass: {p.total_mass_kg:.1f} kg\n")
        lines.append("$\n")
        lines.append("SOL 103\n")           # Normal modes
        lines.append("CEND\n")
        lines.append("  TITLE = SpaceD Satellite Structure\n")
        lines.append("  ECHO = NONE\n")
        lines.append("  METHOD = 1\n")     # EIGRL SID=1
        lines.append("  SUBCASE 1\n")
        lines.append(f"    SUBTITLE = Axial QSL {p.ql_axial_g:.1f}g\n")
        lines.append("    LOAD = 10\n")
        lines.append("    SPC = 100\n")
        lines.append("    STRESS = ALL\n")
        lines.append("    DISPLACEMENT = ALL\n")
        lines.append("  SUBCASE 2\n")
        lines.append(f"    SUBTITLE = Lateral QSL {p.ql_lateral_g:.1f}g\n")
        lines.append("    LOAD = 20\n")
        lines.append("    SPC = 100\n")
        lines.append("    STRESS = ALL\n")
        lines.append("$\n")
        lines.append("BEGIN BULK\n")
        lines.append("$\n")
        lines.append("$ --- GRID NODES ---\n")
        for nid, (x, y, z) in self._nodes.items():
            lines.append(_nastran_grid(nid, x, y, z))
        lines.append("$\n")
        lines.append("$ --- ELEMENTS ---\n")
        for eid, pid, g1, g2, g3, g4 in self._elems:
            lines.append(_nastran_cquad4(eid, pid, g1, g2, g3, g4))
        lines.append("$\n")
        lines.append("$ --- PROPERTIES ---\n")
        lines.append(_nastran_pshell(1, 1, t_m))
        lines.append("$\n")
        lines.append("$ --- MATERIAL ---\n")
        lines.append(_nastran_mat1(1, E_Pa, nu, rho, alpha))
        lines.append("$\n")
        lines.append("$ --- CONCENTRATED MASS ---\n")
        lines.append(self._conm2_lines())
        lines.append("$\n")
        lines.append("$ --- BOUNDARY CONDITIONS (launch interface fixed) ---\n")
        for sn in spc_nodes:
            lines.append(_nastran_spc1(100, "123456", [sn]))
        lines.append("$\n")
        lines.append("$ --- LOADS ---\n")
        # 임의 적용점 = 상단 중앙 절점(CG 근처)
        apex_nid = spc_nodes[0] if spc_nodes else 1
        lines.append(f"$ Axial load SID=10  F={F_axial:.0f} N  (+Z=발사방향)\n")
        lines.append(_nastran_load(10, apex_nid, 3, F_axial))
        lines.append(f"$ Lateral load SID=20  F={F_lateral:.0f} N  (+X)\n")
        lines.append(_nastran_load(20, apex_nid, 1, F_lateral))
        lines.append("$\n")
        lines.append("$ --- EIGENVALUE METHOD ---\n")
        lines.append(_nastran_eigrl(1, 10))      # 10개 모드
        lines.append("$\n")
        lines.append("ENDDATA\n")

        return "".join(lines)
