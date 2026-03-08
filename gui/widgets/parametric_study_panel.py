"""
Parametric Study Panel
고도 × 경사각 그리드 히트맵 — 분석적 근사 기반
"""
from __future__ import annotations
import math
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QHeaderView,
    QFrame, QScrollArea, QGridLayout, QSizePolicy, QDoubleSpinBox,
    QSpinBox, QSpacerItem, QAbstractItemView
)
from PySide6.QtCore    import Signal, Qt, QTimer
from PySide6.QtGui     import QFont, QColor, QBrush

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.domain.orbit import OrbitParams
from core.services.parametric_study import ParametricStudyService, ParamPoint


# ── 지표 메타데이터 ──────────────────────────────────────────────
METRICS = [
    # (key, label, unit, 높을수록 좋나, format)
    ("period_min",               "궤도 주기",       "min",    False, "{:.1f}"),
    ("eclipse_max_min",          "최대 일식",       "min",    False, "{:.1f}"),
    ("sunlight_fraction",        "일조율",          "%",      True,  "{:.1%}"),
    ("contacts_per_day",         "접속 횟수",       "회/일",  True,  "{:.1f}"),
    ("contact_time_per_day_min", "접속 시간",       "min/일", True,  "{:.1f}"),
    ("gsd_m",                    "해상도 GSD",      "m",      False, "{:.1f}"),
    ("tid_krad",                 "TID 5yr",        "krad",   False, "{:.1f}"),
    ("delta_v_ms_yr",            "궤도유지 ΔV",    "m/s/yr", False, "{:.1f}"),
    ("power_margin_pct",         "전력 마진",       "%",      True,  "{:.0f}"),
    ("revisit_hr",               "재방문 주기",     "hr",     False, "{:.1f}"),
]


def _lerp_color(t: float, low: QColor, high: QColor) -> QColor:
    """t ∈ [0,1] → low(bad) → high(good) 색상 보간"""
    r = int(low.red()   + t * (high.red()   - low.red()))
    g = int(low.green() + t * (high.green() - low.green()))
    b = int(low.blue()  + t * (high.blue()  - low.blue()))
    return QColor(r, g, b)


COLOR_BAD  = QColor(120,  30,  30)   # 어두운 빨강
COLOR_MID  = QColor( 40,  55,  75)   # 기본 배경
COLOR_GOOD = QColor( 20,  90,  60)   # 어두운 초록


