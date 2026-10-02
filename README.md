> 이 브랜치는 개발·테스트·검증 기록을 보존합니다. 배포 및 설치는 [main](https://github.com/TLAB-HGU/PIM-P_Codex/tree/main)을 사용하세요.

# PIM-P for Codex

Generates paper review seminar slides from research papers.

PIM-P means: **Presentation Instead of Me – the Paper**.

## Skill: `pimp`

`skills/pimp/` — 논문 PDF 한 편을 한국어 논문 리뷰 세미나 발표 자료(.pptx)와 발표자 노트로 만드는 Codex 스킬.

### 설치

Python 3.10+와 Node.js 20+(npm 포함)를 준비하고, `skills/pimp/` 폴더를 통째로 복사한다.

- 개인: `~/.agents/skills/pimp/`
- 프로젝트: `<project>/.agents/skills/pimp/`

복사한 스킬의 실행 환경을 한 번 준비한다.

```bash
python3 ~/.agents/skills/pimp/scripts/setup_runtime.py
```

프로젝트 설치는 위 경로를 `.agents/skills/pimp/scripts/setup_runtime.py`로 바꾼다.
Windows 명령, 저장소에서 한 번에 설치, 기존 설치 갱신은 [설치 안내](docs/installation.md)를 참고한다.

### 사용법

| 호출 | 모드 |
|---|---|
| `$pimp` 또는 `$pimp normal` | 같은 분야 대학원생·연구실용 |
| `$pimp easy` | 비전공자용. 핵심 논리·결과·한계를 유지하고 용어와 설명을 쉽게 |

Codex에서 논문 PDF를 첨부하고 “30분 발표자료 만들어줘”, “쉽게 설명하는 총 12장 발표자료로 만들어줘”라고 요청해도 동작한다.
스킬이 보이지 않으면 새 채팅을 열거나 Codex를 재시작한다. 별도 LLM API 키는 필요 없다.

### 권장 Codex 모델

2026-10-02 기준. **normal/easy 모두 GPT-6.1 Sol + High를 기본 추천**한다.
아래 조합은 공식 모델 안내와 PIM-P의 작업 요구에 근거한 시작점이며, 모델별 실측 순위는 아니다.

| 작업 | 모델 | 추론 수준 | 선택 이유 |
|---|---|---|---|
| normal 최초 제작 | GPT-6.1 Sol (`gpt-6.1-sol`) | High | 원문·수식·실험 근거 분석과 슬라이드 제작의 균형 |
| easy 최초 제작 | GPT-6.1 Sol (`gpt-6.1-sol`) | High | 같은 원문 분석에 용어 풀이·비유·한계 보존까지 필요 |
| 복잡한 논문 또는 품질 최우선 발표, 두 모드 공통 | GPT-6 Astra (`gpt-6-astra`) | High → 필요 시 Extra High | 까다로운 방법·상충하는 결과·비유의 정확성 검토 |
| 검증된 자료의 문구·서식 수정 | GPT-6.1 Sol 또는 GPT-6 Luna (`gpt-6-luna`) | Sol: Medium / Luna: High | 범위가 정해진 수정에 사용; 변경한 내용은 다시 검증 |

Codex의 모델 선택 메뉴에서 모델과 추론 수준을 먼저 고른 뒤 PDF와 `$pimp normal` 또는 `$pimp easy`를 입력한다.
`easy`는 청중에 맞춘 설명 모드이며 모델을 자동으로 바꾸지 않는다. 모델·추론 옵션은 계정과 클라이언트에 따라 다르다.
High 이상은 시간·사용량이 늘 수 있다. Max/Ultra는 기본으로 요구하지 않는다.

근거: [공식 Codex 모델 안내](https://learn.chatgpt.com/docs/models?surface=app),
[공식 모델 선택 안내](https://developers.openai.com/api/docs/guides/model-selection).
동일 논문으로 모델 간 비교 실험은 아직 하지 않았다. 코드 테스트·PPTX 검증 통과는 모델의 논문 해석 정확도 보증이 아니며 원문 대조와 렌더 검토가 필요하다.
[분석 근거와 선택 방법](docs/model-selection.md)

PPTX 미리보기에는 LibreOffice와 한글 폰트가 필요하다. 설치 명령은 외부 도구 안내를 제공하며, 한글 표시는 실제 렌더로 확인한다.

[검증 기록](docs/validation.md) · [개발 방법](docs/installation.md#개발) · [변경 이력](CHANGELOG.md)

[TLAB-HGU/PIM-P](https://github.com/TLAB-HGU/PIM-P) 기반 · [MIT License](LICENSE) · [원본 출처](UPSTREAM.md)
