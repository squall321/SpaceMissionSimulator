"""
DesignScoreCard Viewer  (v0.9.0)
종합 설계 평가 점수 카드 — Radar Chart + 점수 Gauge + 지표 테이블
"""
import json
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Qt, Signal

from core.domain.thermal import DesignScoreCard

# ── 지표 표시 이름 매핑 ──────────────────────────────────────────
_IND_LABELS = {
    "sunlight_ratio":    ("일조율",         "%",      85,   "≥"),
    "max_eclipse":       ("최대 일식",       "min",    30,   "≤"),
    "battery_dod":       ("배터리 DOD",      "%",      35,   "≤"),
    "temp_max":          ("최고 온도",        "°C",     70,   "≤"),
    "temp_min":          ("최저 온도",        "°C",    -20,  "≥"),
    "tid_5yr":           ("TID 5년",         "krad",   20,   "≤"),
    "contacts_per_day":  ("접속 횟수",        "회/일",   4,   "≥"),
    "mass_margin":       ("질량 마진",        "%",      15,   "≥"),
    "power_margin":      ("전력 마진",        "%",      10,   "≥"),
}

_GRADE_COLOR = {
    "A+": "#00ff88", "A": "#39ff96", "B": "#ffe066",
    "C": "#ffa040",  "F": "#ff4d6d", "N/A": "#5a7a8a"
}

_RADAR_INDS = [
    "sunlight_ratio", "contacts_per_day", "mass_margin",
    "power_margin",   "tid_5yr",          "battery_dod"
]


class _IndicatorRow(QWidget):
    """단일 지표 행: 이름 | 값 | 한계 | 마진 | PASS/FAIL 배지"""

    def __init__(self, key: str, ind: dict, parent=None):
        super().__init__(parent)
        label_info = _IND_LABELS.get(key, (key, "", "—", ""))
        name, unit, limit, op = label_info

        passed = ind.get("pass", True)
        value  = ind.get("value", 0.0)
        margin = ind.get("margin", 0.0)

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 3, 8, 3)
        row.setSpacing(6)

        # 이름
        lbl_name = QLabel(name)
        lbl_name.setFixedWidth(80)
        lbl_name.setStyleSheet("color:#a0c8d8;font-size:10px;")
        row.addWidget(lbl_name)

        # 값
        lbl_val = QLabel(f"{value:.1f} {unit}")
        lbl_val.setFixedWidth(72)
        lbl_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_val.setStyleSheet("color:#e0e8f0;font-size:10px;font-weight:600;")
        row.addWidget(lbl_val)

        # 한계
        lbl_lim = QLabel(f"{op}{limit} {unit}")
        lbl_lim.setFixedWidth(68)
        lbl_lim.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_lim.setStyleSheet("color:#4a6a7a;font-size:9px;")
        row.addWidget(lbl_lim)

        # 마진
        margin_color = "#39ff96" if passed else "#ff4d6d"
        sign = "+" if margin >= 0 else ""
        lbl_margin = QLabel(f"{sign}{margin:.1f}")
        lbl_margin.setFixedWidth(52)
        lbl_margin.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_margin.setStyleSheet(f"color:{margin_color};font-size:10px;font-weight:600;")
        row.addWidget(lbl_margin)

        row.addStretch()

        # PASS / FAIL / MARGIN 배지
        if passed and abs(margin) < 5:
            badge_text, badge_bg = "MARGIN", "#996633"
        elif passed:
            badge_text, badge_bg = "PASS", "#1a4a2a"
        else:
            badge_text, badge_bg = "FAIL", "#4a1a1a"
        badge_fg = "#39ff96" if passed else "#ff4d6d"
        if passed and abs(margin) < 5:
            badge_fg = "#ffa040"

        lbl_badge = QLabel(badge_text)
        lbl_badge.setFixedSize(44, 18)
        lbl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_badge.setStyleSheet(
            f"color:{badge_fg};background:{badge_bg};border:1px solid {badge_fg};"
            f"font-size:8px;font-weight:700;border-radius:3px;"
        )
        row.addWidget(lbl_badge)

        # 통과 여부에 따른 행 배경
        bg = "#0d2a1a" if passed else "#1a0d0d"
        self.setStyleSheet(
            f"QWidget{{background:{bg};border-bottom:1px solid #1a2530;}}"
        )


