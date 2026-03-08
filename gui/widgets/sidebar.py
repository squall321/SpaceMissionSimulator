"""
Sidebar Navigation Widget
아이콘 + 텍스트 수직 메뉴
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QSpacerItem, QSizePolicy
from PySide6.QtCore    import Signal, Qt
from PySide6.QtGui     import QFont

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import version as V


class NavButton(QPushButton):
    def __init__(self, icon_char: str, label: str, section: str):
        super().__init__()
        self.section = section
        self.setCheckable(True)
        self.setFixedSize(64, 64)
        self.setToolTip(label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 6)
        layout.setSpacing(2)

        icon_lbl = QLabel(icon_char)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setFont(QFont("Segoe UI Emoji", 18))
        icon_lbl.setStyleSheet("color: inherit; background: transparent;")

        text_lbl = QLabel(label)
        text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_lbl.setFont(QFont("Segoe UI", 7))
        text_lbl.setStyleSheet("color: inherit; background: transparent;")

        layout.addWidget(icon_lbl)
        layout.addWidget(text_lbl)

        self.setStyleSheet("""
        NavButton {
            background: transparent;
            border: none;
            border-radius: 0;
            color: #4a6a7a;
        }
        NavButton:hover {
            background: rgba(0, 200, 255, 0.08);
            color: #a0c8d8;
        }
        NavButton:checked {
            background: rgba(0, 220, 255, 0.12);
            color: #00dcff;
            border-left: 2px solid #00dcff;
        }
        """)


class Sidebar(QWidget):
    nav_changed      = Signal(str)
    optimize_clicked = Signal()   # 최적화 버튼 시그널
    settings_clicked = Signal()   # 설정 버튼 시그널

    NAV_ITEMS = [
        ("🎯", "Mission",  "mission"),
        ("🌍", "Orbit",    "orbit"),
        ("🛰️", "Satellite","satellite"),
        ("🌡️",  "Thermal",  "thermal"),
        ("☢️",  "Radiation","radiation"),
        ("📊", "Budget",   "budget"),
        ("📈", "Study",    "study"),
        ("🏆", "Score",    "score"),    # v0.9.0
    ]

    def __init__(self):
        super().__init__()
        self.setFixedWidth(64)
        self.setObjectName("sidebar")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 로고
        logo = QLabel("⚡")
        logo.setFont(QFont("Segoe UI Emoji", 22))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedHeight(56)
        logo.setStyleSheet("color: #00dcff; background: #060c18; border-bottom: 1px solid #1e2a3a;")
        layout.addWidget(logo)

        # 네비게이션 버튼
        self.buttons = []
        for icon, label, section in self.NAV_ITEMS:
            btn = NavButton(icon, label, section)
            btn.clicked.connect(lambda checked, s=section, b=btn: self._on_click(s, b))
            layout.addWidget(btn)
            self.buttons.append(btn)

        # 기본 선택: Orbit
        self.buttons[1].setChecked(True)

        layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum,
                                         QSizePolicy.Policy.Expanding))

        # 최적화 버튼
        optimize_btn = NavButton("🔍", "Optimize", "optimize")
        optimize_btn.clicked.connect(self._on_optimize_click)
        layout.addWidget(optimize_btn)
        
        # 설정 버튼
        settings_btn = NavButton("⚙️", "Settings", "settings")
        settings_btn.clicked.connect(self._on_settings_click)
        layout.addWidget(settings_btn)

        # 버전 배지
        ver_lbl = QLabel(V.VERSION_FULL)
        ver_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver_lbl.setFixedHeight(28)
        ver_lbl.setStyleSheet(
            "color:#2a5a6a;font-size:8px;font-weight:700;"
            "background:transparent;letter-spacing:0.5px;"
        )
        layout.addWidget(ver_lbl)

        self.setStyleSheet("""
        #sidebar { background: #060c18; border-right: 1px solid #1e2a3a; }
        """)

    def _on_click(self, section: str, clicked_btn: NavButton):
        for btn in self.buttons:
            if btn is not clicked_btn:
                btn.setChecked(False)
        self.nav_changed.emit(section)

    def select_section(self, section: str):
        """외부에서 특정 섹션으로 전환 (버튼 상태 동기화)"""
        for btn in self.buttons:
            if btn.section == section:
                btn.setChecked(True)
                self._on_click(section, btn)
                return

    def _on_optimize_click(self):
        self.optimize_clicked.emit()

    def _on_settings_click(self):
        self.settings_clicked.emit()
