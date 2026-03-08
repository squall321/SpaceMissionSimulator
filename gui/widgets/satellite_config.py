"""
Satellite Configuration Panel
위성 본체의 물리, 열, 전력 파라미터 입력 위젯
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QDoubleSpinBox, QPushButton, QScrollArea, QFrame
)
from PySide6.QtCore import Signal, Qt, QTimer
import math

class ConfigSpinBoxRow(QWidget):
    value_changed = Signal(float)

    def __init__(self, label: str, unit: str, min_v: float, max_v: float, default: float, step: float = 1.0):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        
        lbl = QLabel(label)
        lbl.setStyleSheet("color: #5a8a9a; font-size: 11px;")
        
        self.spin = QDoubleSpinBox()
        self.spin.setRange(min_v, max_v)
        self.spin.setValue(default)
        self.spin.setSingleStep(step)
        self.spin.setSuffix(f" {unit}")
        self.spin.setStyleSheet("""
        QDoubleSpinBox {
            background: #0d1a2a; color: #00dcff; border: 1px solid #1e2a3a;
            border-radius: 4px; padding: 2px 4px; font-weight: bold;
            width: 80px;
        }
        QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
            background: #1e3a5a; width: 16px; border-left: 1px solid #1e2a3a;
        }
        """)
        self.spin.valueChanged.connect(self.value_changed.emit)

        layout.addWidget(lbl)
        layout.addStretch()
        layout.addWidget(self.spin)
        
    def value(self) -> float:
        return self.spin.value()

class SatelliteConfigPanel(QWidget):
    config_changed = Signal(dict)

    def __init__(self):
        super().__init__()
        self.setObjectName("satelliteConfig")
        
        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._emit_config)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(6)

        hdr = QLabel("🛰  SATELLITE PARAMETERS")
        hdr.setStyleSheet("""
        color: #ffaa00; font-size: 10px; font-weight: bold;
        letter-spacing: 2px; padding: 4px 0;
        border-bottom: 1px solid #2a2010;
        """)
        main_layout.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 입력 파라미터들
        # 컴퓨팅 사양 (app.py 기준)
        self.inputs = {
            'dual_boards':         ConfigSpinBoxRow("Dual Boards",       "ea",  1,   200,  20, 1),
            'total_power_w':       ConfigSpinBoxRow("Total Power",       "W",   100, 300000, 1600*20,  100),
            'mass_bus_kg':         ConfigSpinBoxRow("Bus Mass",          "kg",  5,   200,  20),
            'mass_panel_kg':       ConfigSpinBoxRow("Panel Mass",        "kg",  1,   30,   6),
            'mass_electronics_kg': ConfigSpinBoxRow("Avionics Mass",     "kg",  2,   50,   15),
            'mass_battery_kg':     ConfigSpinBoxRow("Battery Mass",      "kg",  1,   50,   10),
            'panel_area_m2':       ConfigSpinBoxRow("Total Panel Area",  "m²",  0.5, 20.0, 4.0,  0.5),
            'bus_area_m2':         ConfigSpinBoxRow("Bus Surface Area",  "m²",  0.5, 10.0, 1.5,  0.1),
            'radiator_area_m2':    ConfigSpinBoxRow("Radiator Area",     "m²",  0.1, 5.0,  1.2,  0.1),
            'shielding_mm':        ConfigSpinBoxRow("Al Shielding",      "mm",  0.5, 20.0, 3.0,  0.5),
            'aperture_cm':         ConfigSpinBoxRow("Camera Aperture",   "cm",  1.0, 100.0, 15.0, 0.5),
        }
        
        # 카테고리 분리 선
        self._add_section_label(layout, "Datacenter Compute Modules")
        layout.addWidget(self.inputs['dual_boards'])
        
        self._add_section_label(layout, "Power & Thermal Constraints")
        layout.addWidget(self.inputs['total_power_w'])
        layout.addWidget(self.inputs['shielding_mm'])
        
        self._add_section_label(layout, "Surface Areas")
        layout.addWidget(self.inputs['panel_area_m2'])
        layout.addWidget(self.inputs['radiator_area_m2'])
        layout.addWidget(self.inputs['bus_area_m2'])

        self._add_section_label(layout, "Mass Distribution")
        layout.addWidget(self.inputs['mass_bus_kg'])
        layout.addWidget(self.inputs['mass_panel_kg'])
        layout.addWidget(self.inputs['mass_electronics_kg'])
        layout.addWidget(self.inputs['mass_battery_kg'])

        self._add_section_label(layout, "Payload / Imaging Optics")
        layout.addWidget(self.inputs['aperture_cm'])

        for inp in self.inputs.values():
            inp.value_changed.connect(self._on_change)
            
        # 자동 연동
        self.inputs['dual_boards'].spin.valueChanged.connect(self._auto_calc_power)
            
        layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        self.setStyleSheet("""
        #satelliteConfig { background: #0d1525; }
        """)

    def _auto_calc_power(self, val):
        """Dual board 수량에 따라 전력/질량 자동 연동 (app.py 로직)"""
        dual_board_power = 1600.0 # W
        total_p = val * dual_board_power
        self.inputs['total_power_w'].spin.blockSignals(True)
        self.inputs['total_power_w'].spin.setValue(total_p)
        self.inputs['total_power_w'].spin.blockSignals(False)
        
        # Starlink-class 패러미터 추산 (app.py 기준)
        solar_area = (total_p / 0.65 / 1361.0 / 0.3)  # 보수적 추산
        if 'panel_area_m2' in self.inputs:
            self.inputs['panel_area_m2'].spin.setValue(round(solar_area, 1))
            self.inputs['mass_panel_kg'].spin.setValue(round(solar_area * 1.5, 1))
            
        radiator_area = (total_p / 350.0) # 기본 추산
        if 'radiator_area_m2' in self.inputs:
            self.inputs['radiator_area_m2'].spin.setValue(round(radiator_area, 1))
            
        # 컴퓨팅/구조 질량 연동
        dual_board_mass = 2.5
        shielding_per_module = 5.0
        modules = math.ceil(val / 10.0)
        compute_mass = val * dual_board_mass + modules * shielding_per_module
        
        bus_mass = compute_mass + total_p * 0.001
        self.inputs['mass_bus_kg'].spin.setValue(round(bus_mass, 1))

    def _add_section_label(self, layout, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #4a6a7a; font-size: 9px; margin-top: 8px; font-weight: bold;")
        layout.addWidget(lbl)

    def _on_change(self):
        self._debounce.start(800)

    def _emit_config(self):
        self.config_changed.emit(self.get_config())

    def get_config(self) -> dict:
        return {k: v.value() for k, v in self.inputs.items()}

    def set_config(self, cfg: dict):
        """외부에서 설정값 일괄 주입 (시나리오 패널 연동용)"""
        for key, val in cfg.items():
            if key in self.inputs:
                spin = self.inputs[key].spin
                spin.blockSignals(True)
                spin.setValue(float(val))
                spin.blockSignals(False)
