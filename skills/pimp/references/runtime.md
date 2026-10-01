# 실행 환경

Python 3.10 이상, Node 20 이상을 사용한다. 별도 LLM API 키는 필요 없다.
Codex가 논문을 분석하고 JSON을 작성하며 스크립트는 추출·이미지 처리·PPTX 제작을 수행한다.

## 설치와 선택할 실행 파일

`skills/pimp/` 폴더를 개인 또는 프로젝트 스킬 폴더로 복사한 뒤, 그 폴더에서 한 번 준비한다.

```bash
python3 scripts/setup_runtime.py
```

어느 작업 폴더에서든 복사한 스킬의 `scripts/setup_runtime.py` 절대 경로로 실행할 수 있다.
Windows는 `py -3 scripts/setup_runtime.py`를 사용한다. Python 3.10+, Node 20+와 npm이 먼저 필요하다.
준비 명령은 스킬의 최종 경로에 `.venv`와 `node_modules`를 설치하고 doctor로 필수 항목을 검사한다.
시스템 패키지·OS 도구를 설치하지 않는다. 패키지 캐시는 스킬의 `.cache` 안에 둔다.
requirements는 Python 지원 범위이고 Node는 package-lock.json으로 고정된다.

실행 결과 `.pimp-runtime.json`에는 `python`, `node`, `skill_root`, `digest`, `doctor`가 기록된다.
`PYTHON`은 `SKILL_DIR/.venv/bin/python`(Windows는 `.venv/Scripts/python.exe`), `NODE`는 기록된 Node를 우선한다.
스킬 경로를 이동하거나 다른 환경의 실행 기록을 복사했다면 그것을 사용하지 않는다.
소스만 새 위치로 복사하고 실행 환경을 다시 준비한다.
다른 위치에서 가져온 `.venv`는 이동·백업 후 새로 생성한다. 생성된 환경과 기록은 Git에 포함하지 않는다.

```bash
python3 scripts/setup_runtime.py --check
```

`--check`는 패키지 설치나 네트워크 없이 현재 경로·의존성 파일 상태·doctor 결과를 확인한다.
requirements나 lockfile이 달라졌다면 setup_runtime.py를 다시 실행한다.
`--node`, `--npm`으로 다른 실행 파일을 지정할 수 있다. `--json`은 구조화된 결과,
`--timeout`은 각 설치 단계의 제한 시간이다. 준비 실패를 성공으로 표시하지 않는다.

Codex 앱 번들 실행 파일은 필요한 경우 `load_workspace_dependencies`가 반환한 경로를 사용한다.
반환값으로 PIMP_NODE·PIMP_SOFFICE·PIMP_PDFTOPPM을 설정한다. npm을 제공하지 않는 번들 Node는
준비 명령에 지정할 npm이 별도로 필요하다. 개인 PC 경로를 소스 코드에 저장하지 않는다.
이미 프로젝트에서 의존성을 관리한다면 그 환경을 사용할 수 있고 doctor.py --strict로 확인한다.
개발 링크의 저장소 `.venv`도 지원하지만 스킬 안에 준비된 가상환경이 우선이다.

| 환경변수 | 목적 |
|---|---|
| PIMP_NODE | Node 실행 파일 |
| PIMP_NPM | npm 실행 파일 또는 npm-cli.js |
| PIMP_SOFFICE | LibreOffice/soffice 실행 파일 |
| PIMP_PDFTOPPM | Poppler pdftoppm 실행 파일 |
| PIMP_TESSERACT | Tesseract 실행 파일 |
| PIMP_FONT | 슬라이드와 렌더링의 기본 폰트 이름 |
| PIMP_RUNTIME_DIR | 번들 dependencies 루트, render_slides에서 선택적으로 탐색 |
| NODE_PATH | 환경에 이미 설치된 Node 패키지 경로를 사용해야 할 경우 |

LibreOffice와 한글 폰트는 미리보기에 필요하며, PNG는 Poppler 또는 PyMuPDF로 생성한다. Tesseract는 스캔 페이지에 필요하다.
macOS는 `brew install libreoffice poppler tesseract`, Linux는 해당 패키지 관리자로 설치할 수 있다.
한국어 OCR은 `tesseract --list-langs`에서 kor을 확인한다. 언어팩이 없으면 eng로 한국어를 처리했다고 주장하지 않는다.

## OCR

`pdf_inventory.py --ocr auto`는 원문 텍스트가 40자 미만이고 raster 이미지가 페이지의 절반 이상을 차지하는 페이지에 OCR을 적용한다.
스캔 여부가 의심되지만 이 기준에 잡히지 않으면 페이지 이미지를 확인하고 `--ocr on`을 사용할 수 있다.
`--ocr on`은 모든 페이지, `--ocr off`는 사용하지 않는다. 기본 CLI는 off이며 스킬은 auto를 사용한다.
OCR 결과는 검토용 텍스트이고 원문 숫자를 보장하지 않는다. 원본 페이지 이미지는 계속 보존한다.
캡션·크롭 감지는 advisory이며 캡션이 안 잡혀도 원본 페이지를 직접 읽고 좌표를 정할 수 있다.

## 수식

matplotlib mathtext는 LaTeX 부분집합이다. 렌더 가능한 문법 변경이라도 수학적 의미가 유지되는지 원문과 대조한다.
지원되지 않는 식은 원문 PDF의 식 자체를 크롭한다. 식 번호·기호·분수·첨자를 삭제해서 렌더 오류를 피하지 않는다.

equations.json 예시:

```json
[
  {"name": "eq1", "latex": "\\frac{QK^T}{\\sqrt{d_k}}"},
  {"name": "eq2", "latex": "\\begin{aligned}a&=b\\end{aligned}",
   "pdf": "paper.pdf", "page": 4, "bbox": [50, 140, 550, 205]},
  {"name": "eq3", "pdf": "paper.pdf", "page": 4, "bbox": [50, 210, 550, 270]}
]
```

PDF 경로는 equations.json 위치 기준이다. mathtext 실패 시 지정된 PDF/page/bbox로 fallback하며,
latex 없이 crop-only로도 사용할 수 있다. 원점은 좌상단, 단위는 PDF point다.

```bash
python scripts/render_equation.py --batch equations.json --outdir assets --report equations_report.json
```

보고서에서 mathtext/crop/failure를 확인하고 PNG를 열어 원문과 비교한다.
출력 PNG는 식의 원본 의미를 보존하기 위한 이미지이며 PowerPoint의 native 수식 편집기는 아니다.
