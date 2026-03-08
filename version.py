"""
SpaceD-AADE Platform — Version Module
패치마다 이 파일을 업데이트하면 앱 전체에 반영됩니다.
"""

# ── 현재 버전 ────────────────────────────────────────────────────
MAJOR = 0
MINOR = 3
PATCH = 0
STAGE = "alpha"

VERSION = f"{MAJOR}.{MINOR}.{PATCH}"
VERSION_FULL = f"v{VERSION}-{STAGE}"
BUILD_DATE = "2026-03-08"

# ── 체인지로그 (최신순) ────────────────────────────────────────────
CHANGELOG = [
    {
        "version": "0.3.0",
        "date": "2026-03-09",
        "stage": "alpha",
        "highlights": "Parametric Study Panel — 고도×경사각 2D 히트맵",
        "changes": [
            ("feat", "📈 Parametric Study Panel 도입 — 해석적 근사로 고도×경사각 10×10 그리드 계산"),
            ("feat", "🌡️ 10개 지표 히트맵 — 주기/일조율/GSD/TID/접속횟수/전력마진 등 컴보박스로 선택"),
            ("feat", "☕ SSO 대상 자동 강조 표시 — 모든 SSO 섹션에 다른 하이라이트 색상"),
            ("feat", "🎯 셀 더블클릭 → 'Apply to Orbit Config' — 선택 구점을 Orbit 설정에 즉시 반영 + 전체 분석 실행"),
            ("feat", "📦 core/services/parametric_study.py — ParametricStudyService (GMAT무관, ms 단위 계산)"),
            ("feat", "🗃️ 접속 시간/재방문주기/다항작력 ΔV 수식 포함"),
        ],
    },
    {
        "version": "0.2.4",
        "date": "2026-03-08",
        "stage": "alpha",
        "highlights": "기능 완성 3종 — 지상국 자동추가 / Mission 탭 복귀 / GSD 해상도",
        "changes": [
            ("feat", "📡 커버리지 선택 지상국 자동 추가 — 국가/지역 선택 시 해당 중심 좌표가 분석 및 Cesium 지구본에 반영"),
            ("feat", "🎯 RECOMMEND 후 Mission 탭 자동 복귀 — 분석 완료 시 충족도 패널로 즉시 돌아옴"),
            ("feat", "🔭 GSD 기반 해상도 계산 (Rayleigh criterion) — λ=500nm, 카메라 구경 입력값 반영"),
            ("feat", "📸 Satellite Config에 Camera Aperture (cm) 입력 추가 — 기본 15cm"),
            ("fix",  "🗺️ COVERAGE_TARGETS에 중심 lat/lon 추가 — get_ground_station() API 구현"),
        ],
    },
    {
        "version": "0.2.3",
        "date": "2026-03-08",
        "stage": "alpha",
        "highlights": "Coverage Target — 국가/지역 선택 + 위도 기반 경사각 계산",
        "changes": [
            ("feat", "🌏 CoverageSection: 지역·국가·전지구 3-way 토글 + 국가/권역 드롭다운"),
            ("feat", "🗺️ 지역 10개 (한반도 권역·동아시아·유럽 등) / 국가 16개 (대한민국·미국·중국 등) 등록"),
            ("feat", "📐 경사각 자동 계산: SSO → 고도 기반 정밀식, 비SSO → 대상 최대위도 + 5° 규칙"),
            ("feat", "🌐 전지구 선택 시 콤보박스 자동 숨김"),
            ("fix",  "🔧 CoverageToggle → CoverageSection 교체 (하위 호환 value() 유지)"),
        ],
    },
    {
        "version": "0.2.2",
        "date": "2026-03-08",
        "stage": "alpha",
        "highlights": "Mission Card — QPainter Fancy Redesign",
        "changes": [
            ("feat", "🎨 MissionTypeCard QPainter 커스텀 렌더링 — 상단 컬러 액센트 바 (그라디언트)"),
            ("feat", "✨ 선택 시 색상 글로우 효과 (QRadialGradient)"),
            ("feat", "🖱️ 호버 시 배경 페이드 + 우하단 도트 하이라이트"),
            ("feat", "🔲 상태별 테두리: 기본 1px → 호버 1.5px → 선택 2px solid"),
            ("feat", "🚫 coming_soon 카드: 외곽선 대시 스타일 + 선택 비활성"),
        ],
    },
    {
        "version": "0.2.1",
        "date": "2026-03-08",
        "stage": "alpha",
        "highlights": "Mission Panel UX 전면 개선",
        "changes": [
            ("fix",  "👁️ 슬라이더 min/max 범위 레이블 추가 — 범위 가시성 해결"),
            ("fix",  "🔤 라벨 텍스트 색상 밝기 향상 (#b8d4e8, 현재값 #00e8ff)"),
            ("fix",  "📐 슬라이더 핸들 18px + 그루브 6px — 조작감 개선"),
            ("fix",  "🌐 CoverageToggle 30px 높이 + 2px 활성 테두리"),
            ("fix",  "✅ StatusRow 좌측 컬러 보더 + 배경 틴트 (충족/미달 구분)"),
        ],
    },
    {
        "version": "0.2.0",
        "date": "2026-03-08",
        "stage": "alpha",
        "highlights": "Mission Panel & Version System",
        "changes": [
            ("feat", "🎯 Mission Panel 구현 — 임무 유형 선택, 요구사항 슬라이더, 궤도 추천 엔진"),
            ("feat", "📋 버전 관리 시스템 추가 — 패치 공시, 체인지로그 다이얼로그"),
            ("feat", "🏷️ 버전 배지 — 사이드바/타이틀바 상시 표시"),
            ("feat", "✅ 요구사항 충족도 대시보드 — 분석 결과 vs 임무 요구사항 자동 비교"),
        ],
    },
    {
        "version": "0.1.0",
        "date": "2026-03-07",
        "stage": "alpha",
        "highlights": "Initial Release",
        "changes": [
            ("feat", "🚀 최초 릴리즈 — GMAT R2025a 파이프라인 연동"),
            ("feat", "🌍 Cesium 3D 궤도 시각화 (CZML 실시간 스트리밍)"),
            ("feat", "🌑 일식·일조 분석 (Eclipse / Sunlight fraction)"),
            ("feat", "📡 지상국 접속 윈도우 분석 (Contact Windows)"),
            ("feat", "🌡️ 열 해석 / ☢️ 방사선 해석 / 📊 예산 분석"),
            ("fix",  "float/str 타입 불일치 버그 수정 (ephemeris_times)"),
        ],
    },
]

# 타입별 색상 태그 (UI 용)
CHANGE_TYPE_COLOR = {
    "feat": "#00dcff",
    "fix":  "#ffa040",
    "perf": "#80ff80",
    "doc":  "#a0a0ff",
    "refactor": "#d0d0d0",
}
CHANGE_TYPE_LABEL = {
    "feat": "NEW",
    "fix":  "FIX",
    "perf": "OPT",
    "doc":  "DOC",
    "refactor": "REF",
}
