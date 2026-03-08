"""
ReportGenerator  (v0.9.0)
Jinja2 HTML 리포트 생성기
- DesignScoreCard + OrbitResult + BudgetResult + ThermalResult + RadiationResult → HTML
- HTML → 브라우저 직접 열기 / 파일 저장
"""
from __future__ import annotations

import os
import math
import webbrowser
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

try:
    import version as V
    _VERSION = V.VERSION_FULL
except Exception:
    _VERSION = "v0.9.0-alpha"

_TEMPLATE_DIR = Path(__file__).parent.parent.parent / "data" / "design_templates"
_TEMPLATE_FILE = "mission_report.html.j2"

_GRADE_COLOR = {
    "A+": "#00ff88", "A": "#39ff96", "B": "#ffe066",
    "C": "#ffa040",  "F": "#ff4d6d", "N/A": "#5a7a8a"
}

_IND_META = {
    "sunlight_ratio":    ("일조율",         "%",      85,   "≥"),
    "max_eclipse":       ("최대 일식",       "min",    30,   "≤"),
    "battery_dod":       ("배터리 DOD",      "%",      35,   "≤"),
    "temp_max":          ("최고 온도",       "°C",     70,   "≤"),
    "temp_min":          ("최저 온도",       "°C",    -20,  "≥"),
    "tid_5yr":           ("TID 5년",         "krad",   20,   "≤"),
    "contacts_per_day":  ("접속 횟수",       "회/일",   4,   "≥"),
    "mass_margin":       ("질량 마진",       "%",      15,   "≥"),
    "power_margin":      ("전력 마진",       "%",      10,   "≥"),
}

_MASS_FIELDS = [
    ("Structure",  "mass_structure_cbe"),
    ("Power",      "mass_power_cbe"),
    ("Thermal",    "mass_thermal_cbe"),
    ("ADCS",       "mass_adcs_cbe"),
    ("C&DH",       "mass_cdh_cbe"),
    ("Comms",      "mass_comms_cbe"),
    ("Propulsion", "mass_propulsion_cbe"),
    ("Payload",    "mass_payload_cbe"),
    ("Harness",    "mass_harness_cbe"),
]


