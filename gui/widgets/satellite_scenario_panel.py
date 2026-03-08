"""
Satellite Scenario Panel  (v0.5.0)
──────────────────────────────────────────────────────────────
궤도 분석 실행 1회 = 시나리오 1개.
각 시나리오마다 독립적인 위성 설정(SatelliteConfigPanel)을 보유.
3D 뷰어에는 모든 시나리오의 위성이 나란히 표시됨.

레이아웃:
  [ 시나리오 목록 (좌) ]  |  [ 위성 설정 패널 (우) ]
"""
import json
from datetime   import datetime
from pathlib    import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QStackedWidget, QAbstractScrollArea,
    QToolButton, QFileDialog, QMessageBox,
)
from PySide6.QtCore  import Signal, Qt, QSize
from PySide6.QtGui   import QColor, QPainter, QPen, QFont

# 기본 세션 파일 경로
_APP_DIR      = Path(__file__).parent.parent.parent   # SpaceD-AADE/
_SESSION_DIR  = _APP_DIR / "data" / "scenarios"
_SESSION_FILE = _SESSION_DIR / "_session.json"

from gui.widgets.satellite_config import SatelliteConfigPanel

# ── 시나리오 아이템 카드 ──────────────────────────────────────────────────────
class ScenarioCard(QFrame):
    """시나리오 목록의 개별 카드 위젯"""
    clicked    = Signal(str)   # scenario_id
    delete_req = Signal(str)   # scenario_id

    # 색상 팔레트 (시나리오 번호별 고유 색)
    COLORS = [
        "#00dcff", "#ff6b6b", "#39ff96", "#ffa040",
        "#c080ff", "#ffdc40", "#40c8ff", "#ff80c0",
    ]

    def __init__(self, scenario_id: str, name: str, orbit_summary: str,
                 index: int, parent=None):
        super().__init__(parent)
        self.scenario_id  = scenario_id
        self._selected    = False
        self._color       = self.COLORS[index % len(self.COLORS)]

        self.setObjectName("scenarioCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(58)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 6, 4)
        layout.setSpacing(6)

        # 색상 점
        self._dot = QLabel()
        self._dot.setFixedSize(10, 10)
        self._dot.setStyleSheet(
            f"background:{self._color}; border-radius:5px;"
        )
        layout.addWidget(self._dot)

        # 이름 + 궤도 요약
        text_w = QWidget()
        text_l = QVBoxLayout(text_w)
        text_l.setContentsMargins(0, 0, 0, 0)
        text_l.setSpacing(1)

        self._name_lbl = QLabel(name)
        self._name_lbl.setStyleSheet(
            "color:#d0e8f0; font-size:11px; font-weight:bold;"
        )
        self._orbit_lbl = QLabel(orbit_summary)
        self._orbit_lbl.setStyleSheet("color:#4a6a7a; font-size:9px;")
        text_l.addWidget(self._name_lbl)
        text_l.addWidget(self._orbit_lbl)
        layout.addWidget(text_w, stretch=1)

        # 삭제 버튼
        del_btn = QToolButton()
        del_btn.setText("✕")
        del_btn.setFixedSize(18, 18)
        del_btn.setStyleSheet("""
            QToolButton { background:transparent; color:#445566;
                          border:none; font-size:10px; border-radius:3px; }
            QToolButton:hover { color:#ff4d6d; background:rgba(255,77,109,0.12); }
        """)
        del_btn.clicked.connect(lambda: self.delete_req.emit(self.scenario_id))
        layout.addWidget(del_btn)

        self._update_style()

    def set_selected(self, selected: bool):
        self._selected = selected
        self._update_style()

    def set_name(self, name: str):
        self._name_lbl.setText(name)

    def set_orbit_summary(self, summary: str):
        self._orbit_lbl.setText(summary)

    def _update_style(self):
        if self._selected:
            self.setStyleSheet(f"""
                #scenarioCard {{
                    background: rgba(0,180,230,0.10);
                    border: 1px solid {self._color};
                    border-radius: 6px;
                }}
            """)
        else:
            self.setStyleSheet("""
                #scenarioCard {
                    background: transparent;
                    border: 1px solid rgba(40,60,80,0.6);
                    border-radius: 6px;
                }
                #scenarioCard:hover {
                    background: rgba(255,255,255,0.03);
                    border: 1px solid rgba(0,180,230,0.35);
                }
            """)

    def mousePressEvent(self, event):
        self.clicked.emit(self.scenario_id)
        super().mousePressEvent(event)


# ── 빈 상태 플레이스홀더 ─────────────────────────────────────────────────────
class EmptyPlaceholder(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        lbl = QLabel("궤도 분석을 실행하면\n자동으로 시나리오가 추가됩니다.")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color:#2a4050; font-size:11px; line-height:1.8;")
        layout.addWidget(lbl)
        hint = QLabel("Orbit 탭에서 분석 시작 →")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color:#1e3040; font-size:10px; margin-top:8px;")
        layout.addWidget(hint)


# ── 메인 패널 ─────────────────────────────────────────────────────────────────
class SatelliteScenarioPanel(QWidget):
    """
    다중 위성 시나리오 관리 패널.
    분석 결과 1건 = 시나리오 1개.
    각 시나리오는 독립적인 SatelliteConfigPanel 을 가짐.
    """
    scenarios_changed = Signal(list)   # [{sat_id, name, sat_config}, ...]
    scenario_selected = Signal(str)    # 선택된 scenario_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("satScenarioPanel")
        self._scenarios: list[dict] = []   # {id, name, orbit_summary, widget(SatelliteConfigPanel)}
        self._selected_id: str | None = None

        self._build_ui()

    # ── UI 빌드 ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 헤더 ─────────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(36)
        header.setStyleSheet("background:#0a0f1e; border-bottom:1px solid #1a2a3a;")
        hdr_l = QHBoxLayout(header)
        hdr_l.setContentsMargins(10, 0, 8, 0)

        title = QLabel("🛰  SATELLITE SCENARIOS")
        title.setStyleSheet("color:#ffaa00; font-size:10px; font-weight:bold; letter-spacing:1.5px;")
        hdr_l.addWidget(title)
        hdr_l.addStretch()

        # 도구 버튼 스타일 공용
        _btn_ss = (
            "QPushButton { background:transparent; color:#445566; border:1px solid #2a3a4a;"
            "  border-radius:3px; padding:0 7px; font-size:9px; }"
            "QPushButton:hover { color:#00dcff; border-color:#00dcff; }"
        )
        _del_ss = (
            "QPushButton { background:transparent; color:#445566; border:1px solid #2a3a4a;"
            "  border-radius:3px; padding:0 8px; font-size:9px; }"
            "QPushButton:hover { color:#ff4d6d; border-color:#ff4d6d; }"
        )

        # 저장 버튼
        self._save_btn = QPushButton("💾")
        self._save_btn.setFixedSize(24, 22)
        self._save_btn.setToolTip("시나리오 저장 (JSON)")
        self._save_btn.setStyleSheet(_btn_ss)
        self._save_btn.clicked.connect(self.save_scenarios)
        hdr_l.addWidget(self._save_btn)

        # 불러오기 버튼
        self._load_btn = QPushButton("📂")
        self._load_btn.setFixedSize(24, 22)
        self._load_btn.setToolTip("시나리오 불러오기 (JSON)")
        self._load_btn.setStyleSheet(_btn_ss)
        self._load_btn.clicked.connect(self.load_scenarios)
        hdr_l.addWidget(self._load_btn)

        # 전체 클리어 버튼
        self._clear_btn = QPushButton("전체 삭제")
        self._clear_btn.setFixedHeight(22)
        self._clear_btn.setStyleSheet(_del_ss)
        self._clear_btn.clicked.connect(self.clear_all)
        hdr_l.addWidget(self._clear_btn)

        root.addWidget(header)

        # ── 바디: 좌측 목록 + 우측 설정 ─────────────────────────────────────
        body = QWidget()
        body_l = QHBoxLayout(body)
        body_l.setContentsMargins(0, 0, 0, 0)
        body_l.setSpacing(0)

        # 좌측: 시나리오 목록 (고정 너비 130)
        list_panel = QWidget()
        list_panel.setFixedWidth(130)
        list_panel.setStyleSheet("background:#080d1a; border-right:1px solid #1a2a3a;")
        list_l = QVBoxLayout(list_panel)
        list_l.setContentsMargins(6, 6, 6, 6)
        list_l.setSpacing(4)

        # 스크롤 영역 (카드들)
        self._cards_widget = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_widget)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(4)
        self._cards_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._cards_widget)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")
        list_l.addWidget(scroll)

        body_l.addWidget(list_panel)

        # 우측: SatelliteConfigPanel 스택 + 빈 플레이스홀더
        self._right_stack = QStackedWidget()
        self._placeholder = EmptyPlaceholder()
        self._right_stack.addWidget(self._placeholder)   # index 0: 빈 화면
        body_l.addWidget(self._right_stack, stretch=1)

        root.addWidget(body, stretch=1)

        # ── 하단 상태 바 ─────────────────────────────────────────────────────
        status_bar = QWidget()
        status_bar.setFixedHeight(24)
        status_bar.setStyleSheet("background:#060a12; border-top:1px solid #1a2a3a;")
        sb_l = QHBoxLayout(status_bar)
        sb_l.setContentsMargins(10, 0, 10, 0)
        self._status_lbl = QLabel("시나리오 없음")
        self._status_lbl.setStyleSheet("color:#2a4050; font-size:9.5px;")
        sb_l.addWidget(self._status_lbl)
        sb_l.addStretch()
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("color:#2a4050; font-size:9.5px;")
        sb_l.addWidget(self._count_lbl)
        root.addWidget(status_bar)

    # ── 공개 API ─────────────────────────────────────────────────────────────

    def add_scenario(self, scenario_id: str, name: str, orbit_summary: str,
                     default_config: dict | None = None):
        """새 시나리오 추가. orbit 분석 완료 시 main_window에서 호출."""
        idx = len(self._scenarios)

        # SatelliteConfigPanel 생성 (우측 스택에 추가)
        config_panel = SatelliteConfigPanel()
        if default_config:
            config_panel.set_config(default_config)
        config_panel.config_changed.connect(
            lambda cfg, sid=scenario_id: self._on_config_changed(sid, cfg)
        )
        self._right_stack.addWidget(config_panel)  # index = idx + 1 (0은 placeholder)

        # 카드 추가
        card = ScenarioCard(scenario_id, name, orbit_summary, idx)
        card.clicked.connect(self._on_card_clicked)
        card.delete_req.connect(self.remove_scenario)
        # stretch 앞에 삽입
        self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)

        self._scenarios.append({
            "id":            scenario_id,
            "name":          name,
            "orbit_summary": orbit_summary,
            "card":          card,
            "panel":         config_panel,
            "stack_idx":     idx + 1,   # right_stack index
        })

        # 자동 선택
        self._select(scenario_id)
        self._update_status()
        self._emit_scenarios()

    def remove_scenario(self, scenario_id: str):
        entry = self._find(scenario_id)
        if not entry:
            return
        # 위젯 제거
        self._right_stack.removeWidget(entry["panel"])
        entry["panel"].deleteLater()
        self._cards_layout.removeWidget(entry["card"])
        entry["card"].deleteLater()
        self._scenarios.remove(entry)

        # 스택 인덱스 재정렬
        for i, s in enumerate(self._scenarios):
            s["stack_idx"] = i + 1

        # 선택 갱신
        if self._selected_id == scenario_id:
            self._selected_id = None
            if self._scenarios:
                self._select(self._scenarios[-1]["id"])
            else:
                self._right_stack.setCurrentIndex(0)  # placeholder

        self._update_status()
        self._emit_scenarios()

    def clear_all(self):
        for s in list(self._scenarios):
            self.remove_scenario(s["id"])

    def get_all_scenarios(self) -> list[dict]:
        """3D 뷰어에 전달할 형식: [{sat_id, name, sat_config}, ...]"""
        return [
            {"sat_id": s["id"], "name": s["name"],
             "sat_config": s["panel"].get_config()}
            for s in self._scenarios
        ]

    def get_selected_config(self) -> dict | None:
        entry = self._find(self._selected_id)
        return entry["panel"].get_config() if entry else None

    def get_scenario_config(self, scenario_id: str) -> dict | None:
        entry = self._find(scenario_id)
        return entry["panel"].get_config() if entry else None

    def update_orbit_summary(self, scenario_id: str, summary: str):
        entry = self._find(scenario_id)
        if entry:
            entry["orbit_summary"] = summary
            entry["card"].set_orbit_summary(summary)

    # ── 내부 로직 ─────────────────────────────────────────────────────────────
    def _find(self, scenario_id: str) -> dict | None:
        return next((s for s in self._scenarios if s["id"] == scenario_id), None)

    def _select(self, scenario_id: str):
        # 이전 카드 deselect
        if self._selected_id:
            prev = self._find(self._selected_id)
            if prev:
                prev["card"].set_selected(False)

        self._selected_id = scenario_id
        entry = self._find(scenario_id)
        if entry:
            entry["card"].set_selected(True)
            self._right_stack.setCurrentIndex(entry["stack_idx"])
            self.scenario_selected.emit(scenario_id)

    def _on_card_clicked(self, scenario_id: str):
        self._select(scenario_id)

    def _on_config_changed(self, scenario_id: str, cfg: dict):
        """설정 변경 시 3D 뷰어에 전체 시나리오 재전송"""
        self._emit_scenarios()

    def _emit_scenarios(self):
        self.scenarios_changed.emit(self.get_all_scenarios())
        self.save_session()   # 변경 시마다 세션 자동 저장

    # ── 직렬화 헬퍼 ──────────────────────────────────────────────────────────
    def _to_json_data(self) -> dict:
        return {
            "app":      "SpaceD-AADE",
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "scenarios": [
                {
                    "id":            s["id"],
                    "name":          s["name"],
                    "orbit_summary": s["orbit_summary"],
                    "sat_config":    s["panel"].get_config(),
                }
                for s in self._scenarios
            ],
        }

    def _restore_from_data(self, data: dict):
        """JSON data dict 로부터 시나리오 복원 (기존 내용 먼저 클리어)"""
        self.clear_all()
        for sc in data.get("scenarios", []):
            self.add_scenario(
                sc.get("id",            f"SAT-{len(self._scenarios)+1}"),
                sc.get("name",          f"SAT-{len(self._scenarios)+1}"),
                sc.get("orbit_summary", "—"),
                sc.get("sat_config",    {}),
            )

    # ── 공개: 저장/불러오기 (파일 다이얼로그) ────────────────────────────────
    def save_scenarios(self):
        """다른 이름으로 저장 (QFileDialog)"""
        _SESSION_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "시나리오 저장", str(_SESSION_DIR / "scenarios.json"),
            "JSON 파일 (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._to_json_data(), f, ensure_ascii=False, indent=2)
            self._status_lbl.setText(f"저장됨: {Path(path).name}")
        except Exception as e:
            QMessageBox.warning(self, "저장 실패", str(e))

    def load_scenarios(self):
        """파일 선택 후 불러오기 (QFileDialog)"""
        path, _ = QFileDialog.getOpenFileName(
            self, "시나리오 불러오기", str(_SESSION_DIR),
            "JSON 파일 (*.json)"
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self._restore_from_data(data)
            self._status_lbl.setText(f"불러옴: {Path(path).name}")
        except Exception as e:
            QMessageBox.warning(self, "불러오기 실패", str(e))

    # ── 공개: 자동 세션 저장/복원 ────────────────────────────────────────────
    def save_session(self):
        """기본 경로에 자동 저장 (사용자 조작 없음)"""
        try:
            _SESSION_DIR.mkdir(parents=True, exist_ok=True)
            with open(_SESSION_FILE, "w", encoding="utf-8") as f:
                json.dump(self._to_json_data(), f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # 자동 저장 실패는 조용히 무시

    def load_session(self) -> bool:
        """마지막 세션 자동 복원. 성공 시 True 반환."""
        if not _SESSION_FILE.exists():
            return False
        try:
            with open(_SESSION_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if not data.get("scenarios"):
                return False
            self._restore_from_data(data)
            return True
        except Exception:
            return False

    def _update_status(self):
        n = len(self._scenarios)
        if n == 0:
            self._status_lbl.setText("시나리오 없음")
            self._count_lbl.setText("")
        elif n == 1:
            sel = self._find(self._selected_id)
            nm  = sel["name"] if sel else "—"
            self._status_lbl.setText(f"선택: {nm}")
            self._count_lbl.setText(f"1개")
        else:
            sel = self._find(self._selected_id)
            nm  = sel["name"] if sel else "—"
            self._status_lbl.setText(f"선택: {nm}")
            self._count_lbl.setText(f"{n}개 시나리오")
