"""
SpaceD-AADE Platform — Version Module
패치마다 이 파일을 업데이트하면 앱 전체에 반영됩니다.
"""

# ── 현재 버전 ────────────────────────────────────────────────────
MAJOR = 0
MINOR = 2
PATCH = 0
STAGE = "alpha"   # alpha / beta / rc / release

VERSION = f"{MAJOR}.{MINOR}.{PATCH}"
VERSION_FULL = f"v{VERSION}-{STAGE}"
BUILD_DATE = "2026-03-08"

# ── 체인지로그 (최신순) ────────────────────────────────────────────
CHANGELOG = [
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
