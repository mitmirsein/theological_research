# [DEPRECATED] Theological Research Automation
> ⚠️ **ARCHIVED**: This script-heavy approach is superseded by the **Agent-in-the-Loop** workflow (ARC v2.1).
> The Orchestrator's logic is now internalized within the `Secretariat` agent (Antigravity), using `theology-vector-db` directly as a tool.

**Version:** 1.4.1 (Legacy) | **Status:** Archived | **Superseded By:** Agentic Workflow

---

## 🎯 핵심 철학 (Philosophy & Telos)

- **Philosophy:** *"Truth is Antifragile."* (진리는 반대를 통해 정련된다.)
- **Telos:** *"Theological Nash Equilibrium."* (어떤 신학적 전통에서도 파훼 불가능한 논리적 균형점에 도달한다.)
- **Strategy:** *"지식(Knowledge)을 인출하는 자는 Flash, 지혜(Wisdom)를 통합하는 자는 Pro."*

---

## 🏗️ 4-Tier 모델 아키텍처 (v2.1)

정본은 `theology_orchestrator.py`의 `MODEL_REGISTRY`이며, 아래 표는 그 값을 인용한다.

| Tier | Model ID | 모델 (정본 인용) | 역할 | 입력 비용 (참고치) |
|------|----------|----------|------|-----------|
| **Router** | `LITE` | gemini-3-flash-preview | 팀 구성/라우팅, 구조 검수 | $0.15 |
| **Worker** | `WORKER` | gemini-3-flash-preview | RAG 독해, 초안 작성, 패턴 매칭 | $0.15 |
| **Thinker** | `THINKER` | gemini-3-flash-preview (thinking_config) | 논리 추론, 분석, 변증 | $0.15 |
| **Auditor** | `WORKER` | gemini-3-flash-preview | 검증 (Input Pruning 적용) | $0.15 |
| **Commander** | `COMMANDER` | gemini-3-pro-preview | 내쉬 균형, 최종 편집 | $2.00 |

---

## 📂 핵심 구성 요소

```
theological_research/
├── theological_research_v1.4.md   # 핵심 프롬프트 엔진
├── theology_orchestrator.py       # Python 오케스트레이터
├── personas/                      # 50명의 전문가 페르소나
│   └── personas_all.md           # 통합 페르소나 파일
├── requirements.txt               # Python 의존성
├── .env.example                   # API 키 템플릿
└── research_outputs/              # 연구 결과물
```

---

## 🚀 빠른 시작 (Quick Start)

### Step 1: 프로젝트 폴더 이동

```bash
cd /Users/msn/Desktop/MS_Dev.nosync/projects/theological_research
```

### Step 2: 공유 가상환경 활성화

```bash
# 공유 venv 활성화 (.venv → ../../shared_venv 심볼릭 링크, SHARED_VENV.md 규약)
source .venv/bin/activate

# 심링크가 없으면 (머신별 1회):
#   ln -s ../../shared_venv .venv

# 프롬프트가 (shared_venv)로 시작하면 성공
```

### Step 3: 의존성 설치

```bash
pip install -r requirements.txt
```

### Step 4: API 키 설정

```bash
# .env 파일 생성
cp .env.example .env

# .env 파일 편집
nano .env
# 또는: open -e .env
```

`.env` 파일 내용:
```
GOOGLE_API_KEY=your_api_key_here
```

