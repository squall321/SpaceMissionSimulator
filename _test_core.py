import sys
sys.path.insert(0, '.')
from core.domain.orbit import OrbitParams
from core.services.mission_analysis import MissionAnalysisService
from core.services.thermal_analysis import ThermalAnalysisService
from core.services.budget_radiation import BudgetService, RadiationService, DesignEvaluator

params = OrbitParams(altitude_km=550, inclination_deg=97.6, duration_days=2)
print('=== Orbit Analysis ===')
cfg = {'total_power_w':800,'panel_area_m2':4,'radiator_area_m2':1.2,
       'bus_area_m2':1.5,'mass_bus_kg':20,'mass_panel_kg':6,
       'mass_electronics_kg':15,'mass_battery_kg':10}

orbit = MissionAnalysisService().analyze(params, sat_config=cfg)
print(f'Period:     {orbit.period_min:.1f} min')
print(f'Sunlight:   {orbit.sunlight_fraction*100:.1f}%')
print(f'Eclipses:   {len(orbit.eclipse_events)} events')
print(f'Contacts:   {orbit.contacts_per_day:.1f}/day')
print(f'Beta angle: {orbit.beta_angle_deg:.1f} deg')

print()
print('=== Thermal Analysis ===')
thermal = ThermalAnalysisService().analyze(orbit, cfg)
tmax = max(thermal.node_temps_max.values(), default=0)
tmin = min(thermal.node_temps_min.values(), default=0)
print(f'T max: {tmax:.1f} C')
print(f'T min: {tmin:.1f} C')
print(f'Radiator req: {thermal.radiator_area_required_m2:.2f} m2')

print()
print('=== Budget ===')
budget = BudgetService().calc_power_budget(orbit, cfg['total_power_w'], 0.30, sat_config=cfg)
print(f'Solar panel req: {budget.solar_panel_area_m2:.2f} m2')
print(f'Solar panel cfg: {cfg["panel_area_m2"]:.2f} m2')
print(f'Battery req: {budget.battery_capacity_wh:.0f} Wh')
print(f'Mass struct cfg: {cfg["mass_bus_kg"]:.1f} kg')
print(f'Mass total:  {budget.mass_total_mev:.1f} kg (MEV)')
print(f'Mass margin: {budget.mass_margin_pct:.1f}%')
print(f'Power margin:{budget.power_margin_pct:.1f}%')

print()
print('=== Radiation ===')
rad = RadiationService().analyze(orbit, shielding_mm=3.0)
print(f'TID 5yr:  {rad.tid_krad_5yr:.1f} krad')
print(f'Grade:    {rad.component_grade}')
print(f'Risk:     {rad.risk_level}')

print()
print('=== Score ===')
score = DesignEvaluator().evaluate(orbit, budget, rad, tmax, tmin)
print(f'Score: {score.total_score:.1f}/100  Grade: {score.grade}')
for k, v in score.indicators.items():
    mark = 'PASS' if v['pass'] else 'FAIL'
    print(f'  {k:20s}: {v["value"]:7.1f} {v["unit"]:6s}  margin={v["margin"]:+.1f}  [{mark}]')

print()
print('All core services OK')
