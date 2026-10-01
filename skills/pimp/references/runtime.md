# 실행 환경

Python 3.10 이상, Node 20 이상을 사용한다. 별도 LLM API 키는 필요 없다.
Codex가 논문을 분석하고 JSON을 작성하며 스크립트는 추출·이미지 처리·PPTX 제작을 수행한다.

## 설치

저장소에서 실행하는 경우:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r skills/pimp/requirements.txt
npm ci --prefix skills/pimp --ignore-scripts
.venv/bin/python skills/pimp/scripts/doctor.py --strict
```

Windows에서는 `.venv\Scripts\python.exe`를 사용한다.
독립 설치한 스킬도 그 폴더의 requirements.txt와 package-lock.json을 사용한다.
개발·테스트에는 requirements-dev.txt를 사용한다. requirements는 지원 범위이고 Node는 lockfile로 고정된다.

Codex 앱 번들 실행 파일은 `load_workspace_dependencies`가 반환한 경로를 사용한다.
필요하면 그 반환값으로 PIMP_NODE·PIMP_SOFFICE·PIMP_PDFTOPPM을 설정한다.
개인 PC 경로를 스킬 코드에 저장하지 않는다. 개발 링크 설치에서는 실제 스킬 경로를 해석해
저장소의 `.venv/bin/python`(Windows는 `.venv\Scripts\python.exe`)이 있으면 우선 사용한다.
복사 설치에서는 사용자 작업 폴더의 가상환경을 사용할 수 있다. `doctor.py --json`은 필수/선택 항목을 구분한다.

| 환경변수 | 목적 |
|---|---|
| PIMP_NODE | Node 실행 파일 |
| PIMP_SOFFICE | LibreOffice/soffice 실행 파일 |
| PIMP_PDFTOPPM | Poppler pdftoppm 실행 파일 |
| PIMP_TESSERACT | Tesseract 실행 파일 |
| PIMP_FONT | 슬라이드와 렌더링의 기본 폰트 이름 |
| PIMP_RUNTIME_DIR | 번들 dependencies 루트, render_slides에서 선택적으로 탐색 |
| NODE_PATH | 환경에 이미 설치된 Node 패키지 경로를 사용해야 할 경우 |

LibreOffice와 Poppler는 미리보기에 필요하다. Tesseract는 스캔 페이지에 필요하다.
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
