"""PersonaManager 테스트 (Phase 2 결함 #3 패치 + Phase 3 제안 1 검증층 기준)."""

import pytest

from theology_orchestrator import PersonaManager, PersonaValidationError


def _make_manager(tmp_path, content: str) -> PersonaManager:
    f = tmp_path / "personas.md"
    f.write_text(content, encoding="utf-8")
    return PersonaManager(str(f))


def test_count_is_exactly_50(persona_manager):
    """결함 #3 패치: 문서 서문은 페르소나로 등록되지 않는다."""
    assert len(persona_manager.personas) == 50
    assert "Theological Research Personas (Optimized v2.1)" not in persona_manager.personas


def test_sections_without_metadata_are_excluded(tmp_path):
    """결함 #3 패치: Tier 메타데이터 블록이 없는 섹션(서문 등)은 제외된다."""
    manager = _make_manager(
        tmp_path,
        "# 문서 제목 (서문)\n\n이 문서는 페르소나 모음입니다.\n\n"
        "# 진짜 전문가 (Real Expert)\n- **Tier**: WORKER\n본문\n",
    )
    assert list(manager.personas) == ["진짜 전문가 (Real Expert)"]


def test_model_id_parsed_in_full(tmp_path):
    """결함 #3 패치: 모델명이 '-'/'.' 포함 전체로 파싱된다 (절단 금지)."""
    manager = _make_manager(
        tmp_path,
        "# 테스트 전문가 (Test Expert)\n"
        "- **Tier**: WORKER\n"
        "- **Model ID**: `gemini-3-flash-preview`\n"
        "- **Input Pruning**: 해당 없음\n\n"
        "본문 지시문.\n",
    )
    config = manager.get_persona("테스트 전문가 (Test Expert)")
    assert config["model_id"] == "gemini-3-flash-preview"


def test_tier_parsed_from_real_assets(persona_manager):
    assert persona_manager.get_persona("분석신학자 (Analytic Theologian)")["tier"] == "THINKER"
    assert persona_manager.get_persona("성경신학자 (Biblical Theologian)")["tier"] == "WORKER"


def test_no_deprecated_model_ids_in_assets(persona_manager):
    """결함 #4 패치: 페르소나 자산에 폐기 모델(gemini-2.x) 잔재가 없다."""
    for name, config in persona_manager.personas.items():
        model_id = config.get("model_id")
        if model_id:
            assert not model_id.startswith("gemini-2"), f"{name}: {model_id}"


def test_prefixed_persona_name_is_normalized(persona_manager):
    """결함 #3 패치: '페르소나: ' 프리픽스가 정규화되어 정확 일치가 동작한다."""
    exact = persona_manager.get_persona("편향 및 전승 감사 전문가 (Bias and Tradition Auditor)")
    assert exact is not None

    name, config = persona_manager.find_persona("편향 및 전승 감사 전문가")
    assert name == "편향 및 전승 감사 전문가 (Bias and Tradition Auditor)"
    assert config is not None


def test_pruning_none_when_not_applicable(tmp_path):
    manager = _make_manager(
        tmp_path,
        "# A 전문가\n- **Tier**: LITE\n- **Input Pruning**: 해당 없음\n본문\n"
        "# B 전문가\n- **Tier**: WORKER\n- **Input Pruning**: 요약본만 입력\n본문\n",
    )
    assert manager.get_persona("A 전문가")["pruning"] is None
    assert manager.get_persona("B 전문가")["pruning"] == "요약본만 입력"


def test_find_persona_returns_none_for_unknown(persona_manager):
    name, config = persona_manager.find_persona("존재하지않는전문가XYZ")
    assert name is None and config is None


# --- 제안 1: 계약 검증층 -------------------------------------------------------

def test_invalid_tier_raises_at_load(tmp_path):
    """제안 1: 허용 외 Tier는 LLM 호출 전에 로드 시점에 실패한다."""
    with pytest.raises(PersonaValidationError, match="허용되지 않는 Tier"):
        _make_manager(tmp_path, "# A 전문가\n- **Tier**: ROUTER\n본문\n")


def test_unknown_model_id_raises_at_load(tmp_path):
    """제안 1: 미등록 모델명(폐기 모델 포함)은 조용한 폴백 없이 즉시 실패한다."""
    with pytest.raises(PersonaValidationError, match="미등록 Model ID"):
        _make_manager(
            tmp_path,
            "# A 전문가\n- **Tier**: WORKER\n- **Model ID**: `gemini-2.0-flash`\n본문\n",
        )


def test_duplicate_persona_name_raises_at_load(tmp_path):
    with pytest.raises(PersonaValidationError, match="이름 중복"):
        _make_manager(
            tmp_path,
            "# A 전문가\n- **Tier**: WORKER\n본문\n"
            "# A 전문가\n- **Tier**: LITE\n본문2\n",
        )


def test_multiple_violations_reported_together(tmp_path):
    """제안 1: 위반을 하나씩이 아니라 일괄 수집해 보고한다."""
    with pytest.raises(PersonaValidationError, match="2건"):
        _make_manager(
            tmp_path,
            "# A 전문가\n- **Tier**: AUDITOR\n본문\n"
            "# B 전문가\n- **Tier**: WORKER\n- **Model ID**: `gpt-4`\n본문\n",
        )
