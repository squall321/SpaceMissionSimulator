"""
Timeline Widget
궤도 이벤트 타임라인 (일식/접속 바)
"""
import math
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QVBoxLayout
from PySide6.QtCore    import Qt
from PySide6.QtGui     import QPainter, QColor, QLinearGradient, QPen, QFont

from core.domain.orbit import OrbitResult


class TimelineBar(QWidget):
    """궤도 이벤트 시각화 바"""
    def __init__(self):
        super().__init__()
        self.setFixedHeight(28)
        self._orbit = None
        self.setStyleSheet("background: #060c18;")

    def update_timeline(self, orbit: OrbitResult):
        self._orbit = orbit
        self.update()

    def paintEvent(self, event):
        if not self._orbit:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        W = self.width()
        H = self.height()
        total_s = self._orbit.params.duration_days * 86400
        if total_s <= 0:
            return

        def t_to_x(t):
            return int(t / total_s * W)

        # 배경
        p.fillRect(0, 0, W, H, QColor("#070d1a"))

        y = H // 2 - 5
        bar_h = 10

        # 기본 (일조 = 진한 파랑)
        p.fillRect(0, y, W, bar_h, QColor("#0a2040"))

        # 일식 (빨강)
        for ev in self._orbit.eclipse_events:
            x1 = t_to_x(ev.start_time)
            x2 = t_to_x(ev.end_time)
            if x2 > x1:
                p.fillRect(x1, y, x2 - x1, bar_h, QColor("#cc2240"))

        # 접속 (초록)
        for cw in self._orbit.contact_windows:
            x1 = t_to_x(cw.start_time)
            x2 = t_to_x(cw.end_time)
            if x2 > x1:
                p.fillRect(x1, y - 2, max(x2 - x1, 2), bar_h + 4, QColor("#00cc66"))

        # 궤도 구분선
        p.setPen(QPen(QColor("#1e3a5a"), 1))
        period_px = t_to_x(self._orbit.period_min * 60)
        if period_px > 0:
            x = period_px
            while x < W:
                p.drawLine(x, y, x, y + bar_h)
                x += period_px

        p.end()


class TimelineWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(52)
        self.setObjectName("timeline")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        # 헤더 행
        hdr = QHBoxLayout()
        title = QLabel("◈  ORBIT TIMELINE")
        title.setStyleSheet("color: #3a6a8a; font-size: 9px; letter-spacing: 2px;")

        legend = QHBoxLayout()
        legend.setSpacing(10)
        for color, label in [("#0a2040","Sunlight"), ("#cc2240","Eclipse"), ("#00cc66","Contact")]:
            dot = QLabel("■")
            dot.setStyleSheet(f"color: {color}; font-size: 10px;")
            txt = QLabel(label)
            txt.setStyleSheet("color: #3a6a8a; font-size: 9px;")
            legend.addWidget(dot)
            legend.addWidget(txt)

        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addLayout(legend)
        layout.addLayout(hdr)

        self.bar = TimelineBar()
        layout.addWidget(self.bar)

        self.setStyleSheet("""
        #timeline {
            background: #060c18;
            border-top: 1px solid #1e2a3a;
        }
        """)

    def update_timeline(self, orbit: OrbitResult):
        self.bar.update_timeline(orbit)
