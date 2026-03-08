"""v0.8.0 Pipeline Orchestrator Integration Test"""
import sys; sys.path.insert(0,'.')

from core.pipeline import PipelineOrchestrator, PipelineContext
from core.domain.orbit import OrbitParams
from core.services.mission_analysis import MissionAnalysisService
from core.services.thermal_analysis  import ThermalAnalysisService
from core.services.budget_radiation  import BudgetService, RadiationService, DesignEvaluator

logs = []
def _log(m, l): logs.append(f"[{l}] {m}")

stations = list(MissionAnalysisService.DEFAULT_STATIONS)
ctx = PipelineContext(
    orbit_params=OrbitParams(altitude_km=550, inclination_deg=97.6),
    sat_config={
        'total_power_w':800,'panel_area_m2':4.0,'radiator_area_m2':1.2,
        'bus_area_m2':1.5,'shielding_mm':3.0,'dual_boards':20
    },
    stations=stations,
    log_fn=_log,
    progress_fn=lambda m: None,
)
orch = PipelineOrchestrator.default(
    MissionAnalysisService(), ThermalAnalysisService(),
    BudgetService(), RadiationService(), DesignEvaluator()
)
ctx = orch.run(ctx)

print("=== Pipeline v0.8.0 Integration Test ===")
print(f"succeeded : {ctx.succeeded}")
print(f"duration  : {ctx.total_duration_sec:.2f}s")
print()
for r in ctx.stage_results:
    mark = "✓" if r.ok else ("↷" if r.status.name == "SKIPPED" else "✗")
    print(f"  {mark} {r.stage_name:<22} {r.status.name:<10} ({r.duration_sec:.2f}s)  {r.message[:45]}")
print()
if ctx.succeeded:
    o = ctx.orbit_result
    b = ctx.budget_result
    s = ctx.score_result
    print(f"  Orbit period      : {o.period_min:.1f} min")
    print(f"  Sunlight fraction : {o.sunlight_fraction*100:.1f}%")
    print(f"  Power margin      : {b.power_margin_w:.0f} W")
    print(f"  Battery DOD       : {b.battery_dod_pct:.0f}%")
    print(f"  TID 5yr           : {ctx.radiation_result.tid_krad_5yr:.1f} krad")
    print(f"  Score / Grade     : {s.total_score:.0f} / {s.grade}")
    print()
    print("  as_result_dict keys:", list(ctx.as_result_dict().keys()))
    print("  score_card alias  :", ctx.score_card is ctx.score_result)
    print("  ground_stations   :", len(ctx.ground_stations))
    print()
    print("ALL CHECKS PASSED")
else:
    print("FAILED:", [r.message for r in ctx.failed_stages])
    sys.exit(1)
