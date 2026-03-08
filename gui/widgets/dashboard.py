"""
Dashboard Panel
실시간 지표 카드 + Design Score Card
"""
import math
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QGridLayout, QProgressBar, QSizePolicy, QComboBox, QPushButton
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui  import QFont, QColor, QPainter, QPen, QBrush, QConicalGradient
from PySide6.QtCore import QRectF


class ArrowIndicator(QWidget):
    """작은 게이지 바"""
    def __init__(self, color="#00dcff"):
        super().__init__()
        self._value = 0.0      # 0~1
        self._color = color
        self.setFixedHeight(4)

    def set_fraction(self, v: float):
        self._value = max(0.0, min(1.0, v))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#1a2535"))
        w = int(self.width() * self._value)
        if w > 0:
            from PySide6.QtGui import QLinearGradient
            grad = QLinearGradient(0, 0, self.width(), 0)
            grad.setColorAt(0, QColor("#0066aa"))
            grad.setColorAt(1, QColor(self._color))
            p.fillRect(0, 0, w, self.height(), grad)


class MetricCard(QWidget):
    """단일 지표 카드"""
    def __init__(self, icon: str, label: str, unit: str, limit_lo=None, limit_hi=None):
        super().__init__()
        self._limit_lo = limit_lo
        self._limit_hi = limit_hi
        self._unit = unit
        self.setFixedHeight(52)
        self.setObjectName("metricCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 4)
        layout.setSpacing(2)

        top = QHBoxLayout()
        lbl = QLabel(f"{icon}  {label}")
        lbl.setStyleSheet("color: #5a8a9a; font-size: 10px;")

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #5a8a9a; font-size: 10px;")
        self.status_dot.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.value_lbl = QLabel("—")
        self.value_lbl.setStyleSheet("color: #a0c8d8; font-size: 14px; font-weight: bold;")
        self.value_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        top.addWidget(lbl)
        top.addStretch()
        top.addWidget(self.value_lbl)
        top.addWidget(self.status_dot)
        layout.addLayout(top)

        self.bar = ArrowIndicator()
        layout.addWidget(self.bar)

        self.setStyleSheet("""
        #metricCard {
            background: #0d1a2a;
            border: 1px solid #1e2a3a;
            border-radius: 6px;
        }
        #metricCard:hover {
            border: 1px solid #2a4a6a;
        }
        """)

    def update_value(self, value: float, fraction: float = 0.5, passed: bool = True):
        self.value_lbl.setText(f"{value:.1f} {self._unit}")
        if passed:
            self.value_lbl.setStyleSheet("color: #00dcff; font-size: 14px; font-weight: bold;")
            self.status_dot.setStyleSheet("color: #39ff96; font-size: 10px;")
            self.bar = ArrowIndicator("#00dcff")
        else:
            self.value_lbl.setStyleSheet("color: #ff4d6d; font-size: 14px; font-weight: bold;")
            self.status_dot.setStyleSheet("color: #ff4d6d; font-size: 10px;")
            self.bar = ArrowIndicator("#ff4d6d")
        # 바 재구성 필요 없이 색상만 변경하는 단순 방식
        self.status_dot.setText("✅" if passed else "⚠️")


class ScoreCard(QWidget):
    """종합 설계 점수 카드"""
    def __init__(self):
        super().__init__()
        self.setObjectName("scoreCard")
        self._score = 0.0
        self._grade = "—"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        hdr = QLabel("📋  DESIGN SCORE")
        hdr.setStyleSheet("color: #00dcff; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(hdr)

        # 점수 표시
        score_row = QHBoxLayout()
        self.score_lbl = QLabel("—")
        self.score_lbl.setStyleSheet("color: #ffffff; font-size: 32px; font-weight: bold;")
        self.grade_lbl = QLabel("N/A")
        self.grade_lbl.setStyleSheet("""
            color: #00dcff; font-size: 22px; font-weight: bold;
            background: rgba(0,220,255,0.1); border: 1px solid rgba(0,220,255,0.3);
            border-radius: 4px; padding: 2px 8px;
        """)
        self.grade_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_row.addWidget(self.score_lbl)
        score_row.addStretch()
        score_row.addWidget(self.grade_lbl)
        layout.addLayout(score_row)

        # 점수 게이지
        self.score_bar = QProgressBar()
        self.score_bar.setRange(0, 100)
        self.score_bar.setValue(0)
        self.score_bar.setTextVisible(False)
        self.score_bar.setFixedHeight(6)
        self.score_bar.setStyleSheet("""
        QProgressBar { background: #1a2535; border: none; border-radius: 3px; }
        QProgressBar::chunk {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                         stop:0 #0055aa, stop:0.5 #00aacc, stop:1 #00ff88);
            border-radius: 3px;
        }
        """)
        layout.addWidget(self.score_bar)

        # 세부 항목 그리드
        self.detail_grid = QGridLayout()
        self.detail_grid.setSpacing(3)
        layout.addLayout(self.detail_grid)
        self._detail_labels = {}

        self.setStyleSheet("""
        #scoreCard {
            background: #0a1525;
            border: 1px solid rgba(0,220,255,0.2);
            border-radius: 8px;
        }
        """)

    def update_score(self, score, indicators: dict):
        self._score = score.total_score
        self._grade = score.grade

        self.score_lbl.setText(f"{score.total_score:.0f}")
        self.score_bar.setValue(int(score.total_score))

        grade_colors = {
            'A+': '#00ff88', 'A': '#00dcff', 'B': '#88cc00',
            'C': '#ffaa00', 'F': '#ff4d6d'
        }
        c = grade_colors.get(score.grade, '#a0c8d8')
        self.grade_lbl.setText(score.grade)
        self.grade_lbl.setStyleSheet(f"""
            color: {c}; font-size: 22px; font-weight: bold;
            background: rgba(0,220,255,0.08); border: 1px solid {c}55;
            border-radius: 4px; padding: 2px 8px;
        """)

        # 세부 항목 업데이트
        for i in reversed(range(self.detail_grid.count())):
            self.detail_grid.itemAt(i).widget().deleteLater()

        NAMES = {
            'sunlight_ratio': '☀ Sunlight',
            'max_eclipse':    '🌑 Max Eclipse',
            'battery_dod':    '🔋 Battery DOD',
            'temp_max':       '🌡 T max',
            'temp_min':       '🌡 T min',
            'tid_5yr':        '☢ TID 5yr',
            'contacts_per_day':'📡 Contacts',
            'mass_margin':    '⚖ Mass Margin',
            'power_margin':   '⚡ Power Margin',
        }
        row = 0
        for key, ind in indicators.items():
            name = NAMES.get(key, key)
            val  = ind['value']
            unit = ind['unit']
            passed = ind['pass']

            name_lbl = QLabel(name)
            name_lbl.setStyleSheet("color: #4a7a8a; font-size: 9px;")

            val_lbl = QLabel(f"{val:.1f} {unit}")
            dot = "✅" if passed else "⚠️"
            val_lbl.setText(f"{dot} {val:.1f} {unit}")
            val_lbl.setStyleSheet(f"color: {'#39ff96' if passed else '#ffa040'}; font-size: 9px;")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

            self.detail_grid.addWidget(name_lbl, row, 0)
            self.detail_grid.addWidget(val_lbl, row, 1)
            row += 1


class DashboardPanel(QWidget):
    """전체 우측 대시보드 패널"""

    METRICS = [
        ("🔆", "Sunlight Ratio",   "%",    85,  None),
        ("🌑", "Max Eclipse",      "min",  None, 30),
        ("🔋", "Battery DOD",      "%",    None, 35),
        ("🌡", "Temp Max",         "°C",   None, 70),
        ("🌡", "Temp Min",         "°C",   -20,  None),
        ("☢",  "TID 5yr",         "krad", None, 20),
        ("📡", "Contacts/Day",     "회",   4,   None),
        ("⚖",  "Mass Margin",      "%",    15,  None),
        ("⚡", "Power Margin",     "%",    10,  None),
    ]

    def __init__(self):
        super().__init__()
        self.setObjectName("dashboardPanel")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
        QScrollArea { border: none; background: transparent; }
        QScrollBar:vertical { background: #0a0f1e; width: 4px; }
        QScrollBar::handle:vertical { background: #2a3a4a; border-radius: 2px; }
        """)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # 다중 위성 선택 콤보박스 추가
        tf_row = QHBoxLayout()
        tf_lbl = QLabel("📡 Target:")
        tf_lbl.setStyleSheet("color: #7ab0c6; font-size: 10px; font-weight: bold;")
        self.sat_combo = QComboBox()
        self.sat_combo.setMinimumWidth(100)
        self.sat_combo.setStyleSheet("""
        QComboBox { 
            background: rgba(13, 26, 42, 0.8); 
            color: #00dcff; 
            border: 1px solid rgba(0, 220, 255, 0.4);
            border-radius: 4px; padding: 2px 6px; font-size: 11px; font-weight: bold;
        }
        QComboBox::drop-down { border: none; }
        QComboBox QAbstractItemView { background: #0d1a2a; color: #00dcff; }
        """)
        self.sat_combo.currentIndexChanged.connect(self._on_combo_changed)
        tf_row.addWidget(tf_lbl)
        tf_row.addWidget(self.sat_combo, 1)

        self.btn_compare = QPushButton("비교분석")
        self.btn_compare.setStyleSheet("""
        QPushButton {
            background: rgba(0, 150, 200, 0.4);
            color: #ffffff;
            border: 1px solid rgba(0, 220, 255, 0.6);
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 10px; font-weight: bold;
        }
        QPushButton:hover { background: rgba(0, 200, 255, 0.6); }
        """)
        self.btn_compare.clicked.connect(self.compare_requested.emit)
        tf_row.addWidget(self.btn_compare)

        layout.addLayout(tf_row)
        layout.addSpacing(6)

        # 헤더
        hdr = QLabel("⏱  REAL-TIME INDICATORS")
        hdr.setStyleSheet("""
        color: #00dcff; font-size: 10px; font-weight: bold;
        letter-spacing: 2px; padding: 4px 2px;
        border-bottom: 1px solid #1e2a3a;
        """)
        layout.addWidget(hdr)

        # 지표 카드들
        self.cards = {}
        keys = ['sunlight_ratio','max_eclipse','battery_dod','temp_max','temp_min',
                'tid_5yr','contacts_per_day','mass_margin','power_margin']

        for i, (icon, label, unit, lo, hi) in enumerate(self.METRICS):
            card = MetricCard(icon, label, unit, lo, hi)
            self.cards[keys[i]] = card
            layout.addWidget(card)

        # Score Card
        self.score_card = ScoreCard()
        layout.addWidget(self.score_card)
        layout.addStretch()

        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self.setStyleSheet("""
        #dashboardPanel { background: #0d1525; }
        """)

    satellite_selected = Signal(int)
    compare_requested = Signal()

    def _on_combo_changed(self, idx: int):
        if idx >= 0:
            self.satellite_selected.emit(idx)

    def add_satellite(self, name: str):
        self.sat_combo.blockSignals(True)
        self.sat_combo.addItem(name)
        self.sat_combo.setCurrentIndex(self.sat_combo.count() - 1)
        self.sat_combo.blockSignals(False)

    def update_all(self, orbit, budget, radiation, thermal, score):
        inds = score.indicators
        keys_vals = {
            'sunlight_ratio':  (orbit.sunlight_fraction * 100,         85, None),
            'max_eclipse':     (max((e.duration_min for e in orbit.eclipse_events), default=0), None, 30),
            'battery_dod':     (budget.battery_dod_pct,                None, 35),
            'temp_max':        (max(thermal.node_temps_max.values(), default=0), None, 70),
            'temp_min':        (min(thermal.node_temps_min.values(), default=0), -20, None),
            'tid_5yr':         (radiation.tid_krad_5yr,                None, 20),
            'contacts_per_day':(orbit.contacts_per_day,                4,   None),
            'mass_margin':     (budget.mass_margin_pct,                15,  None),
            'power_margin':    (budget.power_margin_pct,               10,  None),
        }

        for key, card in self.cards.items():
            if key in keys_vals:
                val, lo, hi = keys_vals[key]
                if lo is not None:
                    passed = val >= lo
                    frac = min(1.0, max(0.0, (val - lo * 0.5) / (lo * 1.5)))
                elif hi is not None:
                    passed = val <= hi
                    frac = min(1.0, max(0.0, 1.0 - val / (hi * 1.5)))
                else:
                    passed = True
                    frac = 0.5
                card.update_value(val, frac, passed)

        self.score_card.update_score(score, inds)
