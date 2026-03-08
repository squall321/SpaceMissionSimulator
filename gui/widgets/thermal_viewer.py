"""
Thermal Viewer Panel
Plotly 기반 실시간 온도 이력 (시간별 노드 온도) 차트 시각화
"""
import plotly.graph_objects as go
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl
from core.domain.thermal import ThermalResult

class ThermalViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("thermalViewer")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        hdr = QLabel("🌡  THERMAL ANALYSIS (LUMPED-NODE)")
        hdr.setStyleSheet("""
        color: #ffa040; font-size: 10px; font-weight: bold;
        letter-spacing: 2px; padding: 4px 0;
        border-bottom: 1px solid #2a1a10;
        """)
        layout.addWidget(hdr)
        
        self.web_view = QWebEngineView()
        self.web_view.setStyleSheet("background: transparent;")
        layout.addWidget(self.web_view)
        
        self.setStyleSheet("""
        #thermalViewer { background: #0d1525; }
        """)

    def update_data(self, thermal: ThermalResult):
        """해석 완료 시 불림: Plotly HTML을 생성해서 웹뷰에 로드"""
        if not thermal or not thermal.time_s:
            return
            
        fig = go.Figure()
        
        # Plotly 다크/사이버펑크 테마 색상상
        colors = {
            "Bus Structure": "#00dcff",
            "Solar Panel+Y": "#ffa040",
            "Solar Panel-Y": "#ff5500",
            "Radiator":      "#ff4d6d",
            "Electronics":   "#39ff96",
            "Battery":       "#cc33ff"
        }
        
        times_min = [t / 60.0 for t in thermal.time_s]
        
        for node_name, temps in thermal.temp_histories.items():
            color = colors.get(node_name, "#ffffff")
            fig.add_trace(go.Scatter(
                x=times_min, y=temps,
                mode='lines',
                name=node_name,
                line=dict(width=2, color=color)
            ))
            
        # 운용 허용 온도 (예: 전자장비 -20~70)
        fig.add_hrect(
            y0=-20, y1=70, line_width=0, 
            fillcolor="#39ff96", opacity=0.05,
            annotation_text="Operating Range", 
            annotation_position="bottom right",
            annotation_font_color="#39ff96"
        )
            
        # 차트 레이아웃 스타일 설정
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0d1525",
            plot_bgcolor="#0a0f1e",
            margin=dict(l=30, r=10, t=30, b=30),
            legend=dict(
                orientation="h",
                yanchor="bottom", y=1.02,
                xanchor="right", x=1,
                font=dict(size=10, color="#a0c8d8")
            ),
            xaxis=dict(
                title="Time (min)",
                title_font=dict(size=10, color="#5a8a9a"),
                tickfont=dict(size=10, color="#5a8a9a"),
                gridcolor="#1e2a3a",
                zeroline=False
            ),
            yaxis=dict(
                title="Temperature (°C)",
                title_font=dict(size=10, color="#5a8a9a"),
                tickfont=dict(size=10, color="#5a8a9a"),
                gridcolor="#1e2a3a"
            )
        )
        
        # HTML 렌더링 후 로드
        html = fig.to_html(include_plotlyjs='cdn', config={'displayModeBar': False})
        self.web_view.setHtml(html)
