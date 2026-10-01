---
name: pimp
description: 사용자가 준 논문(PDF)을 읽고, 논문의 흐름을 따라 이해하기 쉬운 "정석 논문 리뷰 세미나" 발표 자료(.pptx)를 만든다. Analyst(논문 이해·핵심 정리) → Designer(세미나 흐름으로 시각화·슬라이드 제작) 2단계 파이프라인. 두 가지 모드 — normal(기본, 같은 분야 연구자용)과 easy(비전공자도 알아듣는 쉬운 해석판) — 를 지원하며 `/pimp easy`, `/pimp normal`로 고른다. 논문 리뷰, 논문 발표, 랩미팅 논문 소개, 저널 클럽, paper review, journal club, 세미나 ppt, "이 논문 발표자료 만들어줘", "논문 슬라이드로 정리해줘"처럼 논문 파일과 함께 발표 자료·슬라이드·ppt를 요청하면 반드시 이 스킬을 사용할 것. 사용자가 '리뷰'나 '세미나'라는 단어를 쓰지 않고 논문을 첨부한 채 "발표 준비", "ppt로 만들어줘"라고만 해도 이 스킬을 쓴다. "쉽게", "비전공자용", "초보자도 이해하게" 같은 요청이 함께 오면 easy 모드로 만든다.
argument-hint: "[easy|normal]"
---

# PIMP — Paper Review Slides

사용자가 준 논문 한 편을 **정석 논문 리뷰 세미나 흐름**의 PowerPoint(.pptx)로 만든다.

## 모드 선택 (가장 먼저)

호출 인자: `$ARGUMENTS`

위 인자(또는 인자가 전달되지 않는 환경이라면 사용자 메시지)를 보고 모드를 하나로 정한다.

| 조건 | 모드 |
|---|---|
| `easy`가 있음, 또는 "쉽게", "비전공자", "초보자", "일반인", "쉬운 버전" 같은 요청 | **easy** — 비전공자도 알아듣는 쉬운 해석판 |
| `normal`이 있음, 인자가 비어 있음, 또는 위에 해당하지 않음 | **normal** — 기본. 같은 분야 대학원생/연구실용 |

- 대소문자 무시(`EASY`, `Easy`도 easy). 둘 다 들어 있으면 뒤에 쓴 것을 따른다.
- **easy 모드면 `references/easy-mode.md`를 반드시 읽는다.** 그 파일의 규칙이 이 문서와 analyst.md·designer.md·seminar-flow.md의 해당 부분을 **덮어쓴다**. 덮어쓰지 않은 부분(충실성, 출처 표기, 파이프라인, QA)은 그대로 적용된다.
- 정한 모드는 Analyst·Designer 서브에이전트 프롬프트에 `MODE: easy` / `MODE: normal`로 명시해서 넘긴다. easy면 easy-mode.md도 함께 넘긴다.
- 최종 답변 첫 줄에 어떤 모드로 만들었는지 밝힌다.

## 파이프라인

작업은 두 역할로 나뉜다.

```
논문 PDF ──▶ [0] 인벤토리(텍스트·페이지·Figure 위치)
         ──▶ [A] Analyst  : 논문을 읽고 paper_brief.md 작성 (이해 담당)
         ──▶ [B] Designer : brief만 보고 slide_plan.md → 에셋 → build.js → deck.pptx (시각화 담당)
         ──▶ QA → 전달
```

**왜 둘로 나누는가.** 이해와 디자인을 한 번에 하면 슬라이드 모양에 맞추려고 내용을 왜곡하거나 수치를 지어내기 쉽다.
Analyst는 "무엇이 맞는가"만, Designer는 "어떻게 보여줄까"만 책임진다. Designer는 논문 원문을 새로 해석하지 않고 검증된 brief를 시각화하므로,
슬라이드의 모든 주장·수치가 brief(→ 논문 페이지)로 거슬러 올라갈 수 있다.

## 시작 전에

