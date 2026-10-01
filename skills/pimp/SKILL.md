---
name: pimp
description: "사용자가 제공한 학술 논문 PDF 한 편을 근거가 연결된 한국어 논문 리뷰 세미나 PowerPoint와 발표자 노트로 만든다. 논문 발표·랩미팅·저널 클럽 슬라이드 요청에 사용하며 normal(연구자)과 easy(비전공자)를 지원한다. 논문 검색만 하거나 발표 자료 없이 논문을 요약하는 요청에는 사용하지 않는다."
license: MIT
---

# PIM-P for Codex

논문을 먼저 검증 가능한 분석 문서로 정리하고, 그 문서에서 슬라이드를 만든다.
TLAB-HGU/PIM-P를 Codex용으로 이식했다. [UPSTREAM.md](UPSTREAM.md)와 [LICENSE](LICENSE)를 보존한다.

## 입력과 기본값

- 입력은 사용자가 지정하거나 첨부한 **논문 한 편의 PDF**다. 실제 접근 가능한 파일 경로를 확인한다. 고정된 업로드 폴더를 가정하지 않는다. 입력이 없으면 논문을 요청한다.
- `$pimp easy`, 비전공자·초보자·쉽게 요청은 easy, 나머지는 normal이다. 명시한 모드가 여러 개면 마지막 것을 따른다. 사용자 메시지에서 읽으며 Claude의 인자 치환에 의존하지 않는다.
- 기본은 발표 30분, 한국어 본문과 노트, 16:9이다. 발표자·날짜는 제공된 것만 넣는다. 사용자가 지정한 시간·언어·분량·템플릿을 우선한다.
- normal/easy 분량과 계산 기준은 [presentation-policy.json](references/presentation-policy.json)이 유일한 기준이다. 기본 30분 normal은 본문 18–24장을 목표로 하고, easy는 18–27장이다. 표지·목차·간지·참고문헌·Appendix는 본문에서 제외한다. 사용자가 총 장수를 지정하면 그 총수 안에 모든 장을 포함한다.
- easy면 [easy-mode.md](references/easy-mode.md)를 읽는다. 사실과 근거는 normal과 같고 표현을 쉽게 바꾼다.

## 실행 준비와 작업 폴더

`SKILL_DIR`는 지금 읽은 SKILL.md의 실제 폴더다. `PYTHON`과 `NODE`는 사용 가능한 실행 파일이다.
Codex 앱에서는 `load_workspace_dependencies`로 번들 경로를 확인한다. CLI에서는 프로젝트 가상환경과 설치된 Node를 사용한다.
현재 환경 경로를 결과 코드에 하드코딩하지 않는다. 외부 API 키나 Claude 설치는 필요 없다.

먼저 [runtime.md](references/runtime.md)를 읽고 다음으로 의존성을 확인한다.

```bash
"$PYTHON" "$SKILL_DIR/scripts/doctor.py" --strict
```

의존성이 없으면 runtime.md의 프로젝트 전용 가상환경과 `npm ci --prefix "$SKILL_DIR"` 절차를 따른다.
스킬에 설치된 pptxgenjs와 환경의 Node를 연결한다. 수식 실패·한글 표시 실패를 성공으로 숨기지 않는다.

작업별 `WORK_DIR`를 사용자 작업 폴더 안에 만든다. 같은 논문을 수정할 때는 기존 작업을 이어가고, 다른 논문 파일을 덮어쓰지 않는다.

```text
WORK_DIR/
  inventory/           # full.txt, text/, pages/, inventory.json
  paper_brief.md       # 원문 기반 분석
  slide_plan.md        # 전체 발표 구성
  assets/              # Figure·수식 PNG
  deck.json            # 슬라이드 데이터와 근거
  deck.pptx
  deck_manifest.json   # 슬라이드별 근거와 노트
  qa.json
  preview/             # 렌더 PDF, PNG, montage
```

## 0. PDF 인벤토리

```bash
"$PYTHON" "$SKILL_DIR/scripts/pdf_inventory.py" "$PDF" "$WORK_DIR/inventory" --dpi 150 --ocr auto --ocr-lang eng
```

영문 논문은 eng, 한글 논문은 설치된 kor+eng 언어팩을 사용한다. 스캔·혼합 PDF는 페이지별 상태를 확인한다.
OCR 언어팩이나 실행 파일이 없으면 설치 방법을 안내하고, 해당 페이지를 직접 읽거나 OCR을 준비한다.
OCR 텍스트는 분석 보조 자료이며 수치·수식·표는 항상 원본 페이지 이미지를 대조한다.
캡션·크롭 좌표는 **후보**다. 자동 감지 결과를 확정된 Figure 범위로 취급하지 않는다.

## A. Analyst

[analyst.md](references/analyst.md)의 스키마에 따라 `paper_brief.md`를 작성한다.
텍스트만으로 표·수식을 해석하지 말고 페이지 이미지를 함께 읽는다. easy는 §13을 추가한다.

