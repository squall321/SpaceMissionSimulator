"""
SpaceD-AADE Platform — Version Module
패치마다 이 파일을 업데이트하면 앱 전체에 반영됩니다.
"""

# ── 현재 버전 ────────────────────────────────────────────────────
MAJOR = 0
MINOR = 10
PATCH = 0
STAGE = "alpha"

VERSION = f"{MAJOR}.{MINOR}.{PATCH}"
VERSION_FULL = f"v{VERSION}-{STAGE}"
BUILD_DATE = "2026-03-08"

# ── 체인지로그 (최신순) ────────────────────────────────────────────
CHANGELOG = [
    {
        "version": "0.10.0",
        "date": "2026-03-08",
        "stage": "alpha",
        "highlights": "CesiumJS 멀티위성 CZML — 위성별 궤도 색상 + 지상국 FOV 콜레진로 원",
        "changes": [
            ("feat", "🌈 SAT_COLORS 팔레트 — 위성별 고유 색상 (cyan/amber/purple/yellow/sky-blue/pink/lime/coral 8종)"),
            ("feat", "📍 지상국 FOV 콜레진로 원 — 10° 앙각 마스크 기반 커버리지 영역 시각화"),
            ("feat", "📊 궤도선 세그먼트 색상 — 일조구간은 위성별 고유색, 일식/접속은 고정색 (red/green) 유지"),
            ("feat", "📍 위성 매니저 패널 컈러 도트 — 위성별 할당 색상 표시"),
            ("feat", "📍 calcFovRadiusM() — 고도+최소앙각→지상 커버리지 반경 [m] 관측 수식"),
            ("feat", "📍 범례 업데이트 — 위성 색상 + FOV Coverage 항목 추가"),
        ],
    },
    {
        "version": "0.9.0",
        "date": "2026-03-08",
        "stage": "alpha",
        "highlights": "DesignScoreCard UI + Auto Report Generator",
        "changes": [
            ("feat", "🏆 ScorecardViewer — Radar차트 + Gauge + 지표 테이블 (PASS/MARGIN/FAIL 배지)"),
            ("feat", "📄 ReportDialog — Jinja2 HTML 리포트 미리보기 + Save HTML + 브라우저 열기"),
            ("feat", "🔧 ReportGenerator — 5섹션 HTML 리포트 (궤도/예산/열/방사선/scorecard)"),
            ("feat", "📐 mission_report.html.j2 — 다크테마 풀-섹션 HTML 리포트 템플릿"),
            ("feat", "🔗 Sidebar 'Score' 탭 추가 + main_window 페이지 index 7 연결"),
            ("refactor", "♻️ Valispace 어댑터 제외 (유료 서비스)"),
        ],
    },
    {
        "version": "0.8.0",
        "date": "2026-03-09",
        "stage": "alpha",
        "highlights": "Pipeline Orchestrator — 4-Stage DI 기반 파이프라인 아키텍처",
        "changes": [
            ("feat", "🏛️ PipelineOrchestrator — Mediator 패턴, FAILED 시 자동 중단"),
            ("feat", "🗣️ PipelineContext — 공유 상태 + log_fn/progress_fn 콜백"),
            ("feat", "📊 GmatStage / ThermalStage / BudgetStage / RadiationStage / EvaluationStage"),
            ("feat", "🔀 StageStatus (SUCCESS|FAILED|SKIPPED) + StageResult 타입 찬안"),
            ("feat", "📈 MultiOrbitAnalyzer — 순차/병렬 파라메트릭 스윘 (ThreadPoolExecutor)"),
            ("feat", "➕ generate_orbit_candidates() — list 방식 + range+step 방식 든 지원"),
            ("refactor", "♻️ AnalysisWorker.run() → PipelineOrchestrator 위임 (서비스 DI 유지)"),
        ],
    },
    {
        "version": "0.7.0",
        "date": "2026-03-09",
        "stage": "alpha",
        "highlights": "Budget Panel 3탭 — Mass · Power · Link 전면 재설계",
        "changes": [
            ("feat", "⚖️ Mass Tab — CBE/Margin%/MEV 테이블 + 누적 수평 바차트 (Limit 점선)"),
            ("feat", "⚡ Power Tab — KPI 줄 + 발전/소비/마진 바차트 + Payload/Bus 도넛"),
            ("feat", "📡 Link Tab — 일일 다운링크 게이지 + 접속횟수/속도/마진 바차트"),
            ("feat", "🗂️ BudgetResult 보강 — solar_generated_w, power_margin_w, contact_count, contact_time_per_day_min, MASS_MARGINS"),
            ("feat", "🔢 BudgetService calc_power_budget() — 신규 필드 전산화"),
            ("refactor", "🎨 BudgetViewer → QTabWidget 기반 3탭 레이아웃 (Lazy render)"),
        ],
    },
    {
        "version": "0.6.0",
        "date": "2026-03-08",
        "stage": "alpha",
        "highlights": "Settings Dialog · Analysis Log Panel · GMAT 상태 배지",
        "changes": [
            ("feat", "⚙️ Settings Dialog — GMAT 경로/사용여부, 해석 기본값, 시뮬레이션 설정"),
            ("feat", "📋 Analysis Log Panel — 접기/펼치기, 파이프라인 단계별 컬러 로그"),
            ("feat", "⬤ GMAT 상태 배지 — Console/GUI/N/A 실시간 표시"),
            ("feat", "📊 AnalysisWorker 상세 로그 — Stage별 결과(주기·온도·점수·TID) emit"),
            ("feat", "🚀 Sidebar ⚙ Settings 버튼 → SettingsDialog 오픈"),
            ("feat", "💾 config/settings.json 영속 설정 저장"),
        ],
    },
    {
        "version": "0.5.2",
        "date": "2026-03-08",
        "stage": "alpha",
        "highlights": "이름 편집 · 3D↔카드 동기화 · 비교 모드 · Export Excel/PDF",
        "changes": [
            ("feat", "✏️ ScenarioCard 더블클릭 인라인 이름 편집 (QLineEdit 오버레이)"),
            ("feat", "🔗 3D 위성 클릭 → Python QWebChannel → ScenarioCard 하이라이트"),
            ("feat", "📊 ComparisonDialog 시나리오 이름 열 헤더 적용"),
            ("feat", "🔀 비교 버튼 → ComparisonDialog 시나리오 이름 전달"),
            ("feat", "📊 Export Excel (openpyxl, 다크테마 스타일, 17개 지표)"),
            ("feat", "📄 Export PDF (QPrinter + QTextDocument HTML→PDF)"),
            ("feat", "🗂️ gui/utils/export_service.py — export_excel / export_pdf"),
        ],
    },
    {
        "version": "0.5.1",
        "date": "2026-03-08",
        "stage": "alpha",
        "highlights": "시나리오 저장/불러오기 — 세션 자동 복원",
        "changes": [
            ("feat", "💾 시나리오 저장 (다른 이름으로) — JSON"),
            ("feat", "📂 시나리오 불러오기 — JSON"),
            ("feat", "🔄 앱 재시작 시 마지막 세션 자동 복원 (_session.json)"),
            ("feat", "⚡ 시나리오 변경마다 자동 저장 (data/scenarios/_session.json)"),
            ("fix",  "🗂️ data/scenarios/ 디렉토리 없을 시 자동 생성"),
        ],
    },
    {
        "version": "0.5.0",
        "date": "2026-03-09",
        "stage": "alpha",
        "highlights": "Multi-Satellite Scenario Manager — 궤도 횟수만큼 위성 시나리오 독립 설정",
        "changes": [
            ("feat", "🛰️ SatelliteScenarioPanel — 시나리오 카드 목록 + 독립 SatelliteConfigPanel"),
            ("feat", "🎨 8종 팔레트 색상 컨드로 각 위성 구분 — ScenarioCard 클릭/삭제 시그널"),
            ("feat", "🔮 sat_controller.js 다중 위성 — showSatViewer(scenarios[]) X축 배치"),
            ("feat", "💡 림 라이트 하이라이트 — 선택 위성 PointLight 활성화 + 카메라 타겟 이동"),
            ("feat", "🏷️ 캔버스 라벨 스프라이트 — 위성 이름 3D 표시"),
            ("feat", "📊 HUD N개 시나리오 카운터 + 선택 위성 상세 정보"),
            ("feat", "🔍 레이캐스터 클릭 선택 — 3D 위성 클릭 → 해당 시나리오 강조"),
            ("feat", "➕ 분석 완료 시 시나리오 자동 추가 — on_analysis_done → add_scenario()"),
        ],
    },
    {
        "version": "0.4.0",
        "date": "2026-03-08",
        "stage": "alpha",
        "highlights": "Satellite 3D Viewer — Three.js ESM Two-Canvas 통합",
        "changes": [
            ("feat", "🛰️ Satellite 탭 전용 Three.js r150 3D 위성 형상 뷰어"),
            ("feat", "🔧 6종 버스 타입 자동 선택 — dual_boards 수량 기반 (3U/6U/SmallSat/MedSat/LargeSat/DatacenterSat)"),
            ("feat", "☀️ PBR 재질 — 태양전지판 CanvasTexture 격자, MLI 금박, 알루미늄 구조체"),
            ("feat", "💡 물리 기반 조명 — 태양광(그림자), 지구 반사광, 보조광 3점 조명"),
            ("feat", "🔄 OrbitControls 자동 회전 + 수동 조작 3초 후 자동 재개"),
            ("feat", "📐 bbox 기반 카메라 거리 자동 조정 — 버스 크기에 맞게 FOV 최적화"),
            ("feat", "⚡ show/hide Two-Canvas 전환 — Cesium requestRenderMode 저전력 연동"),
            ("feat", "🔁 config_changed → updateSatViewer 실시간 형상 갱신 (debounce 800ms)"),
            ("feat", "✅ Sprint 0 검증 10/10 PASS — tools/sprint0_three_test.py/.html"),
        ],
    },
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
