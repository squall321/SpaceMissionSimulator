"""
Budget Viewer Panel — v0.7.0
질량 / 전력 / 링크 예산을 3탭으로 시각화
"""
from __future__ import annotations
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QHBoxLayout, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtWebEngineWidgets import QWebEngineView

from core.domain.thermal import BudgetResult

# ── 공통 색상 상수 ────────────────────────────────────────────────────────────
_DARK_BG  = "#0a0f1e"
_PANEL_BG = "#070e1c"
_CYAN     = "#00dcff"
_GREEN    = "#39ff96"
_RED      = "#ff6b6b"
_YELLOW   = "#ffdc40"
_ORANGE   = "#ffa040"
_GREY_DIM = "#2a3a4a"
_PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor=_DARK_BG,
    plot_bgcolor=_PANEL_BG,
    margin=dict(l=10, r=10, t=28, b=10),
    font=dict(family="Consolas, monospace", size=11, color="#c8e0f0"),
)

_SUBSYSTEMS = ["Structure","Power","Thermal","ADCS","C&DH",
               "Comms","Propulsion","Payload","Harness"]
_MARGINS    = [15, 10, 15, 5, 5, 10, 10, 20, 20]  # % per subsystem


def _webview() -> QWebEngineView:
    v = QWebEngineView()
    v.setStyleSheet("background:transparent;")
    v.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return v


def _hdr(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "color:#ffaa00; font-size:10px; font-weight:bold;"
        "letter-spacing:2px; padding:4px 2px;"
        "border-bottom:1px solid #2a2010;"
    )
    return lbl


def _cell(text: str, bold: bool = False) -> QTableWidgetItem:
    it = QTableWidgetItem(text)
    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
    if bold:
        from PySide6.QtGui import QFont as _F; f = _F(); f.setBold(True); it.setFont(f)
    return it


