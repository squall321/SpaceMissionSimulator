"""
GMAT Script Factory
Jinja2 템플릿 기반으로 주어진 파라미터를 사용해 GMAT 스크립트를 동적으로 생성합니다.
"""
import os
from datetime import datetime, timedelta
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from core.domain.orbit import OrbitParams

class GmatScriptFactory:
    def __init__(self, templates_dir: str = None):
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "templates"
        self.env = Environment(loader=FileSystemLoader(str(templates_dir)))
        self.template_name = "mission_basic.script.j2"

    def generate_script(self, 
                        orbit_params: OrbitParams, 
                        sat_config: dict, 
                        ground_stations: list, 
                        output_dir: str, 
                        script_path: str):
        """
        궤도 파라미터와 위성 설정, 지상국 정보를 바탕으로 GMAT 스크립트를 렌더링 후 저장
        """
        template = self.env.get_template(self.template_name)
        
        # GMAT 요구 포맷: 01 Jan 2026 12:00:00.000
        # OrbitParams는 ISO포맷 (2026-01-01T12:00:00)을 사용 중이라면 변환 필요
        # 간소화를 위해 epoch 변환 로직 최소화 (단순 분리)
        epoch = self._format_epoch(orbit_params.epoch)
        final_epoch = self._add_days_to_epoch(orbit_params.epoch, orbit_params.duration_days)

        context = {
            'epoch': epoch,
            'final_epoch': final_epoch,
            'sma': orbit_params.altitude_km + 6378.137, # Earth Eq Radius
            'ecc': 0.0001,  # 거의 원궤도
            'inc': orbit_params.inclination_deg,
            'raan': orbit_params.raan_deg,
            'aop': 0.0,
            'ta': 0.0,
            'dry_mass': sat_config.get('mass_bus_kg', 20) + sat_config.get('mass_electronics_kg', 15),
            'drag_area': sat_config.get('bus_area_m2', 1.5) * 0.25, # 정면 투영 면적 추정
            'srp_area': sat_config.get('panel_area_m2', 4.0),       # 태양전지판 면적
            'duration_days': orbit_params.duration_days,
            'ground_stations': [
                {'name': gs.name.replace(" ", "_"), 'lat': gs.latitude_deg, 'lon': gs.longitude_deg, 'alt': gs.altitude_m}
                for gs in ground_stations
            ],
            # Use forward-slash path (GMAT SPICE requires the full path in its own output dir)
            'output_dir': Path(output_dir).as_posix().replace('//', '/')
        }

        rendered = template.render(**context)
        
        # GMAT requires pure ASCII scripts - encode as ascii, replace non-ASCII with '?'
        with open(script_path, 'w', encoding='ascii', errors='replace') as f:
            f.write(rendered)
            
        return script_path

    def _format_epoch(self, epoch_iso: str) -> str:
        """ 2026-01-01T12:00:00 -> 01 Jan 2026 12:00:00.000 """
        try:
            date_str, time_str = epoch_iso.replace('Z', '').split('T')
            y, m, d = date_str.split('-')
            months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            mon_str = months[int(m)]
            return f"{d} {mon_str} {y} {time_str}.000"
        except:
            return "01 Jan 2026 12:00:00.000" 

    def _add_days_to_epoch(self, epoch_iso: str, duration_days: float) -> str:
        """ epoch ISO string에 duration_days를 더한 epoch 반환 (GMAT 포맷) """
        try:
            dt = datetime.fromisoformat(epoch_iso.replace('Z', ''))
            dt_final = dt + timedelta(days=duration_days)
            return dt_final.strftime("%d %b %Y %H:%M:%S.000")
        except:
            return "08 Jan 2026 12:00:00.000"
