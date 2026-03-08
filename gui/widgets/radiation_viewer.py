"""
Radiation Viewer Panel
방사선 분석 결과 (TID 감쇄 곡선 및 누적 피폭량 게이지)
"""
import plotly.graph_objects as go
import numpy as np
import math
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtWebEngineWidgets import QWebEngineView
from core.domain.thermal import RadiationResult

class RadiationViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("radiationViewer")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        hdr = QLabel("☢  RADIATION ANALYSIS (AP-8 / AE-8)")
        hdr.setStyleSheet("""
        color: #ff4d6d; font-size: 10px; font-weight: bold;
        letter-spacing: 2px; padding: 4px 0;
        border-bottom: 1px solid #331018;
        """)
        layout.addWidget(hdr)
        
        self.web_view = QWebEngineView()
        self.web_view.setStyleSheet("background: transparent;")
        layout.addWidget(self.web_view)
        
        self.setStyleSheet("""
        #radiationViewer { background: #0d1525; }
        """)

    def update_data(self, radiation: RadiationResult):
        if not radiation:
            return
            
        fig = go.Figure()
        
        # 1. 오른쪽 게이지 차트: TID 진행률
        max_tid = 100.0 if radiation.tid_krad_5yr < 100 else 300.0
        
        fig.add_trace(go.Indicator(
            mode="gauge+number",
            value=radiation.tid_krad_5yr,
            title={'text': "TID (5 Years)", 'font': {'size': 14, 'color': '#a0c8d8'}},
            number={'suffix': " kRad", 'font': {'size': 24, 'color': '#ff4d6d'}},
            domain={'x': [0.65, 1], 'y': [0.1, 0.9]},
            gauge={
                'axis': {'range': [None, max_tid], 'tickwidth': 1, 'tickcolor': "#4a6a7a"},
                'bar': {'color': "#ff4d6d"},
                'bgcolor': "#1e2a3a",
                'borderwidth': 2,
                'bordercolor': "#2a3a4a",
                'steps': [
                    {'range': [0, 20], 'color': 'rgba(57, 255, 150, 0.2)'},
                    {'range': [20, 100], 'color': 'rgba(255, 160, 64, 0.2)'},
                    {'range': [100, max_tid], 'color': 'rgba(255, 77, 109, 0.2)'}
                ],
                'threshold': {
                    'line': {'color': "#ffffff", 'width': 3},
                    'thickness': 0.75,
                    'value': 20.0  # 목표 Limit
                }
            }
        ))
        
        # 2. 왼쪽 라인 차트: 차폐 두께 vs TID 감쇄 곡선
        base_tid = radiation.tid_krad_per_year / max(0.02, math.exp(-0.35 * (radiation.shielding_current_mm_al - 1.0)))
        x_mm = np.linspace(1.0, 15.0, 50)
        y_tid = base_tid * 5.0 * np.exp(-0.35 * (x_mm - 1.0))
        y_tid = np.maximum(y_tid, base_tid * 5.0 * 0.02)
        
        fig.add_trace(go.Scatter(
            x=x_mm, y=y_tid,
            mode='lines',
            name="Attenuation Curve",
            line=dict(color='#ff4d6d', width=3),
            xaxis="x", yaxis="y"
        ))
        
        # 현재 설계점
        fig.add_trace(go.Scatter(
            x=[radiation.shielding_current_mm_al], 
            y=[radiation.tid_krad_5yr],
            mode='markers+text',
            name="Current Design",
            marker=dict(size=12, color='#00dcff', symbol='diamond', line=dict(width=2, color='#ffffff')),
            text=["Current"], textposition="top right",
            textfont=dict(color='#00dcff'),
            xaxis="x", yaxis="y"
        ))
        
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0d1525",
            plot_bgcolor="#0a0f1e",
            margin=dict(l=40, r=10, t=50, b=40),
            showlegend=False,
            xaxis=dict(
                domain=[0, 0.55],
                title="Al Shielding Thickness (mm)",
                title_font=dict(size=11, color="#5a8a9a"),
                tickfont=dict(color="#5a8a9a"),
                gridcolor="#1e2a3a",
                zeroline=False
            ),
            yaxis=dict(
                domain=[0, 1],
                title="TID @ 5 Years (kRad)",
                title_font=dict(size=11, color="#5a8a9a"),
                tickfont=dict(color="#5a8a9a"),
                gridcolor="#1e2a3a",
                zeroline=False,
                type="log"
            ),
            annotations=[
                dict(
                    x=0.25, y=1.05, xref='paper', yref='paper',
                    text="Shielding Trade-off (Log Scale)",
                    showarrow=False,
                    font=dict(size=14, color="#a0c8d8"),
                    xanchor='center'
                )
            ]
        )
        
        html = fig.to_html(include_plotlyjs='cdn', config={'displayModeBar': False})
        self.web_view.setHtml(html)