- 모든 수치·식·구체적 주장에 PDF 페이지와 Table/Figure/Eq 번호를 남긴다. PDF 페이지와 논문 인쇄 페이지가 다르면 구분한다.
- 저자 주장, 관찰한 결과, 리뷰어 해석을 구분한다. 논문에 없는 배경 지식을 추가하면 교육용 설명으로 표시하고 검증 가능한 출처를 따로 남긴다.
- 표의 열 순서·단위·지표 방향을 원문과 대조한다. 계산한 값은 계산식과 원문 입력을 기록한다.
- brief 자기 점검을 통과한 뒤 디자인 단계로 넘어간다. 누락된 정보를 발견하면 먼저 brief를 수정한다.

Analyst와 Designer를 순차적으로 직접 수행할 수 있다. 별도 에이전트를 쓸 수 있고 해당 실행에서 허용되면 역할을 분리하되,
Designer는 검증된 brief를 내용 소스로 사용한다. 분석과 디자인을 동시에 진행해 불완전한 brief를 전달하지 않는다.

## B. Designer

[seminar-flow.md](references/seminar-flow.md)와 [designer.md](references/designer.md)를 읽는다.

1. `slide_plan.md`에 섹션·아키타입·제목·메시지·시각 자료·노트·출처를 계획한다. 사용자 분량, 방법의 비중, 논리 연결을 확인한다.
2. 원본 Figure를 눈으로 확인한 좌표로 자른다.

```bash
"$PYTHON" "$SKILL_DIR/scripts/crop_figure.py" "$PDF" --page 3 --bbox 50 80 560 330 -o "$WORK_DIR/assets/fig1.png"
```

3. brief의 수식을 렌더링한다. mathtext가 지원하지 않으면 [runtime.md](references/runtime.md)의 **원문 크롭 fallback**을 사용한다. 수식의 의미를 바꾸는 단순화는 하지 않는다.

```bash
"$PYTHON" "$SKILL_DIR/scripts/render_equation.py" --batch "$WORK_DIR/equations.json" --outdir "$WORK_DIR/assets"
```

4. [deck-format.md](references/deck-format.md)에 따라 `deck.json`을 작성한다. 모든 장에 실질적인 한국어 노트를 넣는다.
내용 슬라이드에는 근거 목록을 넣고 리뷰어 해석은 `kind: reviewer`로 표시한다. 그림 경로는 deck.json 폴더 기준으로 쓴다.
5. 빌드한다. 스크립트가 근거를 노트에 추가하고 manifest를 저장한다.

```bash
"$NODE" "$SKILL_DIR/scripts/build_deck.js" "$WORK_DIR/deck.json" --out "$WORK_DIR/deck.pptx"
```

논문 표·차트는 편집 가능한 native 객체를 사용한다. Figure·수식은 원본 의미를 보존하는 이미지다.
폰트는 macOS Apple SD Gothic Neo, Windows Malgun Gothic, Linux Noto Sans CJK KR가 기본이며 사용자 지정이 우선한다.
받는 PC의 폰트 설치와 대체 가능성을 확인한다. 미리보기 PDF도 함께 제공하면 표시를 확인하기 쉽다.

## QA와 전달

[qa.md](references/qa.md)를 읽고 구조 검사와 실제 렌더를 모두 수행한다.

```bash
"$PYTHON" "$SKILL_DIR/scripts/check_deck.py" "$WORK_DIR/deck.pptx" --manifest "$WORK_DIR/deck_manifest.json" --require-sources --report "$WORK_DIR/qa.json"
"$PYTHON" "$SKILL_DIR/scripts/render_slides.py" "$WORK_DIR/deck.pptx" --outdir "$WORK_DIR/preview"
```

렌더러의 실제 CLI 옵션은 `--help` 또는 qa.md를 확인한다. 한글 검증 옵션을 사용해 텍스트가 사라지는 문제를 잡는다.
한글 폰트 설정은 작업 폴더 안의 독립된 fontconfig·캐시로 처리하며 사용자 전역 설정을 수정하지 않는다.

PNG를 실제로 열어 한글·표·수식·축 레이블·겹침·잘림을 확인한다. 구조 검사 통과는 사실 정확도나 시각 품질을 보장하지 않는다.
원문과 brief, deck의 수치·방법·결론·한계를 대조한다. 수정 후 관련 검사와 렌더를 반복한다.
렌더러가 없으면 생성된 PPTX와 미검증 항목을 구분해 전달하고 검증 완료라고 말하지 않는다.

최종 답변에는 모드·슬라이드 수·발표 시간 가정, PPTX·brief·필요한 미리보기 파일 링크를 제공한다.
Codex 파일 패널을 사용할 수 있으면 결과를 연다. Critical Review와 토론 질문은 발표자가 자신의 관점으로 다듬을 부분임을 알려준다.
