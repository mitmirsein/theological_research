#!/usr/bin/env python3
"""
Theology Research Orchestrator v2.1
====================================

50명의 AI 신학자를 지휘하는 오케스트레이터.

4-Tier 정밀 모델 매핑:
- LITE: 팀 구성/라우팅/구조 검수 ($0.10)
- WORKER: RAG 독해/초안 작성 ($0.15)
- THINKER: 논리 추론/분석 (Thinking Mode)
- COMMANDER: 내쉬 균형/최종 편집 ($2.00)

Usage:
    python theology_orchestrator.py
    
Requirements:
    pip install -r requirements.txt  # google-genai (신형 SDK), python-dotenv
"""

import re
import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types


class AgentExecutionError(RuntimeError):
    """에이전트 호출 실패. 에러를 문자열 반환값으로 평탄화하지 않기 위한 명시적 예외 (결함 #6)."""


class PersonaValidationError(ValueError):
    """페르소나 자산의 계약 위반 — LLM 호출 비용을 태우기 전에 로드 시점에 잡는다 (제안 1)."""


# 일시 오류 식별자 — 재시도 대상. 인증·안전차단 등 그 외 오류는 즉시 전파한다.
RETRYABLE_MARKERS = (
    "429", "500", "502", "503",
    "RESOURCE_EXHAUSTED", "UNAVAILABLE", "DEADLINE_EXCEEDED", "overloaded",
)
MAX_ATTEMPTS = 3


def _is_retryable(error: Exception) -> bool:
    message = str(error)
    return any(marker in message for marker in RETRYABLE_MARKERS)

# ==============================================================================
# 1. 설정 (Configuration)
# ==============================================================================

# .env 파일에서 API 키 로드
load_dotenv()

def init_genai():
    """Gemini API 초기화 (필요시 호출)"""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GOOGLE_API_KEY가 설정되지 않았습니다.")
        print("   .env 파일에 GOOGLE_API_KEY=your_key_here 형식으로 추가하세요.")
        print("   또는 환경 변수로 설정하세요: export GOOGLE_API_KEY=your_key_here")
        return None
    return genai.Client(api_key=api_key)


# 모델 정본 (Single Source of Truth) — README·v1.4.md·personas_all.md의 표는 이 값을 인용한다.
# 최신 모델명: https://ai.google.dev/gemini-api/docs/models
MODEL_REGISTRY = {
    "LITE": "gemini-3-flash-preview",         # 빠른 분류/검수
    "WORKER": "gemini-3-flash-preview",       # 초안 작성/독해
    "THINKER": "gemini-3-flash-preview",      # Thinking 모드 활성화 (thinking_config)
    "COMMANDER": "gemini-3-pro-preview"       # 내쉬 균형/최종 종합 — 상위 모델 차등
}

# 모델별 입력 비용 (1M 토큰 기준, USD) — 사전 견적용 참고치. 실측은 usage_metadata 기반(제안 2).
MODEL_COSTS = {
    "LITE": 0.15,
    "WORKER": 0.15,
    "THINKER": 0.15,  # 입력은 동일, 출력이 다름
    "COMMANDER": 2.00
}

# 페르소나 메타데이터 계약 (제안 1)
VALID_TIERS = {"LITE", "WORKER", "THINKER", "COMMANDER"}
KNOWN_MODELS = set(MODEL_REGISTRY) | set(MODEL_REGISTRY.values())

# 안전 설정 (연구용이므로 차단 기준을 낮춤)
SAFETY_SETTINGS = [
    types.SafetySetting(
        category="HARM_CATEGORY_HARASSMENT",
        threshold="BLOCK_NONE"
    ),
    types.SafetySetting(
        category="HARM_CATEGORY_HATE_SPEECH",
        threshold="BLOCK_NONE"
    ),
    types.SafetySetting(
        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
        threshold="BLOCK_NONE"
    ),
    types.SafetySetting(
        category="HARM_CATEGORY_DANGEROUS_CONTENT",
        threshold="BLOCK_NONE"
    ),
]

# ==============================================================================
# 2. 페르소나 관리자 (Persona Manager)
# ==============================================================================