# ── Tab 1: Mass Budget ────────────────────────────────────────────────────────
class _MassTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 4)
        v.setSpacing(4)
        v.addWidget(_hdr("⚖  MASS BUDGET  (CBE + Margin = MEV)"))

        self._table = QTableWidget(9, 4)
        self._table.setHorizontalHeaderLabels(["서브시스템","CBE (kg)","마진 %","MEV (kg)"])
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in (1,2,3):
            self._table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setFixedHeight(195)
        self._table.setStyleSheet("""
        QTableWidget { background:#050a14; color:#c8e0f0; gridline-color:#1a2535;
                       border:1px solid #1a2535; font-size:10.5px; }
        QHeaderView::section { background:#0d2030; color:#00dcff; padding:3px 6px;
                                border:1px solid #1a2535; font-weight:bold; font-size:10px; }
        """)
        v.addWidget(self._table)
        self._web = _webview()
        v.addWidget(self._web, stretch=1)

    def refresh(self, b: BudgetResult):
        cbes = [b.mass_structure_cbe, b.mass_power_cbe, b.mass_thermal_cbe,
                b.mass_adcs_cbe, b.mass_cdh_cbe, b.mass_comms_cbe,
                b.mass_propulsion_cbe, b.mass_payload_cbe, b.mass_harness_cbe]
        mevs = [c*(1+m/100) for c,m in zip(cbes,_MARGINS)]
        total_mev = sum(mevs)

        for i,(ss,cbe,mg,mev) in enumerate(zip(_SUBSYSTEMS,cbes,_MARGINS,mevs)):
            self._table.setItem(i, 0, _cell(ss, bold=True))
            self._table.setItem(i, 1, _cell(f"{cbe:.1f}"))
            self._table.setItem(i, 2, _cell(f"{mg}%"))
            it = _cell(f"{mev:.1f}")
            ok = mev < b.mass_launch_available * 0.9
            it.setForeground(Qt.GlobalColor.green if ok else Qt.GlobalColor.yellow)
            self._table.setItem(i, 3, it)

        margin_pct = (b.mass_launch_available - total_mev) / b.mass_launch_available * 100
        m_col = _GREEN if margin_pct > 10 else (_YELLOW if margin_pct > 0 else _RED)

        fig = go.Figure()
        fig.add_trace(go.Bar(name="CBE", y=_SUBSYSTEMS, x=cbes, orientation="h",
                             marker_color=_CYAN, opacity=0.85))
        fig.add_trace(go.Bar(name="Margin", y=_SUBSYSTEMS,
                             x=[m-c for m,c in zip(mevs,cbes)],
                             orientation="h", marker_color=_ORANGE, opacity=0.60))
        fig.add_vline(x=b.mass_launch_available, line_dash="dot", line_color=_RED,
                      annotation_text=f"Limit {b.mass_launch_available:.0f}kg",
                      annotation_font_color=_RED, annotation_position="top right")
        fig.update_layout(
            **_PLOTLY_LAYOUT, barmode="stack", xaxis_title="Mass [kg]",
            showlegend=True,
            legend=dict(x=0.7, y=1.08, orientation="h",
                        font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
            annotations=[dict(
                x=total_mev/2, y=8.8,
                text=f"MEV {total_mev:.1f}kg  |  Margin {margin_pct:.1f}%",
                showarrow=False, font=dict(color=m_col, size=11),
                bgcolor="rgba(0,0,0,0.6)", bordercolor=m_col, borderwidth=1,
            )], height=220,
        )
        self._web.setHtml(fig.to_html(include_plotlyjs="cdn", config={"displayModeBar":False}))


# ── Tab 2: Power Budget ───────────────────────────────────────────────────────
class _PowerTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 4)
        v.setSpacing(4)
        v.addWidget(_hdr("⚡  POWER BUDGET"))
        self._kpi = QLabel("")
        self._kpi.setStyleSheet("color:#4a6a7a; font-size:10px;")
        v.addWidget(self._kpi)
        self._web = _webview()
        v.addWidget(self._web, stretch=1)

    def refresh(self, b: BudgetResult):
        mw   = b.power_margin_w
        m_col = _GREEN if mw > 50 else (_YELLOW if mw > 0 else _RED)
        self._kpi.setText(
            f"  발전 {b.solar_generated_w:.0f}W  |  소비 {b.power_total_w:.0f}W  |  "
            f"마진 {mw:.0f}W  |  배터리 {b.battery_capacity_wh:.0f}Wh  DOD {b.battery_dod_pct:.0f}%  |  "
            f"패널 {b.solar_panel_area_m2:.2f}m²"
        )
        fig = make_subplots(rows=1, cols=2,
                            specs=[[{"type":"bar"},{"type":"domain"}]],
                            column_widths=[0.55,0.45])
        cats = ["Payload","Bus","Solar Gen","Margin"]
        vals = [b.power_payload_w, b.power_bus_w, b.solar_generated_w, max(0,mw)]
        clrs = [_ORANGE, _CYAN, _GREEN, m_col]
        fig.add_trace(go.Bar(x=cats, y=vals, marker_color=clrs, opacity=0.85,
                             text=[f"{x:.0f}W" for x in vals],
                             textposition="outside",
                             textfont=dict(size=10,color="#c8e0f0"),
                             showlegend=False), row=1, col=1)
        fig.add_hline(y=b.power_total_w, line_dash="dash", line_color=_RED,
                      annotation_text=f"Load {b.power_total_w:.0f}W",
                      annotation_font_color=_RED, row=1, col=1)
        fig.add_trace(go.Pie(labels=["Payload","Bus"],
                             values=[b.power_payload_w, b.power_bus_w],
                             hole=0.5, marker_colors=[_ORANGE,_CYAN],
                             textinfo="label+percent",
                             insidetextorientation="radial",
                             title=dict(text=f"Load<br>{b.power_total_w:.0f}W",
                                        font=dict(color=_CYAN,size=13)),
                             showlegend=False), row=1, col=2)
        fig.update_layout(**_PLOTLY_LAYOUT, yaxis_title="Power [W]", height=330)
        self._web.setHtml(fig.to_html(include_plotlyjs="cdn", config={"displayModeBar":False}))


