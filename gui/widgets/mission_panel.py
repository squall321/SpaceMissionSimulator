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
    QSizePolicy, QSpacerItem
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui  import QFont

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.domain.orbit import OrbitParams


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
#  MissionTypeCard
# ══════════════════════════════════════════════════════════════════
class MissionTypeCard(QPushButton):
    def __init__(self, info: dict):
        super().__init__()
        self.setCheckable(True)
        self.info = info
        self._color = info["color"]
        self._coming = info.get("coming_soon", False)
        self.setFixedHeight(80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 7, 8, 6)
        lay.setSpacing(2)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        icon_lbl = QLabel(info["icon"])
        icon_lbl.setFont(QFont("Segoe UI Emoji", 17))
        icon_lbl.setStyleSheet("color: inherit; background: transparent;")
        top.addWidget(icon_lbl)
        if self._coming:
            badge = QLabel("SOON")
            badge.setStyleSheet(
                "color: #00f5d4; background: rgba(0,245,212,0.15);"
                "border: 1px solid rgba(0,245,212,0.55); border-radius: 3px;"
                "font-size: 8px; font-weight: 700; padding: 1px 5px;"
            )
            top.addStretch()
            top.addWidget(badge)
        lay.addLayout(top)

        name_lbl = QLabel(info["name"])
        name_lbl.setStyleSheet(
            "color: inherit; background: transparent;"
            "font-size: 11px; font-weight: 800;"
        )
        lay.addWidget(name_lbl)

        desc_lbl = QLabel(info["desc"])
        desc_lbl.setStyleSheet(
            "color: rgba(205,228,242,0.80); background: transparent;"
            "font-size: 9px;"
        )
        desc_lbl.setWordWrap(True)
        lay.addWidget(desc_lbl)

        self._set_style(False)

    def _rgb(self, h: str) -> str:
        h = h.lstrip("#")
        return f"{int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)}"

    def _set_style(self, checked: bool):
        c = self._color
        r = self._rgb(c)
        if self._coming:
            ss = f"""
            MissionTypeCard {{
                background: rgba(0,40,40,0.40);
                border: 1px dashed rgba(0,245,212,0.30);
                border-radius: 7px; color: rgba(155,195,185,0.60);
            }}
            MissionTypeCard:hover {{
                background: rgba(0,55,52,0.55);
                border: 1px dashed rgba(0,245,212,0.65);
                color: rgba(180,220,210,0.85);
            }}"""
        elif checked:
            ss = f"""
            MissionTypeCard {{
                background: rgba({r}, 0.22);
                border: 2px solid {c};
                border-radius: 7px; color: #ffffff;
            }}"""
        else:
            ss = f"""
            MissionTypeCard {{
                background: rgba(20,38,56,0.75);
                border: 1px solid rgba(65,88,108,0.65);
                border-radius: 7px; color: rgba(195,218,232,0.88);
            }}
            MissionTypeCard:hover {{
                background: rgba({r}, 0.13);
                border: 1px solid rgba({r}, 0.75);
                color: #ffffff;
            }}"""
        self.setStyleSheet(ss)

    def nextCheckState(self):
        if not self._coming:
            super().nextCheckState()

    def setChecked(self, v: bool):
        super().setChecked(v)
        self._set_style(v)


# ══════════════════════════════════════════════════════════════════
#  CoverageToggle
# ══════════════════════════════════════════════════════════════════
class CoverageToggle(QWidget):
    changed = Signal(str)
    OPTIONS = [("regional", "지역 (Regional)"), ("national", "국가 (National)"), ("global", "전지구 (Global)")]

    def __init__(self):
        super().__init__()
        self._current = "regional"
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self._btns: dict[str, QPushButton] = {}
        for key, label in self.OPTIONS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._select(k))
            self._btns[key] = btn
            lay.addWidget(btn)
        self._select("regional")

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

    def _select(self, key: str):
        self._current = key
        for k, btn in self._btns.items():
            btn.setStyleSheet(self._ACTIVE if k == key else self._INACTIVE)
        self.changed.emit(key)

    def value(self) -> str:
        return self._current


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
        grid.setSpacing(5)
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
        self.coverage = CoverageToggle()
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
        info = next(m for m in MISSION_TYPES if m["key"] == self._selected_type)
        hint = info["orbit_hint"]
        rev_hr = self.s_revisit.value()
        cov    = self.coverage.value()

        alt_lo, alt_hi = hint["alt"]
        alt = (alt_lo if rev_hr <= 3
               else (alt_lo + alt_hi) / 2 if rev_hr <= 12
               else alt_hi)

        inc_lo, inc_hi = hint["inc"]
        inc = (inc_hi if cov == "global"
               else (inc_lo + inc_hi) / 2 if cov == "national"
               else inc_lo)

        o_type = hint["type"]
        raan   = 90.0 if o_type == "DDSSO" else 0.0

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

    def update_status(self, orbit_result, budget_result=None):
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

        res_achiev = orbit_result.params.altitude_km / 100.0
        self._st_resol.update(
            f"~{res_achiev:.0f} m",
            f"{req.resolution_m:.1f} m",
            res_achiev <= req.resolution_m * 2
        )
