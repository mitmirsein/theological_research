"""테스트 공용 픽스처 — FakeClient (google-genai Client 모킹).

QUALITY_HARDENING.md 제안 3의 골격. Phase 1에서는 '현행 동작 스냅샷'
(characterization) 테스트의 기반으로 사용하고, Phase 2 패치 시
해당 스냅샷 단언을 의도적으로 갱신한다.
"""

import os
import sys
from types import SimpleNamespace

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

PERSONA_FILE = os.path.join(PROJECT_ROOT, "personas_all.md")


class FakeResponse:
    """generate_content 응답 모킹 (.text + usage_metadata)."""

    def __init__(self, text: str):
        self.text = text
        self.usage_metadata = SimpleNamespace(
            prompt_token_count=10,
            candidates_token_count=20,
        )


class FakeModels:
    """client.models 모킹 — 스크립트된 응답 또는 실패 주입.

    script 항목이 Exception 인스턴스면 해당 호출에서 raise한다
    (재시도-후-성공 시나리오 구성용). script 소진 후에는 error가 있으면
    raise, 없으면 자동 응답을 돌려준다.
    """

    def __init__(self, script=None, error=None):
        self.calls = []
        self.script = list(script) if script else None
        self.error = error

    def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self.script:
            item = self.script.pop(0)
            if isinstance(item, Exception):
                raise item
            return FakeResponse(item)
        if self.error is not None:
            raise self.error
        return FakeResponse(f"FAKE_RESPONSE_{len(self.calls)}")


class FakeClient:
    """genai.Client 대체물. TheologyResearchEngine(manager, client)에 주입."""

    def __init__(self, script=None, error=None):
        self.models = FakeModels(script=script, error=error)


@pytest.fixture
def fake_client():
    return FakeClient()


@pytest.fixture(scope="session")
def persona_manager():
    """실제 personas_all.md를 파싱한 매니저 (자산 파일 자체를 회귀 대상으로 고정)."""
    from theology_orchestrator import PersonaManager

    return PersonaManager(PERSONA_FILE)