class ScorecardViewer(QWidget):
    """종합 설계 점수 카드 패널 (v0.9.0)"""

    export_requested = Signal(object)   # DesignScoreCard → 리포트 대화상자 오픈

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("scorecardViewer")
        self._score: DesignScoreCard | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 헤더 ────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(36)
        hdr.setStyleSheet("background:#0c1a10;border-bottom:1px solid #1e3a2a;")
        hdr_row = QHBoxLayout(hdr)
        hdr_row.setContentsMargins(12, 0, 8, 0)

        lbl_title = QLabel("🏆  DESIGN SCORECARD")
        lbl_title.setStyleSheet(
            "color:#39ff96;font-size:10px;font-weight:700;letter-spacing:2px;"
        )
        hdr_row.addWidget(lbl_title)
        hdr_row.addStretch()

        self.export_btn = QPushButton("📄 Export Report")
        self.export_btn.setFixedHeight(22)
        self.export_btn.setEnabled(False)
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.setStyleSheet("""
        QPushButton{
            color:#39ff96;background:#0a2a1a;border:1px solid #39ff96;
            border-radius:3px;font-size:9px;padding:0 8px;
        }
        QPushButton:hover{background:#1a4a2a;}
        QPushButton:disabled{color:#2a4a3a;border-color:#2a4a3a;}
        """)
        self.export_btn.clicked.connect(self._on_export)
        hdr_row.addWidget(self.export_btn)

        root.addWidget(hdr)

        # ── 점수 Summary 행 ──────────────────────────────────────
        self.summary_bar = QWidget()
        self.summary_bar.setFixedHeight(56)
        self.summary_bar.setStyleSheet("background:#080f08;border-bottom:1px solid #1a2a1a;")
        sb_row = QHBoxLayout(self.summary_bar)
        sb_row.setContentsMargins(16, 6, 16, 6)
        sb_row.setSpacing(16)

        # 등급 배지
        self.grade_lbl = QLabel("—")
        self.grade_lbl.setFixedSize(48, 44)
        self.grade_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.grade_lbl.setStyleSheet(
            "color:#5a7a6a;background:#10201a;border:2px solid #2a3a2a;"
            "font-size:22px;font-weight:900;border-radius:6px;"
        )
        sb_row.addWidget(self.grade_lbl)

        # 점수
        score_col = QVBoxLayout()
        score_col.setSpacing(0)
        self.score_lbl = QLabel("—")
        self.score_lbl.setStyleSheet(
            "color:#c8d8e4;font-size:22px;font-weight:700;letter-spacing:-0.5px;"
        )
        score_col.addWidget(self.score_lbl)
        lbl_sub = QLabel("TOTAL SCORE  /  100")
        lbl_sub.setStyleSheet("color:#4a6a5a;font-size:8px;letter-spacing:1px;")
        score_col.addWidget(lbl_sub)
        sb_row.addLayout(score_col)

        sb_row.addStretch()

        # PASS/FAIL 카운터
        self.pass_counter = QLabel("—")
        self.pass_counter.setStyleSheet(
            "color:#4a6a5a;font-size:9px;letter-spacing:0.5px;"
        )
        sb_row.addWidget(self.pass_counter)

        root.addWidget(self.summary_bar)

        # ── Radar + Gauge 차트 ───────────────────────────────────
        self.chart_view = QWebEngineView()
        self.chart_view.setFixedHeight(220)
        self.chart_view.setStyleSheet("background:transparent;")
        root.addWidget(self.chart_view)

        # ── 지표 테이블 (스크롤) ─────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{border:none;background:#0a0f1e;}")

        self.table_container = QWidget()
        self.table_container.setStyleSheet("background:#0a0f1e;")
        self._table_layout = QVBoxLayout(self.table_container)
        self._table_layout.setContentsMargins(0, 0, 0, 0)
        self._table_layout.setSpacing(0)

        # 테이블 헤더
        th = QWidget()
        th.setFixedHeight(24)
        th.setStyleSheet("background:#0d1525;border-bottom:1px solid #1e2a3a;")
        th_row = QHBoxLayout(th)
        th_row.setContentsMargins(8, 0, 8, 0)
        th_row.setSpacing(6)
        for txt, w in [("지표", 80), ("현재값", 72), ("한계", 68), ("마진", 52)]:
            l = QLabel(txt)
            l.setFixedWidth(w)
            l.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter if txt != "지표"
                           else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            l.setStyleSheet("color:#2a6a8a;font-size:8px;font-weight:700;letter-spacing:1px;")
            th_row.addWidget(l)
        th_row.addStretch()
        l2 = QLabel("결과")
        l2.setFixedWidth(44)
        l2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l2.setStyleSheet("color:#2a6a8a;font-size:8px;font-weight:700;letter-spacing:1px;")
        th_row.addWidget(l2)
        self._table_layout.addWidget(th)

        self._table_layout.addStretch()
        scroll.setWidget(self.table_container)
        root.addWidget(scroll, stretch=1)

        self.setStyleSheet("#scorecardViewer{background:#0a0f1e;}")

    # ── public API ───────────────────────────────────────────────
    def update_data(self, score: DesignScoreCard):
        self._score = score
        self._refresh_summary(score)
        self._refresh_chart(score)
        self._refresh_table(score)
        self.export_btn.setEnabled(True)

    # ── 내부 갱신 ────────────────────────────────────────────────
    def _refresh_summary(self, sc: DesignScoreCard):
        grade = sc.grade if sc.grade else "N/A"
        color = _GRADE_COLOR.get(grade, "#5a7a8a")

        self.grade_lbl.setText(grade)
        self.grade_lbl.setStyleSheet(
            f"color:{color};background:#10201a;border:2px solid {color};"
            f"font-size:20px;font-weight:900;border-radius:6px;"
        )

        self.score_lbl.setText(f"{sc.total_score:.1f}")
        self.score_lbl.setStyleSheet(
            f"color:{color};font-size:22px;font-weight:700;letter-spacing:-0.5px;"
        )

        inds = sc.indicators or {}
        pass_cnt  = sum(1 for v in inds.values() if v.get("pass", True))
        total_cnt = len(inds)
        self.pass_counter.setText(f"PASS  {pass_cnt} / {total_cnt}")
        self.pass_counter.setStyleSheet(
            f"color:{'#39ff96' if pass_cnt == total_cnt else '#ffa040'};"
            f"font-size:11px;font-weight:700;letter-spacing:0.5px;"
        )

    def _refresh_chart(self, sc: DesignScoreCard):
        inds = sc.indicators or {}

        # ── Radar 데이터 준비 (0~100 정규화) ────────────────────
        radar_labels = []
        radar_vals   = []
        for key in _RADAR_INDS:
            info = _IND_LABELS.get(key)
            if not info:
                continue
            name, unit, limit, op = info
            ind = inds.get(key, {})
            val  = ind.get("value", 0.0)
            passed = ind.get("pass", True)
            # 정규화: 통과 시 50~100, 실패 시 0~50
            margin = ind.get("margin", 0.0)
            if passed:
                norm = min(100.0, 60.0 + margin * 1.5)
            else:
                norm = max(0.0, 50.0 + margin * 2.0)
            radar_labels.append(name)
            radar_vals.append(round(norm, 1))

        # 6축 레이더 닫기
        theta = radar_labels + [radar_labels[0]] if radar_labels else []
        r     = radar_vals   + [radar_vals[0]]   if radar_vals   else []

        # ── Plotly Figure ────────────────────────────────────────
        fig = make_subplots(
            rows=1, cols=2,
            specs=[[{"type": "polar"}, {"type": "indicator"}]],
            column_widths=[0.6, 0.4],
        )

        # Radar
        fig.add_trace(
            go.Scatterpolar(
                r=r, theta=theta, fill="toself",
                fillcolor="rgba(0,200,120,0.15)",
                line=dict(color="#39ff96", width=2),
                name="Score",
                hovertemplate="%{theta}: %{r:.0f}<extra></extra>",
            ),
            row=1, col=1,
        )

        # Gauge
        grade = sc.grade if sc.grade else "N/A"
        g_color = _GRADE_COLOR.get(grade, "#5a7a8a")
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=sc.total_score,
                number={"font": {"color": g_color, "size": 28}, "suffix": "pt"},
                gauge={
                    "axis": {"range": [0, 100], "tickcolor": "#2a4a3a",
                             "tickfont": {"size": 8, "color": "#2a4a3a"}},
                    "bar":  {"color": g_color, "thickness": 0.22},
                    "bgcolor": "#0a1a10",
                    "bordercolor": "#1a2a1a",
                    "steps": [
                        {"range": [0,  60], "color": "#1a0d0d"},
                        {"range": [60, 70], "color": "#1a1500"},
                        {"range": [70, 80], "color": "#0d1a00"},
                        {"range": [80, 90], "color": "#0a1a10"},
                        {"range": [90,100], "color": "#0a2a1a"},
                    ],
                    "threshold": {
                        "line": {"color": "#39ff96", "width": 2},
                        "thickness": 0.75,
                        "value": sc.total_score,
                    },
                },
                domain={"row": 0, "column": 1},
            ),
            row=1, col=2,
        )

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0a0f1e",
            plot_bgcolor="#0a0f1e",
            margin=dict(l=10, r=10, t=16, b=10),
            font=dict(color="#a0c8d8", size=9),
            polar=dict(
                bgcolor="#080f10",
                radialaxis=dict(
                    visible=True, range=[0, 100],
                    tickfont=dict(size=7, color="#2a4a5a"),
                    gridcolor="#1a2a3a",
                ),
                angularaxis=dict(
                    tickfont=dict(size=9, color="#6a9aaa"),
                    gridcolor="#1a2a3a",
                ),
            ),
            showlegend=False,
            height=200,
        )

        html = fig.to_html(include_plotlyjs="cdn", full_html=True,
                           config={"displayModeBar": False})
        self.chart_view.setHtml(html)

    def _refresh_table(self, sc: DesignScoreCard):
        inds = sc.indicators or {}

        # 기존 지표 행 제거 (헤더 + 스트레치 제외)
        while self._table_layout.count() > 2:
            item = self._table_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        # 새 행 삽입 (헤더 다음 위치)
        insert_pos = 1
        for key, ind in inds.items():
            row_widget = _IndicatorRow(key, ind)
            self._table_layout.insertWidget(insert_pos, row_widget)
            insert_pos += 1

    def _on_export(self):
        if self._score:
            self.export_requested.emit(self._score)
