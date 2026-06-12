# Theological Research + Pipeline 통합 가이드

## 개요

`theological_research` v1.3 프롬프트로 생성한 연구 결과물을 `gemini-scholar-pipeline`에 통합하여 학술적 각주를 보강할 수 있습니다.

---

## 파이프라인 진입점 옵션

| 시작점 | 설명 | 명령어 |
|--------|------|--------|
| **Phase 1** | Deep Research로 초기 조사 | `./pipeline.sh topic account` |
| **Phase 0** | CLI에서 v1.3 프로토콜 실행 | `./run_theological_research_cli.sh topic` |
| **직접 진입** | 외부 리포트 사용 | 수동 복사 후 Phase 2 |

---

## CLI 결과물 → Pipeline 통합 워크플로우

### 1. Phase 0: CLI 리서치 실행

```bash
cd ~/Library/Mobile Documents/iCloud~md~obsidian/Documents/MS_Brain.nosync/300 Tech/320 Coding/Projects.nosync/gemini-scholar-pipeline
./run_theological_research_cli.sh "셰키나"
```

**출력**: `theological_outputs/셰키나_research.md`

### 2. 결과물을 Pipeline 입력으로 복사

```bash
cp theological_outputs/셰키나_research.md reports/셰키나_raw.md
```

### 3. Phase 2부터 실행

```bash
./run.sh account3 셰키나
```

**이후 자동 진행**: Phase 2 → 3 → 4 → 5 → 6

---

## 품질 비교 (Schechina 테스트 기준)

| 결과물 | 분량 | 각주 | 논리 방어 | 최적 용도 |
|--------|------|------|----------|----------|
| Deep Research | 43K자 | 54개 | ⭐⭐⭐ | 출처 수집 |
| CLI v1.3 | 14K자 | 없음 | ⭐⭐⭐⭐⭐ | 논리 구조 |
| **통합 (CLI + Scholar)** | ~20K자 | 추가 | ⭐⭐⭐⭐⭐ | **최종본** |

---

## 권장 워크플로우

```
theological_research v1.3 (CLI)
        ↓ Nash Equilibrium 달성
reports/{topic}_raw.md로 복사
        ↓
Phase 2: 시맨틱 검색문 생성
        ↓
Phase 3: Scholar Labs 학술 출처 수집
        ↓
Phase 4: 각주 통합 (Chicago 17th)
        ↓
Phase 5: 문체 개선
        ↓
Phase 6: HTML 시각화
```

---

## 파일 위치

| 프로젝트 | 경로 |
|----------|------|
| v1.3 프롬프트 | `gemini-scholar-pipeline/prompts/theological_research.md` |
| CLI 스크립트 | `gemini-scholar-pipeline/run_theological_research_cli.sh` |
| 페르소나 폴더 | `theological_research/personas/` |
| CLI 결과물 | `theological_research/research_outputs/` |
