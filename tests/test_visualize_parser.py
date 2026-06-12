"""visualize_session.py 파서 테스트 (Phase 2 — 결함 #8 패치 후 기준)."""

import json

import pytest

import visualize_session as vz


# --- parse_markdown_sections --------------------------------------------------

def test_basic_h2_sections():
    md = (
        "# 문서 제목\n\n서문 텍스트입니다.\n\n"
        "## 서론\n\n서론 내용입니다.\n\n"
        "## 본론\n\n본론 내용입니다.\n"
    )
    sections, abstract = vz.parse_markdown_sections(md)

    assert [s.title for s in sections] == ["서론", "본론"]
    assert "서론 내용입니다." in sections[0].content
    assert "서문 텍스트입니다." in abstract  # 서문 → abstract 폴백


def test_subsection_before_first_h2_is_safe():
    """결함 #8 패치: '###'가 첫 '##'보다 먼저 나와도 크래시하지 않는다."""
    md = "### 하위 제목이 먼저\n본문\n\n## 첫 섹션\n내용\n"
    sections, _ = vz.parse_markdown_sections(md)

    assert [s.title for s in sections] == ["첫 섹션"]


def test_meta_section_filtering_preserves_neighbors():
    """결함 #8-4 패치: 메타 섹션은 제외하되 직전·직후 본문 섹션은 보존된다."""
    # 중간 메타
    md_mid = (
        "## 서론\n\n서론 내용 A\n\n"
        "## 참고문헌\n\n* Smith, *A Book*. 2020.\n\n"
        "## 결론\n\n결론 내용 B\n"
    )
    sections, _ = vz.parse_markdown_sections(md_mid)
    assert [s.title for s in sections] == ["서론", "결론"]

    # 말미 메타 (실전에서 가장 흔한 형태)
    md_tail = (
        "## 서론\n\n서론 내용 A\n\n"
        "## 본론\n\n본론 내용\n\n"
        "## 참고문헌\n\n* Smith, *A Book*. 2020.\n"
    )
    sections, _ = vz.parse_markdown_sections(md_tail)
    assert [s.title for s in sections] == ["서론", "본론"]


def test_abstract_section_routed_to_abstract():
    """결함 #8 패치: Abstract/초록 섹션이 본문이 아닌 abstract로 라우팅된다."""
    md = (
        "## Abstract\n\n이 연구는 셰키나 개념을 다룬다.\n\n"
        "## 서론\n\n서론 내용.\n"
    )
    sections, abstract = vz.parse_markdown_sections(md)

    assert [s.title for s in sections] == ["서론"]
    assert "셰키나 개념" in abstract


def test_meta_subsection_excluded_within_section():
    """결함 #8 패치: 섹션 내부의 '### 참고문헌' 하위 블록만 제외된다."""
    md = (
        "## 본론\n\n본론 내용입니다.\n\n"
        "### 참고문헌\n\n* Smith, *A Book*. 2020.\n\n"
        "### 소결\n\n소결 내용입니다.\n"
    )
    sections, _ = vz.parse_markdown_sections(md)

    assert [s.title for s in sections] == ["본론"]
    assert "본론 내용입니다." in sections[0].content
    assert "Smith" not in sections[0].content
    assert "소결 내용입니다." in sections[0].content


def test_h3_only_document_promotes_headings():
    """형식 갭 해소: 내용 H2가 없고 본문이 ###로만 구조화된 문서(오케스트레이터
    산출물의 전형)는 헤딩을 한 단계 승격해 섹션으로 파싱한다."""
    md = (
        "# 연구 주제: 칭의\n\n"
        "## 연구 메타데이터\n- 생성일: 2026-06-11\n\n---\n\n"
        "### 1. 서론\n\n서론 내용입니다.\n\n"
        "### 2. 본론\n\n본론 내용입니다.\n\n"
        "#### 2.1 세부\n\n세부 내용입니다.\n\n"
        "### 3. 결론\n\n결론 내용입니다.\n"
    )
    sections, _ = vz.parse_markdown_sections(md)

    assert [s.title for s in sections] == ["1. 서론", "2. 본론", "3. 결론"]
    assert "세부 내용입니다." in sections[1].content  # #### → ### 하위 절로 병합
    # 메타데이터 블록은 본문 섹션에서 제외된다
    assert all("메타데이터" not in s.title for s in sections)


def test_single_content_h2_with_subsections_not_promoted():
    """내용 있는 H2가 하나라도 있으면 ###는 하위 절로 유지된다 (승격 금지)."""
    md = "## 본론\n\n본문.\n\n### 소절 A\n\nA 내용.\n\n### 소절 B\n\nB 내용.\n"
    sections, _ = vz.parse_markdown_sections(md)

    assert [s.title for s in sections] == ["본론"]
    assert "A 내용." in sections[0].content


def test_code_block_unwrapping():
    inner = "## 섹션 하나\n\n코드 블록 안의 본문입니다.\n"
    md = f"전처리 대상\n\n```markdown\n{inner}```\n"
    sections, _ = vz.parse_markdown_sections(md)

    assert [s.title for s in sections] == ["섹션 하나"]


def test_extract_extras_produces_essence_and_keywords():
    md = (
        "## 셰키나 분석\n\n"
        "셰키나(Schechina)는 하나님의 임재를 가리키는 용어이다. "
        "이 개념은 Targum 문헌에서 발전했다.\n"
    )
    sections, _ = vz.parse_markdown_sections(md, extract_extras=True)

    assert len(sections) == 1
    assert sections[0].essence  # 비어 있지 않음
    assert "Schechina" in sections[0].keywords


# --- 각주 추출 3원 폴백 --------------------------------------------------------

def test_extract_footnotes_from_markdown_definitions():
    md = "본문[^1] 그리고[^2]\n\n[^1]: Smith, *First Book*, 2020.\n[^2]: Lee, *Second Book*, 2021.\n"
    fns = vz.extract_footnotes_from_markdown(md)

    assert [f.id for f in fns] == [1, 2]
    assert "Smith" in fns[0].citation


def test_extract_bibliography_from_markdown():
    md = (
        "## 본론\n\n내용.\n\n"
        "### 참고문헌\n"
        "* Smith, John. *A Long Book of Things*. Oxford, 2020.\n"
        "* Lee, Kim. *Another Scholarly Volume*. Seoul, 2021.\n"
    )
    fns = vz.extract_bibliography_from_markdown(md)

    assert len(fns) == 2
    assert "Oxford" in fns[0].citation


def test_extract_footnotes_from_json(tmp_path):
    p = tmp_path / "topic_footnotes.json"
    p.write_text(
        json.dumps({"bibliography": ["Smith, *A Book*, 2020.", "Lee, *B Book*, 2021."]}),
        encoding="utf-8",
    )
    fns = vz.extract_footnotes_from_json(p)

    assert [f.id for f in fns] == [1, 2]


def test_extract_footnotes_from_json_missing_file(tmp_path):
    assert vz.extract_footnotes_from_json(tmp_path / "absent.json") == []


# --- 유틸 ----------------------------------------------------------------------

def test_md_to_inline_html_strips_paragraph():
    assert vz.md_to_inline_html("**굵게**") == "<strong>굵게</strong>"


def test_main_exits_nonzero_when_input_missing(monkeypatch):
    """제안 1: 입력 부재 시 정상 종료(return)가 아니라 exit 1 — set -e 셸이 감지 가능."""
    import sys

    monkeypatch.setattr(sys, "argv", ["visualize_session.py", "--topic", "존재하지않는주제xyz"])
    with pytest.raises(SystemExit) as exc:
        vz.main()
    assert exc.value.code == 1
