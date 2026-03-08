"""
Log Panel — v0.6.0
분석 로그 패널: 접기/펼치기 가능한 하단 스트립
GMAT 실행 상태, 파이프라인 단계, 오류 메시지 표시
"""
from __future__ import annotations
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QLabel, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui  import QColor, QTextCharFormat, QFont


# 메시지 유형별 색상 (HTML)
_COLORS = {
    "info":    "#8ab0c0",
    "stage":   "#00dcff",
    "gmat":    "#ffa040",
    "success": "#39ff96",
    "warn":    "#ffdc40",
    "error":   "#ff6b6b",
    "debug":   "#4a6a7a",
}


class LogPanel(QWidget):
    """접기/펼치기 분석 로그 패널"""

    COLLAPSED_H = 28
    EXPANDED_H  = 160

    def __init__(self, max_lines: int = 300, parent=None):
        super().__init__(parent)
        self._max_lines = max_lines
        self._expanded  = True
        self._line_count = 0
        self._build_ui()

    # ── UI 구성 ───────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.setFixedHeight(self.EXPANDED_H)
        self.setStyleSheet("background:#040810; border-top: 1px solid rgba(0,220,255,0.2);")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 헤더 바 ──────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(self.COLLAPSED_H)
        header.setStyleSheet("background:#070e1c; border-bottom: 1px solid rgba(0,220,255,0.15);")
        hrow = QHBoxLayout(header)
        hrow.setContentsMargins(10, 0, 8, 0)
        hrow.setSpacing(8)

        lbl = QLabel("📋  Analysis Log")
        lbl.setStyleSheet("color:#00dcff; font-size:11px; font-weight:bold; letter-spacing:1px;")
        hrow.addWidget(lbl)

        hrow.addStretch()

        # GMAT 상태 배지
        self._gmat_badge = QLabel("⬤  GMAT: checking...")
        self._gmat_badge.setStyleSheet("color:#4a6a7a; font-size:10px; margin-right:8px;")
        hrow.addWidget(self._gmat_badge)

        # 지우기 버튼
        btn_clear = QPushButton("🗑")
        btn_clear.setFixedSize(22, 22)
        btn_clear.setStyleSheet("""
        QPushButton { background:transparent; color:#4a6a7a; border:none; font-size:12px; }
        QPushButton:hover { color:#ff6b6b; }
        """)
        btn_clear.clicked.connect(self.clear)
        btn_clear.setToolTip("로그 지우기")
        hrow.addWidget(btn_clear)

        # 접기/펼치기 버튼
        self._btn_toggle = QPushButton("▼")
        self._btn_toggle.setFixedSize(22, 22)
        self._btn_toggle.setStyleSheet("""
        QPushButton { background:transparent; color:#4a6a7a; border:none; font-size:11px; }
        QPushButton:hover { color:#00dcff; }
        """)
        self._btn_toggle.clicked.connect(self.toggle)
        hrow.addWidget(self._btn_toggle)

        root.addWidget(header)

        # ── 텍스트 영역 ───────────────────────────────────────────────────────
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setStyleSheet("""
        QTextEdit {
            background: #020508;
            color: #8ab0c0;
            border: none;
            font-family: 'Consolas', 'JetBrains Mono', monospace;
            font-size: 10.5px;
            line-height: 1.6;
            padding: 4px 8px;
        }
        QScrollBar:vertical {
            background: #050a14;
            width: 8px;
            border: none;
        }
        QScrollBar::handle:vertical {
            background: rgba(0,220,255,0.25);
            border-radius: 4px;
        }
        """)
        root.addWidget(self._text)

    # ── 공개 API ──────────────────────────────────────────────────────────────
    def log(self, message: str, level: str = "info"):
        """
        로그 메시지 추가
        level: info | stage | gmat | success | warn | error | debug
        """
        color = _COLORS.get(level, _COLORS["info"])
        ts    = datetime.now().strftime("%H:%M:%S")
        # 레벨 접두사
        prefix_map = {
            "stage":   "▶ ",
            "gmat":    "⚙ ",
            "success": "✓ ",
            "warn":    "⚠ ",
            "error":   "✗ ",
            "debug":   "· ",
        }
        prefix = prefix_map.get(level, "  ")

        html = (
            f'<span style="color:#2a4a5a;">[{ts}]</span> '
            f'<span style="color:{color};">{prefix}{message}</span>'
        )
        self._text.append(html)
        self._line_count += 1

        # 최대 줄 수 초과 시 맨 위 절반 삭제
        if self._line_count > self._max_lines:
            cursor = self._text.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(
                cursor.MoveOperation.Down,
                cursor.MoveMode.KeepAnchor,
                self._max_lines // 2
            )
            cursor.removeSelectedText()
            self._line_count -= self._max_lines // 2

        # 자동 스크롤
        vsb = self._text.verticalScrollBar()
        vsb.setValue(vsb.maximum())

    def clear(self):
        self._text.clear()
        self._line_count = 0

    def toggle(self):
        self._expanded = not self._expanded
        if self._expanded:
            self.setFixedHeight(self.EXPANDED_H)
            self._btn_toggle.setText("▼")
        else:
            self.setFixedHeight(self.COLLAPSED_H)
            self._btn_toggle.setText("▲")

    def set_gmat_status(self, available: bool, console: bool = False):
        """GMAT 가용 여부를 배지에 표시"""
        if console:
            self._gmat_badge.setText("⬤  GMAT: Console ✓")
            self._gmat_badge.setStyleSheet("color:#39ff96; font-size:10px; margin-right:8px;")
        elif available:
            self._gmat_badge.setText("⬤  GMAT: GUI only")
            self._gmat_badge.setStyleSheet("color:#ffdc40; font-size:10px; margin-right:8px;")
        else:
            self._gmat_badge.setText("⬤  GMAT: N/A (fallback)")
            self._gmat_badge.setStyleSheet("color:#ff6b6b; font-size:10px; margin-right:8px;")

    def set_max_lines(self, n: int):
        self._max_lines = max(50, n)
