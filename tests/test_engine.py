"""TheologyResearchEngine 스냅샷 테스트.

[characterization] 결함 #4(단일 모델)·#6(에러 문자열 전파)을 현행 그대로 고정.
Phase 2 패치 시 단언을 의도적으로 갱신한다.
"""

import pytest

from theology_orchestrator import (
    MODEL_REGISTRY,
    AgentExecutionError,
    TheologyResearchEngine,
    apply_context_pruning,
)
from conftest import FakeClient


@pytest.fixture
def engine(persona_manager, fake_client):
    return TheologyResearchEngine(persona_manager, fake_client)


# --- 모델 매핑 ---------------------------------------------------------------

def test_commander_uses_differentiated_model():
    """결함 #4 패치: COMMANDER는 상위 모델로 차등화된다."""
    assert MODEL_REGISTRY["COMMANDER"] == "gemini-3-pro-preview"
    assert MODEL_REGISTRY["COMMANDER"] != MODEL_REGISTRY["WORKER"]


def test_model_name_override_resolves_to_itself(engine):
    """결함 #3 패치: 레지스트리 등록 모델명 오버라이드는 그대로 사용된다."""
    assert engine._get_model_id("WORKER", "gemini-3-pro-preview") == "gemini-3-pro-preview"


def test_unknown_model_override_falls_back_to_tier(engine):
    """등록 외 오버라이드는 티어 폴백 (거부 강화는 제안 1 검증층에서)."""
    assert engine._get_model_id("WORKER", "gemini") == MODEL_REGISTRY["WORKER"]


def test_unknown_tier_falls_back_to_worker(engine):
    assert engine._get_model_id("AUDITOR") == MODEL_REGISTRY["WORKER"]


def test_generation_config_per_tier(engine):
    lite = engine._get_generation_config("LITE")
    assert lite.temperature == 0.1 and lite.max_output_tokens == 2048

    commander = engine._get_generation_config("COMMANDER")
    assert commander.temperature == 0.3 and commander.max_output_tokens == 16384

    thinker = engine._get_generation_config("THINKER")
    assert thinker.temperature == 0.5
    # 결함 #5 패치: THINKER에 thinking 설정이 실제로 부여된다.
    assert thinker.thinking_config is not None
    assert thinker.thinking_config.thinking_budget == 4096
    # 다른 티어에는 부여되지 않는다.
    assert engine._get_generation_config("WORKER").thinking_config is None


# --- run_agent ---------------------------------------------------------------

def test_run_agent_success(persona_manager):
    client = FakeClient(script=["성서신학적 초안입니다."])
    engine = TheologyResearchEngine(persona_manager, client)

    result = engine.run_agent(
        "성경신학자 (Biblical Theologian)", "칭의에 대해 분석하라.", verbose=False
    )

    assert result == "성서신학적 초안입니다."
    assert len(client.models.calls) == 1
    assert client.models.calls[0]["model"] == MODEL_REGISTRY["WORKER"]
    assert "칭의에 대해 분석하라." in client.models.calls[0]["contents"]
    assert engine.execution_log[-1]["status"] == "success"


def test_run_agent_nonretryable_failure_raises_immediately(persona_manager):
    """결함 #6 패치: 비일시 오류는 재시도 없이 1회 호출 후 예외 전파 (문자열 반환 금지)."""
    client = FakeClient(error=RuntimeError("invalid API key"))
    engine = TheologyResearchEngine(persona_manager, client)

    with pytest.raises(AgentExecutionError, match="invalid API key"):
        engine.run_agent("성경신학자 (Biblical Theologian)", "분석하라.", verbose=False)

    assert len(client.models.calls) == 1
    assert engine.execution_log[-1]["status"] == "error"


def test_run_agent_retries_transient_errors_then_succeeds(persona_manager, monkeypatch):
    """결함 #6 패치: 일시 오류(503 등)는 지수 백오프로 재시도 후 성공 가능."""
    import theology_orchestrator as orch
    monkeypatch.setattr(orch.time, "sleep", lambda s: None)

    client = FakeClient(script=[
        RuntimeError("503 UNAVAILABLE"),
        RuntimeError("503 UNAVAILABLE"),
        "재시도 후 성공",
    ])
    engine = TheologyResearchEngine(persona_manager, client)

    result = engine.run_agent("성경신학자 (Biblical Theologian)", "분석하라.", verbose=False)

    assert result == "재시도 후 성공"
    assert len(client.models.calls) == 3
    assert engine.execution_log[-1]["status"] == "success"
    assert engine.execution_log[-1]["attempts"] == 3


def test_run_agent_exhausts_retries_then_raises(persona_manager, monkeypatch):
    """결함 #6 패치: 일시 오류가 MAX_ATTEMPTS(3)회 지속되면 예외 전파."""
    import theology_orchestrator as orch
    monkeypatch.setattr(orch.time, "sleep", lambda s: None)

    client = FakeClient(error=RuntimeError("429 RESOURCE_EXHAUSTED"))
    engine = TheologyResearchEngine(persona_manager, client)

    with pytest.raises(AgentExecutionError):
        engine.run_agent("성경신학자 (Biblical Theologian)", "분석하라.", verbose=False)

    assert len(client.models.calls) == 3
    assert engine.execution_log[-1]["attempts"] == 3


def test_run_agent_empty_response_raises(persona_manager):
    """결함 #6 패치: 빈 응답(안전차단 등)도 실패로 간주하고 예외 전파."""
    client = FakeClient(script=[""])
    engine = TheologyResearchEngine(persona_manager, client)

    with pytest.raises(AgentExecutionError, match="빈 응답"):
        engine.run_agent("성경신학자 (Biblical Theologian)", "분석하라.", verbose=False)


def test_run_agent_unknown_persona_raises(engine):
    with pytest.raises(AgentExecutionError, match="찾을 수 없습니다"):
        engine.run_agent("존재하지않는전문가XYZ", "분석하라.", verbose=False)
    assert len(engine.client.models.calls) == 0


def test_run_agent_exact_match_after_normalization(persona_manager):
    """결함 #3 패치: 프리픽스 정규화로 '편향...' 호출이 정확 일치로 연결된다."""
    client = FakeClient(script=["감사 보고서"])
    engine = TheologyResearchEngine(persona_manager, client)

    result = engine.run_agent(
        "편향 및 전승 감사 전문가 (Bias and Tradition Auditor)", "점검하라.", verbose=False
    )

    assert result == "감사 보고서"
    assert engine.execution_log[-1]["persona"] == "편향 및 전승 감사 전문가 (Bias and Tradition Auditor)"


# --- 컨텍스트 프루닝 / 비용 ---------------------------------------------------

def test_context_pruning_labels_truncation_honestly():
    """결함 #5 패치: '요약' 거짓 라벨 대신 '절단'을 명시한다 (전략 해석은 §5 미결 4)."""
    long_context = "가" * 5000
    out = apply_context_pruning(long_context, "핵심 논점만 요약")

    assert out.startswith("[컨텍스트 절단 - 선언된 전략(미적용): 핵심 논점만 요약]")
    assert "이하 2000자 절단" in out
    assert "요약된 컨텍스트" not in out


def test_context_pruning_passthrough_below_limit():
    assert apply_context_pruning("짧은 컨텍스트", "전략") == "짧은 컨텍스트"


def test_estimate_cost_uses_static_input_assumption(engine):
    """[characterization 결함 #4] 고정 50K 입력 토큰 가정·출력 토큰 무시."""
    cost = engine.estimate_cost(["분석신학자"])  # THINKER → $0.15/1M
    assert cost == pytest.approx(50_000 / 1_000_000 * 0.15)
