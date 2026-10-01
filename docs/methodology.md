# Codex 이식 방법론

원본의 논문 이해와 디자인 분리 구조를 유지한다. 모델에게 판단이 필요한 작업은 스킬 지침으로,
반복 가능한 변환·검사는 스크립트로 구현한다. 별도 Claude/OpenAI API 호출을 추가하지 않는다.

| 원본에서 확인한 문제 | 적용한 방법 | 검증 |
|---|---|---|
| Claude 경로·호출·파일 전달 고정 | 실제 SKILL_DIR, 입력·작업 폴더, Codex 파일 전달 | 지침 참조 검사, 독립 스킬 설치 |
| 30분 장수 기준 충돌 | presentation-policy.json 한 곳에서 관리, 사용자 총수 우선 | 지침의 중복 표 제거 |
| 수식 의존성 부재·문법 제한 | 명시적 requirements, mathtext 실패 시 원문 PDF crop | 실제 mathtext·실패·crop fallback 테스트 |
| 2단 캡션·텍스트 혼합 | 단별 텍스트 순서·캡션 줄 분리, advisory 위치 | 2단 합성 PDF 회귀 검사 |
| 스캔·혼합 PDF | 페이지별 판정, Tesseract auto/on/off, 오류 보고 | 실제 영문 scan OCR, 혼합 페이지·언어팩 실패 테스트 |
| 한글이 보이지 않는 QA 렌더 | OS별 폰트, 독립 fontconfig·캐시·LibreOffice profile | 기존 16종 덱의 한글 텍스트 검사와 PNG 확인 |
| 노트·출처 선택 사항 | deck.json 빌드 게이트, manifest, 구조 QA | 누락·잘못된 페이지·PPTX 관계 오류 검사 |
| 차트 highlightIndex 미구현 | 단일 막대 시리즈의 category별 색상 | native chart XML의 실제 point 색상 검사 |
| 의존성·설치 명세 부재 | Python requirements, Node lockfile, doctor, 백업 설치 | 공백 경로·기존 설치 보호·복구 테스트 |

작업 순서는 원문 인벤토리, 근거 brief, 슬라이드 계획, 에셋과 deck.json, PPTX 빌드, 구조 검사,
렌더 이미지 검토, 원문 수치 대조다. 스킬을 복사해 설치할 때도 MIT LICENSE와 UPSTREAM.md를 포함한다.

검사가 보장하는 범위를 구분한다. PDF 캡션은 후보이고 OCR은 확인이 필요한 전사 결과다.
manifest는 출처 선언을 기록하며 논문이 주장을 뒷받침하는지는 자동 판정하지 않는다.
PDF에서 한글 텍스트가 추출되더라도 겹침·잘림은 PNG를 열어 확인한다.

v0.1은 논문 한 편을 제공받는 워크플로다. 관련 논문 검색, 다중 논문 비교, 저널 추천,
완전 자동 사실 검증은 구현 범위에 포함되지 않는다. 다음 개선은 실제 랩미팅 사용에서 발견한
전사 오류·설명 난도·레이아웃 문제를 근거로 좁게 수정하는 방식으로 진행한다.
