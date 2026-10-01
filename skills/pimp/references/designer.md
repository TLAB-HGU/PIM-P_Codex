# Designer — 세미나 슬라이드 제작

내용은 검증된 paper_brief.md에서 가져온다. 빠진 사실이 필요하면 원문 페이지를 확인하고 brief에 먼저 추가한다.
발표 흐름은 seminar-flow.md, 모드별 분량은 presentation-policy.json, easy 표현은 easy-mode.md를 따른다.

## 슬라이드 계획

먼저 slide_plan.md에 다음을 적는다.

| # | 섹션 | 아키타입 | 제목 | 메시지 | 시각 자료 | 노트 요지 | 출처 |
|---|---|---|---|---|---|---|---|

제목을 이어 읽으면 문제·아이디어·방법·검증·결론이 연결되어야 한다.
결과 제목은 원문이 뒷받침하는 발견을 말한다. 배경·방법은 내용을 분명히 식별하는 제목도 적절하다.
한 장은 한 메시지이며, 제목은 normal 40자, easy 35자 내외로 짧게 쓴다.
방법은 본문의 30–40%를 권장한다. 같은 레이아웃을 3장 이상 연속해 사용하지 않는다.
brief의 필수 Figure·Table이 포함되었는지 확인한다. 사용자 총 장수는 모든 장을 포함한다.
easy에서 원본 Figure가 초심자에게 복잡하면 같은 핵심 단계를 보존한 native 도식으로 설명할 수 있다.
원본 Figure의 PDF 페이지를 근거로 연결하고, 생략한 세부 사항은 brief와 노트에 남긴다.

| 요소 | normal 권장 한도 |
|---|---|
| pointsSlide | 2–4개, head 25자, body 70자 |
| figure/compare bullet | 3–5개, 각 45자 |
| TL;DR 칸 | 90자 |
| 표 | 8행 × 6열 |
| 수식 | 한 장에 1–2개 |

easy 한도는 easy-mode.md가 우선한다. 긴 설명은 노트로 옮기고 글자를 과도하게 줄이지 않는다.

## 에셋

- Figure는 페이지 이미지를 먼저 열고 crop_figure.py로 자른 뒤 PNG를 다시 확인한다.
- 캡션·축·범례·서브 Figure가 잘리지 않았는지 확인한다. 캡션 번호와 PDF 페이지를 슬라이드에 적는다.
- PDF point는 좌상단 원점이다. 비율 좌표는 --frac, 일괄 처리에는 --batch를 사용한다.
- 복잡한 도식은 필요한 패널만 선택하고 어디를 봐야 하는지 설명한다.
- 수식은 render_equation.py로 렌더링한다. 실패한 식은 원문 크롭 fallback을 사용하고 기호·직관을 함께 보여준다.
- 표는 brief의 전사 결과로 native tableSlide를 만든다. 차트는 native chartSlide이며 숫자를 원문과 대조한다.
- 실제 수치 개선 폭을 계산했다면 brief에 계산식·입력값을 먼저 남긴다.

## 테마와 폰트

| 테마 | 적합한 인상/분야 |
|---|---|
| teal | 차분함, 일반 ML·시계열·헬스케어 |
| graphite | 시스템·최적화·로보틱스 |
| plum | NLP·생성모델·멀티모달 |
| forest | 바이오·환경·그래프 |
| navy | 이론·금융 |
| crimson | 보안·비전·강화학습 |

사용자 템플릿·기관 색상이 우선한다. colors로 dark/primary/accent/surface/highlight를 덮어쓸 수 있다.
macOS 기본 폰트는 Apple SD Gothic Neo, Windows는 Malgun Gothic, Linux는 Noto Sans CJK KR이다.
기본값도 실제 설치 여부를 확인하며, 다른 PC로 전달할 때 대체 폰트에 의한 줄바꿈을 고려한다.
QA 렌더러에는 시스템 한글 폰트와 독립된 fontconfig·캐시를 연결한다. 한글이 저장되었다는 사실만으로 표시 성공을 판단하지 않는다.

## 빌드

[deck-format.md](deck-format.md)의 아키타입 필드와 스키마를 사용해 deck.json을 작성한다.
모든 장에 notes와 sources 배열을 넣는다. notes는 data 내부가 아니라 슬라이드 최상위다.
이미지 경로는 deck.json 위치 기준으로 적는다. build_deck.js가 PPTX와 deck_manifest.json을 만든다.
manifest의 근거는 발표자 노트에 자동으로 추가된다. 생성된 근거가 실제 주장을 뒷받침하는지는 사람이 원문을 대조한다.

커스텀 레이아웃은 SKILL_DIR/scripts/deck_kit.js를 require하는 build.js로 만들 수 있다.
kit.theme, fonts, contentSlide, text, fit을 사용하고 같은 manifest를 직접 작성한다.
라이브러리 경로와 작업 폴더를 사용자 메시지와 현재 환경에서 해석하고 개인 PC 경로를 하드코딩하지 않는다.

## 발표자 노트

- 한국어 구어체로 장당 150–400자 내외를 권장한다. 화면을 읽기만 하지 말고 의미·근거·다음 장 연결을 설명한다.
- 수치와 식의 Table/Fig/Eq/PDF 페이지를 남긴다. 인쇄 페이지와 PDF 페이지가 다르면 구분한다.
- 비평·토론 노트에는 발표자가 자신의 관점으로 다듬을 부분임을 적는다.
- easy의 비유에는 비유가 성립하지 않는 부분도 노트로 남긴다.
- 표지·목차·간지에도 발표자가 사용할 연결 멘트를 넣는다.

## 최종 확인

[qa.md](qa.md)의 구조 검사와 렌더를 실행한다. 모든 PNG를 열어 읽고 고친다.
원문·brief·슬라이드의 수치, 결론의 강도, 저자/리뷰어 구분을 대조한다.
표·차트의 지표 방향과 제안 기법 강조를 확인한다. 단일 막대 차트는 highlightIndex로 제안 기법 위치를 지정한다.
모든 슬라이드의 노트와 출처, 캡션, 수식의 기호 설명과 직관적 해석이 있는지 확인한다.
렌더링 실패나 미검증 항목을 성공으로 표시하지 않는다.