> 💡 API 키는 [Google AI Studio](https://aistudio.google.com/app/apikey)에서 발급받으세요.

### Step 5: 오케스트레이터 실행

```bash
python theology_orchestrator.py --topic "연구 주제"
# 또는 대화형: python theology_orchestrator.py --interactive
```

### Step 6: 결과 확인

run 1회 = 감사 dossier 디렉토리 1개:

```
research_outputs/{topic}/run_{run_id}/
├── phase1_draft.md        # 성경신학자 초안
├── phase2_analysis.md     # 분석신학자 검증
├── phase3_audit.md        # 편향 감사
├── final.md               # Commander 최종 종합
└── execution_log.json     # 호출별 모델·토큰·비용 실측
```

```bash
ls research_outputs/{topic}/
open research_outputs/{topic}/run_*/final.md
```

### 한 줄 실행 (API 키 설정 후)

```bash
cd /Users/msn/Desktop/MS_Dev.nosync/projects/theological_research && source .venv/bin/activate && python theology_orchestrator.py --topic "주제"
```

---

## 💻 오케스트레이터 사용법

### CLI 명령어

```bash
# 기본 실행 (연구 주제 지정)
python theology_orchestrator.py --topic "칭의론"

# RAG 컨텍스트 포함
python theology_orchestrator.py --topic "삼위일체" --rag context.txt

# 대화형 모드
python theology_orchestrator.py --interactive

# 페르소나 목록 확인
python theology_orchestrator.py --list-personas

# 출력 디렉토리 지정
python theology_orchestrator.py --topic "구원론" --output ./my_research/
```

### CLI 옵션

| 옵션 | 단축 | 설명 |
|------|------|------|
| `--topic` | `-t` | 연구 주제 (필수) |
| `--rag` | `-r` | RAG 컨텍스트 파일 경로 |
| `--output` | `-o` | 출력 디렉토리 |
| `--interactive` | `-i` | 대화형 모드 |
| `--list-personas` | | 페르소나 목록 출력 |

### Python API 사용

```python
from theology_orchestrator import PersonaManager, TheologyResearchEngine, run_research

# 방법 1: 함수 직접 호출
run_research("칭의론", rag_context="참고 자료...")

# 방법 2: 엔진 직접 사용
manager = PersonaManager("personas_all.md")
engine = TheologyResearchEngine(manager)

result = engine.run_agent(
    "성경신학자 (Biblical Theologian)",
    "칭의론에 대해 분석해줘."
)
```

---

## 📋 워크플로우 개요 (v1.4.1)

1. **범위 명료화** [LITE] - 주제 확정 및 팀 구성
2. **범위 견적** [LITE] - 비용/모델 전략 수립
3. **리서치 기획** [WORKER] - 종합 분석 및 팀 선발
4. **자율 리서치** [WORKER/THINKER] - 전문가별 초안 작성
5. **Red Team Challenge** [WORKER + Pruning] - QA Gates
   - Gate 1: 구조 검수 (Structural Linter)
   - Gate 2: 인용 검증 (Citation Validator)
   - Gate 3: 편향 감사 (Bias Auditor)
6. **Nash Equilibrium** [COMMANDER] - 고차원 종합
7. **최종 전달** [COMMANDER] - 윤문 및 출력

---

## ⚙️ 모델 레지스트리

```python
MODEL_REGISTRY = {
    "LITE": "gemini-3-flash-preview",    # 최저가 - 빠른 분류/검수
    "WORKER": "gemini-3-flash-preview",        # 가성비 - 초안 작성/독해
    "THINKER": "gemini-3-flash-preview",       # Thinking 모드 활성화
    "COMMANDER": "gemini-3-pro-preview"        # 최고 성능 - 복잡한 추론/종합
}
```

> ⚠️ **주의:** 모델명은 Google AI Studio의 최신 버전에 맞게 업데이트해야 합니다.

---

## 📊 시각화 (Visualization)

연구 결과물을 HTML로 시각화할 수 있습니다:

```bash
./run_visualize.sh {topic}
# 예: ./run_visualize.sh Schechina
```

**출력:**
- `research_outputs/{topic}_report.html` (Full)
- `research_outputs/{topic}_brief.html` (Condensed)

---

## 🔗 gemini-scholar-pipeline 통합

CLI 결과물을 gemini-scholar-pipeline에 통합하여 학술 각주를 보강할 수 있습니다.
자세한 내용은 `PIPELINE_INTEGRATION.md`를 참조하세요.

```
CLI v1.4 → reports/{topic}_raw.md 복사 → Phase 2 ~ 6
```

---

## 📝 주요 설정

- **언어 설정**: 기본 분석 및 결과물 언어는 **Korean**으로 설정되어 있습니다.
- **전문가 추가**: 새로운 전문가 역할을 추가하려면 `personas/` 디렉토리에 해당 역할에 대한 설명이 담긴 `.md` 파일을 추가하고, `personas_all.md`를 업데이트하세요.
- **모델 변경**: `MODEL_REGISTRY`의 모델명을 업데이트하여 최신 모델을 사용할 수 있습니다.

---

## 🗺️ 로드맵 (Roadmap)

### v2.2 (예정)
- [ ] **Google File Search RAG 연동** - Gemini API의 File Search 기능을 활용한 자동 RAG 컨텍스트 검색
- [ ] 사전 업로드된 신학 문헌 코퍼스에서 관련 자료 자동 추출
- [ ] 연구 주제 기반 지능형 컨텍스트 프루닝

### v2.3 (계획)
- [ ] 다중 주제 배치 처리
- [ ] 연구 결과 비교 리포트 생성
- [ ] 웹 UI 인터페이스