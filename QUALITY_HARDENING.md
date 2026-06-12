# theological_research 품질 고도화 — 제안 및 구현 문서

- **작성일**: 2026-06-11
- **대상**: Theology Research Orchestrator v2.1 (`theology_orchestrator.py`) + Phase 6 시각화 (`visualize_session.py`, `run_visualize.sh`) + 문서·페르소나 자산
- **상태**: **전 Phase 완료** (2026-06-11 — 결함 패치 #1~#8 + 구조 제안 1~3 적용, pytest 44 passed, origin 푸시 완료)
- **방법**: 전 소스 정독 + 페르소나/출력물 실측 대조 (`grep`/`ls` 검증 기반)

---

## 0. 요약

정밀점검 결과 **결함 패치 8건**과 **구조 업그레이드 제안 3건**을 도출했다.

| 구분 | 핵심 |
|------|------|
| #1 | 실행 환경 단절 — 잘못된 SDK 선언, 존재하지 않는 venv 경로 |
| #2 | 오케스트레이터 ↔ 시각화 파일명 계약 불일치 (`_final.md` vs `_research.md`) |
| #3 | 페르소나 파서 결함 — 가짜 51번째 페르소나, Model ID 정규식 오파싱 |
| #4 | 모델 정본 부재 — 4-Tier가 사실상 단일 모델, 비용표 허수 (문서 3종 모두 코드와 불일치) |
| #5 | 약속–구현 갭 — Thinking Mode 허위 로그, Context Pruning 스텁 |
| #6 | 실패 격리 부재 — 에러 문자열이 다음 Phase의 '보고서'로 전파 |
| #7 | 산출물 무결성 — `os.popen('date')`, 무경고 덮어쓰기, 미사용 프롬프트의 허위 메타데이터 |
| #8 | `visualize_session.py` 잠복 NameError + 섹션 저장 로직 중복 |
| 제안 1 | 페르소나·설정 계약 검증층 (로드 시 스키마 검증, fail-fast) |
| 제안 2 | 실행 감사 dossier (run별 디렉토리, 중간 산출물·실측 토큰·로그 보존) |
| 제안 3 | e2e 골든 테스트 + 회귀 게이트 (FakeClient 주입, 파서 단위테스트) |

> 전제: README는 본 프로젝트를 **[DEPRECATED]/Archived** 로 선언하고 있다(ARC v2.1 Agent-in-the-Loop로 대체).
> 본 고도화는 "CLI 트랙을 다시 신뢰 가능한 상태로 복구"하는 작업이며, Archived 선언의 철회 여부는 §5 미결사항에서 사용자 결정을 요청한다.

---

## 1. 점검 범위와 방법

| 파일 | 점검 내용 |
|------|----------|
| `theology_orchestrator.py` (565줄) | 전 소스 정독 — 파서·모델 매핑·워크플로우·CLI |
| `visualize_session.py` (500줄) | 전 소스 정독 — 마크다운 파서·각주 추출·렌더링 |
| `run_visualize.sh`, `README.md`, `PIPELINE_INTEGRATION.md`, `theological_research_v1.4.md` | 코드와 문서의 계약 대조 |
| `personas_all.md` (50 페르소나), `personas/` (50 파일) | 메타데이터 형식 실측 (`grep` 집계) |
| `research_outputs/` | 실제 산출물 파일명과 스크립트 기대값 대조 |

실측 집계: Tier 분포 `COMMANDER 2 / LITE 2 / THINKER 9 / WORKER 37`, Model ID 분포 `gemini-2.0-flash 37 / gemini-2.0-flash-thinking 9 / gemini-2.0-flash-lite 2 / gemini-3.0-pro 2`, Input Pruning 선언 50건.

---

## 2. 결함 패치 #1 ~ #8

### #1 실행 환경 단절 — 깨끗한 환경에서 실행 불가 (심각도: 높음)

**증상**: 신규 머신/신규 환경에서 README Quick Start를 그대로 따르면 어느 단계에서도 성공하지 못한다.

**원인** (3중):
1. `requirements.txt.migrated`는 레거시 SDK `google-generativeai>=0.8.0`을 선언하지만, 코드는 신형 SDK를 import 한다 (`theology_orchestrator.py:24` — `from google import genai`는 **`google-genai`** 패키지). 레거시 SDK만 설치된 환경에서는 `ImportError`.
2. 파일명이 `.migrated` 접미사라 README의 `pip install -r requirements.txt`(README.md:64) 자체가 실패. 모듈 docstring(`theology_orchestrator.py:18`)도 `pip install -U google-generativeai`로 잘못 안내.
3. README Step 2(README.md:56)와 `run_visualize.sh:22`가 `venv.nosync/bin/activate`를 참조하지만 **해당 심링크는 프로젝트에 존재하지 않는다**(`ls -la` 실측). 워크스페이스 규약은 `SHARED_VENV.md`의 공유 venv(`MS_Dev.nosync/shared_venv`, Python 3.12)로 이미 이행됨.

**패치**:
```bash
# 1) requirements 정정 + 리네임
#    requirements.txt.migrated → requirements.txt
#    google-generativeai>=0.8.0  →  google-genai>=1.0.0
#    (visualize용 jinja2, markdown, python-dotenv 추가 선언)

# 2) 공유 venv 연결 (SHARED_VENV.md 규약)
cd ~/Desktop/MS_Dev.nosync/projects/theological_research
ln -s ../../shared_venv .venv

# 3) run_visualize.sh / README의 활성화 경로를 .venv 또는
#    `uv run --inexact python ...` 호출로 교체
```
docstring(line 18)과 README Step 6(`cat final_research_paper.md` → 실제 경로 `research_outputs/{topic}_final.md`)도 함께 정정한다.

**검증**: 새 셸에서 `uv run --inexact python theology_orchestrator.py --list-personas` 성공.

---

### #2 오케스트레이터 ↔ 시각화 파일명 계약 불일치 (심각도: 높음)

**증상**: `./run_visualize.sh {topic}`이 오케스트레이터의 산출물에 대해 항상 "Input file not found"로 실패.

**원인**: 생산자와 소비자가 서로 다른 파일명을 계약으로 삼는다.
- 생산: `theology_orchestrator.py:457` → `research_outputs/{safe_topic}_final.md`
- 소비: `run_visualize.sh:33` → `research_outputs/${TOPIC}_research.md`

실측으로도 `research_outputs/`의 어떤 파일도 `_research.md` 패턴과 매칭되지 않는다 (`Schechina_research_studio.md`, `TRE_..._final.md`).

**패치**: 계약을 `_final.md` 하나로 통일한다.
```bash
# run_visualize.sh:33
INPUT_FILE="research_outputs/${TOPIC}_final.md"
# (전환기 호환: _final.md 우선, 없으면 _research.md 폴백)
```
`cp → reports/ → 실행 → mv` 우회도 제거 대상: `visualize_session.py`에 `--input/--output-dir` 인자를 추가하면 (제안 1과 함께) 셸의 파일 복사 의식 자체가 사라진다.

**검증**: 오케스트레이터 1회 실행 → `./run_visualize.sh {topic}` 무수정 연결 성공.

---

### #3 페르소나 파서 결함 — 가짜 페르소나와 무력화된 Model ID (심각도: 높음)

**증상 1 — 51번째 가짜 페르소나**: `personas_all.md`의 문서 제목 `# Theological Research Personas (Optimized v2.1)`(line 2)이 H1 분리 규칙(`theology_orchestrator.py:101`)에 걸려 페르소나로 등록된다. "총 51명의 전문가" 출력은 오프바이원이며, 문서 서문이 system instruction으로 LLM에 주입될 수 있다.

**증상 2 — Model ID 오버라이드 전면 무력화**: `theology_orchestrator.py:119`의 정규식 `(\w+)`는 `-`와 `.`을 포함하지 않아 `` `gemini-2.0-flash` ``를 **`gemini`로 절단 파싱**한다. 이후 `_get_model_id`(line 195)에서 `"gemini"`는 `MODEL_REGISTRY`에 없으므로 조용히 무시 → 페르소나별 모델 지정 기능이 통째로 죽어 있다. 두 버그가 상쇄되어 **무증상**인 것이 가장 위험한 지점 (한쪽만 고치면 50명 전원이 폐기된 `gemini-2.0-*` 모델을 호출하게 됨).

**증상 3 — 이름 비일관**: 일부 페르소나는 `# 페르소나: 편향 및 전승 감사 전문가 (...)`처럼 `페르소나: ` 프리픽스를 갖는다(personas_all.md:120). 현재는 `find_persona` 부분일치의 요행으로 동작한다.

**패치** (3건은 한 묶음으로 — 반드시 #4와 동시 적용):
```python
# (a) 서문 제외: 첫 페르소나 헤딩 이전 텍스트는 폐기하거나,
#     메타데이터 블록(- **Tier**: ...)이 없는 섹션은 등록하지 않는다.
# (b) Model ID 정규식 교정:
model_match = re.search(r'\- \*\*Model ID\*\*: `?([\w.\-]+)`?', body)
# (c) 이름 정규화: name = re.sub(r'^페르소나:\s*', '', name)
```

**검증**: `--list-personas`가 정확히 50명 출력 + 단위테스트(제안 3)에서 `gemini-2.0-flash` 파싱 결과 assert.

---

### #4 모델 정본 부재 — 4-Tier 아키텍처의 사실상 해체 (심각도: 높음)

**증상**: "4-Tier 정밀 모델 매핑"이 프로젝트의 핵심 설계 철학("지식은 Flash, 지혜는 Pro")인데, 실제로는 모든 호출이 단일 모델로 나간다.

**원인**: 정본이 4곳에 흩어져 서로 다르다.

| 소스 | LITE | WORKER | THINKER | COMMANDER |
|------|------|--------|---------|-----------|
| 코드 `MODEL_REGISTRY` (:47-52) | flash-preview | flash-preview | flash-preview | **flash-preview** |
| `README.md` (:178-184) | 2.5-flash-lite | 2.5-flash | 2.5-flash | 3-pro-preview |
| `theological_research_v1.4.md` (:18-23) | flash-preview | flash-preview | flash-preview | 3-pro-preview |
| `personas_all.md` (50건 실측) | 2.0-flash-lite | 2.0-flash | 2.0-flash-thinking | 3.0-pro |

부수 결함: `MODEL_COSTS`(:55-60)의 COMMANDER `$2.00`은 실제로는 flash 단가의 호출에 적용되어 `estimate_cost`(:317)가 허수를 출력한다. 게다가 입력 토큰(고정 50K 가정)만 계산하고 출력 토큰은 무시한다.

**패치**:
1. **코드의 `MODEL_REGISTRY`를 유일한 정본**으로 선언하고, COMMANDER를 실제 상위 모델(`gemini-3-pro-preview`)로 차등화한다. 비용 때문에 단일 flash를 유지하려면 그 결정을 코드 주석과 README에 명시한다 — 현재처럼 "차등인 척하는 단일"이 최악이다.
2. README·v1.4.md의 표는 코드 값을 인용하는 형태로 정리하고, 2.0/2.5 잔재를 제거한다.
3. `MODEL_COSTS`를 실제 레지스트리 모델 단가와 일치시키되, 사전 견적은 "참고치"로 강등하고 실측은 제안 2(usage_metadata)로 이관한다.

**검증**: `grep -r "gemini-2" *.md personas/` 결과 0건. COMMANDER 호출 로그에 상위 모델명 표기.

---

### #5 약속–구현 갭 — Thinking Mode 허위 로그, Context Pruning 스텁 (심각도: 중간)

**증상 1**: THINKER 티어 실행 시 `🧠 [Thinking Mode] 논리적 추론 강화`를 출력하지만(`theology_orchestrator.py:268-269`), 실제 config는 temperature 0.5 설정뿐이다(:207-209). `thinking_config`는 어디에도 없다 — 로그가 거짓말을 한다.

**증상 2**: `apply_context_pruning`(:163-179)은 전략 텍스트를 라벨로만 쓰고 **3,000자 절단**한다. v1.4.md가 약속하는 "토큰 비용 90% 절감"(v1.4.md:7)의 실체이며, 50개 페르소나 전부에 선언된 Input Pruning 전략이 전혀 해석되지 않는다.

**패치**:
```python
# (a) THINKER에 실제 thinking 설정 부여 (google-genai SDK)
if tier.upper() == "THINKER":
    config["thinking_config"] = types.ThinkingConfig(thinking_budget=4096)
# SDK/모델이 미지원이면: 허위 로그를 제거하는 것이 차선책
```
(b) Pruning은 정직화가 1차 패치다: "요약된 컨텍스트"라는 거짓 라벨 대신 `[절단: 앞 3000자만 제공]`으로 표기하고, max_length를 문자 수가 아닌 대략적 토큰 기준으로 재산정한다. 전략 해석형 프루닝(LITE 모델로 요약 생성)은 비용이 들므로 §5 미결사항으로 분리.

**검증**: THINKER 호출의 request payload에 thinking 설정 존재(또는 로그 제거) 확인.

---

### #6 실패 격리 부재 — 에러 문자열이 보고서로 전파 (심각도: 높음)

**증상**: Phase 1에서 API 호출이 실패하면 `run_agent`가 `"❌ 실행 중 오류 발생: ..."` 문자열을 **반환값으로** 돌려주고(`theology_orchestrator.py:305-315`), `run_research`는 이를 그대로 Phase 2의 `context_data`로 주입한다(:425-431). 결과: 분석신학자가 에러 메시지를 "검증"하고, 최종 편집자가 에러 메시지로 "Nash Equilibrium"을 종합한 가짜 논문이 정상 산출물처럼 저장된다.

**원인**: 예외를 삼켜 문자열로 평탄화하는 안티패턴 + 재시도 없음 + 파이프라인 중단 게이트 없음.

**패치**:
```python
class AgentExecutionError(RuntimeError): ...

def run_agent(self, ...):
    for attempt in range(3):                  # 지수 백오프 재시도
        try:
            response = self.client.models.generate_content(...)
            if not response.text:             # 빈 응답도 실패로 간주
                raise AgentExecutionError(f"{persona_name}: empty response")
            return response.text
        except (서버측/일시 오류) as e:
            time.sleep(2 ** attempt)
    raise AgentExecutionError(...)            # 문자열 반환 금지, 예외 전파

# run_research: 예외 시 해당 시점까지의 중간 산출물을 보존하고 명시적으로 중단
```
재시도 대상은 일시 오류(429/5xx)로 한정하고, 인증·안전차단 오류는 즉시 전파한다.

**검증**: FakeClient로 Phase 1 실패를 주입하는 테스트(제안 3) — 최종 파일이 생성되지 **않고** 예외로 중단되는지 assert.

---

### #7 산출물 무결성 — 허위 메타데이터·무경고 덮어쓰기 (심각도: 중간)

**증상/원인** (3건):
1. **미사용 프롬프트 + 허위 기재**: `run_research`가 v1.4 프롬프트를 로드하고 "📜 메인 프롬프트 v1.4 로드됨"을 출력하지만(`theology_orchestrator.py:403-405`) **이후 어디에도 주입하지 않는다**. 그런데 산출물 메타데이터에는 `프롬프트: theological_research_v1.4.md`라고 기재된다(:464). 실제 실행은 v1.4의 7단계 프로토콜이 아니라 하드코딩된 4-Phase 축약 흐름이다.
2. **`os.popen('date')`**(:462): 생성 시각을 셸 호출로 얻는다 — 로케일 의존·비이식적.
3. **무경고 덮어쓰기**(:456-457): `safe_topic`은 공백·`/`만 치환하고 타임스탬프가 없어, 같은 주제 재실행 시 이전 결과를 조용히 덮어쓴다.

**패치**:
```python
# 1) 양자택일 — (a) main_prompt를 Commander의 instruction 앞에 실제 주입하거나
#    (b) 로드 코드와 메타데이터 기재를 함께 제거. "기재만 남기기"는 금지.
# 2) from datetime import datetime; datetime.now().isoformat(timespec="seconds")
# 3) run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
#    output_file = f"{safe_topic}_{run_id}_final.md"   # 제안 2의 run 디렉토리와 통합 예정
```

**검증**: 동일 주제 2회 실행 → 산출물 2개 공존. 메타데이터의 프롬프트 기재가 실제 주입과 일치.

---

### #8 `visualize_session.py` 잠복 NameError + 구조 중복 (심각도: 중간)

**증상 1 — 잠복 크래시**: `parse_markdown_sections`에서 `clean_title`(:199)과 `skipping_subsection`(:200)은 첫 `## ` 분기 안에서만 정의된다. 입력 마크다운에서 **`###` 라인이 첫 `##`보다 먼저 등장하면** `:241`(`clean_title.lower()`)에서 `NameError`로 즉사한다. LLM 산출물은 헤딩 위계를 보장하지 않으므로 실제 트리거 가능.

**증상 2 — 저장 로직 중복**: "이전 섹션 저장" 블록(:203-222)과 "마지막 섹션 저장" 블록(:259-276)이 거의 동일한 20줄 복제다. 한쪽만 수정되는 회귀의 전형적 온상 (이미 :208-211에 무의미한 중첩 중복 `if`가 존재).

**증상 3 — 죽은 반환값**: `subtitle`은 초기화만 되고 한 번도 채워지지 않은 채 반환된다(:175, :286).

**증상 4 — 메타 섹션이 직전 본문 섹션을 삭제 (Phase 1 테스트에서 발견, 심각도: 높음)**: 메타 섹션 헤딩(참고문헌 등)을 만나면 `skip_current_section = True; continue`(:193-195)로 빠져나가는데, 이때 **누적 중이던 직전 섹션을 flush하지 않는다**. 다음 헤딩/EOF의 저장 블록은 `not skip_current_section` 게이트(:203, :259)에 막혀 그 섹션을 폐기한다. 실측: `서론→참고문헌→결론` 입력에서 서론 소실, `서론→본론→참고문헌` 입력에서 본론 소실. **참고문헌으로 끝나는 통상적 보고서는 시각화 시 마지막 본문 섹션을 항상 잃는다.** 패치: 메타 헤딩 분기에서도 직전 섹션을 먼저 flush(증상 2의 `_flush_section` 헬퍼 공용화로 자연 해결). 회귀 테스트: `tests/test_visualize_parser.py::test_meta_section_silently_drops_preceding_section`.

부수: `visualize_session.py:130` docstring의 `\.` 이스케이프가 `SyntaxWarning`을 발생시킨다 — #8 패치 시 raw string 또는 이스케이프 정정.

**패치**:
```python
# 1) 루프 앞 초기화: clean_title = "" ; skipping_subsection = False
# 2) _flush_section(current_section, current_content, ...) 헬퍼로 추출,
#    두 호출 지점에서 공용 사용
# 3) subtitle 파싱을 구현하지 않을 거면 반환 시그니처에서 제거
```

**검증**: `###`가 선행하는 마크다운 픽스처로 단위테스트(제안 3) — 크래시 없이 파싱.

---

## 3. 구조 업그레이드 제안 1 ~ 3

### 제안 1 — 페르소나·설정 계약 검증층 (Contract Validation Layer)

**문제의식**: #3·#4의 결함이 모두 "조용히 틀린 값으로 계속 달리는" 유형이다. 파싱·매핑 단계에서 fail-fast 검증이 없기 때문이다.

**설계**:
```python
VALID_TIERS = {"LITE", "WORKER", "THINKER", "COMMANDER"}
KNOWN_MODELS = set(MODEL_REGISTRY.values()) | {"gemini-3-pro-preview"}

@dataclass
class Persona:
    name: str
    instruction: str
    tier: str            # VALID_TIERS 강제
    model_id: str | None # KNOWN_MODELS 화이트리스트 검사
    pruning: str | None

class PersonaManager:
    def _load_personas(self, path):
        ...
        errors = []
        # 검증 항목:
        #  - tier ∉ VALID_TIERS → 에러 수집
        #  - model_id가 화이트리스트 밖 → 에러 수집 (조용한 폴백 금지)
        #  - 메타데이터 블록 없는 섹션(서문 등) → 등록 제외
        #  - 이름 중복 → 에러
        #  - 기대 인원수(50) 불일치 → 경고
        if errors:
            raise PersonaValidationError("\n".join(errors))
```
`visualize_session.py`에도 동일 사상 적용: `--input` 경로 인자화 + 입력 파일 부재 시 `sys.exit(1)` (현재는 `return`으로 성공 종료해 셸 파이프라인이 실패를 감지하지 못한다 — `run_visualize.sh`는 `set -e`인데도).

**효과**: personas_all.md 편집 실수(오타 티어, 폐기 모델명)가 LLM 호출 비용을 태우기 **전에** 잡힌다.

### 제안 2 — 실행 감사 dossier (Run Audit Dossier)

**문제의식**: 현재 `execution_log`는 메모리에만 있다가 stdout 요약으로 휘발된다. 중간 산출물(Phase 1~3 보고서)도 버려져 최종본만 남는다. 비용은 사전 견적(허수)만 있고 실측이 없다. 기존 `research_outputs/칭의/` 등의 Stage별 보고서 디렉토리는 수동 운영의 흔적 — 이를 시스템화한다.

**설계**: run 1회 = 디렉토리 1개.
```
research_outputs/{safe_topic}/run_{YYYYMMDD-HHMMSS}/
├── phase1_draft.md            # 성경신학자 초안
├── phase2_analysis.md         # 분석신학자 검증
├── phase3_audit.md            # 편향 감사
├── final.md                   # Commander 종합 (시각화 입력 계약 대상)
└── execution_log.json         # 전 호출 기록 + usage_metadata 실측
```
`execution_log.json` 레코드: persona, tier, **실제 model_id**, 시작/종료 시각, `response.usage_metadata`의 prompt/candidates 토큰 수, 단가 기반 실측 비용, status. 실패 run도 디렉토리와 로그가 남아(#6과 결합) 사후 분석이 가능하다.

**효과**: "Adversarial Rationality Game"의 각 라운드가 감사 가능해진다. 비용 보고가 견적이 아닌 실측이 된다. `run_visualize.sh`는 최신 run의 `final.md`를 자동 발견하도록 단순화된다.

### 제안 3 — e2e 골든 테스트 + 회귀 게이트

**문제의식**: 테스트 0개. #3의 "상쇄된 이중 버그"처럼, 한 곳을 고치면 다른 곳이 터지는 구조를 테스트 없이 패치하는 것은 도박이다.

**설계**: `TheologyResearchEngine`이 이미 생성자에서 `client`를 주입받으므로(:188) 모킹 지점이 준비되어 있다.
```
tests/
├── conftest.py                # FakeClient (고정 응답/실패 주입/usage_metadata 모킹)
├── test_persona_manager.py    # 50명 정합, Model ID 'gemini-2.0-flash' 완전 파싱,
│                              # 서문 제외, '페르소나:' 프리픽스 정규화, 검증층 에러
├── test_engine.py             # tier→model 매핑, 재시도/백오프, 실패 시 예외 전파(#6)
├── test_visualize_parser.py   # '###' 선행 픽스처(NameError 회귀), 메타 섹션 필터,
│                              # 각주 3원 폴백(JSON→각주정의→참고문헌)
└── test_e2e_golden.py         # FakeClient로 전체 4-Phase 실행 →
                               # dossier 구조·final.md·log JSON을 골든과 비교
```
실행 규약: `uv run --inexact python -m pytest` (SHARED_VENV.md 준수). 모든 후속 패치는 이 게이트 통과를 완료 조건으로 삼는다.

---

## 4. 구현 순서와 검증 계획

의존 관계상 아래 순서를 권장한다.

| 단계 | 내용 | 완료 게이트 |
|------|------|------------|
| Phase 0 ✅ | #1 환경 복구 (requirements 정정, 공유 venv 심링크, 경로 정정) — 2026-06-11 완료 | `--list-personas` 실행 성공 ✅ |
| Phase 1 ✅ | 제안 3 골격 선행 (FakeClient + 현행 동작 스냅샷 테스트) — 2026-06-11 완료, `tests/` 32개 (결함 #3·4·5·6·7·8 characterization 포함, #8-4 신규 발견) | pytest 그린 (현행 기준) ✅ 32 passed |
| Phase 2 ✅ | 결함 패치 #3+#4 (동시), #5, #6, #7+#2, #8 — 2026-06-11 완료 (커밋 5건, 패치별 테스트 갱신) | 각 패치마다 그린 ✅ 최종 39 passed + 실문서 시각화 스모크 |
| Phase 3 ✅ | 제안 1 검증층 + 제안 2 dossier + 제안 3 골든 승격 — 2026-06-11 완료 | e2e 골든 4종(dossier 구성·log 스키마·실측) ✅ 44 passed |

**주의 — #3과 #4의 동시 적용**: Model ID 정규식만 먼저 고치면 50명 전원이 폐기된 `gemini-2.0-*` 모델을 실제 호출하게 된다. 정규식 교정과 personas_all.md의 모델명 일괄 갱신(또는 화이트리스트 검증층)을 한 커밋으로 묶는다.

**실 API 검증**: 모킹 테스트 통과 후, 저비용 확인으로 `--topic` 1회 실 실행하여 dossier 구조와 usage_metadata 실측을 육안 확인한다 (API 키 필요, 비용 발생 — 사용자 승인 후).

---

## 5. 미결사항 및 결정 기록

1. **Archived 상태의 거취** (미결): README는 본 프로젝트를 ARC v2.1(Secretariat) 워크플로우로 대체된 레거시로 선언한다. 본 고도화로 CLI 트랙을 현역 복귀시킬 것인지, "보존 품질의 아카이브"로 한정할 것인지는 사용자 결정 대기.
2. **버전 관리** (결정됨, 2026-06-11): `git add -f`로 워크스페이스 레포(main)에서 추적 시작. `.gitignore:54`의 `projects/` 제외는 유지 — 추적된 파일의 변경은 정상 기록되며, **신규 파일 추가 시에만 `git add -f` 필요**.
3. **COMMANDER 모델** (결정됨, Phase 2 #4): `gemini-3-pro-preview` 차등화 적용 — README·v1.4.md가 이미 약속하던 설계 철학("지혜를 통합하는 자는 Pro") 복원. Phase 4 호출 1회만 상위 단가.
4. **Context Pruning의 실구현 수준** (미결): 현재는 정직한 절단 라벨(#5 1차 패치). LITE 모델 요약 기반의 전략 해석형 프루닝까지 갈지는 사용자 결정 대기.
5. **v1.4 프롬프트 거취** (결정됨, Phase 2 #7): 선택지 (b) 채택 — 미주입 로드 코드와 허위 메타데이터 기재를 제거. `theological_research_v1.4.md`는 설계 문서로 보존되며, 7단계 프로토콜의 실구현 여부는 1번(Archived 거취)과 함께 결정할 사안.
6. **제안 1 구현 방식** (결정됨, Phase 3): dataclass 전환 대신 기존 dict 구조를 유지하고 검증층만 추가 — README의 Python API 예시·기존 호출부와의 호환을 우선. 검증 항목: Tier 화이트리스트, Model ID 등록 검사(폐기 모델 차단), 이름 중복, 위반 일괄 보고.
7. **dossier 출력 계약** (결정됨, Phase 3 제안 2): `research_outputs/{safe_topic}/run_{run_id}/` 1-run-1-디렉토리. `run_visualize.sh`는 dossier → 평면 `*_final.md` → 구 `_research.md` 순 3단 폴백. 미푸시 히스토리의 대용량 블롭(msn_th_db vector_db)은 임시 클론 filter-repo로 정리 후 푸시 재개 (백업: `backup-pre-blob-purge-20260611` 브랜치).

### 추가 발견 — 산출물·파서 형식 갭 (해소됨, 2026-06-11)

Phase 2 스모크테스트에서 확인: 오케스트레이터 최종 산출물은 본문 섹션을 `###`로 생성하는 경향이 있는데(LLM 출력 형식), 시각화 파서는 `## `(H2)를 섹션 경계로 삼아 실산출물이 "섹션 1개"로 평탄화되어 렌더링될 수 있었다.

**해소**: (a)+(b) 동시 적용. (a) Commander 프롬프트에 H2 구조 지시 추가(유도), (b) 파서에 결정론적 폴백 — 내용 있는 H2가 0개이고 `###`가 2개 이상이면 헤딩을 한 단계 승격해 파싱. `연구 메타데이터` 블록은 메타 섹션으로 본문에서 제외. 실문서(TRE 보고서) 검증: 섹션 1개 → 5개 정상 분리. 회귀 테스트 2종 + e2e 골든 단언 추가 (총 46 passed).