1. **먼저 읽을 것 (필수)**: `/mnt/skills/public/pptx/SKILL.md` — pptxgenjs 함정, 폰트, QA 절차가 여기 있다. 스캔본이거나 텍스트 추출이 이상하면 `/mnt/skills/public/pdf-reading/SKILL.md`도 읽는다.
2. **논문 파일 확인**: `/mnt/user-data/uploads/`를 본다. 논문이 없으면 파일을 요청하고 멈춘다.
3. **옵션**: 사용자가 말하지 않은 것은 묻지 말고 아래 기본값으로 진행하되, 최종 답변에 어떤 가정을 했는지 한 줄로 밝힌다.

| 옵션 | 기본값 |
|---|---|
| 모드 | normal (위 "모드 선택" 참고) |
| 발표 시간 | 30분 → 본문 18–24장 (분량 표는 `references/seminar-flow.md`). easy는 최대 27장 (`references/easy-mode.md`) |
| 언어 | 한국어 본문, 전문 용어는 영어 병기 (예: 주의 메커니즘(Attention)). easy는 쉬운 우리말이 먼저, 원어는 작게 |
| 청중 | normal: 같은 분야 대학원생/연구실 — 기초 개념은 짧게, 논문 고유 개념은 자세히. easy: 해당 분야 비전공자 |
| 발표자·날짜 | 사용자가 주면 표지에 넣고, 없으면 그 줄을 생략 (placeholder 금지) |
| 파일 형식 | .pptx (16:9, 13.33" × 7.5") |

## 작업 폴더

```
/home/claude/review/
├── inventory/          # [0] pdf_inventory.py 출력 (text/, pages/, inventory.json)
├── paper_brief.md      # [A] Analyst 산출물 — Designer의 유일한 내용 소스
├── slide_plan.md       # [B-1] 슬라이드별 설계
├── assets/             # [B-2] 크롭한 Figure, 렌더링한 수식 PNG
├── build.js            # [B-3] deck_kit.js를 쓰는 생성 스크립트
└── deck.pptx
```

스킬 경로를 `SKILL_DIR`로 부른다 (이 SKILL.md가 있는 폴더).

## [0] 논문 인벤토리

```bash
python3 $SKILL_DIR/scripts/pdf_inventory.py /mnt/user-data/uploads/<paper>.pdf /home/claude/review/inventory
```

페이지별 텍스트(`text/page_001.txt`, `full.txt`), 페이지 이미지(`pages/page-001.png`), 그리고 Figure/Table 캡션 위치와
추천 크롭 영역(`inventory.json`)을 만든다. 텍스트가 거의 안 나오면 스캔본이다 → pdf-reading 스킬의 OCR 절차를 따른다.

## [A] Analyst — 논문 이해

`references/analyst.md`를 읽고 그대로 수행한다. 산출물은 `paper_brief.md` 하나이며, 그 파일의 스키마를 정확히 따른다.
easy 모드면 easy-mode.md의 "Analyst 추가 작업"에 따라 brief 끝에 §13(쉬운 설명)을 더 쓴다.

- **서브에이전트를 쓸 수 있는 환경**(Claude Code, Cowork)이면: analyst.md 전체를 프롬프트로 하는 서브에이전트를 띄우고, 입력으로 인벤토리 경로를, 출력 경로로 `paper_brief.md`를 준다.
- **서브에이전트가 없는 환경**(Claude.ai)이면: 직접 수행하되, 이 단계에서는 슬라이드 모양을 생각하지 않는다. 오직 "논문이 무엇을 왜 어떻게 했고, 무엇을 보였나"에 집중한다.

**게이트**: analyst.md 끝의 자기 점검 체크리스트를 모두 통과해야 [B]로 넘어간다. 특히 모든 수치에 페이지/표 번호가 붙어 있어야 한다.

## [B] Designer — 세미나 슬라이드 제작

