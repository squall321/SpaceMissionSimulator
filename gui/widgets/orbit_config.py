"""
Orbit Configuration Panel
궤도 파라미터 입력 위젯 (우측 상단)
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QDoubleSpinBox, QComboBox, QPushButton, QFrame, QSpinBox,
    QGroupBox
)
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui  import QFont

from core.domain.orbit import OrbitParams


class LabeledSlider(QWidget):
    value_changed = Signal(float)

    def __init__(self, label: str, unit: str,
                 min_val: float, max_val: float,
                 default: float, decimals: int = 0):
        super().__init__()
        self._scale = 10 ** decimals
        self._decimals = decimals

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(2)

        # 레이블 행
        top = QHBoxLayout()
        self.name_lbl = QLabel(label)
        self.name_lbl.setStyleSheet("color: #5a8a9a; font-size: 10px;")
        self.val_lbl = QLabel(f"{default:.{decimals}f} {unit}")
        self.val_lbl.setStyleSheet("color: #00dcff; font-size: 11px; font-weight: bold;")
        self.val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        top.addWidget(self.name_lbl)
        top.addWidget(self.val_lbl)
        layout.addLayout(top)

        # 슬라이더
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(int(min_val * self._scale), int(max_val * self._scale))
        self.slider.setValue(int(default * self._scale))
        self.slider.setStyleSheet("""
        QSlider::groove:horizontal {
            height: 4px; 
            background: rgba(30, 42, 58, 0.6); 
            border-radius: 2px;
        }
        QSlider::handle:horizontal {
            width: 14px; height: 14px;
            background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
                                      stop:0 #ffffff, stop:0.3 #00ffff, stop:1 #0077aa);
            border: 1px solid #ffffff;
            border-radius: 7px;
            margin: -5px 0;
        }
        QSlider::handle:horizontal:hover {
            width: 16px; height: 16px;
            margin: -6px 0;
            background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
                                      stop:0 #ffffff, stop:0.4 #00ffff, stop:1 #0099cc);
        }
        QSlider::sub-page:horizontal {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                         stop:0 rgba(0, 102, 170, 0.8), stop:1 rgba(0, 220, 255, 0.9));
            border-radius: 2px;
        }
        """)
        self.slider.valueChanged.connect(self._on_change)
        layout.addWidget(self.slider)

        self._unit = unit

    def _on_change(self, v: int):
        val = v / self._scale
        self.val_lbl.setText(f"{val:.{self._decimals}f} {self._unit}")
        self.value_changed.emit(val)

    def value(self) -> float:
        return self.slider.value() / self._scale


class OrbitConfigPanel(QWidget):
    params_changed = Signal(OrbitParams)

    ORBIT_TYPES = ["SSO", "DDSSO", "LEO_EQ", "LEO_POLAR"]
    PRESETS = {
        "SSO 550km":     (550,  97.6,  0.0,  "SSO"),
        "DDSSO 600km":   (600,  97.8,  90.0, "DDSSO"),
        "LEO 400km":     (400,  51.6,  0.0,  "LEO_EQ"),
        "Polar 700km":   (700,  98.2,  0.0,  "LEO_POLAR"),
        "우주DC 최적":    (550,  97.6,  30.0, "DDSSO"),
    }

    def __init__(self):
        super().__init__()
        self.setObjectName("orbitConfig")
        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._emit_params)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # 헤더
        hdr = QLabel("🌍  ORBIT PARAMETERS")
        hdr.setStyleSheet("""
        color: #ffffff; font-size: 11px; font-weight: 800;
        letter-spacing: 3px; padding: 6px 0;
        border-bottom: 1px solid rgba(0, 220, 255, 0.3);
        """)
        layout.addWidget(hdr)

        # 프리셋
        preset_row = QHBoxLayout()
        preset_lbl = QLabel("Preset:")
        preset_lbl.setStyleSheet("color: #7ab0c6; font-size: 10px; font-weight: bold;")
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(self.PRESETS.keys())
        self.preset_combo.setStyleSheet("""
        QComboBox { 
            background: rgba(13, 26, 42, 0.6); 
            color: #c8e0f0; 
            border: 1px solid rgba(42, 58, 74, 0.8);
            border-radius: 4px; padding: 4px 8px; font-size: 10px; 
            font-weight: 600;
        }
        QComboBox:hover {
            border: 1px solid rgba(0, 220, 255, 0.6);
            background: rgba(18, 36, 58, 0.8); 
        }
        QComboBox::drop-down { border: none; }
        QComboBox QAbstractItemView { 
            background: #0d1a2a; color: #c8e0f0;
            selection-background-color: rgba(0, 220, 255, 0.3); 
            selection-color: #ffffff;
            border: 1px solid #1e3a5a;
        }
        """)
        self.preset_combo.currentTextChanged.connect(self._apply_preset)
        preset_row.addWidget(preset_lbl)
        preset_row.addWidget(self.preset_combo, 1)
        layout.addLayout(preset_row)

        # 슬라이더들
        self.s_alt  = LabeledSlider("Altitude",    "km",  300, 2000, 550, 0)
        self.s_inc  = LabeledSlider("Inclination", "°",   0,  180,  97.6, 1)
        self.s_raan = LabeledSlider("RAAN",        "°",   0,  360,  0.0,  0)
        self.s_dur  = LabeledSlider("Duration",    "days",1,   10,  3.0,  0)

        for s in [self.s_alt, self.s_inc, self.s_raan, self.s_dur]:
            s.value_changed.connect(self._on_slider_change)
            layout.addWidget(s)

        # 궤도 타입
        type_row = QHBoxLayout()
        type_lbl = QLabel("Orbit Type:")
        type_lbl.setStyleSheet("color: #7ab0c6; font-size: 10px; font-weight: bold;")
        self.type_combo = QComboBox()
        self.type_combo.addItems(self.ORBIT_TYPES)
        self.type_combo.setStyleSheet(self.preset_combo.styleSheet())
        self.type_combo.currentIndexChanged.connect(self._on_slider_change)
        type_row.addWidget(type_lbl)
        type_row.addWidget(self.type_combo, 1)
        layout.addLayout(type_row)

        layout.addSpacing(4)

        # 실행 버튼
        self.run_btn = QPushButton("▶   RE-ANALYZE")
        self.run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_btn.setStyleSheet("""
        QPushButton {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                                      stop:0 rgba(0, 110, 150, 0.9), 
                                      stop:1 rgba(0, 160, 210, 0.9));
            color: #ffffff; 
            border: 1px solid rgba(0, 220, 255, 0.4); 
            border-radius: 5px;
            font-size: 11px; font-weight: 900; padding: 10px;
            letter-spacing: 2px;
        }
        QPushButton:hover  { 
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                                      stop:0 rgba(0, 150, 200, 1.0), 
                                      stop:1 rgba(0, 200, 240, 1.0));
            border: 1px solid rgba(0, 255, 255, 0.8);
        }
        QPushButton:pressed{ 
            background: rgba(0, 50, 80, 0.9); 
            border: 1px solid #00557a;
        }
        """)
        self.run_btn.clicked.connect(self._emit_params)
        layout.addWidget(self.run_btn)

        self.setStyleSheet("""
        #orbitConfig {
            background: rgba(10, 21, 37, 0.85); /* Semi-transparent Glass effect */
            border-bottom: 1px solid rgba(30, 42, 58, 0.9);
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        }
        """)

    def _on_slider_change(self):
        pass # self._debounce.start(800)   # 사용자가 실수로 드래그하는 도중 연쇄 분석되는 것을 막기 위해 비활성화

    def _apply_preset(self, name: str):
        if name in self.PRESETS:
            alt, inc, raan, otype = self.PRESETS[name]
            self.s_alt.slider.setValue(int(alt))
            self.s_inc.slider.setValue(int(inc * 10))
            self.s_raan.slider.setValue(int(raan))
            idx = self.ORBIT_TYPES.index(otype) if otype in self.ORBIT_TYPES else 0
            self.type_combo.setCurrentIndex(idx)
        # self._debounce.start(200) # 프리셋 선택 시엔 즉시 렌더링을 끄고 수동 버튼 클릭으로 유도

    def _emit_params(self):
        self.params_changed.emit(self.get_params())

    def get_params(self) -> OrbitParams:
        return OrbitParams(
            altitude_km      = self.s_alt.value(),
            inclination_deg  = self.s_inc.value(),
            raan_deg         = self.s_raan.value(),
            orbit_type       = self.type_combo.currentText(),
            duration_days    = max(1.0, self.s_dur.value()),
        )

    def set_params(self, params: OrbitParams):
        """외부에서 파라미터를 설정할 때 사용"""
        self.s_alt.slider.setValue(int(params.altitude_km))
        self.s_inc.slider.setValue(int(params.inclination_deg * 10))
        self.s_raan.slider.setValue(int(params.raan_deg))
        if params.orbit_type in self.ORBIT_TYPES:
            idx = self.ORBIT_TYPES.index(params.orbit_type)
            self.type_combo.setCurrentIndex(idx)
        self.s_dur.slider.setValue(int(params.duration_days))
