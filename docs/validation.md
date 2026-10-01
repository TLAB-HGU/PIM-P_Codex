# 검증 기록

검증일: 2026-10-01. 개발 버전 0.1.0.

## 자동 검사

- Python unittest 41개 통과: PDF·OCR·수식 16개, 설치·의존성 16개, PPTX QA 9개.
- Node 테스트 11개 통과: 실제 PPTX·한글 노트·출처 manifest·이미지 경로·차트 OOXML·출력 보호.
- Codex skill-creator의 quick_validate.py와 저장소 validate_skill.py 통과.
- git diff --check 통과.

합성 입력을 사용해 정상 출력만 아니라 다음 실패를 확인했다.
노트/근거 누락, 범위를 벗어난 페이지·크롭, 없는 OCR 언어팩, 존재하지 않는 이미지,
출력 경로 충돌, 잘못된 내부 PPTX 참조, 수식 파싱 실패가 성공으로 보고되지 않는다.
설치 중 기존 폴더는 보존되며 명시적인 교체에서도 백업과 실패 복원이 동작한다.

수식은 실제 mathtext로 긴 Attention 식과 italic 마지막 글자를 렌더링했다.
원본의 잘리던 마지막 V를 포함해 실제 픽셀 경계를 감싸는 투명 여백을 확인했다.
영문 Tesseract OCR도 합성 스캔 페이지에서 실제 실행했다.

## 렌더링 통합 검사

macOS의 Codex 번들 LibreOffice와 Poppler, 시스템 Apple SD Gothic Neo를 사용했다.

- 이전 검토에서 한글이 보이지 않던 원본의 16종 레이아웃을 다시 렌더링해 한글 표시를 확인했다.
- 현재 JSON 빌더의 16종 레이아웃도 PPTX·manifest 검사와 렌더를 통과했다.
- 숫자·한글·표·native 차트의 grey/teal/grey 제안 기법 강조를 확인했다.
- 렌더된 PDF에서 요구한 한글 문구를 검사했고, 없는 문구를 요구하면 exit 1과 missing_text를 반환했다.

## 실제 논문 normal 모드

공개 논문 [Attention Is All You Need](https://arxiv.org/abs/1706.03762)로 10분 연구실 세미나,
사용자가 지정한 총 12장 조건을 시험했다. 논문 PDF와 작업 결과는 Git에 포함하지 않았다.

산출물은 원문 인벤토리, paper_brief.md, slide_plan.md, 그림/수식 크롭,
deck.json, 12장 PPTX, source manifest, qa.json, 12페이지 렌더다.
모든 장에 한국어 발표자 노트가 있으며 구조 검사와 한글 문구 확인을 통과했다.
개별 PNG를 확인해 그림·수식·표·본문·출처의 표시를 검토했다.

논문 안의 EN-FR 결과 표기 충돌(Abstract/Table 2의 41.8과 §6.1 본문의 41.0)을
임의로 통일하지 않고 brief와 노트에 남겼다. Table 2의 test/newstest2014와
Table 3의 dev/newstest2013를 구분하고, base 모델의 EN-FR 열세를 보존했다.
이 독립 시험에서 수식 끝 글자 잘림을 발견해 구현과 회귀 테스트를 수정했다.

## 검증 범위

실제 로컬 렌더는 macOS에서 검증했다. Windows/Linux의 글꼴 표시까지 같다고 보장하지 않는다.
GitHub Actions는 Linux 자동 검사만 수행하며 LibreOffice/한글 폰트나 실제 논문 해석 품질을 검증하는 작업은 아니다.

한국어 OCR 언어팩이 이 검증 환경에 없어 kor OCR은 실행 검증하지 않았다.
대상 논문 언어에 맞는 Tesseract 언어팩을 설치해야 한다.

출처 manifest와 OCR·캡션 후보는 정확도 보증이 아니다. 모든 실제 발표 자료는
원문 수치·수식·해석 대조와 렌더 이미지 확인을 거쳐야 한다.
현재 기록은 한 논문의 정상 흐름과 합성 회귀 사례에 대한 검증이며,
모든 분야의 논문에 대한 모델 품질이나 Claude판과의 동등성을 입증한 벤치마크는 아니다.
