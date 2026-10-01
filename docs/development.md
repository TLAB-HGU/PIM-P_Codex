# 개발·배포 구조

- `main`: `skills/pimp/`, README, LICENSE, `.gitignore`, `.github/workflows/tests.yml`만 배포한다.
- `dev`: 개발 스크립트, 자동 테스트, 개발 의존성, 변경 이력과 검증 문서를 보존한다.
- 스킬의 `scripts`, `references`, `agents`는 실행·분석·디자인·Codex 발견에 사용하는 리소스다.
  `LICENSE`와 `UPSTREAM.md`는 스킬을 따로 복사해도 원본 고지를 유지한다.

설치기는 `skills/pimp/scripts/install_skill.py`에 있어 `main`만 내려받아도 복사 설치와 환경 준비가 가능하다.
프로젝트 스킬의 자동 발견 링크는 배포하지 않는다. 개인 또는 프로젝트에 사용할 폴더를 설치 명령으로 지정한다.

## CI

`main`의 CI는 같은 저장소 `dev`의 검증된 고정 커밋에서 `scripts`, `tests`,
`requirements-dev.txt`만 임시로 가져온다. 검사 대상 `skills/pimp`는 현재 `main`의 파일을 사용한다.
검증 도구를 가져온 후 스킬의 메타데이터·배포 파일 목록·원본 고지·자동 테스트·독립 설치를 검사한다.
개발 스킬을 검사 대상으로 덮어쓰지 않는다. `dev`의 CI는 해당 브랜치의 파일을 직접 검사한다.

## 수정과 배포

`dev`에서 코드·테스트를 수정하고 [설치 안내의 개발 검사](installation.md#개발)를 실행한다.
배포할 때 검증된 `skills/pimp` 변경을 `main`에 적용하고 README를 갱신한다.
검증 도구가 바뀌면 `main` 워크플로의 두 번째 checkout `ref`를 새 `dev` 커밋 SHA로 갱신한다.
`main`에는 배포 파일 목록 밖의 파일을 추가하지 않는다. CI의 `--distribution` 검사가 이를 확인한다.

버전 태그는 `main`에 붙인다. 개인 저장소에 `main`, `dev`, 태그를 먼저 푸시해 CI를 확인한 뒤
동일한 세 참조를 랩실 저장소로 푸시한다. 발표 결과·가상환경·Node 패키지·개인 경로 기록은 추적하지 않는다.