class PersonaManager:
    """마크다운 파일에서 전문가 페르소나와 메타데이터를 파싱합니다."""
    
    def __init__(self, file_path):
        self.personas = {}
        self._load_personas(file_path)

    def _load_personas(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"❌ 페르소나 파일을 찾을 수 없습니다: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # '# 페르소나 이름' 패턴으로 분리
        sections = re.split(r'^#\s+(.+)$', content, flags=re.MULTILINE)

        errors = []  # 계약 위반 수집 — 조용한 폴백 대신 로드 시점 fail-fast (제안 1)

        # split 결과: [서문, 제목1, 내용1, 제목2, 내용2, ...]
        for i in range(1, len(sections), 2):
            # '페르소나: ' 프리픽스 정규화 — 호출명과 헤딩 표기의 불일치 제거
            name = re.sub(r'^페르소나:\s*', '', sections[i].strip())
            body = sections[i+1].strip() if i+1 < len(sections) else ""

            # 메타데이터 파싱 (Tier, Pruning)
            pruning = None
            model_id = None

            # Tier 추출 — 메타데이터 블록이 없는 섹션(문서 서문 등)은 페르소나가 아니므로 제외
            tier_match = re.search(r'\- \*\*Tier\*\*: (\w+)', body)
            if not tier_match:
                continue
            tier = tier_match.group(1)

            # Model ID 추출 — 모델명은 '-'와 '.'을 포함한다 (예: gemini-3-flash-preview)
            model_match = re.search(r'\- \*\*Model ID\*\*: `?([\w.\-]+)`?', body)
            if model_match:
                model_id = model_match.group(1)

            # 계약 검증 (제안 1)
            if tier.upper() not in VALID_TIERS:
                errors.append(f"'{name}': 허용되지 않는 Tier '{tier}' (허용: {sorted(VALID_TIERS)})")
            if model_id and model_id not in KNOWN_MODELS:
                errors.append(f"'{name}': 미등록 Model ID '{model_id}' (MODEL_REGISTRY 키/값만 허용)")
            if name in self.personas:
                errors.append(f"'{name}': 이름 중복")
            
            # Pruning 전략 추출
            pruning_match = re.search(r'\- \*\*Input Pruning\*\*: (.+)', body)
            if pruning_match:
                pruning_text = pruning_match.group(1)
                if "해당 없음" not in pruning_text:
                    pruning = pruning_text.strip()

            self.personas[name] = {
                "instruction": body,
                "tier": tier,
                "model_id": model_id,
                "pruning": pruning
            }

        if errors:
            raise PersonaValidationError(
                f"페르소나 계약 위반 {len(errors)}건:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

    def get_persona(self, name):
        """페르소나 이름으로 설정 가져오기"""
        return self.personas.get(name)
    
    def find_persona(self, keyword):
        """키워드로 페르소나 찾기 (부분 일치)"""
        for name, config in self.personas.items():
            if keyword.lower() in name.lower():
                return name, config
        return None, None
    
    def list_personas(self):
        """모든 페르소나 목록 출력"""
        print("\n📋 등록된 전문가 목록:")
        print("-" * 60)
        for name, config in self.personas.items():
            tier = config.get('tier', 'Worker')
            pruning = "✂️" if config.get('pruning') else ""
            print(f"  [{tier:10}] {name} {pruning}")
        print("-" * 60)
        print(f"  총 {len(self.personas)}명의 전문가")

# ==============================================================================
# 3. 컨텍스트 프루닝 (Context Pruning)
# ==============================================================================

def apply_context_pruning(context_data: str, pruning_strategy: str, max_length: int = 3000) -> str:
    """
    컨텍스트 가지치기 적용
    
    Args:
        context_data: 원본 컨텍스트
        pruning_strategy: 프루닝 전략 설명
        max_length: 최대 길이
        
    Returns:
        가지치기된 컨텍스트
    """
    if not context_data or len(context_data) <= max_length:
        return context_data

    # 정직한 표기: 전략 해석형 요약이 아니라 단순 절단이다 (전략 해석은 미구현 — §5 미결 4)
    return (
        f"[컨텍스트 절단 - 선언된 전략(미적용): {pruning_strategy}]\n"
        f"{context_data[:max_length]}...\n"
        f"(이하 {len(context_data) - max_length}자 절단)"
    )

# ==============================================================================
# 4. 리서치 엔진 (Research Engine)
# ==============================================================================

class TheologyResearchEngine:
    """신학 연구 실행 엔진"""
    
    def __init__(self, persona_manager: PersonaManager, client: genai.Client):
        self.pm = persona_manager
        self.client = client
        self.execution_log = []

    def _get_model_id(self, tier: str, override_model: str = None) -> str:
        """Tier에 맞는 최적 모델 ID 반환.

        override_model은 티어 키(LITE 등) 또는 실제 모델명(레지스트리 등록 값)만 허용.
        그 외 값은 티어 매핑으로 폴백한다 (등록 외 모델명 거부는 제안 1 검증층에서 강화).
        """
        if override_model:
            if override_model in MODEL_REGISTRY:
                return MODEL_REGISTRY[override_model]
            if override_model in MODEL_REGISTRY.values():
                return override_model
        return MODEL_REGISTRY.get(tier.upper(), MODEL_REGISTRY["WORKER"])

    def _get_generation_config(self, tier: str) -> types.GenerateContentConfig:
        """Tier에 맞는 generation config 반환"""
        config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 8192,
        }
        
        if tier.upper() == "THINKER":
            # Thinking Mode 실활성화 — 로그 표기와 실제 설정의 일치 (결함 #5)
            config["temperature"] = 0.5
            config["thinking_config"] = types.ThinkingConfig(thinking_budget=4096)

        elif tier.upper() == "COMMANDER":
            # Commander는 최대 품질
            config["temperature"] = 0.3
            config["max_output_tokens"] = 16384
            
        elif tier.upper() == "LITE":
            # Lite는 빠른 응답
            config["temperature"] = 0.1
            config["max_output_tokens"] = 2048
            
        return types.GenerateContentConfig(**config, safety_settings=SAFETY_SETTINGS)

    def run_agent(
        self, 
        persona_name: str, 
        task_input: str, 
        context_data: str = "",
        verbose: bool = True
    ) -> str:
        """
        지정된 전문가 에이전트를 실행합니다.
        자동으로 모델을 스위칭하고, 컨텍스트를 최적화합니다.
        
        Args:
            persona_name: 페르소나 이름
            task_input: 수행할 태스크
            context_data: RAG 컨텍스트 데이터
            verbose: 상세 로그 출력 여부
            
        Returns:
            에이전트 응답 텍스트
        """
        config = self.pm.get_persona(persona_name)
        if not config:
            # 부분 일치로 재시도
            found_name, config = self.pm.find_persona(persona_name)
            if config:
                persona_name = found_name
            else:
                raise AgentExecutionError(f"'{persona_name}'라는 전문가를 찾을 수 없습니다.")

        tier = config.get('tier', 'Worker')
        model_id = self._get_model_id(tier, config.get('model_id'))
        gen_config = self._get_generation_config(tier)
        
        if verbose:
            print(f"\n🚀 [{persona_name}] 가동 시작...")
            print(f"   ⚙️  Model: {model_id} (Tier: {tier})")

        # 1. 컨텍스트 가지치기 (Context Pruning)
        final_context = context_data
        if config.get('pruning'):
            if verbose:
                print(f"   ✂️  [Context 절단] 적용 (선언된 전략: {config['pruning']} — 해석은 미구현)")
            final_context = apply_context_pruning(context_data, config['pruning'])

        # 2. Thinking Mode 로그
        if tier.upper() == "THINKER" and verbose:
            print("   🧠 [Thinking Mode] 논리적 추론 강화")

        # 3. 모델 호출 — 일시 오류는 지수 백오프 재시도, 실패 확정 시 예외 전파 (결함 #6)
        prompt = f"""
{config['instruction']}

============================================================
[제공된 데이터 / RAG Context]
{final_context if final_context else "(없음)"}
============================================================

[현재 임무 / TASK]
{task_input}
"""

        started = time.time()
        last_error = None
        attempt = 0
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self.client.models.generate_content(
                    model=model_id,
                    contents=prompt,
                    config=gen_config
                )
            except Exception as e:
                last_error = e
                if attempt < MAX_ATTEMPTS and _is_retryable(e):
                    delay = 2 ** attempt
                    if verbose:
                        print(f"   ⏳ 일시 오류 — {delay}초 후 재시도 ({attempt}/{MAX_ATTEMPTS}): {e}")
                    time.sleep(delay)
                    continue
                break

            if not response.text:
                last_error = AgentExecutionError("빈 응답 (안전차단 또는 출력 토큰 소진 가능성)")
                break

            if verbose:
                print("   ✅ 작업 완료.")

            # 실측 기록 (제안 2) — usage_metadata 기반 토큰·참고 비용
            usage = getattr(response, "usage_metadata", None)
            tokens_in = getattr(usage, "prompt_token_count", None)
            tokens_out = getattr(usage, "candidates_token_count", None)
            self.execution_log.append({
                "persona": persona_name,
                "tier": tier,
                "model": model_id,
                "task": task_input[:100],
                "status": "success",
                "attempts": attempt,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "elapsed_s": round(time.time() - started, 3),
                "cost_input_usd": (
                    round(tokens_in / 1_000_000 * MODEL_COSTS.get(tier.upper(), 0.15), 8)
                    if tokens_in is not None else None
                ),
            })
            return response.text

        # 실패 확정 — 에러 문자열을 보고서처럼 반환하는 것을 금지한다.
        self.execution_log.append({
            "persona": persona_name,
            "tier": tier,
            "model": model_id,
            "task": task_input[:100],
            "status": "error",
            "error": str(last_error),
            "attempts": attempt,
            "elapsed_s": round(time.time() - started, 3),
        })
        if verbose:
            print(f"   ❌ 실행 실패 (시도 {attempt}회): {last_error}")
        raise AgentExecutionError(
            f"[{persona_name}] 호출 실패 (시도 {attempt}회): {last_error}"
        ) from last_error

    def estimate_cost(self, persona_list: list, avg_input_tokens: int = 50000) -> float:
        """예상 비용 계산"""
        total_cost = 0.0
        for persona_name in persona_list:
            config = self.pm.get_persona(persona_name)
            if not config:
                _, config = self.pm.find_persona(persona_name)
            
            if config:
                tier = config.get('tier', 'Worker').upper()
                cost_per_million = MODEL_COSTS.get(tier, 0.15)
                total_cost += (avg_input_tokens / 1_000_000) * cost_per_million
        return total_cost

    def print_execution_summary(self):
        """실행 요약 출력"""
        print("\n" + "=" * 60)
        print("📊 실행 요약")
        print("=" * 60)
        
        success_count = sum(1 for log in self.execution_log if log['status'] == 'success')
        error_count = sum(1 for log in self.execution_log if log['status'] == 'error')
        
        print(f"  ✅ 성공: {success_count}")
        print(f"  ❌ 실패: {error_count}")
        print(f"  📝 총 호출: {len(self.execution_log)}")
        
        # 티어별 호출 수
        tier_counts = {}
        for log in self.execution_log:
            tier = log['tier']
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        
        print("\n  🏷️  티어별 호출:")
        for tier, count in tier_counts.items():
            print(f"      - {tier}: {count}회")

# ==============================================================================
# 5. 연구 워크플로우 (Research Workflow)
# ==============================================================================

def run_research(topic: str, rag_context: str = "", output_dir: str = None):
    """
    연구 워크플로우 실행
    
    Args:
        topic: 연구 주제
        rag_context: RAG 컨텍스트 (선택)
        output_dir: 출력 디렉토리 (선택)
    """
    # 파일 경로 설정
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PERSONA_FILE = os.path.join(SCRIPT_DIR, "personas_all.md")
    
    if output_dir is None:
        output_dir = os.path.join(SCRIPT_DIR, "research_outputs")
    os.makedirs(output_dir, exist_ok=True)
    
    # API 초기화
    client = init_genai()
    if not client:
        return None
    
    # 1. 매니저 초기화
    print("📚 디지털 신학대학 교수진을 소집합니다...")
    try:
        manager = PersonaManager(PERSONA_FILE)
        engine = TheologyResearchEngine(manager, client)
        print(f"✅ 총 {len(manager.personas)}명의 전문가가 대기 중입니다.\n")
    except Exception as e:
        print(f"초기화 실패: {e}")
        return None
    
    # --- 연구 시작 ---
    print("\n" + "=" * 60)
    print(f"🔬 연구 주제: {topic}")
    print("=" * 60)
    
    # 비용 추정
    team = ["성경신학자", "편향", "분석신학자", "최종 편집자"]
    estimated_cost = engine.estimate_cost(team)
    print(f"\n💰 예상 비용: ${estimated_cost:.4f}")
    
    # 감사 dossier (제안 2): run 1회 = 디렉토리 1개
    #   research_outputs/{safe_topic}/run_{run_id}/
    #   ├── phase1_draft.md / phase2_analysis.md / phase3_audit.md
    #   ├── final.md
    #   └── execution_log.json (실측 토큰·비용 포함)
    # run_id 충돌 시 카운터 부가 — 동일 주제 재실행이 이전 결과를 덮어쓰지 않는다 (결함 #7)
    safe_topic = re.sub(r'[\\/:*?"<>|\s]+', "_", topic).strip("_")[:30]
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = os.path.join(output_dir, safe_topic, f"run_{run_id}")
    counter = 1
    while os.path.exists(run_dir):
        run_dir = os.path.join(output_dir, safe_topic, f"run_{run_id}-{counter}")
        counter += 1
    os.makedirs(run_dir)

    def save_artifact(filename: str, body: str):
        with open(os.path.join(run_dir, filename), "w", encoding="utf-8") as f:
            f.write(body)

    def write_log(status: str):
        with open(os.path.join(run_dir, "execution_log.json"), "w", encoding="utf-8") as f:
            json.dump({
                "topic": topic,
                "run_id": os.path.basename(run_dir),
                "status": status,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "model_registry": MODEL_REGISTRY,
                "calls": engine.execution_log,
            }, f, ensure_ascii=False, indent=2)

    try:
        # Phase 1: [Worker] 성경신학자 초안
        print("\n📝 Phase 1: 성경신학자 초안 작성...")
        report_1 = engine.run_agent(
            "성경신학자 (Biblical Theologian)",
            f"'{topic}'에 대해 성서신학적 관점에서 초안을 작성해줘. 핵심 성경 본문과 신학적 쟁점을 분석하라.",
            context_data=rag_context
        )
        save_artifact("phase1_draft.md", report_1)

        # Phase 2: [Thinker] 분석신학자 논리 검증
        print("\n🧠 Phase 2: 분석신학자 논리 검증...")
        analysis_report = engine.run_agent(
            "분석신학자 (Analytic Theologian)",
            f"위 성경신학자의 보고서에서 논리적 타당성을 검증하고, 가능한 반례와 대안적 설명을 탐구하라.",
            context_data=report_1
        )
        save_artifact("phase2_analysis.md", analysis_report)

        # Phase 3: [Auditor] 편향 감사
        print("\n🔍 Phase 3: 편향 감사...")
        audit_report = engine.run_agent(
            "편향 및 전승 감사 전문가 (Bias and Tradition Auditor)",
            "위 보고서들이 서구 중심적이거나 특정 교파에 편향되었는지 점검하고, 균형잡힌 관점을 제시하라.",
            context_data=f"=== 초안 ===\n{report_1}\n\n=== 분석 ===\n{analysis_report}"
        )
        save_artifact("phase3_audit.md", audit_report)

        # Phase 4: [Commander] 최종 종합
        print("\n⚔️ Phase 4: Nash Equilibrium 종합 (Commander)...")
        final_paper = engine.run_agent(
            "최종 편집자 (Final Editor)",
            f"""
        연구 주제: {topic}

        아래 자료를 종합하여 Nash Equilibrium을 갖춘 최종 학술 논문을 작성하라.
        - 어떤 신학 전통(개혁, 가톨릭, 정교회)에서도 파훼 불가능한 균형점을 찾으라.
        - SBL 인용 형식을 준수하라.
        - 본문 구조: 최상위 본문 섹션은 반드시 '## '(H2) 헤딩으로, 하위 절은 '### '(H3)으로 작성하라.
        """,
            context_data=f"=== 초안 ===\n{report_1}\n\n=== 분석 ===\n{analysis_report}\n\n=== 감사 ===\n{audit_report}"
        )
    except AgentExecutionError as e:
        # 명시적 중단 — 에러 문자열로 '가짜 논문'을 합성하지 않는다 (결함 #6)
        # 완료된 Phase 산출물은 이미 dossier에 저장되어 있다.
        print(f"\n❌ 파이프라인 중단: {e}")
        write_log("aborted")
        print(f"   💾 부분 산출물·실행 로그 보존: {run_dir}")
        engine.print_execution_summary()
        return None

    # 결과 저장
    output_file = os.path.join(run_dir, "final.md")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# 연구 주제: {topic}\n\n")
        f.write("## 연구 메타데이터\n")
        f.write(f"- 생성일: {datetime.now().isoformat(timespec='seconds')}\n")
        f.write(f"- 모델: 4-Tier Architecture (LITE/WORKER/THINKER/COMMANDER)\n")
        f.write(f"- 워크플로우: 4-Phase (초안 → 논리 검증 → 편향 감사 → Commander 종합)\n\n")
        f.write("---\n\n")
        f.write(final_paper)

    write_log("completed")

    # 실행 요약
    engine.print_execution_summary()

    print(f"\n🎉 모든 연구 과정이 완료되었습니다!")
    print(f"📄 결과 파일: {output_file}")
    print(f"🗂️  감사 dossier: {run_dir}")

    return output_file

# ==============================================================================
# 6. CLI 인터페이스 (Command Line Interface)
# ==============================================================================

def main():
    """CLI 진입점"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="🎓 Theology Research Orchestrator v2.1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python theology_orchestrator.py --topic "칭의론"
  python theology_orchestrator.py --topic "삼위일체" --rag context.txt
  python theology_orchestrator.py --interactive
        """
    )
    parser.add_argument(
        "--topic", "-t",
        type=str,
        help="연구 주제 (필수 또는 --interactive 사용)"
    )
    parser.add_argument(
        "--rag", "-r",
        type=str,
        help="RAG 컨텍스트 파일 경로 (선택)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="출력 디렉토리 (기본: research_outputs/)"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="대화형 모드로 실행"
    )
    parser.add_argument(
        "--list-personas",
        action="store_true",
        help="등록된 페르소나 목록 출력"
    )
    
    args = parser.parse_args()
    
    # 페르소나 목록 출력
    if args.list_personas:
        SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
        manager = PersonaManager(os.path.join(SCRIPT_DIR, "personas_all.md"))
        manager.list_personas()
        return
    
    # RAG 컨텍스트 로드
    rag_context = ""
    if args.rag:
        if os.path.exists(args.rag):
            with open(args.rag, 'r', encoding='utf-8') as f:
                rag_context = f.read()
            print(f"📂 RAG 컨텍스트 로드됨: {args.rag} ({len(rag_context)} chars)")
        else:
            print(f"⚠️ RAG 파일을 찾을 수 없습니다: {args.rag}")
    
    # 대화형 모드
    if args.interactive:
        print("\n🎓 Theology Research Orchestrator v2.1")
        print("=" * 50)
        topic = input("\n📝 연구 주제를 입력하세요: ").strip()
        if not topic:
            print("❌ 연구 주제가 필요합니다.")
            return
        
        rag_input = input("📂 RAG 컨텍스트 (없으면 Enter): ").strip()
        if rag_input and os.path.exists(rag_input):
            with open(rag_input, 'r', encoding='utf-8') as f:
                rag_context = f.read()
        
        run_research(topic, rag_context, args.output)
        return
    
    # CLI 모드
    if args.topic:
        run_research(args.topic, rag_context, args.output)
    else:
        parser.print_help()
        print("\n💡 팁: --topic '주제' 또는 --interactive 옵션을 사용하세요.")


if __name__ == "__main__":
    main()
