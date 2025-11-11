# AI 신학 연구팀 자동화 시스템 (AI Theology Research Team Automation System)

여러 AI 신학 전문가 에이전트를 동시에 실행하여, 깊이 있는 연구 보고서를 자동으로 생성하는 파이썬 기반 워크플로우입니다.

## 1. 시스템 요구사항

- Python 3.9 이상
- `git` (선택 사항, 코드 관리용)

## 2. 초기 설정 (최초 1회만 실행)

### 가. 가상 환경 생성 및 활성화

이 시스템은 사용자 홈 디렉토리(`~` 또는 `/Users/msn`)에 `theology_research`라는 이름의 Python 가상 환경을 사용합니다.

만약 가상 환경이 없다면, 터미널을 열고 다음 명령어를 실행하여 생성합니다.

```bash
# 홈 디렉토리로 이동
cd ~

# 'theology_research' 가상 환경 생성
python3 -m venv theology_research
```

### 나. 필수 라이브러리 설치

터미널에서 `Theology_Research` 폴더로 이동한 후, 다음 명령어를 실행하여 필요한 모든 라이브
러리를 설치합니다.

```bash
# 1. 홈 디렉토리에 있는 가상 환경 활성화
source ~/theology_research/bin/activate

# 2. Theology_Research 폴더로 이동 (Obsidian 볼트 내)
# 예시: cd "/path/to/your/obsidian/vault/Theology_Research"
cd "/Users/msn/Library/Mobile Documents/iCloud~md~obsidian/Documents/MS_Brain/Theology_Research"

# 3. requirements.txt 파일을 사용하여 라이브러리 설치
pip install -r requirements.txt
```

### 다. API 키 설정

Obsidian 볼트의 루트 디렉토리에 있는 `.gemini/.env` 파일에 Gemini API 키가 저장되어 있어야 합니다. 파일 내용은 다음과 같은 형식이어야 합니다.

```
# .gemini/.env 파일 내용 예시
GOOGLE_API_KEY="AIzaSy...your...api...key..."
```

## 3. 연구 실행 방법

모든 설정이 완료된 후, 연구를 실행하는 방법은 간단합니다.

1.  **터미널을 엽니다.**

2.  **가상 환경을 활성화합니다.**
    ```bash
    source ~/theology_research/bin/activate
    ```

3.  **`Theology_Research` 폴더로 이동합니다.**
    ```bash
    cd "/Users/msn/Library/Mobile Documents/iCloud~md~obsidian/Documents/MS_Brain/Theology_Research"
    ```

4.  **오케스트레이터 스크립트를 실행합니다.**
    ```bash
    python3 orchestrator.py
    ```

스크립트가 실행되면 `research_outputs` 폴더 안에 타임스탬프 형식의 새 폴더가 생성되며, 그 안에 각 전문가의 개별 보고서와 최종 종합 보고서가 저장됩니다.

## 4. 커스터마이징

### 가. 연구 주제 변경

`orchestrator.py` 파일의 맨 아래 `if __name__ == "__main__":` 블록에 있는 `RESEARCH_TOPIC` 변수의 값을 원하는 주제로 변경하세요.

```python
# orchestrator.py 파일 하단
if __name__ == "__main__":
    # 예시: 연구 주제를 '부활'로 변경
    RESEARCH_TOPIC = "성경에서 '부활(Resurrection)'의 개념"
    
    asyncio.run(run_parallel_research(RESEARCH_TOPIC))
```

### 나. 특정 전문가만 선택하여 실행

`run_parallel_research` 함수에 `selected_specialists` 리스트를 전달하여 원하는 전문가만 실행할 수 있습니다. 파일 이름(확장자 제외)을 리스트에 추가하면 됩니다.

```python
# orchestrator.py 파일 하단
if __name__ == "__main__":
    RESEARCH_TOPIC = "성경에서 '언약(Covenant)'의 개념"
    
    # 구약학자와 신약학자, 교부학 전문가만 실행
    asyncio.run(run_parallel_research(
        RESEARCH_TOPIC, 
        selected_specialists=["ot_scholar", "nt_scholar", "patristics_specialist"]
    ))
```

### 다. 새로운 전문가 추가/수정

-   **추가**: `personas` 폴더에 새로운 전문가의 역할과 지침을 담은 `.md` 파일을 추가하기만 하면 됩니다. 파일 이름이 해당 전문가의 ID가 됩니다.
-   **수정**: `personas` 폴더에 있는 기존 전문가의 `.md` 파일을 수정하면 다음 실행부터 변경된 지침이 적용됩니다.
