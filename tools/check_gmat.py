"""
GMAT 연결 상태 확인 및 테스트 스크립트
"""
import sys
import os
from pathlib import Path

# 프로젝트 루트 추가
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from adapters.gmat.gmat_adapter import GmatAdapter, _find_gmat_path


def check_gmat_status():
    """GMAT 설치 및 연결 상태 확인"""
    print("=" * 60)
    print("  SpaceD-AADE GMAT 연결 상태 확인")
    print("=" * 60)
    print()
    
    # 경로 탐색
    gmat_path = _find_gmat_path()
    print(f"[경로 탐색]")
    print(f"  탐색된 GMAT 경로: {gmat_path}")
    print()
    
    # 어댑터 초기화
    adapter = GmatAdapter()
    
    print(f"[어댑터 설정]")
    print(f"  gmat_bin_dir: {adapter.gmat_bin_dir}")
    print(f"  gmat_exe:     {adapter.gmat_exe}")
    print()
    
    # 가용성 확인
    available = adapter.is_available()
    print(f"[상태]")
    if available:
        print(f"  ✓ GMAT 사용 가능")
        
        # 파일 크기로 버전 간접 확인
        import os
        size_mb = os.path.getsize(adapter.gmat_exe) / (1024 * 1024)
        print(f"  실행 파일 크기: {size_mb:.1f} MB")
        
        # README에서 버전 확인
        readme = os.path.join(adapter.gmat_bin_dir, "..", "README.txt")
        readme = os.path.normpath(readme)
        if os.path.exists(readme):
            try:
                with open(readme, 'r', encoding='utf-8', errors='replace') as f:
                    first_line = f.readline().strip()
                print(f"  버전 정보: {first_line}")
            except:
                pass
    else:
        print(f"  ✗ GMAT 실행 파일을 찾을 수 없습니다")
        print()
        print(f"[설치 안내]")
        print(f"  1. tools/download_gmat.ps1 실행하여 자동 다운로드")
        print(f"     > powershell -ExecutionPolicy Bypass -File tools/download_gmat.ps1")
        print()
        print(f"  2. 또는 수동 설치:")
        print(f"     - https://sourceforge.net/projects/gmat/files/ 에서 다운로드")
        print(f"     - tools/GMAT/ 폴더에 압축 해제")
        print()
        print(f"  3. 또는 환경 변수 설정:")
        print(f"     $env:GMAT_BIN_DIR = 'C:\\path\\to\\GMAT\\bin'")
    
    print()
    print("=" * 60)
    return available


def test_simple_analysis():
    """간단한 궤도 해석 테스트"""
    from core.domain.orbit import OrbitParams
    from core.services.mission_analysis import MissionAnalysisService
    
    print()
    print("=" * 60)
    print("  간단한 궤도 해석 테스트")
    print("=" * 60)
    print()
    
    # 기본 SSO 궤도 파라미터
    params = OrbitParams(
        altitude_km=550.0,
        inclination_deg=97.6,
        orbit_type="SSO",
        duration_days=1.0
    )
    
    print(f"[입력 파라미터]")
    print(f"  고도: {params.altitude_km} km")
    print(f"  경사각: {params.inclination_deg}°")
    print(f"  궤도 유형: {params.orbit_type}")
    print(f"  시뮬레이션 기간: {params.duration_days} 일")
    print()
    
    # 해석 실행
    service = MissionAnalysisService()
    result = service.analyze(params)
    
    print(f"[해석 결과]")
    if result.error:
        print(f"  ✗ 오류: {result.error}")
        print(f"  (내장 Fallback 모델로 계산됨)")
    else:
        print(f"  ✓ 해석 성공")
    
    print()
    print(f"  궤도 주기: {result.period_min:.2f} 분")
    print(f"  일식 비율: {result.eclipse_fraction*100:.1f}%")
    print(f"  일조율: {result.sunlight_fraction*100:.1f}%")
    print(f"  일일 접속 횟수: {result.contacts_per_day:.1f} 회")
    print(f"  일일 접속 시간: {result.contact_time_per_day_min:.1f} 분")
    print()
    
    if service.gmat_adapter.is_available():
        print(f"  [GMAT 연동 모드로 실행됨]")
    else:
        print(f"  [내장 SGP4 Fallback 모델로 실행됨]")
    
    print("=" * 60)


if __name__ == "__main__":
    available = check_gmat_status()
    
    if "--test" in sys.argv or "-t" in sys.argv:
        test_simple_analysis()
