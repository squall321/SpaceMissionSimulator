"""
Mission Panel Widget
임무 유형 선택 + 요구사항 정의 + 궤도 추천 + 달성도 평가
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QGridLayout, QFrame, QScrollArea, QButtonGroup,
    QSizePolicy, QSpacerItem
)
from PySide6.QtCore import Signal, Qt, QPropertyAnimation, QEasingCurve, Property, QTimer
from PySide6.QtGui  import QFont, QPainter, QColor, QPen, QLinearGradient

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.domain.orbit import OrbitParams


# ── 데이터 클래스 ─────────────────────────────────────────────────
@dataclass
class MissionRequirements:
    mission_type: str          = "earth_obs"
    lifetime_yr: float         = 3.0
    revisit_hr: float          = 12.0
    resolution_m: float        = 5.0
    downlink_gb_day: float     = 10.0
    min_contact_min_day: float = 15.0
    coverage: str              = "regional"   # regional / national / global


@dataclass
class RequirementStatus:
    label: str
    required: str
    actual: str
    met: Optional[bool]        = None   # None = 미평가, True = 충족, False = 미달


# ── 미션 타입 정의 ─────────────────────────────────────────────────
MISSION_TYPES = [
    {
        "key":   "earth_obs",
        "icon":  "🌍",
        "name":  "지구관측",
        "name_en": "Earth Obs",
        "desc":  "광학·SAR 지구 관측\n고해상도 반복 촬영",
        "color": "#00b4d8",
        "orbit_hint": {"alt": (400, 700), "inc": (97.0, 99.0), "type": "SSO"},
    },
    {
        "key":   "comm",
        "icon":  "📡",
        "name":  "통신",
        "name_en": "Communication",
        "desc":  "광대역 위성 통신\n고속 데이터 릴레이",
        "color": "#4cc9f0",
        "orbit_hint": {"alt": (500, 1200), "inc": (53.0, 70.0), "type": "LEO_EQ"},
    },
    {
        "key":   "science",
        "icon":  "🔬",
        "name":  "과학탐사",
        "name_en": "Science",
        "desc":  "우주 환경 계측\n대기·자기장 관측",
        "color": "#7b2d8b",
        "orbit_hint": {"alt": (350, 600), "inc": (90.0, 105.0), "type": "LEO_POLAR"},
    },
    {
        "key":   "weather",
        "icon":  "☀️",
        "name":  "기상",
        "name_en": "Weather",
        "desc":  "기상·기후 관측\n전지구 재방문",
        "color": "#f77f00",
        "orbit_hint": {"alt": (500, 850), "inc": (97.5, 99.5), "type": "SSO"},
    },
    {
        "key":   "defense",
        "icon":  "🛡️",
        "name":  "국방/안보",
        "name_en": "Defense",
        "desc":  "ISR / 전자전\n긴급 재방문",
        "color": "#c1121f",
        "orbit_hint": {"alt": (300, 500), "inc": (97.0, 98.5), "type": "SSO"},
    },
    {
        "key":   "space_dc",
        "icon":  "🏢",
        "name":  "우주 DC",
        "name_en": "Space DC",
        "desc":  "우주데이터센터\n(별도 구성 예정)",
        "color": "#00f5d4",
        "coming_soon": True,
        "orbit_hint": {"alt": (550, 600), "inc": (97.5, 98.0), "type": "DDSSO"},
    },
]


# ── 라벨 슬라이더 컴포넌트 ────────────────────────────────────────
class ReqSlider(QWidget):
    value_changed = Signal(float)

    def __init__(self, label: str, unit: str,
                 mn: float, mx: float, default: float,
                 decimals: int = 0, steps: int = 100):
        super().__init__()
        self._mn = mn
        self._mx = mx
        self._decimals = decimals
        self._steps = steps

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 1, 0, 1)
        lay.setSpacing(1)

        row = QHBoxLayout()
        self._name = QLabel(label)
        self._name.setStyleSheet("color:#5a8a9a;font-size:10px;")
        self._val = QLabel(f"{default:.{decimals}f} {unit}")
        self._val.setStyleSheet("color:#00dcff;font-size:11px;font-weight:bold;")
        self._val.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._unit = unit
        row.addWidget(self._name)
        row.addWidget(self._val)
        lay.addLayout(row)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, steps)
        self.slider.setValue(self._to_step(default))
        self.slider.setStyleSheet("""
        QSlider::groove:horizontal{height:4px;background:rgba(30,42,58,0.7);border-radius:2px;}
        QSlider::handle:horizontal{width:13px;height:13px;
          background:qradialgradient(cx:.5,cy:.5,radius:.5,fx:.5,fy:.5,
            stop:0 #fff,stop:.35 #00dcff,stop:1 #0077aa);
          border:1px solid #fff;border-radius:6px;margin:-5px 0;}
        QSlider::handle:horizontal:hover{width:15px;height:15px;margin:-6px 0;}
        QSlider::sub-page:horizontal{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
          stop:0 rgba(0,100,160,.8),stop:1 rgba(0,220,255,.9));border-radius:2px;}
        """)
        self.slider.valueChanged.connect(self._changed)
        lay.addWidget(self.slider)

    def _to_step(self, v):
        return int((v - self._mn) / (self._mx - self._mn) * self._steps)

    def _to_val(self, s):
        return self._mn + s / self._steps * (self._mx - self._mn)

    def _changed(self, s):
        v = self._to_val(s)
        self._val.setText(f"{v:.{self._decimals}f} {self._unit}")
        self.value_changed.emit(v)

    def value(self) -> float:
        return self._to_val(self.slider.value())

    def set_value(self, v: float):
        self.slider.setValue(self._to_step(v))


# ── 미션 타입 카드 ───────────────────────────────────────────────
class MissionTypeCard(QPushButton):
    def __init__(self, info: dict):
        super().__init__()
        self.setCheckable(True)
        self.info = info
        self.setFixedHeight(72)
        self.setMinimumWidth(120)
        self._color = info["color"]
        self._coming = info.get("coming_soon", False)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 4)
        lay.setSpacing(1)

        top = QHBoxLayout()
        icon_lbl = QLabel(info["icon"])
        icon_lbl.setFont(QFont("Segoe UI Emoji", 16))
        icon_lbl.setStyleSheet("color:inherit;background:transparent;")
        top.addWidget(icon_lbl)
        if self._coming:
            badge = QLabel("SOON")
            badge.setStyleSheet(
                "color:#00f5d4;background:rgba(0,245,212,.15);"
                "border:1px solid rgba(0,245,212,.4);border-radius:3px;"
                "font-size:8px;font-weight:700;padding:1px 4px;"
            )
            top.addStretch()
            top.addWidget(badge)
        lay.addLayout(top)

        name_lbl = QLabel(info["name"])
        name_lbl.setStyleSheet("color:inherit;background:transparent;font-size:10px;font-weight:700;")
        lay.addWidget(name_lbl)

        desc_lbl = QLabel(info["desc"])
        desc_lbl.setStyleSheet("color:rgba(180,210,230,.7);background:transparent;font-size:8px;")
        desc_lbl.setWordWrap(True)
        lay.addWidget(desc_lbl)

        self._update_style(False)

    def _update_style(self, checked: bool):
        c = self._color
        if self._coming:
            base = f"""
            MissionTypeCard {{
                background:rgba(0,245,212,.04);
                border:1px dashed rgba(0,245,212,.25);
                border-radius:6px; color:rgba(180,210,230,.5);
            }}
            MissionTypeCard:hover {{
                background:rgba(0,245,212,.08);
                border:1px dashed rgba(0,245,212,.5);
                color:rgba(200,230,240,.7);
            }}
            """
        elif checked:
            base = f"""
            MissionTypeCard {{
                background:rgba({self._hex_to_rgb(c)},.18);
                border:1px solid {c};
                border-radius:6px; color:#ffffff;
            }}
            """
        else:
            base = f"""
            MissionTypeCard {{
                background:rgba(13,26,42,.6);
                border:1px solid rgba(42,58,74,.8);
                border-radius:6px; color:rgba(180,210,230,.8);
            }}
            MissionTypeCard:hover {{
                background:rgba({self._hex_to_rgb(c)},.10);
                border:1px solid rgba({self._hex_to_rgb(c)},.6);
                color:#ffffff;
            }}
            """
        self.setStyleSheet(base)

    def _hex_to_rgb(self, h: str) -> str:
        h = h.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"{r},{g},{b}"

    def nextCheckState(self):
        if not self._coming:
            super().nextCheckState()
        else:
            self.setChecked(False)

    def setChecked(self, v: bool):
        super().setChecked(v)
        self._update_style(v)


# ── 요구사항 상태 행 ────────────────────────────────────────────
class StatusRow(QWidget):
    def __init__(self, label: str):
        super().__init__()
        self.setFixedHeight(22)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self._icon = QLabel("—")
        self._icon.setFixedWidth(16)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet("font-size:12px;")
        self._label = QLabel(label)
        self._label.setStyleSheet("color:#7ab0c6;font-size:10px;")
        self._label.setFixedWidth(90)
        self._actual = QLabel("—")
        self._actual.setStyleSheet("color:#c8e0f0;font-size:10px;font-weight:700;")
        self._req = QLabel("")
        self._req.setStyleSheet("color:#4a6a7a;font-size:9px;")
        self._req.setAlignment(Qt.AlignmentFlag.AlignRight)

        lay.addWidget(self._icon)
        lay.addWidget(self._label)
        lay.addWidget(self._actual)
        lay.addStretch()
        lay.addWidget(self._req)

    def update(self, actual: str, required: str, met: Optional[bool]):
        self._actual.setText(actual)
        self._req.setText(f"req: {required}")
        if met is None:
            self._icon.setText("–")
            self._icon.setStyleSheet("color:#4a6a7a;font-size:12px;")
            self._actual.setStyleSheet("color:#7ab0c6;font-size:10px;font-weight:700;")
        elif met:
            self._icon.setText("✓")
            self._icon.setStyleSheet("color:#00ff88;font-size:12px;font-weight:bold;")
            self._actual.setStyleSheet("color:#00ff88;font-size:10px;font-weight:700;")
        else:
            self._icon.setText("✗")
            self._icon.setStyleSheet("color:#ff4444;font-size:12px;font-weight:bold;")
            self._actual.setStyleSheet("color:#ff6666;font-size:10px;font-weight:700;")


# ── 커버리지 토글 버튼 ───────────────────────────────────────────
class CoverageToggle(QWidget):
    changed = Signal(str)

    OPTIONS = [("regional", "지역"), ("national", "국가"), ("global", "전지구")]

    def __init__(self):
        super().__init__()
        self._current = "regional"
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        self._btns: dict[str, QPushButton] = {}
        for key, label in self.OPTIONS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._select(k))
            self._btns[key] = btn
            lay.addWidget(btn)

        self._select("regional")

    def _select(self, key: str):
        self._current = key
        inactive = (
            "QPushButton{background:rgba(13,26,42,.6);border:1px solid rgba(42,58,74,.8);"
            "border-radius:4px;color:#5a8a9a;font-size:10px;font-weight:600;}"
            "QPushButton:hover{border:1px solid rgba(0,220,255,.4);color:#a0c8d8;}"
        )
        active = (
            "QPushButton{background:rgba(0,160,200,.25);border:1px solid rgba(0,220,255,.7);"
            "border-radius:4px;color:#00dcff;font-size:10px;font-weight:700;}"
        )
        for k, btn in self._btns.items():
            btn.setChecked(k == key)
            btn.setStyleSheet(active if k == key else inactive)
        self.changed.emit(key)

    def value(self) -> str:
        return self._current


# ── 메인 Mission 패널 ─────────────────────────────────────────────
class MissionPanel(QWidget):
    """
    임무 유형 + 요구사항 → 궤도 추천 시그널 방출
    분석 완료 후 update_status()로 충족도 표시
    """
    orbit_recommended = Signal(OrbitParams)
    requirements_changed = Signal(object)   # MissionRequirements

    def __init__(self):
        super().__init__()
        self.setObjectName("missionPanel")
        self._selected_type = "earth_obs"
        self._card_btns: dict[str, MissionTypeCard] = {}

        # 스크롤 래퍼
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
        QScrollArea{background:transparent;border:none;}
        QScrollBar:vertical{background:rgba(13,26,42,.5);width:5px;border-radius:2px;}
        QScrollBar::handle:vertical{background:#2a3a4e;border-radius:2px;}
        QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}
        """)

        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(12, 8, 12, 12)
        lay.setSpacing(10)

        # ── 섹션 헤더 ─────────────────────────────────────────
        hdr = QLabel("🎯  MISSION DEFINITION")
        hdr.setStyleSheet("""
        color:#ffffff;font-size:11px;font-weight:800;
        letter-spacing:3px;padding:6px 0;
        border-bottom:1px solid rgba(0,220,255,.3);
        """)
        lay.addWidget(hdr)

        # ── 미션 타입 카드 그리드 ─────────────────────────────
        type_lbl = self._section_label("MISSION TYPE")
        lay.addWidget(type_lbl)

        grid = QGridLayout()
        grid.setSpacing(4)
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

        # ── 구분선 ────────────────────────────────────────────
        lay.addWidget(self._divider())

        # ── 미션 요구사항 슬라이더 ────────────────────────────
        req_lbl = self._section_label("MISSION REQUIREMENTS")
        lay.addWidget(req_lbl)

        self.s_life    = ReqSlider("임무 수명",       "yr",   1,  15,  3,   1)
        self.s_revisit = ReqSlider("재방문 주기",     "hr",   1,  48, 12,   1)
        self.s_resol   = ReqSlider("지상 해상도",     "m",    0.5, 30, 5,   1)
        self.s_link    = ReqSlider("일일 다운링크",   "GB",   1, 100, 10,   0)
        self.s_contact = ReqSlider("최소 접속시간",   "min",  5, 120, 15,   0)

        for s in [self.s_life, self.s_revisit, self.s_resol, self.s_link, self.s_contact]:
            lay.addWidget(s)

        # ── 커버리지 목표 ─────────────────────────────────────
        lay.addWidget(self._divider())
        cov_hdr = QHBoxLayout()
        cov_hdr.addWidget(self._section_label("COVERAGE TARGET"))
        lay.addLayout(cov_hdr)
        self.coverage = CoverageToggle()
        lay.addWidget(self.coverage)

        # ── 궤도 추천 버튼 ────────────────────────────────────
        lay.addWidget(self._divider())
        self.recommend_btn = QPushButton("🎯   RECOMMEND ORBIT")
        self.recommend_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.recommend_btn.setFixedHeight(40)
        self.recommend_btn.setStyleSheet("""
        QPushButton{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
              stop:0 rgba(0,130,180,.9),stop:1 rgba(0,180,230,.9));
            color:#ffffff;border:1px solid rgba(0,220,255,.5);
            border-radius:5px;font-size:11px;font-weight:900;
            letter-spacing:2px;
        }
        QPushButton:hover{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
              stop:0 rgba(0,170,220,1.),stop:1 rgba(0,220,255,1.));
            border:1px solid rgba(0,255,255,.9);
        }
        QPushButton:pressed{background:rgba(0,50,80,.9);}
        """)
        self.recommend_btn.clicked.connect(self._on_recommend)
        lay.addWidget(self.recommend_btn)

        # ── 요구사항 충족도 섹션 ──────────────────────────────
        lay.addWidget(self._divider())
        status_lbl = self._section_label("REQUIREMENT STATUS")
        lay.addWidget(status_lbl)

        self._st_revisit = StatusRow("재방문 주기")
        self._st_contact = StatusRow("접속 시간")
        self._st_link    = StatusRow("다운링크")
        self._st_life    = StatusRow("임무 수명")
        self._st_resol   = StatusRow("해상도 적합")

        for w in [self._st_revisit, self._st_contact, self._st_link,
                  self._st_life, self._st_resol]:
            lay.addWidget(w)

        # 미평가 초기상태 안내
        self._hint_lbl = QLabel("  ▶ RE-ANALYZE 후 결과가 여기에 표시됩니다")
        self._hint_lbl.setStyleSheet("color:#3a5a6a;font-size:9px;font-style:italic;")
        self._hint_lbl.setWordWrap(True)
        lay.addWidget(self._hint_lbl)

        lay.addSpacerItem(QSpacerItem(0, 20, QSizePolicy.Policy.Minimum,
                                       QSizePolicy.Policy.Expanding))

        scroll.setWidget(inner)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        self.setStyleSheet("""
        #missionPanel{
            background:rgba(10,21,37,.85);
            border-bottom:1px solid rgba(30,42,58,.9);
        }
        """)

    # ── 헬퍼 ────────────────────────────────────────────────────
    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color:#4a8a9a;font-size:9px;font-weight:800;letter-spacing:2px;"
            "padding-top:2px;"
        )
        return lbl

    def _divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet("background:rgba(30,42,58,.9);border:none;")
        return line

    # ── 이벤트 ──────────────────────────────────────────────────
    def _on_type_selected(self, key: str):
        self._selected_type = key
        # 타입별 기본 요구사항 프리셋 자동 적용
        presets = {
            "earth_obs": (3,  12, 5,  10, 20),
            "comm":      (5,  1,  50, 50, 30),
            "science":   (3,  24, 30, 5,  10),
            "weather":   (5,  6,  500,15, 25),
            "defense":   (5,  3,  1,  20, 15),
            "space_dc":  (7,  6,  10, 100,60),
        }
        if key in presets:
            life, rev, res, dl, ct = presets[key]
            self.s_life.set_value(life)
            self.s_revisit.set_value(rev)
            self.s_resol.set_value(min(res, 30))
            self.s_link.set_value(min(dl, 100))
            self.s_contact.set_value(min(ct, 120))

    def _on_recommend(self):
        """미션 요구사항 → 최적 궤도 파라미터 추천"""
        info = next(m for m in MISSION_TYPES if m["key"] == self._selected_type)
        hint = info["orbit_hint"]
        rev_hr  = self.s_revisit.value()
        link_gb = self.s_link.value()
        cov     = self.coverage.value()

        # 고도 결정: 재방문 짧으면 낮은 고도 선호
        alt_lo, alt_hi = hint["alt"]
        if rev_hr <= 3:
            alt = alt_lo
        elif rev_hr <= 12:
            alt = (alt_lo + alt_hi) / 2
        else:
            alt = alt_hi

        # 경사각: 커버리지 → 전지구면 더 높은 경사각
        inc_lo, inc_hi = hint["inc"]
        if cov == "global":
            inc = inc_hi
        elif cov == "national":
            inc = (inc_lo + inc_hi) / 2
        else:
            inc = inc_lo

        # RAAN: Dawn-Dusk SSO이면 90°
        o_type = hint["type"]
        raan = 90.0 if o_type == "DDSSO" else 0.0

        # 수명 → duration_days (분석용은 3일 고정, 수명은 별도 요구사항)
        params = OrbitParams(
            altitude_km     = round(alt, 0),
            inclination_deg = round(inc, 1),
            raan_deg        = raan,
            orbit_type      = o_type,
            duration_days   = 3.0,
        )
        self.orbit_recommended.emit(params)

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
        """
        분석 결과를 받아 요구사항 충족도를 갱신합니다.
        orbit_result: OrbitResult (mission_analysis 반환 객체)
        """
        self._hint_lbl.setVisible(False)
        req = self.get_requirements()

        # 재방문 주기: contacts_per_day로 역산
        if orbit_result.contacts_per_day > 0:
            actual_rev_hr = 24.0 / orbit_result.contacts_per_day
        else:
            actual_rev_hr = 999.0
        self._st_revisit.update(
            actual=f"{actual_rev_hr:.1f} hr",
            required=f"{req.revisit_hr:.1f} hr",
            met=(actual_rev_hr <= req.revisit_hr)
        )

        # 접속 시간
        ct = orbit_result.contact_time_per_day_min
        self._st_contact.update(
            actual=f"{ct:.1f} min",
            required=f"{req.min_contact_min_day:.0f} min",
            met=(ct >= req.min_contact_min_day)
        )

        # 다운링크
        dl = budget_result.data_per_day_gb if budget_result else 0.0
        self._st_link.update(
            actual=f"{dl:.1f} GB",
            required=f"{req.downlink_gb_day:.0f} GB",
            met=(dl >= req.downlink_gb_day)
        )

        # 임무 수명: 연료/열 여유도 기반 간이 판단
        # 고도가 충분히 높으면(>400km) OK로 간이 처리
        life_ok = orbit_result.params.altitude_km >= 400
        self._st_life.update(
            actual="OK" if life_ok else "LOW ALT",
            required=f"{req.lifetime_yr:.0f} yr",
            met=life_ok
        )

        # 해상도 적합성: 고도가 낮을수록 고해상도 유리
        # 간이 모델: res_achievable ≈ altitude_km / 100 m (경험적)
        res_achiev = orbit_result.params.altitude_km / 100.0
        self._st_resol.update(
            actual=f"~{res_achiev:.0f} m class",
            required=f"{req.resolution_m:.1f} m",
            met=(res_achiev <= req.resolution_m * 2)
        )
