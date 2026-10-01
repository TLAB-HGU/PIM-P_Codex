# PPTX 검증과 한글 렌더링

`check_deck.py`와 `render_slides.py`는 최종 결과의 서로 다른 측면을 확인한다. 두 도구가 성공해도 논문 해석의 정확성이나 시각적 완성도를 자동으로 증명하지는 않는다. 원문과 슬라이드를 대조하고 모든 페이지를 눈으로 확인해야 한다.

## 패키지와 출처 검사

```bash
python skills/pimp/scripts/check_deck.py output/deck.pptx \
  --manifest output/deck_manifest.json --require-sources \
  --report output/deck_qa.json
```

- ZIP 무결성, XML 파싱, 내부 관계 파일과 이미지·차트·노트의 존재를 검사한다.
- 각 슬라이드에 실제 발표자 노트가 있어야 한다. 기본 기준은 공백·문장부호를 제외한 글자·숫자 20개 이상이다. 자동 슬라이드 번호는 노트로 세지 않는다.
- `TODO`, `TBD`, `PLACEHOLDER`, `Lorem ipsum` 등의 미완성 텍스트는 실패다.
- 선언한 manifest의 버전·모드·슬라이드 순서·출처 형식을 검사한다. `paper_pages`가 있으면 전체 PDF 페이지보다 큰 출처 페이지도 실패다. `--require-sources`는 본문 슬라이드마다 한 개 이상의 출처 선언을 요구한다. 표지·목차·간지·참고문헌·인사 슬라이드는 예외다.
- manifest의 notes가 실제 PPTX 노트와 일치해야 한다. Unicode 정규화와 공백 차이만 허용한다. 각 sources의 `[논문] label (PDF p.N)` 또는 `[리뷰어 관점] label (PDF p.N)`도 실제 노트에 있어야 한다. build_deck.js는 자동으로 이 형식을 추가한다. 커스텀 빌드도 같은 형식을 사용한다.
- 논문 출처는 `{ "page": 3, "kind": "paper", "label": "Figure 2" }`처럼 물리적인 PDF 페이지를 1부터 기록한다. 리뷰어 해석도 `kind: "reviewer"`와 **필수 양의 정수 `page`**로 원문의 관련 근거를 연결한다. 후속 연구 아이디어도 관련 한계·논의 페이지에 연결하고 label에 리뷰어 제안임을 밝힌다.
- 캔버스 밖의 텍스트·이미지·차트는 시각 검토 경고로 보고한다. 장식 도형의 의도적 넘침은 실패 처리하지 않는다. 그룹이나 회전 도형, 텍스트 상자 내부 줄바꿈·겹침은 렌더링으로 확인한다.

종료 코드는 성공 `0`, 검사 실패 `1`이다. JSON 보고서에는 검사 범위와 오류가 포함된다. 출처 선언의 존재를 확인하는 것이므로 논문 주장과 수치가 실제로 일치하는지는 분석 단계에서 직접 검증한다.

## PDF·PNG 렌더링과 한글 확인

```bash
python skills/pimp/scripts/render_slides.py output/deck.pptx \
  --output output/render --expect-text '핵심 연구 질문'
```

결과는 PDF, 개별 `slide-0001.png` 파일, `montage.png`, `rendered_text.txt`, `render_report.json`이다. `--expect-text`는 **슬라이드 본문에 실제로 사용한 한글 구절**을 전달한다. 발표자 노트는 PDF 본문에 나오지 않는다. 여러 번 지정하거나 `--expect-text-file expected.txt`로 구절별 한 줄을 전달할 수 있다. 필요한 구절이 PDF에서 사라지면 종료 코드 `1`과 `missing_text`를 반환한다. 한글이 있는 슬라이드마다 구절을 골라 확인한 후 개별 PNG를 검사한다.

렌더러 탐색 순서는 `--soffice`, `PIMP_SOFFICE`, `PIMP_RUNTIME_DIR`, `PATH`, macOS 기본 LibreOffice 설치 위치이다. Codex에서 번들 런타임을 사용할 때는 `load_workspace_dependencies`가 반환한 LibreOffice 실행 파일 또는 런타임 경로를 환경 변수로 전달한다. 저장소에는 개인 컴퓨터 경로를 넣지 않는다.

```bash
PIMP_SOFFICE=/absolute/path/to/soffice python skills/pimp/scripts/render_slides.py output/deck.pptx
```

한글 글꼴은 macOS에서 `Apple SD Gothic Neo`, Linux에서 `Noto Sans CJK KR`, Windows에서 `Malgun Gothic`을 기본으로 사용한다. Linux에 CJK 글꼴이 없다면 운영체제의 패키지 관리자를 통해 적절한 글꼴을 설치하거나 사용자가 보유한 글꼴을 명시한다. 코드가 글꼴을 다운로드하거나 사용자 설정을 바꾸지는 않는다.

```bash
python skills/pimp/scripts/render_slides.py output/deck.pptx \
  --font-file /absolute/path/to/KoreanFont.otf --font-family 'Korean Font Family' \
  --expect-text '실험 결과'
```

`--font-dir`도 반복 지정할 수 있다. 렌더러는 OS 글꼴 폴더와 지정한 파일만 보이는 임시 fontconfig를 만들고, 캐시와 LibreOffice 사용자 프로필도 임시 폴더에 격리한다. `Malgun Gothic` 등 원본 PPTX의 글꼴 이름에는 선택한 한글 글꼴을 대체 글꼴로 지정한다. 이것은 PPTX에 글꼴을 포함시키거나 PPTX의 글꼴 이름을 바꾸는 작업이 아니다. 공유받은 사람이 편집하려면 같은 글꼴 또는 적절한 대체 글꼴이 필요하다.

이미지는 PyMuPDF로 렌더링하며, 없으면 `pypdf`와 Poppler `pdftoppm`으로 자동 대체한다. `pdftoppm`도 `PIMP_PDFTOPPM`, `PIMP_RUNTIME_DIR`, `PATH` 순서로 탐색한다. 따라서 번들 Python에 PyMuPDF가 없어도 `PIMP_RUNTIME_DIR`에 번들 의존성 경로를 지정하면 작업할 수 있다.

`--timeout`은 LibreOffice 변환 및 Poppler 변환의 개별 제한 시간(기본 120초), `--dpi`는 PNG 해상도(기본 120)이다. LibreOffice·Pillow 또는 지원되는 PDF 렌더러가 없거나 변환이 실패하면 종료 코드 `2`를 반환한다. PDF 텍스트 검사는 누락 탐지에 유용하지만 겹침, 작은 글씨, 오역을 검사하지 않으므로 최종 시각 검토를 생략하지 않는다.