class ReportGenerator:
    """HTML 분석 리포트 생성기"""

    def __init__(self):
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=False
        )

    # ── public ───────────────────────────────────────────────────
    def generate_html(
        self,
        score,       # DesignScoreCard
        orbit,       # OrbitResult
        budget,      # BudgetResult
        thermal,     # ThermalResult
        radiation,   # RadiationResult
    ) -> str:
        """Jinja2 렌더링 → HTML 문자열 반환"""
        ctx = self._build_context(score, orbit, budget, thermal, radiation)
        tpl = self._env.get_template(_TEMPLATE_FILE)
        return tpl.render(**ctx)

    def save_html(
        self,
        score, orbit, budget, thermal, radiation,
        out_path: Optional[str] = None,
    ) -> str:
        """HTML 파일로 저장 → 파일 경로 반환"""
        html = self.generate_html(score, orbit, budget, thermal, radiation)
        if out_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = str(Path(tempfile.gettempdir()) / f"SpaceD_Report_{ts}.html")
        Path(out_path).write_text(html, encoding="utf-8")
        return out_path

    def open_in_browser(
        self,
        score, orbit, budget, thermal, radiation,
        out_path: Optional[str] = None,
    ) -> str:
        """HTML 저장 후 기본 브라우저로 열기 → 파일 경로 반환"""
        path = self.save_html(score, orbit, budget, thermal, radiation, out_path)
        webbrowser.open(f"file:///{path.replace(os.sep, '/')}")
        return path

    # ── context builder ──────────────────────────────────────────
    def _build_context(self, score, orbit, budget, thermal, radiation) -> dict:
        grade      = score.grade if score else "N/A"
        grade_col  = _GRADE_COLOR.get(grade, "#5a7a8a")
        total_score = round(score.total_score, 1) if score else 0.0

        inds       = score.indicators if score else {}
        pass_cnt   = sum(1 for v in inds.values() if v.get("pass", True))
        total_ind  = len(inds)
        pass_color = "#39ff96" if pass_cnt == total_ind else "#ffa040"

        # ── Orbit ────────────────────────────────────────────────
        alt = orbit.params.altitude_km if orbit else 0
        inc = orbit.params.inclination_deg if orbit else 0
        orbit_ctx = {
            "altitude_km":     round(alt, 1),
            "inclination_deg": round(inc, 2),
            "period_min":      round(orbit.period_min, 1) if orbit else 0,
            "sunlight_pct":    round((orbit.sunlight_fraction or 0) * 100, 1) if orbit else 0,
            "contacts_per_day": round(orbit.contacts_per_day, 1) if orbit else 0,
            "contact_min_day": round(orbit.contact_time_per_day_min, 1) if orbit else 0,
        }

        # ── Budget ───────────────────────────────────────────────
        margin_15 = (budget.mass_margin_pct or 0) >= 15 if budget else False
        pw_margin = (budget.power_margin_pct or 0) >= 10 if budget else False
        dod_ok    = (budget.battery_dod_pct or 35) <= 35 if budget else True
        budget_ctx = {
            "mass_total_cbe":       round(budget.mass_total_cbe, 1)      if budget else 0,
            "mass_total_mev":       round(budget.mass_total_mev, 1)      if budget else 0,
            "mass_margin_pct":      round(budget.mass_margin_pct, 1)     if budget else 0,
            "mass_launch_available": round(budget.mass_launch_available, 1) if budget else 0,
            "power_payload_w":      round(budget.power_payload_w, 1)     if budget else 0,
            "power_bus_w":          round(budget.power_bus_w, 1)         if budget else 0,
            "power_total_w":        round(budget.power_total_w, 1)       if budget else 0,
            "solar_generated_w":    round(budget.solar_generated_w, 1)   if budget else 0,
            "solar_panel_area_m2":  round(budget.solar_panel_area_m2, 2) if budget else 0,
            "battery_capacity_wh":  round(budget.battery_capacity_wh, 0) if budget else 0,
            "battery_dod_pct":      round(budget.battery_dod_pct, 1)     if budget else 30,
            "power_margin_w":       round(budget.power_margin_w, 1)      if budget else 0,
            "power_margin_pct":     round(budget.power_margin_pct, 1)    if budget else 0,
        }

        mass_rows = []
        if budget:
            for name, field in _MASS_FIELDS:
                cbe = getattr(budget, field, 0.0)
                mev = round(cbe * 1.15, 1)
                mass_rows.append({"name": name, "cbe": round(cbe, 1), "mev": mev})

        # ── Thermal ──────────────────────────────────────────────
        t_max = max(thermal.node_temps_max.values(), default=0.0)  if thermal else 0
        t_min = min(thermal.node_temps_min.values(), default=0.0)  if thermal else 0
        thermal_ctx = {
            "temp_max_c": round(t_max, 1),
            "temp_min_c": round(t_min, 1),
            "radiator_m2": round(thermal.radiator_area_required_m2, 2) if thermal else 0,
        }
        thermal_rows = []
        if thermal:
            for node in thermal.node_temps_max:
                thermal_rows.append({
                    "name": node,
                    "min":  round(thermal.node_temps_min.get(node, 0), 1),
                    "max":  round(thermal.node_temps_max.get(node, 0), 1),
                    "avg":  round(thermal.node_temps_avg.get(node, 0), 1),
                })

        # ── Radiation ────────────────────────────────────────────
        risk   = radiation.risk_level if radiation else "LOW"
        risk_to_badge = {"LOW": "badge-low", "MEDIUM": "badge-med", "HIGH": "badge-high"}
        rad_ctx = {
            "tid_5yr":        round(radiation.tid_krad_5yr, 1)       if radiation else 0,
            "tid_per_year":   round(radiation.tid_krad_per_year, 1)  if radiation else 0,
            "shielding_mm":   round(radiation.shielding_current_mm_al, 1) if radiation else 3,
            "component_grade": radiation.component_grade              if radiation else "—",
            "risk_level":     risk,
            "seu_rate":       f"{radiation.seu_rate_per_day:.2e}"    if radiation else "0",
        }
        tid_5yr = rad_ctx["tid_5yr"]
        tid_color = "#39ff96" if tid_5yr < 20 else ("#ffa040" if tid_5yr < 50 else "#ff4d6d")

        # ── ScoreCard rows ──────────────────────────────────────
        score_rows = []
        for key, ind in inds.items():
            meta = _IND_META.get(key)
            if not meta:
                continue
            name, unit, limit, op = meta
            val    = ind.get("value", 0.0)
            margin = ind.get("margin", 0.0)
            passed = ind.get("pass", True)
            sign   = "+" if margin >= 0 else ""
            if passed and abs(margin) < 5:
                badge, badge_cls, m_col = "MARGIN", "badge-margin", "#ffa040"
            elif passed:
                badge, badge_cls, m_col = "PASS", "badge-pass", "#39ff96"
            else:
                badge, badge_cls, m_col = "FAIL", "badge-fail", "#ff4d6d"
            score_rows.append({
                "name": name, "unit": unit,
                "value": round(val, 1), "limit": limit, "op": op,
                "margin_str": f"{sign}{margin:.1f}",
                "margin_color": m_col,
                "badge_text": badge, "badge_class": badge_cls,
            })

        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "version":       _VERSION,
            "orbit_summary": f"{alt:.0f} km / {inc:.1f}°",
            "duration_days": orbit.params.duration_days if orbit else 1,
            "grade":         grade,
            "grade_color":   grade_col,
            "total_score":   total_score,
            "pass_count":    pass_cnt,
            "total_ind":     total_ind,
            "pass_color":    pass_color,
            "orbit":         orbit_ctx,
            "budget":        budget_ctx,
            "mass_rows":     mass_rows,
            "thermal":       thermal_ctx,
            "thermal_rows":  thermal_rows,
            "rad":           rad_ctx,
            "risk_badge_class": risk_to_badge.get(risk, "badge-low"),
            "tid_color":     tid_color,
            "score_rows":    score_rows,
            "mass_margin_color": "#39ff96" if margin_15 else "#ff4d6d",
            "power_margin_color": "#39ff96" if pw_margin else "#ff4d6d",
            "dod_color":    "#39ff96" if dod_ok else "#ff4d6d",
        }
