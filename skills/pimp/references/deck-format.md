# deck.json과 근거 manifest

deck.json은 Codex가 검증한 brief와 slide_plan에서 작성한다. JSON 빌더가 논문을 자동 해석하는 것은 아니다.
입력 파일 위치를 기준으로 이미지 경로를 해석한다. 빌드 결과는 PPTX와 deck_manifest.json이다.

```json
{
  "schema_version": 1,
  "mode": "normal",
  "title": "논문 리뷰",
  "short": "논문 약칭",
  "theme": "teal",
  "duration_minutes": 30,
  "paper_pages": 12,
  "input_pdf": "paper.pdf",
  "paper_brief": "paper_brief.md",
  "slides": [
    {
      "archetype": "pointsSlide",
      "section": "방법",
      "data": {
        "eyebrow": "Method",
        "title": "이 장에서 설명할 실제 논문 구성요소",
        "points": [{"head": "원문 기반 요점", "body": "검증한 설명"}]
      },
      "notes": "발표자가 화면 요소를 짚으며 말할 충분한 길이의 한국어 설명을 작성한다.",
      "sources": [{"page": 4, "kind": "paper", "label": "Section 3, Eq. (1)"}]
    }
  ]
}
```

위 내용은 형식 예시다. 실제 출력에서는 논문에 근거한 내용으로 작성한다.

- `schema_version`은 1, `mode`는 normal/easy, `slides`는 순서대로 배열이다.
- `font_head`, `font_body`로 지정 폰트를 사용한다. 미지정이면 OS 기본값, `PIMP_FONT` 환경변수로도 변경할 수 있다.
- `section`은 비어 있지 않은 섹션 이름이다. `appendix: true`는 본문 장수에서 제외한다.
- `data`는 아래 아키타입의 인자다. notes를 data 안에 넣지 않는다.
- `notes`는 최소 20자 이상의 실질적 설명이며, 실제 발표는 150–400자 내외를 권장한다. 표지·목차·간지에도 짧은 연결 멘트를 넣는다.
- `sources`는 항상 배열이다. 내용 슬라이드는 최소 1개가 필요하다. `page`는 1부터 시작하는 **PDF 페이지**다.
- `kind: paper`는 저자의 내용, `kind: reviewer`는 해당 페이지를 근거로 한 리뷰어 해석이다. label에 Table/Figure/Eq/Section과 구분을 적는다.
- 리뷰어 해석을 논문 주장인 것처럼 표시하지 않는다. 발표 화면에도 저자 언급/리뷰어 관점을 구분한다.
- paper_pages를 넣으면 범위를 벗어난 페이지를 빌드에서 거부한다. manifest는 작성한 근거를 기록하지만 그 근거가 주장을 뒷받침하는지는 원문 대조가 필요하다.
- 표지·목차·간지·참고문헌은 근거 배열이 비어 있어도 된다. titleSlide에 원문 제목·저자·연도가 있으면 PDF p.1을 연결하는 편이 좋다.
- image와 eqImages 경로는 로컬 PNG/JPEG다. URL을 넘기지 않는다.

| archetype | data 주요 필드 |
|---|---|
| titleSlide | title, subtitle, authors, venue, presenter, date |
| agendaSlide | title, items[] |
| sectionSlide | num, title, subtitle |
| tldrSlide | title, oneLiner, problem, idea, result |
| pointsSlide | title, eyebrow, points[{head,body}], image?, caption? |
| figureSlide | title, image, caption, points[], takeaway, layout(side/full) |
| equationSlide | title, eqImages[], eqLabels[], symbols[{sym,desc}], intuition |
| compareSlide | title, left{label,points}, right{label,points}, verdict |
| processSlide | title, steps[{title,desc}], footer |
| tableSlide | title, header[], rows[][], highlightRows[], bestCells[[row,col]], takeaway, note |
| statSlide | title, stats[{value,label,sub}], note |
| chartSlide | title, type(bar/line), labels[], series[{name,values}], valTitle, highlightIndex?, note |
| critiqueSlide | title, strengths[], weaknesses[], future[] |
| questionsSlide | title, questions[] |
| closingSlide | title, takeaways[], closing |
| referencesSlide | title, refs[] |

chartSlide의 highlightIndex는 단일 bar series의 제안 기법 막대 위치를 0부터 시작하는 인덱스로 강조한다.
차트의 실제 숫자는 number로, 원문 표의 숫자는 원래 자릿수를 유지한 문자열로 쓴다.
symbols.sym은 LaTeX 대신 유니코드 기호를 쓴다. points의 bullet은 문자열 또는 `{text, sub:[...]}`다.

직접 커스텀 레이아웃이 필요한 경우 deck_kit.js를 사용하는 build.js를 작성할 수 있다.
이 경우에도 같은 manifest 스키마를 만들고 구조 검사·렌더·원문 검증을 수행한다.
