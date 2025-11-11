#!/usr/bin/env python3
"""
Parallel AI Research Team Orchestrator for Theological Research
병렬 AI 연구팀 오케스트레이터 (신학 연구용)

Uses Gemini Python SDK to simulate multiple specialists working simultaneously
"""

import asyncio
import os
from pathlib import Path
from datetime import datetime
import json
import google.generativeai as genai

# --- Configuration -------------------------------------------------------
# IMPORTANT: Replace with your actual GOOGLE_API_KEY
# This is directly embedded due to environment variable loading issues in the execution environment.
# For production, consider more secure methods like a dedicated secrets manager.
from dotenv import load_dotenv

# Load environment variables from .gemini/.env
# Assuming .gemini/.env is in the project root, relative to the current working directory
load_dotenv(dotenv_path=Path(__file__).parents[2] / ".gemini" / ".env")

# Configure Gemini API
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Model to use for specialist and synthesis tasks
GEMINI_MODEL = "gemini-2.5-pro"

# Base directory for personas and outputs (relative to this script)
BASE_DIR = Path(__file__).parent
PERSONAS_DIR = BASE_DIR / "personas"
OUTPUT_DIR = BASE_DIR / "research_outputs"

# --- Helper Functions ----------------------------------------------------
def setup_directories():
    """Create output directories if they don't exist."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = OUTPUT_DIR / timestamp
    session_dir.mkdir(exist_ok=True)
    return session_dir

def load_specialist_persona(specialist_id: str) -> dict:
    """Load specialist persona from a .md file."""
    file_path = PERSONAS_DIR / f"{specialist_id}.md"
    if not file_path.exists():
        raise FileNotFoundError(f"Persona file not found: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse name and system_prompt from the markdown content
    # Assuming the first H1 is the name, and the rest is the prompt
    lines = content.split('\n')
    name = "Unknown Specialist"
    system_prompt_lines = []
    
    if lines and lines[0].startswith('# '):
        name = lines[0][2:].strip()
        system_prompt_lines = lines[1:]
    else:
        system_prompt_lines = lines # If no H1, treat all as prompt

    system_prompt = '\n'.join(system_prompt_lines).strip()

    return {"name": name, "system_prompt": system_prompt}

async def call_gemini_specialist(specialist_id: str, research_topic: str, 
                                  session_dir: Path) -> dict:
    """Call Gemini SDK for a specific specialist asynchronously."""
    try:
        config = load_specialist_persona(specialist_id)
    except FileNotFoundError as e:
        print(f"❌ {specialist_id} 오류: {e}")
        return {"specialist_id": specialist_id, "name": specialist_id, "error": str(e), "content": "", "success": False}

    print(f"🔄 {config['name']} 작업 시작...")
    
    full_prompt = f"{config['system_prompt']}

---

RESEARCH TOPIC: {research_topic}

위 지침에 따라 상세한 분석을 제공해주세요."
    
    output_file = session_dir / f"{specialist_id}_report.md"

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = await model.generate_content_async(full_prompt)
        result = response.text
        print(f"✅ {config['name']} 완료!")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# {config['name']} Report\n\n")
            f.write(f"**Research Topic:** {research_topic}\n\n")
            f.write(f"**Generated:** {datetime.now().isoformat()}\n\n")
            f.write("---\n\n")
            f.write(result)
        
        return {
            "specialist_id": specialist_id,
            "name": config['name'],
            "output_file": str(output_file),
            "content": result,
            "success": True
        }
        
    except Exception as e:
        print(f"❌ {specialist_id} 오류: {str(e)}")
        return {
            "specialist_id": specialist_id,
            "name": config['name'],
            "error": str(e),
            "content": f"오류 발생: {str(e)}",
            "success": False
        }

async def synthesize_reports(reports: list, research_topic: str, 
                             session_dir: Path) -> str:
    """Synthesize all specialist reports into a final comprehensive document."""
    print("\n📊 보고서 종합 중...")
    
    all_reports = ""
    for report in reports:
        if report['success']:
            all_reports += f"\n\n{'='*80}\n"
            all_reports += f"REPORT FROM: {report['name']}\n"
            all_reports += f"{ '='*80}\n\n"
            all_reports += report['content']
    
    synthesis_prompt = f"""You are an academic editor tasked with synthesizing 
multiple specialist reports into a single, coherent comprehensive research paper.

RESEARCH TOPIC: {research_topic}

