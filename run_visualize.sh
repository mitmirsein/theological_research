#!/bin/bash
# Theological Research Visualization
# research_outputs/*.md → Interactive HTML 변환
#
# Usage: ./run_visualize.sh {topic}
# Example: ./run_visualize.sh Schechina

set -e

TOPIC="${1:-}"

if [ -z "$TOPIC" ]; then
    echo "Usage: ./run_visualize.sh {topic}"
    echo "Example: ./run_visualize.sh Schechina"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 공유 venv 활성화 (.venv → ../../shared_venv 심볼릭 링크, SHARED_VENV.md 참조)
source .venv/bin/activate

# reports 폴더 생성 (visualize_session.py 기본 경로)
mkdir -p reports

echo "================================"
echo "Theological Research Visualization"
echo "Topic: $TOPIC"
echo "================================"

# 입력 파일 확인 — 오케스트레이터 산출 계약(제안 2 dossier):
#   research_outputs/{topic}/run_{run_id}/final.md (최신 run 자동 선택)
INPUT_FILE=$(ls -t "research_outputs/${TOPIC}"/run_*/final.md 2>/dev/null | head -1)
if [ -z "$INPUT_FILE" ]; then
    # 전환기 호환 1: 평면 명명 {topic}*_final.md
    INPUT_FILE=$(ls -t "research_outputs/${TOPIC}"*_final.md 2>/dev/null | head -1)
fi
if [ -z "$INPUT_FILE" ]; then
    # 전환기 호환 2: 구 명명 _research.md
    if [ -f "research_outputs/${TOPIC}_research.md" ]; then
        INPUT_FILE="research_outputs/${TOPIC}_research.md"
    else
        echo "Error: no input found for topic '${TOPIC}'"
        echo "  expected: research_outputs/${TOPIC}/run_*/final.md"
        exit 1
    fi
fi
echo "Input: $INPUT_FILE"

# reports 폴더로 복사 (visualize_session.py 기대 경로)
cp "$INPUT_FILE" "reports/${TOPIC}_final.md"

# 시각화 실행
python visualize_session.py --topic "$TOPIC" --mode both

# 결과물을 research_outputs로 이동
mv "reports/${TOPIC}_report.html" "research_outputs/${TOPIC}_report.html" 2>/dev/null || true
mv "reports/${TOPIC}_brief.html" "research_outputs/${TOPIC}_brief.html" 2>/dev/null || true

echo ""
echo "✅ 시각화 완료!"
echo ""
echo "Output:"
echo "  research_outputs/${TOPIC}_report.html"
echo "  research_outputs/${TOPIC}_brief.html"
echo ""
echo "To view:"
echo "  open research_outputs/${TOPIC}_report.html"
