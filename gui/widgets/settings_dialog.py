"""
Settings Dialog — v0.6.0
GMAT 경로·사용 여부, 시뮬레이션 기본값, 분석 파이프라인 설정
"""
from __future__ import annotations
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QPushButton, QCheckBox, QSpinBox, QDoubleSpinBox,
    QGroupBox, QFormLayout, QFileDialog, QMessageBox, QComboBox,
    QSizePolicy
)
from PySide6.QtCore import Qt, Signal

# 설정 파일 위치
CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "settings.json"
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── 기본값 ────────────────────────────────────────────────────────────────────
DEFAULTS = {
    "gmat": {
        "enabled":          True,
        "path":             "",           # 빈 문자열 → 자동 탐색
        "timeout_s":        300,
        "fallback_on_fail": True,
    },
    "analysis": {
        "duration_days":    1.0,
        "time_step_s":      60,
        "min_elevation_deg": 5.0,
    },
    "simulation": {
        "default_speed":    2880,   # 1 실시간 초 = 2880 시뮬레이션 초
        "loop":             True,
    },
    "ui": {
        "show_log_panel":   True,
        "log_max_lines":    300,
        "dark_hud":         True,
    },
}

_BTN = """
QPushButton {
    background: rgba(0, 150, 200, 0.35);
    color: #c8e0f0;
    border: 1px solid rgba(0, 220, 255, 0.5);
    border-radius: 4px;
    padding: 5px 14px;
    font-size: 11px; font-weight: bold;
}
QPushButton:hover  { background: rgba(0, 200, 255, 0.5); color:#fff; }
QPushButton:pressed{ background: rgba(0, 150, 200, 0.7); }
"""

_INPUT = """
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: rgba(10, 20, 35, 0.9);
    color: #c8e0f0;
    border: 1px solid rgba(0, 220, 255, 0.35);
    border-radius: 3px;
    padding: 3px 6px;
    font-size: 11px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: rgba(0, 220, 255, 0.7);
}
"""

_GROUP = """
QGroupBox {
    color: #00dcff;
    border: 1px solid rgba(0, 220, 255, 0.25);
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 6px;
    font-size: 11px; font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px; top: -2px;
}
"""

_CHECK = """
QCheckBox {
    color: #c8e0f0;
    font-size: 11px;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 14px; height: 14px;
    border: 1px solid rgba(0, 220, 255, 0.4);
    border-radius: 3px;
    background: rgba(10, 20, 35, 0.9);
}
QCheckBox::indicator:checked {
    background: rgba(0, 180, 220, 0.8);
    border-color: #00dcff;
}
"""


def load_settings() -> dict:
    """설정 파일 로드 (없으면 기본값 반환)"""
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 기본값 병합 (새 키 보완)
            for section, vals in DEFAULTS.items():
                data.setdefault(section, {})
                for k, v in vals.items():
                    data[section].setdefault(k, v)
            return data
    except Exception:
        pass
    return {s: dict(v) for s, v in DEFAULTS.items()}