Below are the individual specialist reports. Please:
1. Synthesize all insights into a unified narrative
2. Identify common themes and connections across disciplines
3. Resolve any apparent contradictions or tensions
4. Organize the content logically with clear sections
5. Maintain academic rigor and proper attribution
6. Aim for approximately 3000-4000 tokens

SPECIALIST REPORTS:
{all_reports}

Please provide the comprehensive synthesized research paper."""
    
    final_path = session_dir / "FINAL_COMPREHENSIVE_REPORT.md"

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = await model.generate_content_async(synthesis_prompt)
        final_report_content = response.text
        
        with open(final_path, 'w', encoding='utf-8') as f:
            f.write(f"# Comprehensive Research Report\n\n")
            f.write(f"**Topic:** {research_topic}\n\n")
            f.write(f"**Generated:** {datetime.now().isoformat()}\n\n")
            f.write(f"**Contributors:** {
                ', '.join([r['name'] for r in reports if r['success']])
            }\n\n")
            f.write("---\n\n")
            f.write(final_report_content)
        
        print(f"✅ 최종 보고서 저장됨: {final_path}")
        return str(final_path)
        
    except Exception as e:
        print(f"❌ 종합 오류: {str(e)}")
        return f"종합 중 오류 발생: {str(e)}"

async def run_parallel_research(research_topic: str, 
                                selected_specialists: list = None):
    """Main orchestrator function - runs all specialists in parallel."""
    print("="*80)
    print("🎓 병렬 AI 연구팀 오케스트레이터")
    print("="*80)
    print(f"\n📋 연구 주제: {research_topic}\n")
    
    session_dir = setup_directories()
    
    # Load all available specialists from the personas directory
    available_specialists = {}
    for persona_file in PERSONAS_DIR.glob("*.md"):
        specialist_id = persona_file.stem
        try:
            available_specialists[specialist_id] = load_specialist_persona(specialist_id)
        except Exception as e:
            print(f"경고: {specialist_id} 페르소나 로드 실패 - {e}")

    if not available_specialists:
        print("오류: 'personas' 디렉토리에서 전문가 페르소나 파일을 찾을 수 없습니다.")
        return

    # Select specialists to run
    if selected_specialists is None:
        selected_specialists = list(available_specialists.keys())
    else:
        # Filter selected_specialists to only include those actually available
        selected_specialists = [s for s in selected_specialists if s in available_specialists]
        if not selected_specialists:
            print("오류: 선택된 전문가 중 유효한 페르소나 파일을 찾을 수 없습니다.")
            return

    print(f"👥 {len(selected_specialists)}명의 전문가 배치:")
    for spec_id in selected_specialists:
        print(f"   - {available_specialists[spec_id]['name']}")
    print()
    
    print("🚀 병렬 연구 작업 실행 중...\n")
    start_time = datetime.now()
    
    tasks = [
        call_gemini_specialist(spec_id, research_topic, session_dir)
        for spec_id in selected_specialists
    ]
    
    reports = await asyncio.gather(*tasks)
    
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n⏱️  모든 전문가 작업 완료 ({elapsed:.1f}초)")
    
    final_report_path = await synthesize_reports(reports, research_topic, session_dir)
    
    metadata = {
        "research_topic": research_topic,
        "timestamp": session_dir.name,
        "specialists_used": selected_specialists,
        "execution_time_seconds": elapsed,
        "session_directory": str(session_dir),
        "final_report": final_report_path,
        "individual_reports": [
            {
                "specialist": r['name'],
                "file": r.get('output_file'),
                "success": r['success']
            }
            for r in reports
        ]
    }
    
    metadata_path = session_dir / "metadata.json"
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n📁 모든 결과물 저장됨: {session_dir}")
    print(f"📄 최종 보고서: {final_report_path}")
    print(f"📊 메타데이터: {metadata_path}")
    print("\n✅ 연구 파이프라인 성공적으로 완료!")

# --- Entry Point ---------------------------------------------------------
if __name__ == "__main__":
    # Example usage
    RESEARCH_TOPIC = "성경에서 '언약(Covenant)'의 개념"
    
    # Run with all specialists found in the personas directory
    asyncio.run(run_parallel_research(RESEARCH_TOPIC))
    
    # Or run with selected specialists only:
    # asyncio.run(run_parallel_research(
    #     RESEARCH_TOPIC, 
    #     selected_specialists=["ot_scholar", "nt_scholar"]
    # ))