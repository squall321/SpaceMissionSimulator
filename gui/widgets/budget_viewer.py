"""
Budget Viewer Panel
질량, 전력 예산을 시각화하는 파이 차트/도넛 차트 뷰어
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtWebEngineWidgets import QWebEngineView
from core.domain.thermal import BudgetResult

class BudgetViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("budgetViewer")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        hdr = QLabel("📊  MASS & POWER BUDGETS")
        hdr.setStyleSheet("""
        color: #ffaa00; font-size: 10px; font-weight: bold;
        letter-spacing: 2px; padding: 4px 0;
        border-bottom: 1px solid #2a2010;
        """)
        layout.addWidget(hdr)
        
        self.web_view = QWebEngineView()
        self.web_view.setStyleSheet("background: transparent;")
        layout.addWidget(self.web_view)
        
        self.setStyleSheet("""
        #budgetViewer { background: #0d1525; }
        """)

    def update_data(self, budget: BudgetResult):
        if not budget:
            return
            
        fig = make_subplots(rows=2, cols=1, specs=[[{"type": "domain"}], [{"type": "domain"}]])
        
        # 1. Mass Budget (Donut Chart)
        mass_labels = ['Structure', 'Power', 'Thermal', 'ADCS', 'C&DH', 'Comms', 'Propulsion', 'Payload', 'Harness']
        mass_values = [
            budget.mass_structure_cbe, budget.mass_power_cbe, budget.mass_thermal_cbe,
            budget.mass_adcs_cbe, budget.mass_cdh_cbe, budget.mass_comms_cbe,
            budget.mass_propulsion_cbe, budget.mass_payload_cbe, budget.mass_harness_cbe
        ]
        
        fig.add_trace(go.Pie(
            labels=mass_labels, values=mass_values, hole=.4,
            name="Mass",
            marker=dict(colors=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22"]),
            textinfo='label+percent',
            textposition='inside',
            insidetextorientation='radial',
            title=dict(text=f"Mass<br>{sum(mass_values):.1f} kg", font=dict(color="#00dcff", size=14))
        ), 1, 1)
        
        # 2. Power Budget (Donut Chart)
        power_labels = ['Payload', 'Bus']
        power_values = [budget.power_payload_w, budget.power_bus_w]
        
        fig.add_trace(go.Pie(
            labels=power_labels, values=power_values, hole=.4,
            name="Power",
            marker=dict(colors=["#ffaa00", "#00dcff"]),
            textinfo='label+value',
            textposition='inside',
            insidetextorientation='radial',
            title=dict(text=f"Power<br>{sum(power_values):.1f} W", font=dict(color="#00dcff", size=14))
        ), 2, 1)
        
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0d1525",
            plot_bgcolor="#0a0f1e",
            margin=dict(l=10, r=10, t=30, b=10),
            showlegend=False,
            annotations=[
                dict(text=f"Mass Margin: {budget.mass_margin_pct:.1f}%", x=0.5, y=0.55, font_size=11, showarrow=False, font_color="#00ff00" if budget.mass_margin_pct > 10 else "#ff0000"),
                dict(text=f"Power Margin: {budget.power_margin_pct:.1f}%", x=0.5, y=-0.05, font_size=11, showarrow=False, font_color="#00ff00" if budget.power_margin_pct > 10 else "#ff0000")
            ]
        )
        
        html = fig.to_html(include_plotlyjs='cdn', config={'displayModeBar': False})
        self.web_view.setHtml(html)
