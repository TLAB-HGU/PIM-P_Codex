# 설치 안내

PIM-P는 Codex가 논문을 읽고 내용을 작성하는 스킬이다. Python 스크립트와 Node 패키지는
PDF 처리·수식·PPTX 제작·검사를 담당한다. Claude 설치나 별도 LLM API 키는 필요 없다.

## 폴더 복사

저장소의 `skills/pimp/`를 개인 `~/.agents/skills/pimp/` 또는 프로젝트 `.agents/skills/pimp/`로 복사한다.
새로 받은 저장소의 소스 폴더를 사용한다. 이미 실행한 폴더의 `.venv`, `node_modules`, `.cache`,
`.pimp-runtime.json`은 다른 위치로 복사하지 않는다. [공식 스킬 문서](https://learn.chatgpt.com/docs/build-skills)는
개인·프로젝트 설치 경로와 심볼릭 링크 탐색을 설명한다.

Python 3.10+, Node.js 20+와 npm이 필요하다. 아래 명령은 복사한 스킬 안에 `.venv`와
`node_modules`를 설치하고 실제 의존성을 검사한다. 최초 준비에는 패키지 다운로드를 위한 인터넷 연결이 필요하다.

macOS/Linux 개인 설치:

```bash
python3 ~/.agents/skills/pimp/scripts/setup_runtime.py
```

Windows PowerShell 개인 설치:

```powershell
py -3 "$env:USERPROFILE\.agents\skills\pimp\scripts\setup_runtime.py"
```

프로젝트 설치에서는 작업 폴더에서 `python3 .agents/skills/pimp/scripts/setup_runtime.py`
(Windows는 `py -3 .agents/skills/pimp/scripts/setup_runtime.py`)를 사용한다.

출력의 `ready`는 PPTX 제작에 필요한 Python·Node 환경이 준비됐다는 뜻이다.
가상환경은 최종 설치 경로에서 생성한다. 시스템 Python 패키지나 운영체제 설정은 변경하지 않는다.
설치 결과 `.pimp-runtime.json`에 실행 경로와 의존성 파일의 상태가 저장된다.

## 저장소에서 한 번에 설치

폴더 복사와 실행 환경 준비를 한 명령으로 처리할 수도 있다.

```bash
git clone https://github.com/TLAB-HGU/PIM-P_Codex.git
cd PIM-P_Codex
python3 skills/pimp/scripts/install_skill.py --target-dir ~/.agents/skills --setup
```

Windows PowerShell:

```powershell
py -3 skills/pimp/scripts/install_skill.py --target-dir "$env:USERPROFILE\.agents\skills" --setup
```

프로젝트에 설치하려면 `--target-dir /path/to/project/.agents/skills`로 지정한다.
지정한 폴더 아래에 `pimp`를 만든다. 기존 설치는 명시한 `--replace` 없이 덮어쓰지 않는다.
`--replace --setup`은 기존 설치를 스킬 탐색 폴더 밖의 `.pimp-skill-backups`에 보관하며,
새 실행 환경 준비가 실패하면 기존 설치를 원래 위치로 복구한다. 백업 경로는 명령 출력에서 확인한다.
링크 백업은 링크 대상을 복제한 스냅샷이 아니다.

`--dry-run`은 설치 계획과 사전 조건을 확인하고 파일을 변경하지 않는다.
`--node`와 `--npm`으로 실행 파일을 지정할 수 있다. setup_runtime.py에도 같은 옵션이 있다.

## 기존 설치와 갱신

기존 Codex 환경의 `~/.codex/skills/pimp`도 사용할 수 있다. 설치기 기본 경로는
`CODEX_HOME/skills` 또는 `~/.codex/skills`이며 위 예시는 최신 공식 경로를 명시한다.
같은 스킬을 개인 경로 두 곳에 중복 설치하지 않는다. 현재 사용하는 폴더를 유지하며 준비 명령을 실행해도 된다.

```bash
python3 ~/.codex/skills/pimp/scripts/setup_runtime.py
```

복사 설치 갱신은 저장소를 `git pull`한 뒤 처음 설치한 `--target-dir`에
`skills/pimp/scripts/install_skill.py --replace --setup`을 실행한다. 직접 소스를 복사했다면 생성된 실행 환경을
함께 이동하지 말고 소스만 갱신한 뒤 setup_runtime.py를 다시 실행한다.

설치 폴더를 이동했다면 새 위치에서 다시 준비한다. 다른 위치의 가상환경이나 성공 기록은 사용하지 않는다.
실행 환경 검사만 하려면 다음 명령을 사용한다. 네트워크 연결이나 패키지 설치 없이 현재 상태를 확인한다.

```bash
python3 ~/.agents/skills/pimp/scripts/setup_runtime.py --check
```

## 미리보기와 OCR

PPTX 생성과 미리보기의 준비 상태는 별개다. 미리보기에는 LibreOffice와 한글 폰트,
PNG 생성에는 Poppler 또는 PyMuPDF가 필요하다. 스캔 논문에는 Tesseract와 논문 언어의 OCR 언어팩이 필요하다.
운영체제 도구는 준비 명령이 자동으로 설치하지 않으며 실행 파일의 탐색 결과를 보고한다.
한글 폰트의 실제 표시 여부는 발표 자료를 렌더링해 확인한다.
Codex 앱의 번들 도구도 사용할 수 있다. 자세한 설정은 [실행 환경](../skills/pimp/references/runtime.md)에 있다.

## 개발

자동 테스트와 개발 의존성은 `dev` 브랜치에 있다. 아래 개발 명령은 `git switch dev` 후 실행한다.
배포용 `main`의 구조와 검증 도구의 고정 커밋 사용법은 [개발·배포 구조](development.md)를 참고한다.

개발 폴더를 스킬로 연결하려면 `skills/pimp/scripts/install_skill.py --link --target-dir ...`를 사용하고
`python3 skills/pimp/scripts/setup_runtime.py`로 원본 폴더의 실행 환경을 준비한다.
링크 설치에는 `--setup`을 결합하지 않는다. 원본 폴더의 실행 환경 변경은 링크 교체만으로 되돌릴 수 없기 때문이다.

테스트용 의존성은 저장소의 별도 개발 가상환경에 설치한다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
npm ci --prefix skills/pimp --ignore-scripts
.venv/bin/python scripts/validate_skill.py
.venv/bin/python -m unittest discover -s tests -v
node --test tests/test_build_deck.js
```

Windows는 `.venv/bin/python`을 `.venv\Scripts\python.exe`로 바꾼다.
[deck.json 형식](../skills/pimp/references/deck-format.md), [검증 결과](validation.md),
[이식 방법론](methodology.md)을 함께 참고한다. 사용자 논문과 결과·의존성·실행 경로 기록은 Git에 포함하지 않는다.
