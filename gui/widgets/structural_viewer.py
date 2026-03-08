"""
Structural Viewer Panel
내장 구조 해석기(StructuralAnalyzer) 결과 시각화 위젯.

표시 항목:
  - 고유진동수 바 차트 (1~10차)
  - 안전 여유(Margin of Safety) 테이블
  - 최대 응력 / 최대 변위 카드
  - 랜덤 진동 3σ 요약
  - 열응력 요약
"""
import plotly.graph_objects as go
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGridLayout, QFrame, QScrollArea,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Qt

from core.domain.structural import StructuralResult


# ── 색상 팔레트 ────────────────────────────────────────────────
_PASS_CLR   = "#39ff96"
_MARGIN_CLR = "#ffa040"
_FAIL_CLR   = "#ff4d6d"
_ACCENT     = "#00dcff"
_BG         = "#0d1525"
_CARD_BG    = "#0a1220"
_BORDER     = "#1e2a3a"


def _status_color(status: str) -> str:
    return {
        "PASS":   _PASS_CLR,
        "MARGIN": _MARGIN_CLR,
        "FAIL":   _FAIL_CLR,
    }.get(status, "#888")


class _MetricCard(QFrame):
    """단일 지표 카드"""
    def __init__(self, label: str, value: str, unit: str,
                 status: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        lbl = QLabel(label)
        lbl.setStyleSheet("color:#5a7a8a;font-size:9px;font-weight:bold;"
                          "letter-spacing:1px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        clr = _status_color(status) if status else _ACCENT
        val_lbl = QLabel(f"{value} <span style='font-size:9px;color:#5a7a8a'>{unit}</span>")
        val_lbl.setStyleSheet(f"color:{clr};font-size:14px;font-weight:bold;")
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val_lbl.setTextFormat(Qt.TextFormat.RichText)

        layout.addWidget(lbl)
        layout.addWidget(val_lbl)
        self.setStyleSheet(f"""
        #metricCard {{
            background:{_CARD_BG}; border:1px solid {_BORDER};
            border-radius:4px; min-width:80px;
        }}
        """)


class StructuralViewer(QWidget):
    """구조 해석 결과 패널"""

    def __init__(self):
        super().__init__()
        self.setObjectName("structuralViewer")

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── 헤더 ─────────────────────────────────────────────────
        hdr = QLabel("🏗  STRUCTURAL ANALYSIS")
        hdr.setStyleSheet(
            f"color:#00dcff;font-size:10px;font-weight:bold;"
            f"letter-spacing:2px;padding:4px 0;"
            f"border-bottom:1px solid {_BORDER};"
        )
        root.addWidget(hdr)

        # ── 요약 카드 행 ─────────────────────────────────────────
        self._card_row = QHBoxLayout()
        self._card_row.setSpacing(4)
        root.addLayout(self._card_row)
        self._cards: list[_MetricCard] = []

        # ── 고유진동수 차트 ──────────────────────────────────────
        freq_hdr = QLabel("고유진동수  (Natural Frequencies)")
        freq_hdr.setStyleSheet(
            "color:#5a7a8a;font-size:9px;letter-spacing:1px;margin-top:4px;")
        root.addWidget(freq_hdr)

        self.freq_chart = QWebEngineView()
        self.freq_chart.setFixedHeight(180)
        self.freq_chart.setStyleSheet("background:transparent;")
        root.addWidget(self.freq_chart)

        # ── MarginOfSafety 테이블 ────────────────────────────────
        ms_hdr = QLabel("안전 여유  (Margin of Safety)")
        ms_hdr.setStyleSheet(
            "color:#5a7a8a;font-size:9px;letter-spacing:1px;margin-top:4px;")
        root.addWidget(ms_hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"background:{_BG};border:none;")
        self._ms_widget = QWidget()
        self._ms_layout = QGridLayout(self._ms_widget)
        self._ms_layout.setContentsMargins(0, 0, 0, 0)
        self._ms_layout.setSpacing(1)
        scroll.setWidget(self._ms_widget)
        scroll.setFixedHeight(160)
        root.addWidget(scroll)

        # ── 하단 요약 (랜덤/열응력) ──────────────────────────────
        self._extra_label = QLabel()
        self._extra_label.setWordWrap(True)
        self._extra_label.setStyleSheet(
            f"color:#8aabb8;font-size:10px;padding:6px;"
            f"border:1px solid {_BORDER};border-radius:4px;"
            f"background:{_CARD_BG};"
        )
        self._extra_label.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(self._extra_label)

        root.addStretch()

        self.setStyleSheet(f"#structuralViewer {{ background:{_BG}; }}")

    # ── 공개 API ─────────────────────────────────────────────────

    def update_data(self, result: StructuralResult):
        """분석 완료 시 호출 — StructuralResult로 모든 위젯 갱신"""
        if not result or not result.success:
            err = getattr(result, 'error', '') or '결과 없음'
            self._extra_label.setText(f"<span style='color:{_FAIL_CLR}'>⚠ {err}</span>")
            return

        self._update_cards(result)
        self._update_freq_chart(result)
        self._update_ms_table(result)
        self._update_extra(result)

    # ── 내부 갱신 메서드 ──────────────────────────────────────────

    def _update_cards(self, r: StructuralResult):
        # 기존 카드 제거
        for c in self._cards:
            self._card_row.removeWidget(c)
            c.deleteLater()
        self._cards.clear()

        freq_status = "PASS" if r.first_freq_hz >= 50 else \
                      "MARGIN" if r.first_freq_hz >= 35 else "FAIL"
        ms_status   = "PASS" if r.min_ms_yield >= 0.1 else \
                      "MARGIN" if r.min_ms_yield >= 0.0 else "FAIL"

        items = [
            ("1차 고유진동수", f"{r.first_freq_hz:.0f}", "Hz", freq_status),
            ("주파수 마진",    f"{r.freq_margin_pct:+.0f}", "%",  freq_status),
            ("최대 응력",      f"{r.max_von_mises_MPa:.1f}", "MPa",""),
            ("MS_yield",       f"{r.min_ms_yield:.2f}",  "",   ms_status),
            ("최대 변위",      f"{r.max_displacement_mm:.2f}", "mm", ""),
        ]
        for label, val, unit, status in items:
            card = _MetricCard(label, val, unit, status)
            self._card_row.addWidget(card)
            self._cards.append(card)

    def _update_freq_chart(self, r: StructuralResult):
        if not r.modes:
            return

        modes   = r.modes[:10]
        labels  = [f"Mode {m.mode_number}<br>{m.direction}" for m in modes]
        freqs   = [m.freq_hz for m in modes]
        colors  = [_PASS_CLR if f >= 50 else _MARGIN_CLR if f >= 35 else _FAIL_CLR
                   for f in freqs]

        fig = go.Figure(go.Bar(
            x=labels, y=freqs,
            marker_color=colors,
            text=[f"{f:.0f} Hz" for f in freqs],
            textposition="outside",
            textfont=dict(size=9, color="#c8d8e4"),
        ))
        # 최소 요구 주파수 기준선
        fig.add_hline(
            y=50.0, line=dict(color=_FAIL_CLR, dash="dash", width=1),
            annotation_text="Req 50 Hz", annotation_font_color=_FAIL_CLR,
            annotation_font_size=9,
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#060f1c",
            font=dict(color="#8aabb8", size=9), margin=dict(l=4,r=4,t=4,b=4),
            xaxis=dict(tickfont=dict(size=8), gridcolor="#1a2535"),
            yaxis=dict(title="Hz", gridcolor="#1a2535", tickfont=dict(size=8)),
            showlegend=False,
            height=170,
        )
        html = fig.to_html(full_html=True, include_plotlyjs="cdn",
                           config={"displayModeBar": False})
        self.freq_chart.setHtml(html)

    def _update_ms_table(self, r: StructuralResult):
        # 기존 내용 제거
        while self._ms_layout.count():
            item = self._ms_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 헤더
        headers = ["위치", "하중", "σ (MPa)", "MS_yield", "MS_ult", "판정"]
        hdr_style = ("color:#5a7a8a;font-size:8px;font-weight:bold;"
                     f"background:{_CARD_BG};padding:2px 4px;")
        for j, h in enumerate(headers):
            lbl = QLabel(h)
            lbl.setStyleSheet(hdr_style)
            self._ms_layout.addWidget(lbl, 0, j)

        for row_i, mg in enumerate(r.margins, start=1):
            clr = _status_color(mg.status)
            row_style = (f"color:#c8d8e4;font-size:8px;padding:2px 4px;"
                         f"border-bottom:1px solid {_BORDER};"
                         f"background:{'#080e1a' if row_i%2==0 else _CARD_BG};")
            vals = [mg.location[:14], mg.load_case[:8],
                    f"{mg.actual_stress_MPa:.2f}",
                    f"{mg.ms_yield:.3f}", f"{mg.ms_ultimate:.3f}", mg.status]
            for j, v in enumerate(vals):
                lbl = QLabel(v)
                lbl.setStyleSheet(row_style if j < 5 else
                                  f"color:{clr};font-size:8px;font-weight:bold;"
                                  f"padding:2px 4px;")
                self._ms_layout.addWidget(lbl, row_i, j)

    def _update_extra(self, r: StructuralResult):
        parts = []
        parts.append(
            f"<b>랜덤 진동 (Miles, Q=10):</b>  "
            f"3σ = <span style='color:{_ACCENT}'>{r.three_sigma_g} g</span>  |  "
            f"3σ 응력 = <span style='color:{_ACCENT}'>{r.three_sigma_stress_MPa} MPa</span>"
        )
        if r.thermal_stress:
            ts = r.thermal_stress
            ms_clr = _PASS_CLR if ts.ms_thermal >= 0.1 else \
                     _MARGIN_CLR if ts.ms_thermal >= 0.0 else _FAIL_CLR
            parts.append(
                f"<b>열응력 (ΔT={ts.delta_T_K:.0f} K, {ts.material}):</b>  "
                f"σ_th = <span style='color:{_ACCENT}'>{ts.thermal_stress_MPa} MPa</span>  |  "
                f"MS_th = <span style='color:{ms_clr}'>{ts.ms_thermal:.3f}</span>"
            )
        mode_tag = "Mock (내장 공식)" if r.mock_mode else "FEM"
        parts.append(
            f"<span style='color:#3a5a6a;font-size:9px;'>해석 모드: {mode_tag}</span>"
        )
        self._extra_label.setText("<br>".join(parts))
