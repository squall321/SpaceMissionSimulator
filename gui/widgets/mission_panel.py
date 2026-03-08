"""
Mission Panel Widget — v2 (UX 개선)
임무 유형 선택 + 요구사항 정의 + 궤도 추천 + 달성도 평가
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QGridLayout, QFrame, QScrollArea, QButtonGroup,
    QSizePolicy, QSpacerItem, QComboBox
)
from PySide6.QtCore import Signal, Qt, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui  import QFont, QPainter, QColor, QPen, QBrush, QLinearGradient, QRadialGradient, QPainterPath

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.domain.orbit import OrbitParams, GroundStation


# ── 데이터 클래스 ─────────────────────────────────────────────────
@dataclass
class MissionRequirements:
    mission_type:        str   = "earth_obs"
    lifetime_yr:         float = 3.0
    revisit_hr:          float = 12.0
    resolution_m:        float = 5.0
    downlink_gb_day:     float = 10.0
    min_contact_min_day: float = 15.0
    coverage:            str   = "regional"


# ── 미션 타입 정의 ────────────────────────────────────────────────
MISSION_TYPES = [
    {
        "key": "earth_obs", "icon": "🌍", "name": "지구관측",
        "desc": "광학·SAR 고해상도\n반복 관측",
        "color": "#00b4d8",
        "orbit_hint": {"alt": (400, 700), "inc": (97.0, 99.0), "type": "SSO"},
    },
    {
        "key": "comm", "icon": "📡", "name": "통신",
        "desc": "광대역 위성통신\n고속 데이터 릴레이",
        "color": "#4cc9f0",
        "orbit_hint": {"alt": (500, 1200), "inc": (53.0, 70.0), "type": "LEO_EQ"},
    },
    {
        "key": "science", "icon": "🔬", "name": "과학탐사",
        "desc": "우주환경 계측\n대기·자기장 관측",
        "color": "#b56bff",
        "orbit_hint": {"alt": (350, 600), "inc": (90.0, 105.0), "type": "LEO_POLAR"},
    },
    {
        "key": "weather", "icon": "☀️", "name": "기상",
        "desc": "기상·기후 관측\n전지구 재방문",
        "color": "#f77f00",
        "orbit_hint": {"alt": (500, 850), "inc": (97.5, 99.5), "type": "SSO"},
    },
    {
        "key": "defense", "icon": "🛡️", "name": "국방/안보",
        "desc": "ISR·전자전\n긴급 재방문",
        "color": "#ff4d4d",
        "orbit_hint": {"alt": (300, 500), "inc": (97.0, 98.5), "type": "SSO"},
    },
    {
        "key": "space_dc", "icon": "🏢", "name": "우주 DC",
        "desc": "우주데이터센터\n별도 구성 예정",
        "color": "#00f5d4",
        "coming_soon": True,
        "orbit_hint": {"alt": (550, 600), "inc": (97.5, 98.0), "type": "DDSSO"},
    },
]


# ══════════════════════════════════════════════════════════════════
#  ReqSlider — min/max 범위 표시 + 밝은 글자
# ══════════════════════════════════════════════════════════════════
class ReqSlider(QWidget):
    value_changed = Signal(float)

    def __init__(self, label: str, unit: str,
                 mn: float, mx: float, default: float,
                 decimals: int = 0, steps: int = 200):
        super().__init__()
        self._mn = mn
        self._mx = mx
        self._decimals = decimals
        self._steps = steps
        self._unit = unit

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 5, 0, 3)
        root.setSpacing(0)

        # ① 라벨 행 (이름 + 현재값)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 3)

        name_lbl = QLabel(label)
        name_lbl.setStyleSheet(
            "color: #b8d4e8; font-size: 11px; font-weight: 600;"
        )

        self._val_lbl = QLabel(self._fmt(default))
        self._val_lbl.setStyleSheet(
            "color: #00e8ff; font-size: 14px; font-weight: 800;"
        )
        self._val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        top.addWidget(name_lbl)
        top.addStretch()
        top.addWidget(self._val_lbl)
        root.addLayout(top)

        # ② 슬라이더
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, steps)
        self.slider.setValue(self._to_step(default))
        self.slider.setFixedHeight(24)
        self.slider.setStyleSheet("""
        QSlider::groove:horizontal {
            height: 6px;
            background: rgba(255,255,255,0.10);
            border: 1px solid rgba(255,255,255,0.14);
            border-radius: 3px;
        }
        QSlider::handle:horizontal {
            width: 18px; height: 18px;
            background: qradialgradient(cx:.5,cy:.5,radius:.5,fx:.5,fy:.5,
                stop:0 #ffffff, stop:0.4 #00e8ff, stop:1 #006699);
            border: 2px solid rgba(255,255,255,0.80);
            border-radius: 9px;
            margin: -7px 0;
        }
        QSlider::handle:horizontal:hover {
            width: 20px; height: 20px;
            margin: -8px 0;
            border: 2px solid #ffffff;
            background: qradialgradient(cx:.5,cy:.5,radius:.5,fx:.5,fy:.5,
                stop:0 #ffffff, stop:0.35 #00ffff, stop:1 #0099bb);
        }
        QSlider::sub-page:horizontal {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #005588, stop:1 #00ddf0);
            border-radius: 3px;
        }
        QSlider::add-page:horizontal {
            background: rgba(255,255,255,0.06);
            border-radius: 3px;
        }
        """)
        self.slider.valueChanged.connect(self._on_change)
        root.addWidget(self.slider)

        # ③ min / max 범위 레이블
        range_row = QHBoxLayout()
        range_row.setContentsMargins(2, 1, 2, 0)

        mn_lbl = QLabel(self._fmt_range(mn))
        mn_lbl.setStyleSheet("color: #4a8090; font-size: 9px; font-weight: 600;")

        mx_lbl = QLabel(self._fmt_range(mx))
        mx_lbl.setStyleSheet("color: #4a8090; font-size: 9px; font-weight: 600;")
        mx_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        range_row.addWidget(mn_lbl)
        range_row.addStretch()
        range_row.addWidget(mx_lbl)
        root.addLayout(range_row)

        # ④ 구분선
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255,255,255,0.06); border:none; margin-top:5px;")
        root.addWidget(sep)

    def _fmt(self, v: float) -> str:
        return f"{v:.{self._decimals}f} {self._unit}"

    def _fmt_range(self, v: float) -> str:
        return f"{v:.{self._decimals}f} {self._unit}"

    def _to_step(self, v: float) -> int:
        return int((v - self._mn) / (self._mx - self._mn) * self._steps)

    def _to_val(self, s: int) -> float:
        return self._mn + s / self._steps * (self._mx - self._mn)

    def _on_change(self, s: int):
        v = self._to_val(s)
        self._val_lbl.setText(self._fmt(v))
        self.value_changed.emit(v)

    def value(self) -> float:
        return self._to_val(self.slider.value())

    def set_value(self, v: float):
        self.slider.blockSignals(True)
        self.slider.setValue(self._to_step(max(self._mn, min(self._mx, v))))
        self.slider.blockSignals(False)
        self._val_lbl.setText(self._fmt(v))


# ══════════════════════════════════════════════════════════════════
#  MissionTypeCard — QPainter 커스텀 렌더링
# ══════════════════════════════════════════════════════════════════
class MissionTypeCard(QPushButton):
    """컬러 상단 액센트 바 + 글로우 테두리 + 호버 페이드 카드"""

    def __init__(self, info: dict):
        super().__init__()
        self.setCheckable(True)
        self.info      = info
        self._color    = info["color"]
        self._coming   = info.get("coming_soon", False)
        self._hover    = False
        self._c        = QColor(self._color)   # accent QColor
        self.setFixedHeight(86)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        # 배경 없는 투명 베이스 (paintEvent에서 직접 그림)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setStyleSheet("border: none; background: transparent;")

        # ── 자식 위젯 ──────────────────────────────────────────
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 28, 10, 8)   # 상단 28px = 액센트 바 높이 이후
        lay.setSpacing(2)

        # 아이콘 + 이름 한 줄
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self._icon_lbl = QLabel(info["icon"])
        self._icon_lbl.setFont(QFont("Segoe UI Emoji", 18))
        self._icon_lbl.setStyleSheet("background: transparent; border: none;")
        self._icon_lbl.setFixedWidth(28)
        row.addWidget(self._icon_lbl)

        name_col = QVBoxLayout()
        name_col.setSpacing(0)
        self._name_lbl = QLabel(info["name"])
        self._name_lbl.setStyleSheet(
            "color: #ffffff; background: transparent; border: none;"
            "font-size: 11px; font-weight: 800;"
        )
        name_col.addWidget(self._name_lbl)

        self._desc_lbl = QLabel(info["desc"].replace("\n", "  "))
        self._desc_lbl.setStyleSheet(
            "color: rgba(200,228,245,0.72); background: transparent; border: none;"
            "font-size: 8px;"
        )
        name_col.addWidget(self._desc_lbl)
        row.addLayout(name_col, 1)

        if self._coming:
            soon = QLabel("SOON")
            soon.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            soon.setStyleSheet(
                "color: #00f5d4; background: rgba(0,245,212,0.15);"
                "border: 1px solid rgba(0,245,212,0.5); border-radius: 3px;"
                "font-size: 7px; font-weight: 800; padding: 1px 4px;"
            )
            row.addWidget(soon)

        lay.addLayout(row)

    # ── 호버 감지 ────────────────────────────────────────────────
    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def nextCheckState(self):
        if not self._coming:
            super().nextCheckState()

    def setChecked(self, v: bool):
        super().setChecked(v)
        self._name_lbl.setStyleSheet(
            f"color: {'#ffffff' if v else 'rgba(210,230,245,0.92)'};"
            "background: transparent; border: none;"
            "font-size: 11px; font-weight: 800;"
        )
        self.update()

    # ── 커스텀 페인트 ────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        r     = 8          # corner radius
        c     = self._c
        chk   = self.isChecked()
        hov   = self._hover and not self._coming

        # ── 1. 배경 ──────────────────────────────────────────────
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, r, r)

        if self._coming:
            bg = QColor(10, 32, 30, 120)
        elif chk:
            bg = QColor(c.red(), c.green(), c.blue(), 52)
        elif hov:
            bg = QColor(c.red(), c.green(), c.blue(), 30)
        else:
            bg = QColor(16, 30, 48, 185)

        p.fillPath(path, QBrush(bg))

        # ── 2. 테두리 ────────────────────────────────────────────
        if self._coming:
            pen = QPen(QColor(0, 245, 212, 80), 1, Qt.PenStyle.DashLine)
        elif chk:
            pen = QPen(c, 2)
        elif hov:
            pen = QPen(QColor(c.red(), c.green(), c.blue(), 180), 1.5)
        else:
            pen = QPen(QColor(60, 85, 110, 160), 1)
        p.setPen(pen)
        p.drawPath(path)

        # ── 3. 상단 액센트 바 (선택/호버 시 컬러) ──────────────
        bar_h = 3
        bar_path = QPainterPath()
        bar_path.addRoundedRect(0, 0, w, bar_h + r, r, r)
        # 하단을 평평하게 자름
        bar_path.addRect(0, bar_h, w, r)

        if self._coming:
            bar_alpha = 60
        elif chk:
            bar_alpha = 255
        elif hov:
            bar_alpha = 160
        else:
            bar_alpha = 55

        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0, QColor(c.red(), c.green(), c.blue(), bar_alpha))
        grad.setColorAt(1, QColor(c.red(), c.green(), c.blue(),
                                   max(0, bar_alpha - 80)))
        p.fillPath(bar_path, QBrush(grad))

        # ── 4. 선택 시 글로우 ────────────────────────────────────
        if chk:
            glow = QRadialGradient(w / 2, 0, w * 0.7)
            glow.setColorAt(0,   QColor(c.red(), c.green(), c.blue(), 40))
            glow.setColorAt(0.6, QColor(c.red(), c.green(), c.blue(), 12))
            glow.setColorAt(1,   QColor(0, 0, 0, 0))
            p.fillPath(path, QBrush(glow))

        # ── 5. 호버 시 우측 하이라이트 점 ───────────────────────
        if hov and not chk:
            dot = QRadialGradient(w - 12, h - 12, 16)
            dot.setColorAt(0,   QColor(c.red(), c.green(), c.blue(), 50))
            dot.setColorAt(1,   QColor(0, 0, 0, 0))
            p.fillPath(path, QBrush(dot))

        p.end()
        # 자식 위젯은 Qt가 자동으로 그림
        super().paintEvent(event)


# ══════════════════════════════════════════════════════════════════
#  커버리지 국가/지역 데이터  (key → [(표시명, lat_min, lat_max), ...])
# ══════════════════════════════════════════════════════════════════
# (name, center_lat, center_lon, lat_min, lat_max)
COVERAGE_TARGETS: dict[str, list[tuple]] = {
    "regional": [
        ("한반도 권역",   37.5,  127.0,  33.0,  43.0),
        ("동아시아",      35.0,  120.0,  20.0,  50.0),
        ("동남아시아",    10.0,  108.0,   5.0,  20.0),
        ("남아시아",      20.0,   78.0,   8.0,  36.0),
        ("중동",          28.0,   45.0,  20.0,  37.0),
        ("유럽",          50.0,   15.0,  36.0,  70.0),
        ("북미",          38.0,  -95.0,  25.0,  50.0),
        ("남미",         -15.0,  -55.0, -55.0,  10.0),
        ("아프리카",       0.0,   20.0, -35.0,  37.0),
        ("오세아니아",   -25.0,  135.0, -44.0, -10.0),
    ],
    "national": [
        ("대한민국 🇰🇷",  36.5,  127.5,  34.0,  38.5),
        ("일본 🇯🇵",      36.0,  138.0,  31.0,  45.5),
        ("중국 🇨🇳",      35.0,  105.0,  18.0,  53.5),
        ("미국 🇺🇸",      38.0,  -97.0,  25.0,  49.0),
        ("러시아 🇷🇺",    60.0,   60.0,  50.0,  72.0),
        ("인도 🇮🇳",      22.0,   78.0,   8.0,  36.0),
        ("호주 🇦🇺",     -27.0,  133.0, -44.0, -10.0),
        ("브라질 🇧🇷",   -15.0,  -47.0, -33.0,   5.0),
        ("독일 🇩🇪",      51.0,   10.0,  47.5,  55.0),
        ("영국 🇬🇧",      53.0,   -1.5,  50.0,  59.0),
        ("프랑스 🇫🇷",    46.0,    2.5,  42.5,  51.0),
        ("이스라엘 🇮🇱",  31.5,   34.8,  29.5,  33.5),
        ("UAE 🇦🇪",       24.2,   54.4,  22.5,  26.0),
        ("사우디 🇸🇦",    24.0,   45.0,  16.5,  32.0),
        ("싱가포르 🇸🇬",   1.3,  103.8,   1.1,   1.5),
        ("캐나다 🇨🇦",    60.0,  -96.0,  42.0,  83.0),
    ],
    "global":  [],
}


# ══════════════════════════════════════════════════════════════════
#  CoverageSection  (3-way toggle + 국가/지역 드롭다운)
# ══════════════════════════════════════════════════════════════════
class CoverageSection(QWidget):
    """커버리지 타입 선택 + 국가/지역 드롭다운이 통합된 위젯"""
    changed = Signal(str)   # 'regional' | 'national' | 'global'

    _TOGGLE_OPTIONS = [
        ("regional", "지역"),
        ("national", "국가"),
        ("global",   "전지구"),
    ]
    _INACTIVE = (
        "QPushButton {"
        "  background: rgba(20,38,56,0.75);"
        "  border: 1px solid rgba(65,88,108,0.65);"
        "  border-radius: 5px; color: #90b4c8;"
        "  font-size: 9px; font-weight: 700;"
        "}"
        "QPushButton:hover {"
        "  border: 1px solid rgba(0,220,255,0.55); color: #c8e4f0;"
        "  background: rgba(0,100,140,0.20);"
        "}"
    )
    _ACTIVE = (
        "QPushButton {"
        "  background: rgba(0,165,210,0.30);"
        "  border: 2px solid rgba(0,220,255,0.85);"
        "  border-radius: 5px; color: #00eeff;"
        "  font-size: 9px; font-weight: 800;"
        "}"
    )

    def __init__(self):
        super().__init__()
        self._cov_type = "regional"

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        # ── 3-way 토글 ─────────────────────────────────────────
        toggle_row = QHBoxLayout()
        toggle_row.setContentsMargins(0, 0, 0, 0)
        toggle_row.setSpacing(4)
        self._btns: dict[str, QPushButton] = {}
        for key, label in self._TOGGLE_OPTIONS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._select_type(k))
            self._btns[key] = btn
            toggle_row.addWidget(btn)
        root.addLayout(toggle_row)

        # ── 대상 선택 드롭다운 ──────────────────────────────────
        self._combo = QComboBox()
        self._combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self._combo.setFixedHeight(30)
        self._combo.setStyleSheet("""
        QComboBox {
            background: rgba(14,30,48,0.90);
            border: 1px solid rgba(65,100,130,0.70);
            border-radius: 5px;
            color: #b8d8f0;
            font-size: 10px; font-weight: 700;
            padding: 0 8px;
        }
        QComboBox:hover {
            border: 1px solid rgba(0,210,255,0.60);
            color: #d8f0ff;
        }
        QComboBox::drop-down { border: none; width: 22px; }
        QComboBox::down-arrow {
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid rgba(0,200,255,0.80);
            margin-right: 6px;
        }
        QComboBox QAbstractItemView {
            background: #0a1e30;
            border: 1px solid rgba(0,180,240,0.45);
            color: #b8d8f0;
            selection-background-color: rgba(0,150,210,0.45);
            selection-color: #ffffff;
            font-size: 10px;
            padding: 2px;
            outline: none;
        }
        """)
        root.addWidget(self._combo)

        # 초기화
        self._select_type("regional")

    def _select_type(self, key: str):
        self._cov_type = key
        for k, btn in self._btns.items():
            btn.setStyleSheet(self._ACTIVE if k == key else self._INACTIVE)

        targets = COVERAGE_TARGETS.get(key, [])
        self._combo.blockSignals(True)
        self._combo.clear()
        if targets:
            for name, *_ in targets:
                self._combo.addItem(name)
            self._combo.setVisible(True)
        else:
            self._combo.addItem("전지구 커버리지")
            self._combo.setVisible(False)
        self._combo.blockSignals(False)

        self.changed.emit(key)

    # ── 공개 API ────────────────────────────────────────────────
    def value(self) -> str:
        """'regional' | 'national' | 'global'"""
        return self._cov_type

    def target_lat_range(self) -> tuple[float, float]:
        """선택된 지역의 위도 범위 (min_lat, max_lat). global → (0, 90)"""
        targets = COVERAGE_TARGETS.get(self._cov_type, [])
        if not targets:
            return (0.0, 90.0)
        idx = self._combo.currentIndex()
        if idx < 0 or idx >= len(targets):
            return (0.0, 90.0)
        name, lat_c, lon_c, lat_min, lat_max = targets[idx]
        return (lat_min, lat_max)

    def get_ground_station(self) -> Optional[GroundStation]:
        """선택 국가/지역 중심 좌표 → GroundStation 반환. global → None"""
        if self._cov_type == "global":
            return None
        targets = COVERAGE_TARGETS.get(self._cov_type, [])
        idx = self._combo.currentIndex()
        if idx < 0 or idx >= len(targets):
            return None
        name, lat_c, lon_c, lat_min, lat_max = targets[idx]
        gs_name = name.split(" ")[0]   # 이모지 제거
        return GroundStation(gs_name, lat_c, lon_c, 0.0, 5.0)

    def selected_target_name(self) -> str:
        if self._cov_type == "global":
            return "전지구"
        return self._combo.currentText()


# ══════════════════════════════════════════════════════════════════
#  StatusRow — 충족도 행
# ══════════════════════════════════════════════════════════════════
class StatusRow(QWidget):
    def __init__(self, label: str):
        super().__init__()
        self.setFixedHeight(28)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(8)

        self._icon = QLabel("—")
        self._icon.setFixedWidth(18)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel(label)
        self._label.setFixedWidth(72)
        self._label.setStyleSheet("color: #94bcd0; font-size: 10px; font-weight: 600;")

        self._actual = QLabel("—")
        self._actual.setStyleSheet("color: #c8e0f0; font-size: 11px; font-weight: 700;")

        self._req = QLabel("")
        self._req.setStyleSheet("color: #526878; font-size: 9px;")
        self._req.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        lay.addWidget(self._icon)
        lay.addWidget(self._label)
        lay.addWidget(self._actual)
        lay.addStretch()
        lay.addWidget(self._req)

        self.setStyleSheet("StatusRow { background: rgba(255,255,255,0.03); border-radius: 4px; }")

    def update(self, actual: str, required: str, met: Optional[bool]):
        self._actual.setText(actual)
        self._req.setText(f"/ req {required}")
        if met is None:
            self._icon.setText("–")
            self._icon.setStyleSheet("color: #526878; font-size: 12px;")
            self._actual.setStyleSheet("color: #c8e0f0; font-size: 11px; font-weight: 700;")
            self.setStyleSheet("StatusRow { background: rgba(255,255,255,0.03); border-radius: 4px; }")
        elif met:
            self._icon.setText("✓")
            self._icon.setStyleSheet("color: #00ff88; font-size: 14px; font-weight: 900;")
            self._actual.setStyleSheet("color: #00ff88; font-size: 11px; font-weight: 800;")
            self.setStyleSheet(
                "StatusRow { background: rgba(0,255,136,0.06);"
                "  border-radius: 4px; border-left: 2px solid #00cc66; }"
            )
        else:
            self._icon.setText("✗")
            self._icon.setStyleSheet("color: #ff5555; font-size: 14px; font-weight: 900;")
            self._actual.setStyleSheet("color: #ff6666; font-size: 11px; font-weight: 800;")
            self.setStyleSheet(
                "StatusRow { background: rgba(255,60,60,0.07);"
                "  border-radius: 4px; border-left: 2px solid #cc3333; }"
            )


# ══════════════════════════════════════════════════════════════════
#  MissionPanel
# ══════════════════════════════════════════════════════════════════
class MissionPanel(QWidget):
    orbit_recommended    = Signal(OrbitParams)
    requirements_changed = Signal(object)

    def __init__(self):
        super().__init__()
        self.setObjectName("missionPanel")
        self._selected_type = "earth_obs"
        self._card_btns: dict[str, MissionTypeCard] = {}

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
        QScrollBar::handle:vertical:hover { background: rgba(0,220,255,0.35); }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(14, 10, 14, 14)
        lay.setSpacing(10)

        # ── 패널 헤더 ─────────────────────────────────────────
        hdr = QLabel("🎯  MISSION DEFINITION")
        hdr.setStyleSheet("""
            color: #e8f4ff;
            font-size: 12px; font-weight: 900;
            letter-spacing: 3px; padding: 6px 0 8px 0;
            border-bottom: 1px solid rgba(0,220,255,0.40);
        """)
        lay.addWidget(hdr)

        # ── 미션 타입 카드 ────────────────────────────────────
        lay.addWidget(self._sec("MISSION TYPE"))
        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setContentsMargins(0, 2, 0, 2)
        bg = QButtonGroup(self)
        bg.setExclusive(True)
        for i, info in enumerate(MISSION_TYPES):
            card = MissionTypeCard(info)
            if not info.get("coming_soon"):
                bg.addButton(card)
                card.clicked.connect(lambda _, k=info["key"]: self._on_type_selected(k))
            self._card_btns[info["key"]] = card
            grid.addWidget(card, i // 3, i % 3)
        self._card_btns["earth_obs"].setChecked(True)
        lay.addLayout(grid)

        # ── 요구사항 슬라이더 ─────────────────────────────────
        lay.addWidget(self._div())
        lay.addWidget(self._sec("MISSION REQUIREMENTS"))

        self.s_life    = ReqSlider("임무 수명",      "yr",   1,   15,   3,  1)
        self.s_revisit = ReqSlider("재방문 주기",    "hr",   1,   48,  12,  1)
        self.s_resol   = ReqSlider("지상 해상도",    "m",  0.5,   30,   5,  1)
        self.s_link    = ReqSlider("일일 다운링크",  "GB",   1,  100,  10,  0)
        self.s_contact = ReqSlider("최소 접속시간",  "min",  5,  120,  15,  0)
        for s in [self.s_life, self.s_revisit, self.s_resol, self.s_link, self.s_contact]:
            lay.addWidget(s)

        # ── 커버리지 ──────────────────────────────────────────
        lay.addWidget(self._sec("COVERAGE TARGET"))
        self.coverage = CoverageSection()
        lay.addWidget(self.coverage)

        # ── 추천 버튼 ─────────────────────────────────────────
        lay.addWidget(self._div())
        self.recommend_btn = QPushButton("🎯   RECOMMEND ORBIT  →  ANALYZE")
        self.recommend_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.recommend_btn.setFixedHeight(44)
        self.recommend_btn.setStyleSheet("""
        QPushButton {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #00527a, stop:1 #0099cc);
            color: #ffffff;
            border: 1px solid rgba(0,230,255,0.60);
            border-radius: 6px;
            font-size: 12px; font-weight: 900; letter-spacing: 1px;
        }
        QPushButton:hover {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #007aa8, stop:1 #00ccee);
            border: 1px solid rgba(0,255,255,0.90);
        }
        QPushButton:pressed { background: #002a44; }
        """)
        self.recommend_btn.clicked.connect(self._on_recommend)
        lay.addWidget(self.recommend_btn)

        # ── 충족도 ────────────────────────────────────────────
        lay.addWidget(self._div())
        lay.addWidget(self._sec("REQUIREMENT STATUS"))

        self._st_revisit = StatusRow("재방문 주기")
        self._st_contact = StatusRow("접속 시간")
        self._st_link    = StatusRow("다운링크")
        self._st_life    = StatusRow("임무 수명")
        self._st_resol   = StatusRow("해상도 적합")

        st_wrap = QVBoxLayout()
        st_wrap.setSpacing(3)
        for w in [self._st_revisit, self._st_contact,
                  self._st_link, self._st_life, self._st_resol]:
            st_wrap.addWidget(w)
        lay.addLayout(st_wrap)

        self._hint_lbl = QLabel("  ▶  RECOMMEND 실행 후 충족도가 표시됩니다")
        self._hint_lbl.setStyleSheet(
            "color: #3a6070; font-size: 9px; font-style: italic; padding: 4px 0 0 4px;"
        )
        lay.addWidget(self._hint_lbl)

        lay.addSpacerItem(QSpacerItem(
            0, 16, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        ))

        scroll.setWidget(inner)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        self.setStyleSheet("#missionPanel { background: rgba(8,18,32,0.94); }")

    # ── 헬퍼 ────────────────────────────────────────────────────
    def _sec(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #6ab8d0; font-size: 9px; font-weight: 800;"
            "letter-spacing: 2.5px; padding: 4px 0 2px 0;"
        )
        return lbl

    def _div(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setFixedHeight(1)
        f.setStyleSheet("background: rgba(255,255,255,0.08); border: none;")
        return f

    # ── 이벤트 ──────────────────────────────────────────────────
    def _on_type_selected(self, key: str):
        self._selected_type = key
        presets = {
            "earth_obs": (3,  12,  5,  10,  20),
            "comm":      (5,   1, 30,  50,  30),
            "science":   (3,  24, 20,   5,  10),
            "weather":   (5,   6, 20,  15,  25),
            "defense":   (5,   3,  1,  20,  15),
            "space_dc":  (7,   6, 10, 100,  60),
        }
        if key in presets:
            life, rev, res, dl, ct = presets[key]
            self.s_life.set_value(float(life))
            self.s_revisit.set_value(float(rev))
            self.s_resol.set_value(min(float(res), 30.0))
            self.s_link.set_value(min(float(dl), 100.0))
            self.s_contact.set_value(min(float(ct), 120.0))

    def _on_recommend(self):
        info   = next(m for m in MISSION_TYPES if m["key"] == self._selected_type)
        hint   = info["orbit_hint"]
        rev_hr = self.s_revisit.value()
        cov    = self.coverage.value()
        o_type = hint["type"]

        # ── 고도 추천 (재방문 주기에 따라) ──────────────────────
        alt_lo, alt_hi = hint["alt"]
        alt = (alt_lo if rev_hr <= 3
               else (alt_lo + alt_hi) / 2 if rev_hr <= 12
               else alt_hi)

        # ── 경사각 추천 (위도 기반) ──────────────────────────────
        inc_lo, inc_hi = hint["inc"]
        if cov == "global":
            # SSO 계열은 항상 hint_hi; 적도계열은 최대 inclination
            inc = inc_hi
        else:
            lat_min, lat_max = self.coverage.target_lat_range()
            target_lat = abs(lat_max)   # 커버해야 할 최대 위도

            if o_type in ("SSO", "DDSSO"):
                # SSO: LTAN 계산 → 경사각 = 97~99° 고정, 고도에 따라 미세 조정
                # i ≈ 90.0 + acos(-3/2 * J2 * Re² / (a²) * ...) → 근사식:
                # i_sso ≈ 97.8 + 0.0016 * (alt - 500)
                inc = 97.8 + 0.0016 * (alt - 500.0)
                inc = max(inc_lo, min(inc_hi, inc))
            else:
                # 비 SSO: 경사각 ≥ target_lat (커버리지 확보)
                # 지구관측/통신: 최적값 = max(hint_lo, target_lat + 5°)
                inc_from_lat = target_lat + 5.0
                inc = max(inc_lo, min(inc_hi, inc_from_lat))

        raan = 90.0 if o_type == "DDSSO" else 0.0

        self.orbit_recommended.emit(OrbitParams(
            altitude_km     = round(alt),
            inclination_deg = round(inc, 1),
            raan_deg        = raan,
            orbit_type      = o_type,
            duration_days   = 3.0,
        ))

    def get_requirements(self) -> MissionRequirements:
        return MissionRequirements(
            mission_type         = self._selected_type,
            lifetime_yr          = self.s_life.value(),
            revisit_hr           = self.s_revisit.value(),
            resolution_m         = self.s_resol.value(),
            downlink_gb_day      = self.s_link.value(),
            min_contact_min_day  = self.s_contact.value(),
            coverage             = self.coverage.value(),
        )

    def get_coverage_ground_station(self) -> Optional[GroundStation]:
        """커버리지에서 선택된 국가/지역 중심 지상국 반환. global → None"""
        return self.coverage.get_ground_station()

    def update_status(self, orbit_result, budget_result=None, aperture_cm: float = 15.0):
        self._hint_lbl.setVisible(False)
        req = self.get_requirements()

        actual_rev = (24.0 / orbit_result.contacts_per_day
                      if orbit_result.contacts_per_day > 0 else 999.0)
        self._st_revisit.update(
            f"{actual_rev:.1f} hr", f"{req.revisit_hr:.1f} hr",
            actual_rev <= req.revisit_hr
        )

        ct = orbit_result.contact_time_per_day_min
        self._st_contact.update(
            f"{ct:.1f} min", f"{req.min_contact_min_day:.0f} min",
            ct >= req.min_contact_min_day
        )

        dl = budget_result.data_per_day_gb if budget_result else 0.0
        self._st_link.update(
            f"{dl:.1f} GB", f"{req.downlink_gb_day:.0f} GB",
            dl >= req.downlink_gb_day
        )

        life_ok = orbit_result.params.altitude_km >= 400
        self._st_life.update(
            "OK" if life_ok else "LOW ALT",
            f"{req.lifetime_yr:.0f} yr", life_ok
        )

        # GSD = 1.22 × λ × h / D  (Rayleigh criterion, λ=500nm)
        # aperture_cm 기본값 15cm → 500km에서 약 2m 해상도
        h_m = orbit_result.params.altitude_km * 1000.0
        aperture_m = max(0.01, aperture_cm * 0.01)
        gsd_m = 1.22 * 5e-7 * h_m / aperture_m
        self._st_resol.update(
            f"~{gsd_m:.1f} m",
            f"{req.resolution_m:.1f} m",
            gsd_m <= req.resolution_m
        )
