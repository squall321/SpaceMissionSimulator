"""
Comparison Dialog
다중 위성 분석 결과를 한눈에 비교하는 표를 띄우는 다이얼로그
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLabel, QHBoxLayout, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt

class ComparisonDialog(QDialog):
    def __init__(self, results_history, parent=None, scenario_names=None):
        super().__init__(parent)
        self._results_history = results_history
        self._scenario_names  = scenario_names or []
        self.setWindowTitle("Satellite Constellation Comparison")
        self.resize(800, 500)
        self.setup_ui(results_history, self._scenario_names)

    def setup_ui(self, results_history, scenario_names):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # 헤더
        hdr_layout = QHBoxLayout()
        hdr = QLabel("🛰 Constellation Comparison Report")
        hdr.setStyleSheet("color: #00dcff; font-size: 14px; font-weight: bold; letter-spacing: 2px;")
        hdr_layout.addWidget(hdr)
        hdr_layout.addStretch()
        layout.addLayout(hdr_layout)

        # 테이블
        self.table = QTableWidget()
        cols = len(results_history)
        
        # 행: 표시할 항목 리스트
        ROWS = [
            ("Orbit Type",        lambda r: str(r['orbit'].params.orbit_type)),
            ("Altitude (km)",     lambda r: f"{r['orbit'].params.altitude_km:.1f}"),
            ("Inclination (°)",   lambda r: f"{r['orbit'].params.inclination_deg:.1f}"),
            ("RAAN (°)",          lambda r: f"{r['orbit'].params.raan_deg:.1f}"),
            ("Period (min)",      lambda r: f"{r['orbit'].period_min:.1f}"),
            ("Sunlight (%)",      lambda r: f"{r['orbit'].sunlight_fraction * 100:.1f}"),
            ("Max Eclipse (min)", lambda r: f"{max((e.duration_min for e in r['orbit'].eclipse_events), default=0):.1f}"),
            ("Contacts/Day",      lambda r: f"{r['orbit'].contacts_per_day:.1f}"),
            ("Temp Max (°C)",     lambda r: f"{max(r['thermal'].node_temps_max.values(), default=0):.1f}"),
            ("Temp Min (°C)",     lambda r: f"{min(r['thermal'].node_temps_min.values(), default=0):.1f}"),
            ("Battery DOD (%)",   lambda r: f"{r['budget'].battery_dod_pct:.1f}"),
            ("TID 5yr (krad)",    lambda r: f"{r['radiation'].tid_krad_5yr:.1f}"),
            ("Data Limit (GB/d)", lambda r: f"{r['budget'].data_per_day_gb:.1f}"),
            ("Total Score",       lambda r: f"{r['score'].total_score:.0f}"),
            ("Grade",             lambda r: str(r['score'].grade))
        ]

        self.table.setRowCount(len(ROWS))
        self.table.setColumnCount(cols)
        
        # 행 헤더 라벨 적용
        self.table.setVerticalHeaderLabels([row[0] for row in ROWS])
        # 열 헤더 라벨 적용 (시나리오 이름 우선, 없으면 SAT-N)
        col_names = [(scenario_names[i] if i < len(scenario_names) else f"SAT-{i+1}")
                     for i in range(cols)]
        self.table.setHorizontalHeaderLabels(col_names)

        # 데이터 채우기
        for col_idx, results in enumerate(results_history):
            for row_idx, (_, func) in enumerate(ROWS):
                val_str = func(results)
                item = QTableWidgetItem(val_str)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # 약간의 색상 변경 등 (Grade 표기 등)
                if row_idx == len(ROWS) - 1: # Grade
                    if 'A' in val_str: item.setForeground(Qt.GlobalColor.green)
                    elif 'F' in val_str: item.setForeground(Qt.GlobalColor.red)
                    else: item.setForeground(Qt.GlobalColor.yellow)

                self.table.setItem(row_idx, col_idx, item)

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # 스타일 (다크 테마 우주 컨셉)
        self.table.setStyleSheet("""
        QTableWidget {
            background-color: rgba(10, 15, 30, 0.9);
            color: #c8e0f0;
            gridline-color: rgba(0, 220, 255, 0.2);
            border: 1px solid rgba(0, 220, 255, 0.4);
            font-size: 11px;
        }
        QHeaderView::section {
            background-color: rgba(20, 35, 55, 0.9);
            color: #00dcff;
            padding: 4px;
            border: 1px solid rgba(0, 220, 255, 0.2);
            font-weight: bold;
        }
        QTableCornerButton::section {
            background-color: rgba(10, 15, 30, 0.9);
            border: 1px solid rgba(0, 220, 255, 0.2);
        }
        """)

        layout.addWidget(self.table)
        
        # 닫기 버튼
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_close.setStyleSheet("""
        QPushButton {
            background: rgba(0, 150, 200, 0.4);
            color: #ffffff;
            border: 1px solid rgba(0, 220, 255, 0.6);
            border-radius: 4px;
            padding: 6px 15px;
            font-size: 11px; font-weight: bold;
            max-width: 100px;
        }
        QPushButton:hover { background: rgba(0, 200, 255, 0.6); }
        """)
        
        _BTN = """
        QPushButton {
            background: rgba(0, 150, 200, 0.4);
            color: #ffffff;
            border: 1px solid rgba(0, 220, 255, 0.6);
            border-radius: 4px;
            padding: 6px 15px;
            font-size: 11px; font-weight: bold;
            max-width: 130px;
        }
        QPushButton:hover { background: rgba(0, 200, 255, 0.6); }
        """
        btn_excel = QPushButton("📊 Export Excel")
        btn_excel.clicked.connect(self._export_excel)
        btn_excel.setStyleSheet(_BTN)

        btn_pdf = QPushButton("📄 Export PDF")
        btn_pdf.clicked.connect(self._export_pdf)
        btn_pdf.setStyleSheet(_BTN)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(btn_excel)
        btn_layout.addWidget(btn_pdf)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        self.setStyleSheet("""
        QDialog { background: #050a14; }
        """)

    # ── Export helpers ────────────────────────────────────────────────────────
    def _export_excel(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Excel", "mission_analysis.xlsx",
            "Excel Files (*.xlsx)"
        )
        if not path:
            return
        try:
            from gui.utils.export_service import export_excel
            export_excel(self._results_history, self._scenario_names, path)
            QMessageBox.information(self, "Export", f"Excel 저장 완료:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF", "mission_analysis.pdf",
            "PDF Files (*.pdf)"
        )
        if not path:
            return
        try:
            from gui.utils.export_service import export_pdf
            export_pdf(self._results_history, self._scenario_names, path)
            QMessageBox.information(self, "Export", f"PDF 저장 완료:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))