# ── Tab 3: Link Budget ────────────────────────────────────────────────────────
class _LinkTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 4)
        v.setSpacing(4)
        v.addWidget(_hdr("📡  LINK BUDGET"))
        self._kpi = QLabel("")
        self._kpi.setStyleSheet("color:#4a6a7a; font-size:10px; margin-bottom:2px;")
        v.addWidget(self._kpi)
        self._web = _webview()
        v.addWidget(self._web, stretch=1)

    def refresh(self, b: BudgetResult, orbit=None):
        contacts = b.contact_count or 0
        ct_min   = b.contact_time_per_day_min
        dl_gb    = b.data_per_day_gb
        link_db  = b.link_margin_db
        dl_rate  = b.downlink_rate_mbps
        link_col = _GREEN if link_db >= 3 else (_YELLOW if link_db >= 0 else _RED)

        self._kpi.setText(
            f"  접속 {contacts}회/일 ({ct_min:.1f}min)  |  "
            f"다운링크 {dl_rate:.0f}Mbps  |  일일 {dl_gb:.2f}GB/d  |  링크마진 {link_db:.1f}dB"
        )

        fig = make_subplots(rows=1, cols=2,
                            specs=[[{"type":"indicator"},{"type":"bar"}]],
                            column_widths=[0.40,0.60])
        fig.add_trace(go.Indicator(
            mode="gauge+number+delta",
            value=dl_gb,
            delta={"reference":1.0,"valueformat":".2f",
                   "increasing":{"color":_GREEN},"decreasing":{"color":_RED}},
            number={"suffix":" GB/d","font":{"size":18,"color":_CYAN}},
            title={"text":"Daily Downlink","font":{"size":11,"color":"#8ab0c0"}},
            gauge={
                "axis":{"range":[0,max(5,dl_gb*1.5)],"tickcolor":"#4a6a7a","tickwidth":1},
                "bar":{"color":_CYAN,"thickness":0.4},
                "bgcolor":_PANEL_BG,"bordercolor":_GREY_DIM,
                "steps":[
                    {"range":[0,0.5],"color":"rgba(255,100,100,0.15)"},
                    {"range":[0.5,2.0],"color":"rgba(255,220,64,0.12)"},
                    {"range":[2.0,max(5,dl_gb*1.5)],"color":"rgba(57,255,150,0.10)"},
                ],
                "threshold":{"line":{"color":_GREEN,"width":2},"thickness":0.8,"value":dl_gb},
            }
        ), row=1, col=1)

        items = ["Contacts/d","Contact\n(min)","DL rate\n(Mbps÷10)","Link\nmargin (dB)"]
        vals  = [contacts, ct_min, dl_rate/10.0, link_db]
        clrs  = [
            _GREEN if contacts >= 4 else _YELLOW,
            _GREEN if ct_min >= 20  else _YELLOW,
            _GREEN if dl_rate >= 50 else _YELLOW,
            link_col,
        ]
        fig.add_trace(go.Bar(x=items, y=vals, marker_color=clrs, opacity=0.85,
                             text=[f"{x:.1f}" for x in vals],
                             textposition="outside",
                             textfont=dict(size=10,color="#c8e0f0"),
                             showlegend=False), row=1, col=2)
        fig.update_layout(**_PLOTLY_LAYOUT, height=330)
        self._web.setHtml(fig.to_html(include_plotlyjs="cdn", config={"displayModeBar":False}))


# ── 메인 BudgetViewer ─────────────────────────────────────────────────────────
class BudgetViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("budgetViewer")
        self._budget = None
        self._orbit  = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        hdr = QLabel("📊  MASS · POWER · LINK BUDGETS")
        hdr.setStyleSheet(
            "color:#ffaa00; font-size:10px; font-weight:bold;"
            "letter-spacing:2px; padding:6px 8px;"
            "background:#070e1c; border-bottom:1px solid #2a2010;"
        )
        layout.addWidget(hdr)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
        QTabWidget::pane { border:none; background:#050a14; }
        QTabBar::tab {
            background:#070e1c; color:#4a6a7a; padding:5px 12px;
            font-size:10px; border:1px solid #1a2535;
            border-bottom:none; border-radius:4px 4px 0 0; margin-right:2px;
        }
        QTabBar::tab:selected { background:#050a14; color:#00dcff; font-weight:bold; }
        QTabBar::tab:hover    { color:#c8e0f0; }
        """)
        self._mass_tab  = _MassTab()
        self._power_tab = _PowerTab()
        self._link_tab  = _LinkTab()
        self._tabs.addTab(self._mass_tab,  "⚖ Mass")
        self._tabs.addTab(self._power_tab, "⚡ Power")
        self._tabs.addTab(self._link_tab,  "📡 Link")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._tabs)
        self.setStyleSheet("#budgetViewer { background:#050a14; }")

    def update_data(self, budget: BudgetResult, orbit=None):
        self._budget = budget
        self._orbit  = orbit
        if budget:
            self._render_tab(self._tabs.currentIndex())

    def _on_tab_changed(self, idx: int):
        if self._budget:
            self._render_tab(idx)

    def _render_tab(self, idx: int):
        b = self._budget
        if idx == 0:
            self._mass_tab.refresh(b)
        elif idx == 1:
            self._power_tab.refresh(b)
        elif idx == 2:
            self._link_tab.refresh(b, self._orbit)
