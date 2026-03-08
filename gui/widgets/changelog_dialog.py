"""
Changelog Dialog — 버전 히스토리 공시 뷰어
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui  import QFont

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import version as V


class ChangelogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"SpaceD-AADE — Release Notes")
        self.setFixedSize(520, 600)
        self.setModal(True)
        self._apply_style()
        self._build_ui()

    def _apply_style(self):
        self.setStyleSheet("""
        QDialog { background: #0a0f1e; }
        QScrollArea { background: transparent; border: none; }
        QScrollBar:vertical { background: rgba(13,26,42,.5); width: 5px; border-radius: 2px; }
        QScrollBar::handle:vertical { background: #2a3a4e; border-radius: 2px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 헤더 배너 ──────────────────────────────────────────
        banner = QWidget()
        banner.setFixedHeight(72)
        banner.setStyleSheet("""
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
          stop:0 #060c18, stop:0.5 #0d1a2e, stop:1 #060c18);
        border-bottom: 1px solid rgba(0,220,255,.25);
        """)
        b_lay = QHBoxLayout(banner)
        b_lay.setContentsMargins(24, 0, 24, 0)

        title_lbl = QLabel("⚡  SpaceD-AADE  —  Release Notes")
        title_lbl.setStyleSheet("color:#ffffff;font-size:16px;font-weight:800;letter-spacing:1px;")
        b_lay.addWidget(title_lbl)
        b_lay.addStretch()

        ver_lbl = QLabel(V.VERSION_FULL)
        ver_lbl.setStyleSheet(
            "color:#00dcff;font-size:12px;font-weight:700;"
            "background:rgba(0,220,255,.1);border:1px solid rgba(0,220,255,.4);"
            "border-radius:4px;padding:4px 10px;"
        )
        b_lay.addWidget(ver_lbl)
        root.addWidget(banner)

        # ── 스크롤 영역 ────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        i_lay = QVBoxLayout(inner)
        i_lay.setContentsMargins(20, 16, 20, 16)
        i_lay.setSpacing(16)

        for entry in V.CHANGELOG:
            i_lay.addWidget(self._build_entry(entry))

        i_lay.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll)

        # ── 하단 버튼 ──────────────────────────────────────────
        footer = QWidget()
        footer.setFixedHeight(52)
        footer.setStyleSheet("background:#060c18;border-top:1px solid rgba(30,42,58,.9);")
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(20, 0, 20, 0)
        f_lay.addWidget(self._build_date_lbl())
        f_lay.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setFixedSize(80, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
        QPushButton{background:rgba(0,130,180,.3);border:1px solid rgba(0,220,255,.4);
          border-radius:4px;color:#00dcff;font-size:11px;font-weight:700;}
        QPushButton:hover{background:rgba(0,180,230,.5);border:1px solid rgba(0,255,255,.7);}
        QPushButton:pressed{background:rgba(0,50,80,.8);}
        """)
        close_btn.clicked.connect(self.accept)
        f_lay.addWidget(close_btn)
        root.addWidget(footer)

    def _build_date_lbl(self) -> QLabel:
        lbl = QLabel(f"Build  {V.BUILD_DATE}")
        lbl.setStyleSheet("color:#3a5a6a;font-size:10px;")
        return lbl

    def _build_entry(self, entry: dict) -> QWidget:
        card = QWidget()
        card.setStyleSheet("""
        QWidget { background: rgba(13,26,42,.6);
                  border: 1px solid rgba(30,42,58,.9);
                  border-radius: 8px; }
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        # 버전 행
        top = QHBoxLayout()
        ver_badge = QLabel(f" v{entry['version']} ")
        stage_color = {"alpha": "#ffa040", "beta": "#ffee40", "rc": "#80ff80",
                       "release": "#00ff88"}.get(entry["stage"], "#aaaaaa")
        ver_badge.setStyleSheet(
            f"color:#ffffff;background:rgba(0,180,230,.25);"
            f"border:1px solid rgba(0,220,255,.5);border-radius:4px;"
            f"font-size:12px;font-weight:800;padding:2px 6px;"
        )
        top.addWidget(ver_badge)

        stage_badge = QLabel(entry["stage"].upper())
        stage_badge.setStyleSheet(
            f"color:{stage_color};background:rgba(255,160,64,.12);"
            f"border:1px solid {stage_color}44;border-radius:3px;"
            f"font-size:9px;font-weight:700;padding:2px 6px;"
        )
        top.addWidget(stage_badge)
        top.addStretch()

        date_lbl = QLabel(entry["date"])
        date_lbl.setStyleSheet("color:#4a6a7a;font-size:10px;")
        top.addWidget(date_lbl)
        lay.addLayout(top)

        # 하이라이트
        hl = QLabel(entry["highlights"])
        hl.setStyleSheet("color:#a0c8d8;font-size:11px;font-weight:700;")
        lay.addWidget(hl)

        # 구분선
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet("background:rgba(30,42,58,.9);border:none;")
        lay.addWidget(line)

        # 변경사항 목록
        for change_type, change_text in entry["changes"]:
            color = V.CHANGE_TYPE_COLOR.get(change_type, "#aaaaaa")
            badge_text = V.CHANGE_TYPE_LABEL.get(change_type, change_type.upper())

            row = QWidget()
            row.setStyleSheet("QWidget{background:transparent;border:none;}")
            r_lay = QHBoxLayout(row)
            r_lay.setContentsMargins(0, 1, 0, 1)
            r_lay.setSpacing(8)

            badge = QLabel(badge_text)
            badge.setFixedWidth(34)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                f"color:{color};background:rgba({self._hex_rgb(color)},.12);"
                f"border:1px solid {color}55;border-radius:3px;"
                f"font-size:8px;font-weight:800;"
            )
            r_lay.addWidget(badge)

            txt = QLabel(change_text)
            txt.setStyleSheet("color:#c8e0f0;font-size:10px;background:transparent;border:none;")
            txt.setWordWrap(True)
            txt.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            r_lay.addWidget(txt, 1)
            lay.addWidget(row)

        return card

    def _hex_rgb(self, h: str) -> str:
        h = h.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"{r},{g},{b}"