`references/seminar-flow.md`(무엇을 어떤 순서로)와 `references/designer.md`(어떻게 보여줄지)를 읽고 수행한다.
서브에이전트 환경이면 두 파일을 프롬프트로 하는 Designer 에이전트를 띄우고, 입력은 `paper_brief.md` + `inventory/` 경로만 준다.
easy 모드면 `references/easy-mode.md`도 프롬프트에 넣는다 — 흐름·분량·글자 수 한도는 easy-mode.md가 우선한다.

Designer의 규칙: **내용은 brief에서만 가져온다.** brief에 없는 정보가 필요하면 brief가 가리키는 논문 페이지를 확인해 brief에 먼저 추가한 뒤 사용한다. 기억이나 추측으로 채우지 않는다.

1. **slide_plan.md** — 세미나 흐름에 따라 슬라이드마다 `섹션 / 아키타입 / 액션 타이틀 / 내용 / 시각 요소 / 발표자 노트 요지 / 출처(p.)`를 적는다. 먼저 전체 계획을 세우고 나서 만들기 시작한다 — 흐름 문제는 코드 쓰기 전에 고치는 게 훨씬 싸다.
2. **에셋 준비**
   - Figure 크롭: 페이지 이미지(`inventory/pages/`)를 직접 보고 `inventory.json`의 추천 영역을 확인·수정한 뒤
     `python3 $SKILL_DIR/scripts/crop_figure.py <pdf> --page N --bbox x0 top x1 bottom -o assets/fig3.png`
   - 수식: `python3 $SKILL_DIR/scripts/render_equation.py --batch equations.json --outdir assets/`
3. **build.js** — `$SKILL_DIR/scripts/deck_kit.js`를 require해서 아키타입 함수로 슬라이드를 쌓는다. 사용법과 전체 예시는 designer.md에 있다. deck_kit에 없는 레이아웃이 꼭 필요하면 같은 테마 값(`kit.theme`)을 써서 직접 그린다.
4. **빌드 & QA** — `node build.js` 후 pptx 스킬의 QA(내용·파일·시각)를 모두 수행하고, designer.md의 "세미나 품질 체크리스트"로 한 번 더 본다. 렌더 이미지를 실제로 열어 보고 넘침·겹침을 고친다.

## 전달

1. `deck.pptx`를 `/mnt/user-data/outputs/<논문약칭>_review.pptx`(easy 모드는 `<논문약칭>_review_easy.pptx`)로 복사하고 `present_files`로 전달한다. (`paper_brief.md`도 함께 주면 발표 준비에 유용하다.)
2. 답변은 짧게: 적용한 모드, 슬라이드 수와 구성(섹션별 장수), 적용한 가정(발표 시간 등), 그리고 **발표자가 직접 확인해야 할 부분** —
   특히 "Critical Review / 토론 질문" 슬라이드는 발표자 본인의 의견으로 다듬어야 한다는 점.

## 핵심 원칙 (모든 단계 공통)

- **충실성**: 수치·주장·수식은 논문에 있는 그대로. 슬라이드의 모든 수치는 노트에 출처(p., Table/Fig 번호)를 남긴다. 확신이 없으면 빼는 쪽을 택한다.
- **논문의 목소리와 발표자의 목소리를 구분**: 논문이 주장한 한계는 "저자 언급", 리뷰어 관점의 비판은 "리뷰어 관점"으로 라벨을 붙인다.
- **한 슬라이드 = 한 메시지**: 제목은 주제어("실험 결과")가 아니라 그 장의 결론을 말하는 액션 타이틀("TSMixer가 8개 중 6개 데이터셋에서 최저 MSE").
- **이해 우선**: 수식은 반드시 기호 설명 + 직관적 해석과 함께, 복잡한 구조는 논문 Figure + 단계별 흐름으로 나눠 보여준다.
- **발표자 노트**: 모든 슬라이드에 한국어 구어체 발표 스크립트(30–90초 분량)를 넣는다. 세미나 자료의 절반은 노트다.
