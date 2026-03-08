"""도메인 모델 패키지"""
from core.domain.orbit import OrbitParams, OrbitResult, EclipseEvent, ContactWindow
from core.domain.thermal import ThermalNode, ThermalResult
from core.domain.structural import (
    StructuralParams, StructuralResult,
    ModeShape, NodeResult, MarginOfSafety,
    ThermalStressResult, MATERIALS,
)

__all__ = [
    "OrbitParams", "OrbitResult", "EclipseEvent", "ContactWindow",
    "ThermalNode", "ThermalResult",
    "StructuralParams", "StructuralResult",
    "ModeShape", "NodeResult", "MarginOfSafety",
    "ThermalStressResult", "MATERIALS",
]