def save_settings(cfg: dict) -> None:
    """설정 파일 저장"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


class SettingsDialog(QDialog):
    """앱 설정 다이얼로그"""
    settings_changed = Signal(dict)     # 저장 후 emit

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings — SpaceD-AADE")
        self.resize(560, 480)
        self._cfg = load_settings()
        self._build_ui()
        self._load_into_ui()
        self.setStyleSheet("""
        QDialog      { background: #050a14; }
        QTabWidget::pane { border: 1px solid rgba(0,220,255,0.2); background: #07101e; }
        QTabBar::tab {
            background: rgba(10,20,35,0.8); color:#7ea8be;
            padding: 6px 16px; font-size: 11px;
            border: 1px solid rgba(0,220,255,0.15);
            border-bottom: none; border-radius: 4px 4px 0 0;
        }
        QTabBar::tab:selected { background: #07101e; color:#00dcff; font-weight:bold; }
        QLabel { color: #8ab0c0; font-size: 11px; }
        """ + _GROUP + _CHECK + _INPUT)

    # ── UI 구성 ───────────────────────────────────────────────────────────────
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 10)
        layout.setSpacing(8)

        title = QLabel("⚙  Platform Settings")
        title.setStyleSheet("color:#00dcff; font-size:14px; font-weight:bold; letter-spacing:1px;")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._build_gmat_tab(),       "🚀 GMAT")
        tabs.addTab(self._build_analysis_tab(),   "📊 Analysis")
        tabs.addTab(self._build_sim_tab(),        "🌍 Simulation")
        tabs.addTab(self._build_ui_tab(),         "🖥 UI")
        layout.addWidget(tabs, stretch=1)

        # 버튼 바
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_save = QPushButton("💾  Save")
        btn_save.setStyleSheet(_BTN)
        btn_save.clicked.connect(self._on_save)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet(_BTN)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _build_gmat_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        grp = QGroupBox("GMAT Executable")
        grp.setStyleSheet(_GROUP)
        form = QFormLayout(grp)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(8)
        form.setContentsMargins(10, 16, 10, 10)

        # Enable 체크박스
        self._chk_gmat = QCheckBox("Enable GMAT pipeline")
        self._chk_gmat.setStyleSheet(_CHECK)
        form.addRow("", self._chk_gmat)

        # 경로 + 찾기 버튼
        path_row = QHBoxLayout()
        self._le_gmat_path = QLineEdit()
        self._le_gmat_path.setPlaceholderText("자동 탐색 (비워두면 tools/GMAT 우선)")
        self._le_gmat_path.setStyleSheet(_INPUT)
        path_row.addWidget(self._le_gmat_path)
        btn_browse = QPushButton("📁 Browse")
        btn_browse.setStyleSheet(_BTN)
        btn_browse.setFixedWidth(90)
        btn_browse.clicked.connect(self._browse_gmat)
        path_row.addWidget(btn_browse)
        form.addRow("GMAT bin dir:", path_row)

        # Timeout
        self._sp_timeout = QSpinBox()
        self._sp_timeout.setRange(30, 1800)
        self._sp_timeout.setSuffix(" s")
        self._sp_timeout.setStyleSheet(_INPUT)
        form.addRow("Timeout:", self._sp_timeout)

        # Fallback
        self._chk_fallback = QCheckBox("Use internal engine if GMAT fails")
        self._chk_fallback.setStyleSheet(_CHECK)
        form.addRow("", self._chk_fallback)

        v.addWidget(grp)

        # GMAT 상태 확인 버튼
        btn_check = QPushButton("🔍  Check GMAT Status")
        btn_check.setStyleSheet(_BTN)
        btn_check.clicked.connect(self._check_gmat_status)
        v.addWidget(btn_check)

        self._lbl_gmat_status = QLabel("")
        v.addWidget(self._lbl_gmat_status)

        v.addStretch()
        return w

    def _build_analysis_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        grp = QGroupBox("Orbit Propagation Defaults")
        grp.setStyleSheet(_GROUP)
        form = QFormLayout(grp)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(8)
        form.setContentsMargins(10, 16, 10, 10)

        self._sp_dur = QDoubleSpinBox()
        self._sp_dur.setRange(0.1, 30.0)
        self._sp_dur.setSingleStep(0.5)
        self._sp_dur.setSuffix(" days")
        self._sp_dur.setStyleSheet(_INPUT)
        form.addRow("Duration:", self._sp_dur)

        self._sp_step = QSpinBox()
        self._sp_step.setRange(10, 600)
        self._sp_step.setSingleStep(10)
        self._sp_step.setSuffix(" s")
        self._sp_step.setStyleSheet(_INPUT)
        form.addRow("Time step:", self._sp_step)

        self._sp_elev = QDoubleSpinBox()
        self._sp_elev.setRange(0.0, 30.0)
        self._sp_elev.setSingleStep(1.0)
        self._sp_elev.setSuffix(" °")
        self._sp_elev.setStyleSheet(_INPUT)
        form.addRow("Min elevation:", self._sp_elev)

        v.addWidget(grp)
        v.addStretch()
        return w

    def _build_sim_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        grp = QGroupBox("CesiumJS Simulation")
        grp.setStyleSheet(_GROUP)
        form = QFormLayout(grp)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(8)
        form.setContentsMargins(10, 16, 10, 10)

        self._cb_speed = QComboBox()
        self._cb_speed.addItems(["x60 (1min/s)", "x600 (10min/s)", "x2880 (48min/s)", "x5760 (96min/s)"])
        self._cb_speed.setStyleSheet(_INPUT)
        form.addRow("Default speed:", self._cb_speed)

        self._chk_loop = QCheckBox("Loop simulation")
        self._chk_loop.setStyleSheet(_CHECK)
        form.addRow("", self._chk_loop)

        v.addWidget(grp)
        v.addStretch()
        return w

    def _build_ui_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        grp = QGroupBox("Interface")
        grp.setStyleSheet(_GROUP)
        form = QFormLayout(grp)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(8)
        form.setContentsMargins(10, 16, 10, 10)

        self._chk_log = QCheckBox("Show analysis log panel")
        self._chk_log.setStyleSheet(_CHECK)
        form.addRow("", self._chk_log)

        self._sp_logmax = QSpinBox()
        self._sp_logmax.setRange(50, 2000)
        self._sp_logmax.setSingleStep(50)
        self._sp_logmax.setSuffix(" lines")
        self._sp_logmax.setStyleSheet(_INPUT)
        form.addRow("Max log lines:", self._sp_logmax)

        self._chk_hud = QCheckBox("Dark HUD overlay")
        self._chk_hud.setStyleSheet(_CHECK)
        form.addRow("", self._chk_hud)

        v.addWidget(grp)
        v.addStretch()
        return w

    # ── 데이터 로드/저장 ──────────────────────────────────────────────────────
    def _load_into_ui(self):
        g = self._cfg["gmat"]
        self._chk_gmat.setChecked(g["enabled"])
        self._le_gmat_path.setText(g["path"])
        self._sp_timeout.setValue(g["timeout_s"])
        self._chk_fallback.setChecked(g["fallback_on_fail"])

        a = self._cfg["analysis"]
        self._sp_dur.setValue(a["duration_days"])
        self._sp_step.setValue(a["time_step_s"])
        self._sp_elev.setValue(a["min_elevation_deg"])

        s = self._cfg["simulation"]
        speed_map = {60: 0, 600: 1, 2880: 2, 5760: 3}
        self._cb_speed.setCurrentIndex(speed_map.get(s["default_speed"], 2))
        self._chk_loop.setChecked(s["loop"])

        u = self._cfg["ui"]
        self._chk_log.setChecked(u["show_log_panel"])
        self._sp_logmax.setValue(u["log_max_lines"])
        self._chk_hud.setChecked(u["dark_hud"])

    def _collect_from_ui(self) -> dict:
        speed_vals = [60, 600, 2880, 5760]
        return {
            "gmat": {
                "enabled":          self._chk_gmat.isChecked(),
                "path":             self._le_gmat_path.text().strip(),
                "timeout_s":        self._sp_timeout.value(),
                "fallback_on_fail": self._chk_fallback.isChecked(),
            },
            "analysis": {
                "duration_days":    self._sp_dur.value(),
                "time_step_s":      self._sp_step.value(),
                "min_elevation_deg": self._sp_elev.value(),
            },
            "simulation": {
                "default_speed": speed_vals[self._cb_speed.currentIndex()],
                "loop":          self._chk_loop.isChecked(),
            },
            "ui": {
                "show_log_panel": self._chk_log.isChecked(),
                "log_max_lines":  self._sp_logmax.value(),
                "dark_hud":       self._chk_hud.isChecked(),
            },
        }

    def _on_save(self):
        self._cfg = self._collect_from_ui()
        save_settings(self._cfg)
        self.settings_changed.emit(self._cfg)
        self.accept()

    # ── GMAT 경로 찾기 + 상태 확인 ───────────────────────────────────────────
    def _browse_gmat(self):
        path = QFileDialog.getExistingDirectory(self, "GMAT bin 디렉토리 선택", "")
        if path:
            self._le_gmat_path.setText(path)

    def _check_gmat_status(self):
        import os
        try:
            from adapters.gmat.gmat_adapter import GmatAdapter
            path = self._le_gmat_path.text().strip() or None
            adapter = GmatAdapter(path) if path else GmatAdapter()
            if adapter.is_console_available():
                msg = f"✅  GmatConsole.exe 확인\n경로: {adapter.gmat_console}"
                self._lbl_gmat_status.setStyleSheet("color:#39ff96; font-size:11px;")
            elif adapter.is_available():
                msg = f"⚠️  GMAT.exe 확인 (Console 없음)\n경로: {adapter.gmat_exe}"
                self._lbl_gmat_status.setStyleSheet("color:#ffdc40; font-size:11px;")
            else:
                msg = f"❌  GMAT 실행 파일 없음\n탐색 경로: {adapter.gmat_exe}"
                self._lbl_gmat_status.setStyleSheet("color:#ff6b6b; font-size:11px;")
        except Exception as e:
            msg = f"❌  오류: {e}"
            self._lbl_gmat_status.setStyleSheet("color:#ff6b6b; font-size:11px;")
        self._lbl_gmat_status.setText(msg)
