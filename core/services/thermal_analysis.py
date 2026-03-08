"""
Thermal Analysis Service
간소 노드법 열해석 (Lumped-Parameter Thermal Network)
GMAT 궤도 결과 → 열유속 → 온도 분포
"""
import math
import numpy as np
from typing import List, Dict, Optional

from core.domain.orbit import OrbitResult
from core.domain.thermal import ThermalNode, ThermalResult

SIGMA = 5.670374419e-8   # Stefan-Boltzmann [W/m²K⁴]
SOLAR_CONST = 1361.0     # W/m²
EARTH_IR = 237.0         # W/m²  (지구 적외선 평균)
ALBEDO = 0.30            # 지구 알베도 계수


class ThermalAnalysisService:
    """
    간소 열해석 서비스
    6-노드 Lumped-Parameter 모델
    RK4 시간 적분
    """

    def analyze(self, orbit: OrbitResult, satellite_config: dict) -> ThermalResult:
        """
        satellite_config keys:
          panel_area_m2: 태양전지판 면적
          radiator_area_m2: 라디에이터 면적
          bus_area_m2: 버스 면적
          total_power_w: 총 소비전력
          mass_bus_kg: 버스 구조 질량
          mass_panel_kg: 패널 질량
          shielding_mm: 차폐 두께
        """
        result = ThermalResult()

        # 노드 생성
        nodes = self._build_nodes(satellite_config)

        # Hot / Cold Case 각각 해석
        hot = self._run_case(nodes, orbit, satellite_config, is_hot=True)
        cold = self._run_case(nodes, orbit, satellite_config, is_hot=False)

        # 결과 통합
        result.node_temps_max = hot['max']
        result.node_temps_min = cold['min']
        result.node_temps_avg = hot['avg']
        result.temp_histories = hot['histories']
        result.time_s = hot['times']

        result.q_solar_w = hot['q_solar']
        result.q_albedo_w = hot['q_albedo']
        result.q_ir_w = hot['q_ir']
        result.q_internal_w = hot['q_internal']
        result.q_radiated_w = hot['q_radiated']
        result.is_hot_case = True

        # 마진 계산 (전자장비 허용: -20°C ~ +70°C)
        max_temp = max(hot['max'].values(), default=0)
        min_temp = min(cold['min'].values(), default=0)
        result.margin_hot_c = 70.0 - max_temp
        result.margin_cold_c = min_temp - (-20.0)

        # 방열판 크기 요구량
        p_total = satellite_config.get('total_power_w', 500)
        # 정상상태 Q_rad = ε·σ·T⁴·A → A = Q/(ε·σ·T⁴)
        T_oper = 50 + 273.15   # 50°C 운용 가정
        epsilon = 0.85
        result.radiator_area_required_m2 = p_total / (epsilon * SIGMA * T_oper**4)
        result.heater_power_required_w = max(0.0, -result.margin_cold_c * 2)

        return result

    def _build_nodes(self, cfg: dict) -> List[ThermalNode]:
        """위성 구성에 따른 열 노드 생성"""
        p_total = cfg.get('total_power_w', 500)
        panel_half = cfg.get('panel_area_m2', 4.0) / 2.0
        rad_area   = cfg.get('radiator_area_m2', 1.2)
        return [
            ThermalNode(1, "Bus Structure",  cfg.get('mass_bus_kg', 20),
                        900,  cfg.get('bus_area_m2', 1.5), 0.85, 0.30, p_total*0.05),
            ThermalNode(2, "Solar Panel+Y",  cfg.get('mass_panel_kg', 6),
                        900,  panel_half, 0.85, 0.10, 0),   # 태양전지: 반사율 높음
            ThermalNode(3, "Solar Panel-Y",  cfg.get('mass_panel_kg', 6),
                        900,  panel_half, 0.85, 0.10, 0),
            ThermalNode(4, "Radiator",       5.0,
                        900,  rad_area,   0.92, 0.05, 0),   # 방열판: 방사율 높음
            ThermalNode(5, "Electronics",    cfg.get('mass_electronics_kg', 15),
                        850,  0.4,        0.85, 0.80, p_total*0.90),
            ThermalNode(6, "Battery",        cfg.get('mass_battery_kg', 8),
                        1000, 0.2,        0.88, 0.80, p_total*0.05),
        ]

    def _run_case(self, nodes: List[ThermalNode], orbit: OrbitResult,
                  cfg: dict, is_hot: bool) -> dict:
        """RK4 시간 적분으로 궤도 주기 반복 열해석"""
        # 일조율로 eclipse factor 시간표 근사
        sf = orbit.sunlight_fraction if is_hot else (1 - orbit.eclipse_fraction * 1.1)
        sf = max(0.0, min(1.0, sf))
        period_s = orbit.period_min * 60

        T = np.array([n.initial_temp_c + 273.15 for n in nodes])
        dt = 10.0  # 10초 스텝
        n_steps = int(min(period_s * 3, 30000) / dt)

        histories = {n.name: [] for n in nodes}
        times = []

        # 열전도 행렬 (간소화: 인접 노드 간 전도)
        GL = self._build_conduction_matrix(nodes)

        for step in range(n_steps):
            t = step * dt
            # 궤도 위상 (0~1) → 일식 여부
            phase = (t % period_s) / period_s
            eclipse = phase > sf   # 일조 구간 이후 = 일식

            q_in = self._calc_heat_inputs(nodes, orbit, is_hot, eclipse)
            dT = self._dT_dt(T, nodes, GL, q_in)
            T = T + dT * dt  # 오일러 (충분히 작은 dt)

            if step % 6 == 0:  # 1분마다 저장
                times.append(t)
                for i, n in enumerate(nodes):
                    histories[n.name].append(T[i] - 273.15)

        temps_c = {n.name: T[i] - 273.15 for i, n in enumerate(nodes)}
        max_t = {k: max(v) for k, v in histories.items() if v}
        min_t = {k: min(v) for k, v in histories.items() if v}
        avg_t = {k: sum(v)/len(v) for k, v in histories.items() if v}

        # 열플럭스 (마지막 스텝 기준)
        q_in_final = self._calc_heat_inputs(nodes, orbit, is_hot, False)
        q_solar = sum(q_in_final[i] for i in [1, 2])
        q_int = sum(n.internal_heat_w for n in nodes)
        q_rad = sum(n.emissivity * SIGMA * T[i]**4 * n.area_m2 for i, n in enumerate(nodes))

        return {
            'max': max_t, 'min': min_t, 'avg': avg_t,
            'histories': histories, 'times': times,
            'q_solar': q_solar, 'q_albedo': q_solar*0.3,
            'q_ir': EARTH_IR * 0.5, 'q_internal': q_int, 'q_radiated': q_rad
        }

    def _calc_heat_inputs(self, nodes, orbit, is_hot, eclipse) -> List[float]:
        """각 노드에 입력되는 열량 [W]"""
        q = []
        for n in nodes:
            q_node = n.internal_heat_w
            if not eclipse:
                if 'Panel' in n.name:
                    # 패널: 태양전지 흡수율 낮음 (대부분 전기 변환 or 반사)
                    q_node += SOLAR_CONST * n.absorptivity * n.area_m2 * 0.5
                elif 'Radiator' in n.name:
                    # 라디에이터: 태양 회피 면 → 적은 입열
                    q_node += SOLAR_CONST * n.absorptivity * n.area_m2 * 0.05
                elif 'Bus' in n.name:
                    q_node += SOLAR_CONST * n.absorptivity * n.area_m2 * 0.20
                else:
                    q_node += SOLAR_CONST * n.absorptivity * n.area_m2 * 0.05
                # 알베도 (모든 노드, 소량)
                q_node += SOLAR_CONST * ALBEDO * n.absorptivity * n.area_m2 * 0.05
            # 지구 IR (항상, 지구방향 면만 해당 → 계수로 조정)
            q_node += EARTH_IR * n.emissivity * n.area_m2 * 0.08
            q.append(q_node)
        return q

    def _build_conduction_matrix(self, nodes) -> np.ndarray:
        """노드 간 전도 계수 행렬 [W/K]"""
        n = len(nodes)
        GL = np.zeros((n, n))
        # 간단한 연결 (버스-패널, 버스-전자장비, 전자장비-라디에이터)
        # 전자장비→라디에이터 전도 대폭 증가 (cold plate)
        pairs = [(0,1,3.0),(0,2,3.0),(0,4,8.0),(0,5,5.0),(4,3,30.0),(5,3,8.0)]
        for i, j, g in pairs:
            GL[i][j] = g
            GL[j][i] = g
        return GL

    def _dT_dt(self, T, nodes, GL, q_in) -> np.ndarray:
        """온도 시간 미분 dT/dt [K/s]"""
        n = len(nodes)
        dT = np.zeros(n)
        for i, node in enumerate(nodes):
            C = node.mass_kg * node.cp_jkg   # 열용량
            q_cond = sum(GL[i][j] * (T[j] - T[i]) for j in range(n))
            q_rad_out = node.emissivity * SIGMA * T[i]**4 * node.area_m2
            dT[i] = (q_in[i] + q_cond - q_rad_out) / max(C, 1.0)
        return dT
