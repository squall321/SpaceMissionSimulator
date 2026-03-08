"""
SpaceD-AADE Main Window
PySide6 메인 윈도우 + CesiumJS Globe (QWebEngineView) + 실시간 대시보드
"""
import sys, os, json, math
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QLabel, QStatusBar, QProgressBar, QSizePolicy, QStackedWidget,
    QPushButton
)
from PySide6.QtCore    import Qt, QThread, Signal, QUrl, QObject, Slot
from PySide6.QtGui     import QFont, QIcon, QColor
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore    import QWebEngineSettings, QWebEnginePage
from PySide6.QtWebChannel       import QWebChannel

# 내부 모듈
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.domain.orbit   import OrbitParams
from core.domain.thermal import BudgetResult, RadiationResult, DesignScoreCard
from core.services.mission_analysis  import MissionAnalysisService
from core.services.thermal_analysis  import ThermalAnalysisService
from core.services.budget_radiation  import BudgetService, RadiationService, DesignEvaluator

from gui.widgets.sidebar      import Sidebar
from gui.widgets.orbit_config import OrbitConfigPanel
from gui.widgets.satellite_config import SatelliteConfigPanel
from gui.widgets.satellite_scenario_panel import SatelliteScenarioPanel
from gui.widgets.dashboard    import DashboardPanel
from gui.widgets.timeline     import TimelineWidget
from gui.widgets.thermal_viewer import ThermalViewer
from gui.widgets.radiation_viewer import RadiationViewer
from gui.widgets.budget_viewer  import BudgetViewer
from gui.widgets.parametric_study_panel import ParametricStudyPanel
from gui.controllers.analysis_worker import AnalysisWorker
from gui.widgets.comparison_dialog import ComparisonDialog
from gui.widgets.optimization_dialog import OrbitOptimizationDialog
from gui.widgets.mission_panel import MissionPanel
from gui.widgets.changelog_dialog import ChangelogDialog
from gui.widgets.log_panel import LogPanel
from gui.widgets.settings_dialog import SettingsDialog, load_settings
from gui.widgets.scorecard_viewer import ScorecardViewer   # v0.9.0
from gui.widgets.report_dialog import ReportDialog          # v0.9.0
import version as V

BASE_DIR = Path(__file__).parent


class CesiumBridge(QObject):
    """Python ↔ CesiumJS 양방향 통신 브리지"""
    orbitDataChanged       = Signal(str)
    groundStationsChanged  = Signal(str)
    satSelected            = Signal(str)   # 3D 뷰어 위성 클릭 → Python

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ready = False
        self._last_orbit = None
        self._last_stations = None

    @Slot()
    def ready(self):
        self._ready = True
        if self._last_stations:
            self.groundStationsChanged.emit(self._last_stations)
        if self._last_orbit:
            self.orbitDataChanged.emit(self._last_orbit)

    @Slot(str)
    def notify_sat_selected(self, sat_id: str):
        """JS selectSat 실행 시 호출됨 → 시나리오 패널 카드 동기화"""
        self.satSelected.emit(sat_id)

    def push_orbit(self, orbit_dict: dict):
        self._last_orbit = json.dumps(orbit_dict)
        if self._ready:
            self.orbitDataChanged.emit(self._last_orbit)

    def push_stations(self, stations: list):
        self._last_stations = json.dumps(stations)
        if self._ready:
            self.groundStationsChanged.emit(self._last_stations)


class CustomWebPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        print(f"JS: {message} (line {lineNumber} in {sourceID})")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"SpaceD-AADE Platform  ·  {V.VERSION_FULL}")
        self.resize(1600, 960)
        self.setMinimumSize(1200, 700)

        # 서비스 인스턴스
        self.mission_svc = MissionAnalysisService()
        self.thermal_svc = ThermalAnalysisService()
        self.budget_svc  = BudgetService()
        self.rad_svc     = RadiationService()
        self.evaluator   = DesignEvaluator()

        # 스타일
        self._apply_stylesheet()
        self._build_ui()
        self._connect_signals()

        # 마지막 세션 복원 → 없으면 기본 파라미터로 첫 분석 실행
        if not self.scenario_panel.load_session():
            self.run_analysis(OrbitParams())

    # ── UI 구성 ────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 1. 사이드바
        self.sidebar = Sidebar()
        root.addWidget(self.sidebar)

        # 2. 중앙 영역 (Globe + 타임라인)
        center_widget = QWidget()
        center_widget.setObjectName("centerArea")
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        # CesiumJS Globe
        self.globe_view = self._build_globe()
        center_layout.addWidget(self.globe_view, stretch=8)

        # 궤도 타임라인
        self.timeline = TimelineWidget()
        center_layout.addWidget(self.timeline, stretch=1)

        # 분석 로그 패널
        cfg = load_settings()
        self.log_panel = LogPanel(max_lines=cfg["ui"]["log_max_lines"])
        if not cfg["ui"]["show_log_panel"]:
            self.log_panel.toggle()   # 접힌 상태로 시작
        center_layout.addWidget(self.log_panel)

        # 3. 우측 패널 (QStackedWidget)
        self.right_stack = QStackedWidget()
        self.right_stack.setObjectName("rightPanel")
        self.right_stack.setFixedWidth(310)

        # -- 페이지 1: 궤도/대시보드 --
        page_orbit = QWidget()
        layout_orbit = QVBoxLayout(page_orbit)
        layout_orbit.setContentsMargins(0, 0, 0, 0)
        layout_orbit.setSpacing(0)
        self.orbit_config = OrbitConfigPanel()
        layout_orbit.addWidget(self.orbit_config)
        self.dashboard = DashboardPanel()
        layout_orbit.addWidget(self.dashboard, stretch=1)
        self.right_stack.addWidget(page_orbit)

        # -- 페이지 2: 위성 시나리오 매니저 --
        self.scenario_panel = SatelliteScenarioPanel()
        self.right_stack.addWidget(self.scenario_panel)

        # -- 페이지 3: 열 해석 차트 --
        self.thermal_viewer = ThermalViewer()
        self.right_stack.addWidget(self.thermal_viewer)

        # -- 페이지 4: 방사선 해석 차트 --
        self.rad_viewer = RadiationViewer()
        self.right_stack.addWidget(self.rad_viewer)

        # -- 페이지 0 (index 0): 미션 정의 패널 --
        self.mission_panel = MissionPanel()
        self.right_stack.insertWidget(0, self.mission_panel)

        # -- 페이지 5: 예산 (질량/전력) 뷰어 --
        self.budget_viewer = BudgetViewer()
        self.right_stack.addWidget(self.budget_viewer)

        # -- 페이지 6: 파라메트릭 스터디 (고도×경사각 히트맵) --
        self.parametric_panel = ParametricStudyPanel()
        self.right_stack.addWidget(self.parametric_panel)

        # -- 페이지 7: 종합 설계 ScoreCard (v0.9.0) --
        self.scorecard_viewer = ScorecardViewer()
        self.right_stack.addWidget(self.scorecard_viewer)

        # 메인 스플리터
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(center_widget)
        splitter.addWidget(self.right_stack)
        splitter.setSizes([1290, 310])
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background: #1e2a3a; }")
        root.addWidget(splitter)

        # 초기 패널: Orbit (mission_panel이 index 0에 삽입됐으므로 orbit=1)
        self.right_stack.setCurrentIndex(1)

        # 상태 바
        self.status_bar = QStatusBar()
        self.status_bar.setObjectName("statusBar")
        self.setStatusBar(self.status_bar)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(200)
        self.progress.setFixedHeight(14)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress)
        self.status_label = QLabel("  Ready")
        self.status_bar.addWidget(self.status_label)

        # 버전 배지 (우측 하단)
        self.ver_btn = QPushButton(V.VERSION_FULL)
        self.ver_btn.setFixedHeight(18)
        self.ver_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ver_btn.setStyleSheet("""
        QPushButton{
            color:#2a8aaa;background:transparent;border:none;
            font-size:10px;font-weight:700;padding:0 8px;
        }
        QPushButton:hover{color:#00dcff;text-decoration:underline;}
        """)
        self.ver_btn.clicked.connect(self._show_changelog)
        self.status_bar.addPermanentWidget(self.ver_btn)

    def _build_globe(self) -> QWebEngineView:
        """CesiumJS 웹뷰 생성"""
        view = QWebEngineView()
        
        # JS 에러 검출용 커스텀 페이지 적용
        page = CustomWebPage(view)
        view.setPage(page)

        # WebChannel 설정
        self.bridge = CesiumBridge(self)
        self.channel = QWebChannel(page)
        self.channel.registerObject("bridge", self.bridge)
        page.setWebChannel(self.channel)

        # WebEngine 설정
        settings = page.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)

        # HTML 로드
        html_path = BASE_DIR / "cesium_app" / "index.html"
        view.load(QUrl.fromLocalFile(str(html_path)))
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return view

    def _connect_signals(self):
        self.orbit_config.params_changed.connect(self.trigger_analysis)
        # v0.5.0: 시나리오 변경 시 3D 뷰어 실시간 업데이트
        self.scenario_panel.scenarios_changed.connect(self._on_scenarios_changed)
        # v0.5.2: 3D 뷰어 위성 클릭 → 좌측 카드 동기화
        self.bridge.satSelected.connect(self.scenario_panel.select_by_id)
        # v0.5.2: 시나리오 패널 비교 버튼
        self.scenario_panel.compare_requested.connect(self.show_comparison_dialog)
        self.sidebar.nav_changed.connect(self.on_nav_changed)
        self.sidebar.optimize_clicked.connect(self.show_optimization_dialog)
        self.sidebar.settings_clicked.connect(self.show_settings_dialog)     # v0.6.0
        self.dashboard.satellite_selected.connect(self.on_satellite_selected)
        self.dashboard.compare_requested.connect(self.show_comparison_dialog)
        # Mission Panel 시그널
        self.mission_panel.orbit_recommended.connect(self._apply_recommended_orbit)
        # Parametric Study 시그널
        self.parametric_panel.orbit_selected.connect(self._on_parametric_orbit)
        # v0.9.0: ScoreCard 리포트 익스포트
        self.scorecard_viewer.export_requested.connect(self._on_report_export)
        # v0.6.0: GMAT 상태 배지 초기화
        self._init_gmat_status()

    def _on_scenarios_changed(self, scenarios: list):
        """시나리오 변경 → Satellite 탭 활성화 중일 때 3D 뷰어 실시간 업데이트"""
        if self.right_stack.currentIndex() == 2:  # satellite tab
            page = self.globe_view.page()
            page.runJavaScript(
                f"window.updateSatViewer && window.updateSatViewer({json.dumps(scenarios)})"
            )

    def show_comparison_dialog(self):
        if not hasattr(self, 'results_history') or not self.results_history:
            return
        names = [s["name"] for s in self.scenario_panel._scenarios]
        dlg = ComparisonDialog(self.results_history, self, scenario_names=names)
        dlg.exec()

    def show_optimization_dialog(self):
        """궤도 최적화 대화상자 표시"""
        sat_config = self.scenario_panel.get_selected_config() or {}
        dlg = OrbitOptimizationDialog(self, sat_config=sat_config)
        dlg.result_selected.connect(self._apply_optimized_orbit)
        dlg.exec()
    
    def _apply_optimized_orbit(self, orbit_params: OrbitParams):
        """최적화 결과를 UI에 적용하고 분석 실행"""
        self.orbit_config.set_params(orbit_params)
        self.run_analysis(orbit_params)

    def _on_parametric_orbit(self, orbit_params: OrbitParams):
        """파라메트릭 스터디 선택 궤도 → Orbit Config 적용 후 분석"""
        self.orbit_config.set_params(orbit_params)
        self.on_nav_changed("orbit")    # Orbit 패널로 이동
        self.run_analysis(orbit_params)

    def _apply_recommended_orbit(self, orbit_params: OrbitParams):
        """Mission Panel 추천 궤도 → 커버리지 지상국 추출 + 분석 실행"""
        self.orbit_config.set_params(orbit_params)
        # 커버리지 선택 지상국 추출
        cov_gs = self.mission_panel.get_coverage_ground_station()
        self._coverage_stations = [cov_gs] if cov_gs else []
        # 분석 완료 후 Mission 탭으로 복귀 플래그
        self._from_mission_recommend = True
        self.sidebar.select_section("orbit")
        self.run_analysis(orbit_params, extra_stations=self._coverage_stations)

    def _show_changelog(self):
        dlg = ChangelogDialog(self)
        dlg.exec()

    def _on_report_export(self, score):
        """v0.9.0 ScoreCard → ReportDialog 오픈"""
        if not hasattr(self, 'results_history') or not self.results_history:
            return
        last = self.results_history[-1]
        dlg = ReportDialog(
            score      = score,
            orbit      = last.get('orbit'),
            budget     = last.get('budget'),
            thermal    = last.get('thermal'),
            radiation  = last.get('radiation'),
            parent     = self,
        )
        dlg.exec()

    def show_settings_dialog(self):
        """v0.6.0 설정 다이얼로그"""
        dlg = SettingsDialog(self)
        dlg.settings_changed.connect(self._on_settings_changed)
        dlg.exec()

    def _on_settings_changed(self, cfg: dict):
        self.log_panel.set_max_lines(cfg["ui"]["log_max_lines"])
        show = cfg["ui"]["show_log_panel"]
        if show and not self.log_panel._expanded:
            self.log_panel.toggle()
        elif not show and self.log_panel._expanded:
            self.log_panel.toggle()
        self.log_panel.log("설정 저장 완료", "success")

    def _init_gmat_status(self):
        """앱 시작 시 GMAT 가용 여부 확인 → 로그 패널 배지 갱신"""
        try:
            from adapters.gmat.gmat_adapter import GmatAdapter
            adapter = GmatAdapter()
            console = adapter.is_console_available()
            avail   = adapter.is_available()
            self.log_panel.set_gmat_status(avail, console)
            if console:
                self.log_panel.log(f"GMAT 준비: GmatConsole.exe  ({adapter.gmat_console})", "gmat")
            elif avail:
                self.log_panel.log(f"GMAT 준비: GMAT.exe  ({adapter.gmat_exe})", "warn")
            else:
                self.log_panel.log("GMAT 없음 — 내장 해석 엔진으로 동작", "warn")
        except Exception as e:
            self.log_panel.log(f"GMAT 상태 확인 실패: {e}", "error")

    # ── 분석 실행 ──────────────────────────────────────────────
    def trigger_analysis(self):
        orbit_params = self.orbit_config.get_params()
        self.run_analysis(orbit_params)

    def run_analysis(self, orbit_params: OrbitParams, extra_stations: list = None):
        self.status_label.setText("  🔄  Analyzing orbit...")
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # 무한 진행

        self.log_panel.log(
            f"분석 시작 — h={orbit_params.altitude_km:.0f}km  "
            f"i={orbit_params.inclination_deg:.1f}°  "
            f"RAAN={orbit_params.raan_deg:.1f}°", "stage"
        )

        # 분석 스레드 생성
        self._worker = AnalysisWorker(
            params=orbit_params,
            mission_svc=self.mission_svc,
            thermal_svc=self.thermal_svc,
            budget_svc=self.budget_svc,
            rad_svc=self.rad_svc,
            evaluator=self.evaluator,
            sat_config=self.scenario_panel.get_selected_config() or {},
            extra_stations=extra_stations or []
        )
        self._worker.finished.connect(self.on_analysis_done)
        self._worker.progress_msg.connect(lambda m: self.status_label.setText(f"  {m}"))
        self._worker.log_msg.connect(self.log_panel.log)       # v0.6.0
        self._worker.start()

    def on_analysis_done(self, results: dict):
        self.progress.setVisible(False)
        self.status_label.setText("  ✅  Analysis complete")

        orbit   = results['orbit']
        budget  = results['budget']
        rad     = results['radiation']
        thermal = results['thermal']
        score   = results['score']

        if not hasattr(self, 'results_history'):
            self.results_history = []
        self.results_history.append(results)

        sat_id_str = f"SAT-{len(self.results_history)}"
        self.dashboard.add_satellite(sat_id_str)

        # v0.5.0: 시나리오 패널에 추가
        orbit_summary = f"{orbit.params.altitude_km:.0f}km / {orbit.params.inclination_deg:.1f}°"
        current_cfg   = self.scenario_panel.get_selected_config() or {}
        self.scenario_panel.add_scenario(sat_id_str, sat_id_str, orbit_summary, current_cfg)

        # 대시보드 갱신
        self.dashboard.update_all(orbit, budget, rad, thermal, score)

        # Mission Panel 요구사항 충족도 갱신 (카메라 구경 기반 해상도 계산)
        aperture_cm = (self.scenario_panel.get_selected_config() or {}).get('aperture_cm', 15.0)
        self.mission_panel.update_status(orbit, budget, aperture_cm=aperture_cm)

        # RECOMMEND 후 Mission 탭으로 자동 복귀
        if getattr(self, '_from_mission_recommend', False):
            self._from_mission_recommend = False
            self.sidebar.select_section("mission")

        # 타임라인 갱신
        self.timeline.update_timeline(orbit)

        # 차트 갱신
        self.thermal_viewer.update_data(thermal)
        self.rad_viewer.update_data(rad)
        self.budget_viewer.update_data(budget)
        self.scorecard_viewer.update_data(score)   # v0.9.0

        # CesiumJS 궤도 데이터 전송
        orbit_dict = self._orbit_to_dict(orbit, budget)
        self.bridge.push_orbit(orbit_dict)

        # 지상국 전송 (커버리지 선택 지상국 포함)
        extra_gs = getattr(self, '_coverage_stations', [])
        all_gs = list(MissionAnalysisService.DEFAULT_STATIONS) + extra_gs
        stations = [
            {"name": gs.name, "lat": gs.latitude_deg, "lon": gs.longitude_deg, "alt": gs.altitude_m}
            for gs in all_gs
        ]
        self.bridge.push_stations(stations)

    def on_satellite_selected(self, idx: int):
        if not hasattr(self, 'results_history') or idx < 0 or idx >= len(self.results_history):
            return
        results = self.results_history[idx]
        orbit   = results['orbit']
        budget  = results['budget']
        rad     = results['radiation']
        thermal = results['thermal']
        score   = results['score']

        self.dashboard.update_all(orbit, budget, rad, thermal, score)
        self.timeline.update_timeline(orbit)
        self.thermal_viewer.update_data(thermal)
        self.rad_viewer.update_data(rad)
        self.budget_viewer.update_data(budget)

    def _orbit_to_dict(self, orbit, budget) -> dict:
        """OrbitResult → CesiumJS CZML용 dict"""
        # 일식/접속 플래그 배열 생성
        # ephemeris_times, ev.start_time, cw.start_time 모두 미션 시작 이후 초(float)
        eclipse_set = set()
        for ev in orbit.eclipse_events:
            for t in orbit.ephemeris_times:
                if ev.start_time <= t <= ev.end_time:
                    eclipse_set.add(t)

        contact_set = set()
        for cw in orbit.contact_windows:
            for t in orbit.ephemeris_times:
                if cw.start_time <= t <= cw.end_time:
                    contact_set.add(t)

        # Space Data Center 추가 매트릭 (통신 지연시간, 데이터 다운링크량)
        SPEED_OF_LIGHT = 299792.458  # km/s
        EARTH_RADIUS = 6371.0 # km
        alt = orbit.altitude_min_km if orbit.altitude_min_km > 0 else orbit.params.altitude_km
        lat_min_ms = (alt / SPEED_OF_LIGHT) * 1000.0 if alt > 0 else 0
        r = EARTH_RADIUS + alt
        dist_max = math.sqrt(r**2 - EARTH_RADIUS**2) if r > EARTH_RADIUS else 0
        lat_max_ms = (dist_max / SPEED_OF_LIGHT) * 1000.0 if dist_max > 0 else 0
        
        dt_gb = budget.data_per_day_gb if budget else 0.0

        return {
            "epoch": orbit.params.epoch if orbit.params.epoch.endswith('Z')
                     else orbit.params.epoch + 'Z',
            "times": orbit.ephemeris_times,
            "x": orbit.ephemeris_x,
            "y": orbit.ephemeris_y,
            "z": orbit.ephemeris_z,
            "eclipse_flags": [t in eclipse_set for t in orbit.ephemeris_times],
            "contact_flags":  [t in contact_set  for t in orbit.ephemeris_times],
            "period_min": orbit.period_min,
            "beta_angle": orbit.beta_angle_deg,
            "sunlight_fraction": orbit.sunlight_fraction,
            "eclipse_fraction": orbit.eclipse_fraction,
            "velocity": orbit.velocity_kms,
            "contacts_per_day": orbit.contacts_per_day,
            "delta_v": orbit.delta_v_per_year_ms,
            "inclination": orbit.params.inclination_deg,
            "raan": orbit.params.raan_deg,
            "orbit_type": orbit.params.orbit_type,
            "eccentricity": orbit.params.eccentricity,
            "arg_perigee": orbit.params.arg_perigee_deg,
            "altitude_min": orbit.altitude_min_km,
            "altitude_max": orbit.altitude_max_km,
            "duration_days": orbit.params.duration_days,
            "contact_time_min": orbit.contact_time_per_day_min,
            "rad_proton": orbit.radiation_flux_proton,
            "rad_electron": orbit.radiation_flux_electron,
            "latency_min_ms": lat_min_ms,
            "latency_max_ms": lat_max_ms,
            "data_per_day_gb": dt_gb
        }

    def on_nav_changed(self, section: str):
        # Mission Panel이 index 0에 삽입되었으므로 모든 인덱스 +1
        mapping = {
            "mission":   0,
            "orbit":     1,
            "satellite": 2,
            "thermal":   3,
            "radiation": 4,
            "budget":    5,
            "study":     6,
            "score":     7,
        }
        if section in mapping:
            self.right_stack.setCurrentIndex(mapping[section])

        # v0.5.0: Satellite 3D Viewer show/hide (다중 시나리오)
        page = self.globe_view.page()
        if section == "satellite":
            scenarios = json.dumps(self.scenario_panel.get_all_scenarios())
            page.runJavaScript(f"window.showSatViewer && window.showSatViewer({scenarios})")
        else:
            page.runJavaScript("window.hideSatViewer && window.hideSatViewer()")

    # ── 스타일 ─────────────────────────────────────────────────
    def _apply_stylesheet(self):
        self.setStyleSheet("""
        QMainWindow, QWidget { background: #0a0f1e; color: #c8d8e4; }
        #centerArea   { background: #000; }
        #rightPanel   { background: #0d1525; border-left: 1px solid #1e2a3a; }
        #statusBar    { background: #060c18; color: #5a7a8a; font-size: 11px;
                        border-top: 1px solid #1e2a3a; }
        QProgressBar  { background: #1a2535; border: none; border-radius: 3px; }
        QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                              stop:0 #0088cc, stop:1 #00dcff); border-radius: 3px; }
        QSplitter     { background: #0a0f1e; }
        """)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SpaceD-AADE")
    app.setOrganizationName("SpaceDataCenter")

    # 고해상도 지원
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    # 기본 폰트
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
