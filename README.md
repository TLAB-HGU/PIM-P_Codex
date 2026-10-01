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
Windows 명령, 저장소에서 한 번에 설치, 기존 설치 갱신은 [설치 안내](https://github.com/TLAB-HGU/PIM-P_Codex/blob/dev/docs/installation.md)를 참고한다.

### 사용법

| 호출 | 모드 |
|---|---|
| `$pimp` 또는 `$pimp normal` | 같은 분야 대학원생·연구실용 |
| `$pimp easy` | 비전공자용. 핵심 논리·결과·한계를 유지하고 용어와 설명을 쉽게 |

Codex에서 논문 PDF를 첨부하고 “30분 발표자료 만들어줘”, “쉽게 설명하는 총 12장 발표자료로 만들어줘”라고 요청해도 동작한다.
스킬이 보이지 않으면 새 채팅을 열거나 Codex를 재시작한다. 별도 LLM API 키는 필요 없다.

PPTX 미리보기에는 LibreOffice와 한글 폰트가 필요하다. 설치 명령은 외부 도구 안내를 제공하며, 한글 표시는 실제 렌더로 확인한다.

개발·테스트·검증 자료는 `dev` 브랜치에 보관한다. `.github`은 자동 검증 설정이다.

[검증 기록](https://github.com/TLAB-HGU/PIM-P_Codex/blob/dev/docs/validation.md) · [개발 방법](https://github.com/TLAB-HGU/PIM-P_Codex/blob/dev/docs/installation.md#개발) · [변경 이력](https://github.com/TLAB-HGU/PIM-P_Codex/blob/dev/CHANGELOG.md)

[TLAB-HGU/PIM-P](https://github.com/TLAB-HGU/PIM-P) 기반 · [MIT License](LICENSE) · [원본 출처](skills/pimp/UPSTREAM.md)
