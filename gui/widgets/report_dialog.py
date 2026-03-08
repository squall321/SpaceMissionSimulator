"""
ReportDialog  (v0.9.0)
HTML 분석 리포트 미리보기 + 저장 다이얼로그
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QWidget, QProgressBar
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Qt, QUrl, QThread, Signal


class _RenderThread(QThread):
    """Jinja2 렌더링을 백그라운드 스레드에서 실행"""
    done  = Signal(str)   # HTML 문자열
    error = Signal(str)

    def __init__(self, score, orbit, budget, thermal, radiation):
        super().__init__()
        self._args = (score, orbit, budget, thermal, radiation)

    def run(self):
        try:
            from core.services.report_generator import ReportGenerator
            gen  = ReportGenerator()
            html = gen.generate_html(*self._args)
            self.done.emit(html)
        except Exception as e:
            self.error.emit(str(e))


class ReportDialog(QDialog):
    """리포트 미리보기 + 저장 다이얼로그"""

    def __init__(self, score, orbit, budget, thermal, radiation, parent=None):
        super().__init__(parent)
        self._score    = score
        self._orbit    = orbit
        self._budget   = budget
        self._thermal  = thermal
        self._radiation = radiation
        self._html: str | None = None

        self.setWindowTitle("Mission Analysis Report")
        self.resize(980, 760)
        self.setModal(True)
        self._apply_style()
        self._build_ui()
        self._start_render()

    # ── UI ───────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 툴바
        toolbar = QWidget()
        toolbar.setFixedHeight(40)
        toolbar.setStyleSheet("background:#060c18;border-bottom:1px solid #1e2a3a;")
        tb_row = QHBoxLayout(toolbar)
        tb_row.setContentsMargins(12, 0, 8, 0)
        tb_row.setSpacing(8)

        title = QLabel("📄  MISSION ANALYSIS REPORT")
        title.setStyleSheet("color:#00dcff;font-size:10px;font-weight:700;letter-spacing:2px;")
        tb_row.addWidget(title)

        tb_row.addStretch()

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedSize(140, 12)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet("""
        QProgressBar{background:#1a2535;border:none;border-radius:3px;}
        QProgressBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 #0088cc,stop:1 #00dcff);border-radius:3px;}
        """)
        tb_row.addWidget(self._progress)
        self._progress_lbl = QLabel("렌더링 중...")
        self._progress_lbl.setStyleSheet("color:#4a6a7a;font-size:9px;")
        tb_row.addWidget(self._progress_lbl)

        # 버튼들
        def _btn(text, color, slot):
            b = QPushButton(text)
            b.setFixedHeight(26)
            b.setEnabled(False)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"""
            QPushButton{{color:{color};background:#0a0f1e;border:1px solid {color};
                border-radius:3px;font-size:9px;padding:0 10px;}}
            QPushButton:hover{{background:#1a2a3a;}}
            QPushButton:disabled{{color:#2a4a5a;border-color:#1a2a3a;}}
            """)
            b.clicked.connect(slot)
            return b

        self._save_btn   = _btn("💾 Save HTML", "#00dcff", self._on_save)
        self._browser_btn = _btn("🌐 Open in Browser", "#39ff96", self._on_browser)
        self._close_btn   = QPushButton("✕  Close")
        self._close_btn.setFixedHeight(26)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setStyleSheet("""
        QPushButton{color:#5a7a8a;background:transparent;border:none;
            font-size:9px;padding:0 8px;}
        QPushButton:hover{color:#c8d8e4;}
        """)
        self._close_btn.clicked.connect(self.close)

        for btn in (self._save_btn, self._browser_btn, self._close_btn):
            tb_row.addWidget(btn)

        root.addWidget(toolbar)

        # WebView 미리보기
        self._web = QWebEngineView()
        self._web.setStyleSheet("background:#0a0f1e;")
        root.addWidget(self._web)

    # ── 렌더링 ──────────────────────────────────────────────────
    def _start_render(self):
        self._thread = _RenderThread(
            self._score, self._orbit, self._budget,
            self._thermal, self._radiation
        )
        self._thread.done.connect(self._on_render_done)
        self._thread.error.connect(self._on_render_error)
        self._thread.start()

    def _on_render_done(self, html: str):
        self._html = html
        self._web.setHtml(html, QUrl("about:blank"))
        self._progress.setVisible(False)
        self._progress_lbl.setText("렌더링 완료")
        self._progress_lbl.setStyleSheet("color:#39ff96;font-size:9px;")
        for btn in (self._save_btn, self._browser_btn):
            btn.setEnabled(True)

    def _on_render_error(self, msg: str):
        self._progress.setVisible(False)
        self._progress_lbl.setText(f"오류: {msg}")
        self._progress_lbl.setStyleSheet("color:#ff4d6d;font-size:9px;")
        self._web.setHtml(
            f"<body style='background:#1a0d0d;color:#ff4d6d;font-family:monospace;padding:24px'>"
            f"<b>Report Generation Error</b><br><pre>{msg}</pre></body>"
        )

    # ── 저장 / 열기 ─────────────────────────────────────────────
    def _on_save(self):
        if not self._html:
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"SpaceD_Report_{ts}.html"
        path, _ = QFileDialog.getSaveFileName(
            self, "리포트 저장", default_name,
            "HTML Files (*.html);;All Files (*)"
        )
        if path:
            Path(path).write_text(self._html, encoding="utf-8")
            self._progress_lbl.setText(f"저장됨: {Path(path).name}")
            self._progress_lbl.setStyleSheet("color:#39ff96;font-size:9px;")

    def _on_browser(self):
        if not self._html:
            return
        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        tmp = Path(tempfile.gettempdir()) / f"SpaceD_Report_{ts}.html"
        tmp.write_text(self._html, encoding="utf-8")
        import webbrowser
        webbrowser.open(f"file:///{str(tmp).replace(os.sep, '/')}")
        self._progress_lbl.setText("브라우저에서 열림")
        self._progress_lbl.setStyleSheet("color:#39ff96;font-size:9px;")

    def _apply_style(self):
        self.setStyleSheet("""
        QDialog { background: #0a0f1e; color: #c8d8e4; }
        """)
