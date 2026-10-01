# PIM-P for Codex

논문 PDF 한 편을 **한국어 논문 리뷰 세미나 PPTX와 발표자 노트**로 만드는 Codex 스킬입니다.
[TLAB-HGU/PIM-P](https://github.com/TLAB-HGU/PIM-P)를 기반으로 Codex의 로컬 실행 환경에 맞게 개발했습니다.

개발 버전: **0.1.0**. normal(연구자)·easy(비전공자) 모드를 지원합니다.
Codex가 논문을 읽고 분석·슬라이드 내용을 작성하며, 동봉 스크립트가 PDF 추출과 PPTX 제작·검사를 수행합니다.
별도 Claude 설치나 LLM API 키는 필요 없습니다.

## 빠른 시작

Python 3.10+, Node 20+를 준비하고 실행합니다.

```bash
git clone https://github.com/prestige-kim/PIM-P_codex.git
cd PIM-P_codex
python3 -m venv .venv
.venv/bin/python -m pip install -r skills/pimp/requirements.txt
npm ci --prefix skills/pimp --ignore-scripts
.venv/bin/python skills/pimp/scripts/doctor.py --strict
```

Windows는 `.venv\Scripts\python.exe`를 사용합니다.
이 저장소를 Codex 프로젝트로 열면 `.agents/skills/pimp`가 실제 스킬 폴더를 연결합니다.
심볼릭 링크를 지원하지 않는 환경에서는
`python scripts/install_skill.py --target-dir .agents/skills --replace`로 기존 링크 파일을 백업하고 복사할 수 있습니다.
스킬이 목록에 보이지 않으면 새 채팅을 열거나 Codex를 재시작합니다.

PDF를 첨부하거나 접근 가능한 파일 경로를 주고 요청하세요.

```text
$pimp normal
첨부한 논문을 30분 랩미팅 발표 자료로 만들어줘.
한국어 발표자 노트와 수치의 논문 출처를 포함해줘.
```

```text
$pimp easy
이 논문을 비전공자 대상 15분 발표, 총 12장으로 만들어줘.
수식은 직관을 먼저 설명하고 논문의 핵심 단계와 한계를 유지해줘.
```

```text
$pimp normal /path/to/paper.pdf
20분 발표용으로 만들어줘. 이전 작업의 실험 결과 슬라이드만 수정해줘.
```

`$pimp`는 Codex에 보내는 요청이며 터미널 명령이 아닙니다.
사용자가 지정한 발표 시간·총 장수·언어·템플릿을 우선합니다.
별도 요청이 없으면 30분·한국어·16:9를 사용합니다.

## 다른 프로젝트에서도 사용하기

공식 문서의 개인 스킬 경로로 설치하려면:

```bash
python3 scripts/install_skill.py --target-dir "$HOME/.agents/skills" --link
```

Codex 설정에 따라 `~/.codex/skills`를 사용하는 환경도 지원합니다.
설치기는 기본으로 `${CODEX_HOME}/skills` 또는 `~/.codex/skills`를 사용합니다.
`--target-dir`로 선택한 환경의 경로를 명시하면 됩니다.

- `--link`: 개발 폴더의 변경을 즉시 사용하는 심볼릭 링크. 저장소를 이동하면 링크도 갱신해야 합니다.
- 기본 복사 설치: 독립된 스킬 폴더를 만듭니다. node_modules는 복사하지 않으므로 설치된 폴더에서 npm ci를 실행합니다.
- `--dry-run`: 변경 없이 경로를 확인합니다.
- 기존 설치는 자동으로 덮어쓰지 않습니다. 명시한 `--replace`는 기존 폴더를 백업한 뒤 교체합니다.
- 어느 방식이든 원본 LICENSE와 UPSTREAM.md가 포함됩니다.

프로젝트에 복사하는 예:

```bash
python3 scripts/install_skill.py --target-dir /path/to/project/.agents/skills
npm ci --prefix /path/to/project/.agents/skills/pimp --ignore-scripts
```

개인/프로젝트 스킬 탐색과 `$` 호출은 [공식 스킬 문서](https://learn.chatgpt.com/docs/build-skills)를 참고하세요.

## 출력과 검증

작업별 폴더에 paper_brief.md, slide_plan.md, deck.json, assets/, deck.pptx,
deck_manifest.json, qa.json, preview/를 저장합니다.
슬라이드마다 노트와 근거를 연결하고, 표·차트는 편집 가능한 PowerPoint 객체로 만듭니다.
Figure·수식은 원문 의미를 보존하는 이미지입니다.

미리보기에는 LibreOffice와 Poppler가 필요합니다. Codex 앱의 번들 도구도 사용할 수 있습니다.
스캔 PDF는 Tesseract가 필요하며, 한글 OCR은 kor 언어팩을 확인해야 합니다.
사용 가능한 도구는 doctor가 보고합니다. 자세한 설정은 [실행 환경](skills/pimp/references/runtime.md)에 있습니다.

폰트는 macOS Apple SD Gothic Neo, Windows Malgun Gothic, Linux Noto Sans CJK KR가 기본입니다.
렌더러는 시스템 한글 폰트에 접근하는 독립 설정을 만들며 사용자 전역 폰트 설정을 바꾸지 않습니다.
다른 PC에서 PPTX를 열 때 폰트 대체로 줄바꿈이 달라질 수 있으므로 미리보기 PDF도 확인하세요.

정확도 검사는 **구조 검사·PNG 확인·원문 대조**를 함께 수행합니다.
자동 검사는 출처 선언과 파일 구조를 확인하며, 주장의 사실 여부를 자동으로 보장하지 않습니다.
OCR과 캡션/크롭 좌표는 검토용 후보입니다. 비평과 토론 질문은 발표자의 관점으로 다듬으세요.

## 개발과 테스트

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python scripts/validate_skill.py
.venv/bin/python -m unittest discover -s tests -v
node --test tests/test_build_deck.js
```

GitHub Actions에서도 같은 테스트를 실행합니다. 실제 LibreOffice 렌더와 논문 해석의 품질 검토는
로컬 통합 검증으로 별도 기록합니다.

- [문제 해결 방법론](docs/methodology.md)
- [검증 결과와 한계](docs/validation.md)
- [deck.json 형식](skills/pimp/references/deck-format.md)
- [변경 이력](CHANGELOG.md)

## 원본과 라이선스

원본 분석 규칙·세미나 흐름·easy 모드·디자인 라이브러리는 TLAB-HGU의 PIM-P에서 가져왔습니다.
정확한 기준 커밋과 변경 출처는 [UPSTREAM.md](UPSTREAM.md)에 기록합니다.
MIT 저작권 고지와 라이선스 전문을 보존했습니다. 논문·Figure·외부 폰트는 각 자료의 권리가 적용되며,
이 저장소의 MIT가 해당 자료까지 포괄하는 것은 아닙니다. 사용자의 논문·작업 결과·가상환경은 Git에서 제외합니다.
