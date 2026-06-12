"""run_research 4-Phase 파이프라인 e2e 골든 테스트 (Phase 3 — 제안 2 dossier 기준).

init_genai를 FakeClient로 치환해 전체 워크플로우를 무비용 실행하고,
감사 dossier(run 디렉토리)의 파일 구성과 execution_log.json 스키마를
골든으로 고정한다.
"""

import json
import re
from pathlib import Path

import pytest

import theology_orchestrator as orch
from conftest import FakeClient

DOSSIER_COMPLETE = [
    "execution_log.json",
    "final.md",
    "phase1_draft.md",
    "phase2_analysis.md",
    "phase3_audit.md",
]


def _single_run_dir(base: Path, safe_topic: str) -> Path:
    run_dirs = sorted((base / safe_topic).glob("run_*"))
    assert len(run_dirs) == 1
    return run_dirs[0]


def test_run_research_dossier_golden(monkeypatch, tmp_path):
    fake = FakeClient(script=["P1 초안", "P2 분석", "P3 감사", "P4 최종 논문 본문"])
    monkeypatch.setattr(orch, "init_genai", lambda: fake)

    out = orch.run_research("테스트 주제", rag_context="원자료", output_dir=str(tmp_path))

    # 산출 경로 계약: {output}/{safe_topic}/run_{run_id}/final.md
    assert out is not None
    out_path = Path(out)
    assert out_path.name == "final.md"
    run_dir = out_path.parent
    assert re.fullmatch(r"run_\d{8}-\d{6}(-\d+)?", run_dir.name)
    assert run_dir.parent.name == "테스트_주제"

    # 골든 1: dossier 파일 구성
    assert sorted(p.name for p in run_dir.iterdir()) == DOSSIER_COMPLETE
    assert (run_dir / "phase1_draft.md").read_text(encoding="utf-8") == "P1 초안"
    assert (run_dir / "phase3_audit.md").read_text(encoding="utf-8") == "P3 감사"

    # 골든 2: final.md 본문·메타데이터
    content = out_path.read_text(encoding="utf-8")
    assert "# 연구 주제: 테스트 주제" in content
    assert "P4 최종 논문 본문" in content
    assert "워크플로우: 4-Phase" in content
    assert re.search(r"- 생성일: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", content)

    # 골든 3: 4-Phase 체인과 모델 차등
    assert len(fake.models.calls) == 4
    assert "원자료" in fake.models.calls[0]["contents"]      # Phase 1 ← RAG
    assert "P1 초안" in fake.models.calls[1]["contents"]      # Phase 2 ← Phase 1
    assert "P2 분석" in fake.models.calls[2]["contents"]      # Phase 3 ← Phase 1+2
    assert "P3 감사" in fake.models.calls[3]["contents"]      # Phase 4 ← 전체
    assert fake.models.calls[3]["model"] == "gemini-3-pro-preview"  # COMMANDER 차등
    assert "'## '(H2) 헤딩" in fake.models.calls[3]["contents"]      # H2 구조 강제 (형식 갭)

    # 골든 4: execution_log.json 스키마 + usage_metadata 실측
    log = json.loads((run_dir / "execution_log.json").read_text(encoding="utf-8"))
    assert log["status"] == "completed"
    assert log["topic"] == "테스트 주제"
    assert log["model_registry"] == orch.MODEL_REGISTRY
    assert len(log["calls"]) == 4

    first = log["calls"][0]
    assert first["persona"] == "성경신학자 (Biblical Theologian)"
    assert first["status"] == "success"
    assert first["tokens_in"] == 10 and first["tokens_out"] == 20   # FakeResponse 고정값
    assert first["cost_input_usd"] == pytest.approx(10 / 1_000_000 * 0.15)
    assert all(c["attempts"] == 1 for c in log["calls"])
    assert all("elapsed_s" in c for c in log["calls"])


def test_run_research_aborts_on_failure_without_fake_paper(monkeypatch, tmp_path):
    """결함 #6: Phase 1 실패(비일시 오류) 시 즉시 중단 — dossier에는 로그만 남는다."""
    fake = FakeClient(error=RuntimeError("invalid API key"))
    monkeypatch.setattr(orch, "init_genai", lambda: fake)

    out = orch.run_research("실패 주제", output_dir=str(tmp_path))

    assert out is None
    assert len(fake.models.calls) == 1          # 비일시 오류 → 재시도 없음

    run_dir = _single_run_dir(tmp_path, "실패_주제")
    assert sorted(p.name for p in run_dir.iterdir()) == ["execution_log.json"]

    log = json.loads((run_dir / "execution_log.json").read_text(encoding="utf-8"))
    assert log["status"] == "aborted"
    assert log["calls"][0]["status"] == "error"
    assert "invalid API key" in log["calls"][0]["error"]


def test_run_research_preserves_partials_on_midway_failure(monkeypatch, tmp_path):
    """결함 #6 + 제안 2: 중도 실패 시 완료 Phase 산출물이 dossier에 보존된다."""
    fake = FakeClient(script=["P1 초안", "P2 분석"], error=RuntimeError("boom"))
    monkeypatch.setattr(orch, "init_genai", lambda: fake)

    out = orch.run_research("중도 실패", output_dir=str(tmp_path))

    assert out is None
    run_dir = _single_run_dir(tmp_path, "중도_실패")
    assert sorted(p.name for p in run_dir.iterdir()) == [
        "execution_log.json", "phase1_draft.md", "phase2_analysis.md",
    ]
    assert (run_dir / "phase1_draft.md").read_text(encoding="utf-8") == "P1 초안"

    log = json.loads((run_dir / "execution_log.json").read_text(encoding="utf-8"))
    assert log["status"] == "aborted"
    assert [c["status"] for c in log["calls"]] == ["success", "success", "error"]


def test_run_research_reruns_do_not_overwrite(monkeypatch, tmp_path):
    """결함 #7: 동일 주제 재실행은 별도 run 디렉토리로 분리 보존된다."""
    fake1 = FakeClient(script=["a", "b", "c", "첫 번째 결과"])
    monkeypatch.setattr(orch, "init_genai", lambda: fake1)
    out1 = orch.run_research("같은 주제", output_dir=str(tmp_path))

    fake2 = FakeClient(script=["a", "b", "c", "두 번째 결과"])
    monkeypatch.setattr(orch, "init_genai", lambda: fake2)
    out2 = orch.run_research("같은 주제", output_dir=str(tmp_path))

    assert out1 != out2
    assert len(list((tmp_path / "같은_주제").glob("run_*"))) == 2
    assert "첫 번째 결과" in Path(out1).read_text(encoding="utf-8")
    assert "두 번째 결과" in Path(out2).read_text(encoding="utf-8")
