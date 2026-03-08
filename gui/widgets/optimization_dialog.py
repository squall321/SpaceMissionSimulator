"""
Orbit Optimization Dialog
궤도 최적화 탐색을 위한 대화상자
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QDoubleSpinBox, QSpinBox, QComboBox, QPushButton,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QWidget, QCheckBox, QTextEdit
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont
from typing import Optional
import time

from core.domain.orbit import OrbitParams
from core.services.orbit_optimization import (
    OrbitOptimizer, OptimizationConstraints, OptimizationObjectives,
    OptimizationResult, calculate_sso_inclination
)


class OptimizationWorker(QThread):
    """최적화 백그라운드 워커"""
    progress = Signal(int, int, float)  # current, total, best_score
    finished = Signal(object)  # OptimizationResult
    
    def __init__(self, optimizer: OrbitOptimizer, method: str, params: dict):
        super().__init__()
        self.optimizer = optimizer
        self.method = method
        self.params = params
        self._cancelled = False
    
    def run(self):
        self.optimizer.set_progress_callback(self._on_progress)
        
        if self.method == "grid":
            result = self.optimizer.grid_search(**self.params)
        elif self.method == "random":
            result = self.optimizer.random_search(**self.params)
        elif self.method == "evolutionary":
            result = self.optimizer.evolutionary_search(**self.params)
        else:
            result = OptimizationResult()
        
        self.finished.emit(result)
    
    def _on_progress(self, current, total, best_score):
        if not self._cancelled:
            self.progress.emit(current, total, best_score)
    
    def cancel(self):
        self._cancelled = True


class OrbitOptimizationDialog(QDialog):
    """궤도 최적화 대화상자"""
    
    result_selected = Signal(object)  # 선택된 OrbitParams
    
    def __init__(self, parent=None, sat_config: dict = None):
        super().__init__(parent)
        self.setWindowTitle("🛰 Orbit Optimization Explorer")
        self.resize(900, 700)
        self.sat_config = sat_config or {}
        self.worker: Optional[OptimizationWorker] = None
        self.last_result: Optional[OptimizationResult] = None
        
        self._build_ui()
        self._apply_style()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # 헤더
        header = QLabel("Orbit Design Space Exploration")
        header.setStyleSheet("color: #00dcff; font-size: 16px; font-weight: bold;")
        layout.addWidget(header)
        
        # 탭 위젯
        tabs = QTabWidget()
        tabs.addTab(self._build_search_tab(), "🔍 Search")
        tabs.addTab(self._build_constraints_tab(), "⚙️ Constraints")
        tabs.addTab(self._build_results_tab(), "📊 Results")
        layout.addWidget(tabs)
        
        # 하단 버튼
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_run = QPushButton("▶ Run Optimization")
        self.btn_run.setFixedWidth(160)
        self.btn_run.clicked.connect(self._run_optimization)
        btn_layout.addWidget(self.btn_run)
        
        self.btn_stop = QPushButton("■ Stop")
        self.btn_stop.setFixedWidth(80)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_optimization)
        btn_layout.addWidget(self.btn_stop)
        
        self.btn_apply = QPushButton("Apply Best")
        self.btn_apply.setFixedWidth(100)
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._apply_best)
        btn_layout.addWidget(self.btn_apply)
        
        btn_close = QPushButton("Close")
        btn_close.setFixedWidth(80)
        btn_close.clicked.connect(self.close)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
    
    def _build_search_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 탐색 방법 선택
        method_group = QGroupBox("Search Method")
        method_layout = QGridLayout(method_group)
        
        method_layout.addWidget(QLabel("Method:"), 0, 0)
        self.combo_method = QComboBox()
        self.combo_method.addItems(["Grid Search", "Random Search", "Evolutionary"])
        self.combo_method.currentIndexChanged.connect(self._on_method_changed)
        method_layout.addWidget(self.combo_method, 0, 1)
        
        layout.addWidget(method_group)
        
        # 파라미터 그룹
        params_group = QGroupBox("Search Parameters")
        params_layout = QGridLayout(params_group)
        
        # 고도 범위
        params_layout.addWidget(QLabel("Altitude Range (km):"), 0, 0)
        self.spin_alt_min = QDoubleSpinBox()
        self.spin_alt_min.setRange(200, 2000)
        self.spin_alt_min.setValue(400)
        params_layout.addWidget(self.spin_alt_min, 0, 1)
        
        params_layout.addWidget(QLabel("~"), 0, 2)
        self.spin_alt_max = QDoubleSpinBox()
        self.spin_alt_max.setRange(200, 2000)
        self.spin_alt_max.setValue(700)
        params_layout.addWidget(self.spin_alt_max, 0, 3)
        
        params_layout.addWidget(QLabel("Step:"), 0, 4)
        self.spin_alt_step = QDoubleSpinBox()
        self.spin_alt_step.setRange(10, 200)
        self.spin_alt_step.setValue(50)
        params_layout.addWidget(self.spin_alt_step, 0, 5)
        
        # 경사각 범위
        params_layout.addWidget(QLabel("Inclination Range (°):"), 1, 0)
        self.spin_inc_min = QDoubleSpinBox()
        self.spin_inc_min.setRange(0, 180)
        self.spin_inc_min.setValue(90)
        params_layout.addWidget(self.spin_inc_min, 1, 1)
        
        params_layout.addWidget(QLabel("~"), 1, 2)
        self.spin_inc_max = QDoubleSpinBox()
        self.spin_inc_max.setRange(0, 180)
        self.spin_inc_max.setValue(98)
        params_layout.addWidget(self.spin_inc_max, 1, 3)
        
        params_layout.addWidget(QLabel("Step:"), 1, 4)
        self.spin_inc_step = QDoubleSpinBox()
        self.spin_inc_step.setRange(0.5, 20)
        self.spin_inc_step.setValue(2)
        params_layout.addWidget(self.spin_inc_step, 1, 5)
        
        # SSO 자동 계산 버튼
        btn_sso = QPushButton("Calculate SSO Inclination")
        btn_sso.clicked.connect(self._calc_sso)
        params_layout.addWidget(btn_sso, 2, 0, 1, 2)
        
        self.label_sso = QLabel("")
        self.label_sso.setStyleSheet("color: #00ff88;")
        params_layout.addWidget(self.label_sso, 2, 2, 1, 4)
        
        # Random/Evolutionary 전용 파라미터
        params_layout.addWidget(QLabel("Samples / Population:"), 3, 0)
        self.spin_samples = QSpinBox()
        self.spin_samples.setRange(10, 500)
        self.spin_samples.setValue(50)
        params_layout.addWidget(self.spin_samples, 3, 1)
        
        params_layout.addWidget(QLabel("Generations (Evo only):"), 3, 2)
        self.spin_generations = QSpinBox()
        self.spin_generations.setRange(1, 50)
        self.spin_generations.setValue(10)
        params_layout.addWidget(self.spin_generations, 3, 3)
        
        layout.addWidget(params_group)
        
        # 진행 상황
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        self.label_status = QLabel("Ready")
        self.label_status.setStyleSheet("color: #c8e0f0;")
        progress_layout.addWidget(self.label_status)
        
        layout.addWidget(progress_group)
        layout.addStretch()
        
        return widget
    
    def _build_constraints_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 제약 조건
        const_group = QGroupBox("Constraints")
        const_layout = QGridLayout(const_group)
        
        const_layout.addWidget(QLabel("Max Eclipse Fraction:"), 0, 0)
        self.spin_max_eclipse = QDoubleSpinBox()
        self.spin_max_eclipse.setRange(0, 1)
        self.spin_max_eclipse.setSingleStep(0.05)
        self.spin_max_eclipse.setValue(0.4)
        const_layout.addWidget(self.spin_max_eclipse, 0, 1)
        
        const_layout.addWidget(QLabel("Min Contacts/Day:"), 1, 0)
        self.spin_min_contacts = QDoubleSpinBox()
        self.spin_min_contacts.setRange(0, 20)
        self.spin_min_contacts.setValue(4)
        const_layout.addWidget(self.spin_min_contacts, 1, 1)
        
        const_layout.addWidget(QLabel("Min Contact Time (min/day):"), 2, 0)
        self.spin_min_contact_time = QDoubleSpinBox()
        self.spin_min_contact_time.setRange(0, 120)
        self.spin_min_contact_time.setValue(30)
        const_layout.addWidget(self.spin_min_contact_time, 2, 1)
        
        const_layout.addWidget(QLabel("Max Total Dose (krad):"), 3, 0)
        self.spin_max_dose = QDoubleSpinBox()
        self.spin_max_dose.setRange(0, 500)
        self.spin_max_dose.setValue(100)
        const_layout.addWidget(self.spin_max_dose, 3, 1)
        
        layout.addWidget(const_group)
        
        # 목표 가중치
        obj_group = QGroupBox("Objective Weights")
        obj_layout = QGridLayout(obj_group)
        
        self.chk_sunlight = QCheckBox("Maximize Sunlight")
        self.chk_sunlight.setChecked(True)
        obj_layout.addWidget(self.chk_sunlight, 0, 0)
        self.spin_w_sun = QDoubleSpinBox()
        self.spin_w_sun.setRange(0, 5)
        self.spin_w_sun.setValue(1.0)
        obj_layout.addWidget(self.spin_w_sun, 0, 1)
        
        self.chk_contact = QCheckBox("Maximize Contact")
        self.chk_contact.setChecked(True)
        obj_layout.addWidget(self.chk_contact, 1, 0)
        self.spin_w_contact = QDoubleSpinBox()
        self.spin_w_contact.setRange(0, 5)
        self.spin_w_contact.setValue(1.0)
        obj_layout.addWidget(self.spin_w_contact, 1, 1)
        
        self.chk_dv = QCheckBox("Minimize ΔV")
        self.chk_dv.setChecked(True)
        obj_layout.addWidget(self.chk_dv, 2, 0)
        self.spin_w_dv = QDoubleSpinBox()
        self.spin_w_dv.setRange(0, 5)
        self.spin_w_dv.setValue(0.5)
        obj_layout.addWidget(self.spin_w_dv, 2, 1)
        
        self.chk_rad = QCheckBox("Minimize Radiation")
        self.chk_rad.setChecked(True)
        obj_layout.addWidget(self.chk_rad, 3, 0)
        self.spin_w_rad = QDoubleSpinBox()
        self.spin_w_rad.setRange(0, 5)
        self.spin_w_rad.setValue(0.8)
        obj_layout.addWidget(self.spin_w_rad, 3, 1)
        
        layout.addWidget(obj_group)
        layout.addStretch()
        
        return widget
    
    def _build_results_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 요약
        self.label_summary = QLabel("No results yet")
        self.label_summary.setStyleSheet("color: #00dcff; font-size: 12px;")
        layout.addWidget(self.label_summary)
        
        # 결과 테이블
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(7)
        self.results_table.setHorizontalHeaderLabels([
            "Rank", "Altitude (km)", "Inclination (°)", 
            "Sunlight (%)", "Contacts/Day", "ΔV (m/s/yr)", "Score"
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.itemDoubleClicked.connect(self._on_result_double_click)
        layout.addWidget(self.results_table)
        
        # 상세 정보
        self.text_details = QTextEdit()
        self.text_details.setReadOnly(True)
        self.text_details.setMaximumHeight(150)
        layout.addWidget(self.text_details)
        
        return widget
    
    def _apply_style(self):
        self.setStyleSheet("""
            QDialog {
                background-color: rgba(10, 15, 30, 0.95);
            }
            QGroupBox {
                color: #00dcff;
                border: 1px solid rgba(0, 220, 255, 0.3);
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
            QLabel {
                color: #c8e0f0;
            }
            QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: rgba(20, 35, 55, 0.9);
                color: #c8e0f0;
                border: 1px solid rgba(0, 220, 255, 0.3);
                border-radius: 3px;
                padding: 3px;
            }
            QPushButton {
                background-color: rgba(0, 100, 150, 0.7);
                color: #c8e0f0;
                border: 1px solid rgba(0, 220, 255, 0.5);
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: rgba(0, 150, 200, 0.8);
            }
            QPushButton:disabled {
                background-color: rgba(50, 50, 50, 0.5);
                color: #666;
            }
            QProgressBar {
                background-color: rgba(20, 35, 55, 0.9);
                border: 1px solid rgba(0, 220, 255, 0.3);
                border-radius: 3px;
                text-align: center;
                color: #c8e0f0;
            }
            QProgressBar::chunk {
                background-color: rgba(0, 220, 255, 0.7);
            }
            QTableWidget {
                background-color: rgba(10, 15, 30, 0.9);
                color: #c8e0f0;
                gridline-color: rgba(0, 220, 255, 0.2);
                border: 1px solid rgba(0, 220, 255, 0.4);
            }
            QHeaderView::section {
                background-color: rgba(20, 35, 55, 0.9);
                color: #00dcff;
                padding: 4px;
                border: 1px solid rgba(0, 220, 255, 0.2);
            }
            QTextEdit {
                background-color: rgba(10, 15, 30, 0.9);
                color: #c8e0f0;
                border: 1px solid rgba(0, 220, 255, 0.3);
            }
            QCheckBox {
                color: #c8e0f0;
            }
            QTabWidget::pane {
                border: 1px solid rgba(0, 220, 255, 0.3);
            }
            QTabBar::tab {
                background-color: rgba(20, 35, 55, 0.9);
                color: #c8e0f0;
                padding: 8px 20px;
                border: 1px solid rgba(0, 220, 255, 0.3);
            }
            QTabBar::tab:selected {
                background-color: rgba(0, 100, 150, 0.7);
                color: #00dcff;
            }
        """)
    
    def _on_method_changed(self, idx):
        # Grid Search는 step 파라미터 사용
        # Random/Evolutionary는 samples 사용
        is_grid = idx == 0
        self.spin_alt_step.setEnabled(is_grid)
        self.spin_inc_step.setEnabled(is_grid)
        self.spin_samples.setEnabled(not is_grid)
        self.spin_generations.setEnabled(idx == 2)
    
    def _calc_sso(self):
        alt = (self.spin_alt_min.value() + self.spin_alt_max.value()) / 2
        inc = calculate_sso_inclination(alt)
        self.label_sso.setText(f"SSO at {alt:.0f} km → {inc:.2f}°")
        self.spin_inc_min.setValue(inc - 1)
        self.spin_inc_max.setValue(inc + 1)
    
    def _build_constraints(self) -> OptimizationConstraints:
        return OptimizationConstraints(
            altitude_min=self.spin_alt_min.value(),
            altitude_max=self.spin_alt_max.value(),
            max_eclipse_fraction=self.spin_max_eclipse.value(),
            min_contacts_per_day=self.spin_min_contacts.value(),
            min_contact_time_per_day_min=self.spin_min_contact_time.value(),
            max_total_dose_krad=self.spin_max_dose.value()
        )
    
    def _build_objectives(self) -> OptimizationObjectives:
        return OptimizationObjectives(
            maximize_sunlight=self.chk_sunlight.isChecked(),
            maximize_contact=self.chk_contact.isChecked(),
            minimize_delta_v=self.chk_dv.isChecked(),
            minimize_radiation=self.chk_rad.isChecked(),
            weight_sunlight=self.spin_w_sun.value(),
            weight_contact=self.spin_w_contact.value(),
            weight_delta_v=self.spin_w_dv.value(),
            weight_radiation=self.spin_w_rad.value()
        )
    
    def _run_optimization(self):
        constraints = self._build_constraints()
        objectives = self._build_objectives()
        
        optimizer = OrbitOptimizer(constraints, objectives)
        
        method_idx = self.combo_method.currentIndex()
        method = ["grid", "random", "evolutionary"][method_idx]
        
        if method == "grid":
            params = {
                'altitude_range': (self.spin_alt_min.value(), self.spin_alt_max.value()),
                'altitude_step': self.spin_alt_step.value(),
                'inclination_range': (self.spin_inc_min.value(), self.spin_inc_max.value()),
                'inclination_step': self.spin_inc_step.value(),
                'sat_config': self.sat_config
            }
        elif method == "random":
            params = {
                'n_samples': self.spin_samples.value(),
                'sat_config': self.sat_config
            }
        else:
            params = {
                'population_size': self.spin_samples.value(),
                'generations': self.spin_generations.value(),
                'sat_config': self.sat_config
            }
        
        self.worker = OptimizationWorker(optimizer, method, params)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_apply.setEnabled(False)
        self.label_status.setText("Running optimization...")
        self.progress_bar.setValue(0)
        
        self.worker.start()
    
    def _stop_optimization(self):
        if self.worker:
            self.worker.cancel()
            self.worker.quit()
            self.label_status.setText("Cancelled")
        
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
    
    def _on_progress(self, current, total, best_score):
        progress = int(current / total * 100) if total > 0 else 0
        self.progress_bar.setValue(progress)
        self.label_status.setText(f"Progress: {current}/{total} | Best Score: {best_score:.3f}")
    
    def _on_finished(self, result: OptimizationResult):
        self.last_result = result
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_apply.setEnabled(result.best_params is not None)
        
        self.progress_bar.setValue(100)
        self.label_status.setText(
            f"Complete: {result.feasible_count}/{result.total_evaluated} feasible | "
            f"Best Score: {result.best_score:.3f}"
        )
        
        # 결과 탭 업데이트
        self._update_results(result)
    
    def _update_results(self, result: OptimizationResult):
        self.label_summary.setText(
            f"Total Evaluated: {result.total_evaluated} | "
            f"Feasible: {result.feasible_count} | "
            f"Best Score: {result.best_score:.3f}"
        )
        
        # 테이블 채우기
        self.results_table.setRowCount(0)
        
        for rank, (params, score, ctx) in enumerate(result.pareto_front[:20]):
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)
            
            orbit = ctx.orbit_result
            
            items = [
                f"#{rank+1}",
                f"{params.altitude_km:.1f}",
                f"{params.inclination_deg:.2f}",
                f"{orbit.sunlight_fraction*100:.1f}" if orbit else "-",
                f"{orbit.contacts_per_day:.1f}" if orbit else "-",
                f"{orbit.delta_v_per_year_ms:.1f}" if orbit else "-",
                f"{score:.3f}"
            ]
            
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 0 and rank == 0:
                    item.setForeground(Qt.GlobalColor.green)
                self.results_table.setItem(row, col, item)
        
        # 최고 결과 상세 정보
        if result.best_params and result.best_context:
            ctx = result.best_context
            orbit = ctx.orbit_result
            details = f"""
=== Best Orbit Configuration ===
Altitude: {result.best_params.altitude_km:.1f} km
Inclination: {result.best_params.inclination_deg:.2f}°
Period: {orbit.period_min:.1f} min

=== Performance ===
Sunlight Fraction: {orbit.sunlight_fraction*100:.1f}%
Eclipse Fraction: {orbit.eclipse_fraction*100:.1f}%
Contacts/Day: {orbit.contacts_per_day:.1f}
Contact Time/Day: {orbit.contact_time_per_day_min:.1f} min
ΔV/Year: {orbit.delta_v_per_year_ms:.1f} m/s

=== Score: {result.best_score:.3f} ===
"""
            self.text_details.setText(details)
    
    def _on_result_double_click(self, item):
        row = item.row()
        if self.last_result and row < len(self.last_result.pareto_front):
            params, _, ctx = self.last_result.pareto_front[row]
            self.result_selected.emit(params)
    
    def _apply_best(self):
        if self.last_result and self.last_result.best_params:
            self.result_selected.emit(self.last_result.best_params)
            self.accept()
