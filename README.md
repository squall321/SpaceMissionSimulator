# SpaceD-AADE Platform

**AADE 기반 우주데이터센터 위성 설계 자동화 시스템**

> AI Aided Design & Engineering for Space Data Center Satellites

## 프로젝트 개요

SpaceD-AADE는 GMAT 궤도 데이터를 자동으로 가져와 위성 기본설계를 수행하고, 열·구조 해석까지 하나의 파이프라인으로 연결하는 자동 설계 시스템입니다.

### 주요 기능

- **GMAT 직접 연동**: 궤도/임무 해석 결과를 자동 추출하여 설계 입력으로 변환
- **실시간 3D 시각화**: CesiumJS 기반 궤도 시각화
- **열/방사선 분석**: 궤도 환경 기반 열유속 및 방사선 자동 계산
- **예산 관리**: 질량/전력/통신 예산 자동 산출

## 설치 및 실행

### 1. Python 환경 설정

```powershell
cd SpaceD-AADE
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. GMAT 설치 (선택사항)

GMAT은 NASA에서 개발한 오픈소스 궤도 역학 분석 도구입니다.
GMAT 없이도 내장 SGP4 모델로 기본 해석이 가능하지만, 정밀한 궤도 분석을 위해서는 GMAT 설치를 권장합니다.

#### 자동 설치 (권장)

```powershell
# PowerShell에서 실행
cd SpaceD-AADE
powershell -ExecutionPolicy Bypass -File tools/download_gmat.ps1
```

#### 수동 설치

1. [GMAT SourceForge](https://sourceforge.net/projects/gmat/files/) 방문
2. `GMAT-R2022a` > `gmat-win-R2022a.zip` 다운로드
3. `tools/GMAT/` 폴더에 압축 해제

#### 설치 확인

```powershell
python tools/check_gmat.py
```

### 3. 프로그램 실행

```powershell
python main.py
```

## 프로젝트 구조

```
SpaceD-AADE/
├── main.py                     # 진입점
├── core/                       # 도메인 모델 + 서비스
│   ├── domain/                 # 데이터 모델 (Orbit, Thermal 등)
│   ├── services/               # 비즈니스 로직
│   └── pipeline/               # 워크플로우 오케스트레이터
├── adapters/                   # 외부 도구 어댑터
│   ├── gmat/                   # GMAT 연동
│   ├── ipsap/                  # DIAMOND/IPSAP 연동 (개발 예정)
│   └── valispace/              # Valispace 연동 (개발 예정)
├── gui/                        # PySide6 GUI
│   ├── widgets/                # UI 위젯
│   ├── controllers/            # 컨트롤러
│   └── cesium_app/             # CesiumJS 3D 뷰어
├── analysis/                   # 간소 해석 엔진 (내장)
├── config/                     # 설정 파일
├── data/                       # 데이터/DB
├── tools/                      # 유틸리티 도구
│   ├── download_gmat.ps1       # GMAT 다운로드 스크립트
│   ├── check_gmat.py           # GMAT 연결 확인
│   └── GMAT/                   # GMAT 설치 위치
└── tests/                      # 테스트
```

## GMAT 연동 상세

### 경로 탐색 우선순위

GMAT 어댑터는 다음 순서로 GMAT 경로를 탐색합니다:

1. **환경 변수** `GMAT_BIN_DIR`
2. **프로젝트 내장** `tools/GMAT/bin`
3. **시스템 기본** `C:\GMAT\bin`

### 연동 모드

| 모드 | 설명 | 장점 |
|------|------|------|
| GMAT 연동 | GMAT.exe 직접 실행 | 고정밀 궤도 해석, 다양한 섭동 모델 |
| Fallback | 내장 SGP4 모델 | GMAT 없이 즉시 사용 가능 |

### GMAT 스크립트 템플릿

`adapters/gmat/templates/mission_basic.script.j2`에서 GMAT 스크립트 템플릿을 확인할 수 있습니다.

## 개발 현황

### 완료된 기능 ✅

- [x] PySide6 메인 윈도우
- [x] CesiumJS 3D 지구 시각화
- [x] 궤도 파라미터 입력 UI
- [x] 위성 구성 패널
- [x] 실시간 대시보드
- [x] GMAT 어댑터 (배치 실행 모드)
- [x] GMAT 스크립트 자동 생성
- [x] 결과 파서 (에페메리스, 일식, 접속)
- [x] 내장 SGP4 Fallback 모델
- [x] 열/방사선 분석 서비스
- [x] 예산 계산 서비스

### 개발 중 🔧

- [ ] GMAT Python/Java API 연동 (2단계)
- [ ] 다중 궤도 비교 분석
- [ ] 설계 최적화 엔진

### 예정 📋

- [ ] DIAMOND/IPSAP 연동
- [ ] Valispace 연동
- [ ] AI/ML 기반 설계 가속 (AADE 엔진)
- [ ] 자동 리포트 생성

## 라이선스

- SpaceD-AADE: 내부 개발
- GMAT: Apache 2.0 (NASA GSFC)

## 참고 자료

- [GMAT 공식 문서](https://gmat.atlassian.net/wiki/)
- [GMAT 사용자 가이드 (PDF)](https://gmat.atlassian.net/wiki/spaces/GW/pages/380600333/GMAT+User+Guide)