class ParametricStudyPanel(QWidget):
    """고도 × 경사각 히트맵 + 궤도 추천"""
    orbit_selected = Signal(OrbitParams)    # 셀 더블클릭 → 궤도 설정

    ALT_STEPS = 10
    INC_STEPS = 10

    def __init__(self):
        super().__init__()
        self.setObjectName("paramStudyPanel")
        self._svc    = ParametricStudyService()
        self._result = None
        self._metric_key   = "contacts_per_day"
        self._metric_higher = True
        self._selected_point: Optional[ParamPoint] = None
        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._run_study)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
        QScrollArea { background: transparent; border: none; }
        QScrollBar:vertical {
            background: rgba(255,255,255,0.04); width: 6px; border-radius: 3px;
        }
        QScrollBar::handle:vertical {
            background: rgba(255,255,255,0.18); border-radius: 3px; min-height: 20px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(12, 10, 12, 14)
        lay.setSpacing(8)

        # ── 헤더 ────────────────────────────────────────────────
        hdr = QLabel("📈  PARAMETRIC STUDY")
        hdr.setStyleSheet("""
            color: #e8f4ff; font-size: 12px; font-weight: 900;
            letter-spacing: 3px; padding: 6px 0 8px 0;
            border-bottom: 1px solid rgba(0,220,255,0.40);
        """)
        lay.addWidget(hdr)

        # ── 컨트롤 ──────────────────────────────────────────────
        lay.addWidget(self._sec("SWEEP RANGE"))
        ctrl = QGridLayout()
        ctrl.setSpacing(4)
        ctrl.setContentsMargins(0, 0, 0, 0)

        # 고도 범위
        ctrl.addWidget(self._lbl("고도 범위"), 0, 0)
        self.alt_lo = self._spin(200, 2000, 300,  50, "km")
        self.alt_hi = self._spin(200, 2000, 1200, 50, "km")
        ctrl.addWidget(self.alt_lo, 0, 1)
        ctrl.addWidget(QLabel("~"), 0, 2)
        ctrl.addWidget(self.alt_hi, 0, 3)

        # 경사각 범위
        ctrl.addWidget(self._lbl("경사각 범위"), 1, 0)
        self.inc_lo = self._spin(0, 180, 0,   5, "°")
        self.inc_hi = self._spin(0, 180, 105, 5, "°")
        ctrl.addWidget(self.inc_lo, 1, 1)
        ctrl.addWidget(QLabel("~"), 1, 2)
        ctrl.addWidget(self.inc_hi, 1, 3)

        # 지상국 위도 / 카메라 구경
        ctrl.addWidget(self._lbl("지상국 위도"), 2, 0)
        self.gs_lat = self._dspin(-90, 90, 37.5, 0.5, "°N")
        ctrl.addWidget(self.gs_lat, 2, 1, 1, 3)

        ctrl.addWidget(self._lbl("카메라 구경"), 3, 0)
        self.aperture = self._dspin(1, 200, 15.0, 1.0, "cm")
        ctrl.addWidget(self.aperture, 3, 1, 1, 3)

        lay.addLayout(ctrl)

        # 지표 선택
        lay.addWidget(self._sec("표시 지표"))
        self.metric_combo = QComboBox()
        self.metric_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        for key, label, unit, *_ in METRICS:
            self.metric_combo.addItem(f"{label}  ({unit})", key)
        self.metric_combo.setCurrentIndex(3)   # 접속 횟수 기본
        self.metric_combo.setFixedHeight(28)
        self.metric_combo.setStyleSheet("""
        QComboBox {
            background: rgba(14,30,48,0.90);
            border: 1px solid rgba(65,100,130,0.70);
            border-radius: 5px; color: #b8d8f0;
            font-size: 10px; font-weight: 700; padding: 0 8px;
        }
        QComboBox:hover { border: 1px solid rgba(0,210,255,0.60); }
        QComboBox::drop-down { border: none; width: 22px; }
        QComboBox::down-arrow {
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid rgba(0,200,255,0.80);
            margin-right: 6px;
        }
        QComboBox QAbstractItemView {
            background: #0a1e30; border: 1px solid rgba(0,180,240,0.45);
            color: #b8d8f0; selection-background-color: rgba(0,150,210,0.45);
            font-size: 10px; padding: 2px; outline: none;
        }
        """)
        self.metric_combo.currentIndexChanged.connect(self._on_metric_changed)
        lay.addWidget(self.metric_combo)

        # 실행 버튼
        run_btn = QPushButton("▶   CALCULATE GRID")
        run_btn.setFixedHeight(34)
        run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        run_btn.setStyleSheet("""
        QPushButton {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #0a4a6a, stop:1 #0077aa);
            color: #fff; border: 1px solid rgba(0,200,255,0.55);
            border-radius: 5px; font-size: 10px; font-weight: 800;
        }
        QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 #0a6a9a, stop:1 #00aadd); }
        """)
        run_btn.clicked.connect(self._run_study)
        lay.addWidget(run_btn)

        # ── 히트맵 테이블 ─────────────────────────────────────
        lay.addWidget(self._div())
        lay.addWidget(self._sec("ALTITUDE × INCLINATION  HEATMAP"))

        self._legend_lbl = QLabel("")
        self._legend_lbl.setStyleSheet("color: #4a7a90; font-size: 8px; font-style: italic;")
        lay.addWidget(self._legend_lbl)

        self.table = QTableWidget(self.INC_STEPS, self.ALT_STEPS)
        self.table.setFixedHeight(210)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet("""
        QTableWidget {
            background: rgba(8,16,28,0.95); gridline-color: rgba(255,255,255,0.06);
            border: 1px solid rgba(0,150,200,0.25); border-radius: 4px;
            color: #c0d8e8; font-size: 8px;
        }
        QHeaderView::section {
            background: rgba(0,40,65,0.80); color: #6ab8d0;
            border: none; padding: 2px; font-size: 7px; font-weight: 700;
        }
        QTableWidget::item:selected {
            background: rgba(0,200,255,0.25); color: #ffffff;
            border: 1px solid rgba(0,220,255,0.70);
        }
        """)
        self.table.itemDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.itemClicked.connect(self._on_cell_clicked)
        lay.addWidget(self.table)

        # 색 범례
        leg_row = QHBoxLayout()
        leg_row.setSpacing(6)
        for color_hex, txt in [("#1e2a3a", ""), ("#7c1e1e", "낮음/불량"),
                                ("#145a38", "높음/양호"), ("#2a6080", "SSO")]:
            lbl = QLabel(f"■ {txt}")
            lbl.setStyleSheet(f"color: {color_hex}; font-size: 8px;")
            leg_row.addWidget(lbl)
        leg_row.addStretch()
        lay.addLayout(leg_row)

        # ── 선택 셀 상세 ─────────────────────────────────────────
        lay.addWidget(self._div())
        lay.addWidget(self._sec("SELECTED ORBIT DETAILS"))

        self._detail_grid = QGridLayout()
        self._detail_grid.setSpacing(3)
        self._detail_labels: dict[str, QLabel] = {}

        detail_keys = [
            ("period_min",               "주기",       "min"),
            ("eclipse_max_min",          "최대 일식",  "min"),
            ("sunlight_fraction",        "일조율",     ""),
            ("contacts_per_day",         "접속/일",    "회"),
            ("contact_time_per_day_min", "접속시간",   "min"),
            ("gsd_m",                    "GSD",        "m"),
            ("tid_krad",                 "TID 5yr",    "krad"),
            ("delta_v_ms_yr",            "ΔV",         "m/s/yr"),
            ("power_margin_pct",         "전력마진",   "%"),
            ("revisit_hr",               "재방문",     "hr"),
        ]
        for idx, (key, label, unit) in enumerate(detail_keys):
            k_lbl = QLabel(f"{label}:")
            k_lbl.setStyleSheet("color: #5a8090; font-size: 9px;")
            v_lbl = QLabel("—")
            v_lbl.setStyleSheet("color: #b0d0e8; font-size: 9px; font-weight: 700;")
            v_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            self._detail_labels[key] = v_lbl
            r, c = divmod(idx, 2)
            self._detail_grid.addWidget(k_lbl, r, c * 2)
            self._detail_grid.addWidget(v_lbl, r, c * 2 + 1)
        lay.addLayout(self._detail_grid)

        # SSO 뱃지
        self._sso_badge = QLabel("")
        self._sso_badge.setStyleSheet(
            "color: #00f5d4; background: rgba(0,245,212,0.1);"
            "border: 1px solid rgba(0,245,212,0.4); border-radius: 3px;"
            "font-size: 8px; font-weight: 800; padding: 2px 6px;"
        )
        self._sso_badge.setVisible(False)
        lay.addWidget(self._sso_badge)

        # 추천 버튼
        self.apply_btn = QPushButton("🎯  APPLY TO ORBIT CONFIG")
        self.apply_btn.setFixedHeight(36)
        self.apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_btn.setEnabled(False)
        self.apply_btn.setStyleSheet("""
        QPushButton {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #004466, stop:1 #006688);
            color: #c8dde8; border: 1px solid rgba(0,160,200,0.50);
            border-radius: 5px; font-size: 10px; font-weight: 800;
        }
        QPushButton:enabled {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #00527a, stop:1 #0099cc);
            color: #fff; border: 1px solid rgba(0,230,255,0.60);
        }
        QPushButton:enabled:hover {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #007aa8, stop:1 #00ccee);
        }
        """)
        self.apply_btn.clicked.connect(self._on_apply)
        lay.addWidget(self.apply_btn)

        lay.addSpacerItem(QSpacerItem(0, 8, QSizePolicy.Policy.Minimum,
                                       QSizePolicy.Policy.Expanding))

        scroll.setWidget(inner)
        root.addWidget(scroll)
        self.setStyleSheet("#paramStudyPanel { background: rgba(8,18,32,0.94); }")

        # 신호 연결 & 초기 계산
        for w in [self.alt_lo, self.alt_hi, self.inc_lo, self.inc_hi,
                  self.gs_lat, self.aperture]:
            w.valueChanged.connect(lambda _: self._debounce.start(500))

        self._run_study()

    # ── 헬퍼 위젯 ────────────────────────────────────────────────
    def _sec(self, txt: str) -> QLabel:
        l = QLabel(txt)
        l.setStyleSheet("color: #6ab8d0; font-size: 9px; font-weight: 800;"
                        "letter-spacing: 2.5px; padding: 4px 0 2px 0;")
        return l

    def _div(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setFixedHeight(1)
        f.setStyleSheet("background: rgba(255,255,255,0.08); border: none;")
        return f

    def _lbl(self, txt: str) -> QLabel:
        l = QLabel(txt)
        l.setStyleSheet("color: #8ab4c8; font-size: 9px;")
        return l

    def _spin(self, lo, hi, val, step, suffix) -> QSpinBox:
        s = QSpinBox()
        s.setRange(lo, hi); s.setValue(val); s.setSingleStep(step)
        s.setSuffix(f" {suffix}"); s.setFixedHeight(24)
        s.setStyleSheet("""
        QSpinBox { background: rgba(14,28,44,0.85); border: 1px solid rgba(55,90,115,0.65);
            border-radius: 4px; color: #b8d8f0; font-size: 9px; padding: 0 4px; }
        QSpinBox::up-button, QSpinBox::down-button { width: 16px; }
        """)
        return s

    def _dspin(self, lo, hi, val, step, suffix) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(lo, hi); s.setValue(val); s.setSingleStep(step)
        s.setSuffix(f" {suffix}"); s.setFixedHeight(24)
        s.setStyleSheet("""
        QDoubleSpinBox { background: rgba(14,28,44,0.85); border: 1px solid rgba(55,90,115,0.65);
            border-radius: 4px; color: #b8d8f0; font-size: 9px; padding: 0 4px; }
        QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 16px; }
        """)
        return s

    # ── 계산 ─────────────────────────────────────────────────────
    def _run_study(self):
        alt_lo = min(self.alt_lo.value(), self.alt_hi.value())
        alt_hi = max(self.alt_lo.value(), self.alt_hi.value())
        inc_lo = min(self.inc_lo.value(), self.inc_hi.value())
        inc_hi = max(self.inc_lo.value(), self.inc_hi.value())

        self._result = self._svc.sweep(
            alt_range  = (alt_lo, alt_hi),
            inc_range  = (inc_lo, inc_hi),
            alt_steps  = self.ALT_STEPS,
            inc_steps  = self.INC_STEPS,
            aperture_cm= self.aperture.value(),
            gs_lat     = self.gs_lat.value(),
        )
        self._refresh_table()

    def _on_metric_changed(self, idx: int):
        key = self.metric_combo.itemData(idx)
        meta = next((m for m in METRICS if m[0] == key), None)
        if meta:
            self._metric_key    = meta[0]
            self._metric_higher = meta[3]
        if self._result:
            self._refresh_table()

    def _refresh_table(self):
        r = self._result
        if not r:
            return

        key = self._metric_key
        higher_better = self._metric_higher

        # 헤더
        self.table.setColumnCount(r.alt_steps)
        self.table.setRowCount(r.inc_steps)
        self.table.setHorizontalHeaderLabels([f"{int(a)}km" for a in r.alt_values])
        self.table.setVerticalHeaderLabels([f"{inc:.0f}°" for inc in r.inc_values])

        # 최솟값/최댓값 수집
        vals = []
        for row in r.grid:
            for pt in row:
                v = getattr(pt, key, 0.0)
                vals.append(v)
        v_min = min(vals)
        v_max = max(vals)
        v_range = max(v_max - v_min, 1e-9)

        # 지표 포맷 문자열
        meta = next((m for m in METRICS if m[0] == key), None)
        fmt   = meta[4] if meta else "{:.1f}"
        unit  = meta[2] if meta else ""

        self._legend_lbl.setText(
            f"  범위: {v_min:.2g} ~ {v_max:.2g} {unit}  "
            f"({'높을수록 ✓' if higher_better else '낮을수록 ✓'})"
        )

        for row_i, (inc, row) in enumerate(zip(r.inc_values, r.grid)):
            for col_i, pt in enumerate(row):
                v = getattr(pt, key, 0.0)
                t = (v - v_min) / v_range        # 0~1
                if not higher_better:
                    t = 1.0 - t                  # 낮을수록 좋으면 반전

                # 색상 보간
                if pt.is_sso:
                    bg = QColor(14, 55, 100)     # SSO: 파란 강조
                else:
                    bg = _lerp_color(t, COLOR_BAD, COLOR_GOOD)

                txt_v = fmt.format(v)
                if key == "sunlight_fraction":
                    txt_v = f"{v*100:.1f}%"

                item = QTableWidgetItem(txt_v)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setBackground(QBrush(bg))
                # 밝기에 따른 글자색
                brightness = (bg.red() * 299 + bg.green() * 587 + bg.blue() * 114) / 1000
                item.setForeground(QBrush(QColor(220, 240, 255) if brightness < 80
                                          else QColor(10, 20, 30)))
                # 포인트 데이터 저장
                item.setData(Qt.ItemDataRole.UserRole, pt)
                self.table.setItem(row_i, col_i, item)

    # ── 셀 이벤트 ────────────────────────────────────────────────
    def _on_cell_clicked(self, item: QTableWidgetItem):
        pt: Optional[ParamPoint] = item.data(Qt.ItemDataRole.UserRole)
        if not pt:
            return
        self._selected_point = pt
        self._update_detail(pt)

    def _on_cell_double_clicked(self, item: QTableWidgetItem):
        self._on_cell_clicked(item)
        self._on_apply()

    def _update_detail(self, pt: ParamPoint):
        fmts = {k: f for k, _, _, _, f in METRICS}
        for key, lbl in self._detail_labels.items():
            v = getattr(pt, key, None)
            if v is None:
                lbl.setText("—")
                continue
            fmt = fmts.get(key, "{:.1f}")
            if key == "sunlight_fraction":
                lbl.setText(f"{v*100:.1f}%")
            else:
                lbl.setText(fmt.format(v))

        # SSO 뱃지
        if pt.is_sso:
            self._sso_badge.setText(f"  ☀️  SSO  (i ≈ {pt.inclination_deg:.1f}°)  ")
            self._sso_badge.setVisible(True)
        else:
            self._sso_badge.setVisible(False)

        self.apply_btn.setEnabled(True)

    def _on_apply(self):
        pt = self._selected_point
        if not pt:
            return
        o = OrbitParams(
            altitude_km     = pt.altitude_km,
            inclination_deg = pt.inclination_deg,
            orbit_type      = "SSO" if pt.is_sso else "LEO",
            duration_days   = 3.0,
        )
        self.orbit_selected.emit(o)

    # ── 외부 API ─────────────────────────────────────────────────
    def set_aperture(self, aperture_cm: float):
        self.aperture.setValue(aperture_cm)

    def set_gs_lat(self, lat: float):
        self.gs_lat.setValue(lat)
