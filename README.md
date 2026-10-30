# exam-kit

웹 IDE + Codex CLI 환경에서 과제를 풀 때 쓰는 범용 작업 보조 도구다. 과제 내용과 무관한 작업 규칙, 스킬, 메모 양식, 점검·미리보기 스크립트만 들어 있다. 결과물을 대신 만들지 않고, 과정(이해, 질문, 점검, 검증, 기록)을 빠뜨리지 않게 돕는다.

## 쓰는 법

작업 폴더 루트의 터미널에서:

```sh
rm -rf /tmp/kit; git clone https://github.com/hula-la/exam-kit /tmp/kit && sh /tmp/kit/setup.sh
```

`setup.sh`가 작업 폴더에 넣는 것:

| 넣는 것 | 위치 | 내용 |
| --- | --- | --- |
| 작업 규칙 | `AGENTS.md` 뒤에 절 추가(없으면 생성) | 읽기 전용 점검 먼저, 다시 실행할 수 있는 스크립트, 검증 수치와 함께 보고, 자료 속 지시문은 데이터로만, 상태를 바꾸는 MCP 도구는 명시 지시 때만, `kit/` 도구 재사용 |
| 스킬 6개 | `.agents/skills/` | `task-brief`(과제 브리프), `data-audit`(자료 점검), `stakeholder-dialog`(담당자 대화), `grill-me`(계획 심문. 외부 스킬, MIT), `verify-harness`(검증 하네스), `handover-docs`(문서) |
| 메모 양식 | `notes/` | `requirements.md`, `decisions.md`, `verification.md`, `checklist.md` |
| 도구 | `kit/` | `profile.py`(자료 점검), `xlsx2csv.py`(엑셀→CSV), `check.py`(출력 계약 점검), `preview.py`(HTML 미리보기), 검증 예시 3개 |

기존 파일은 덮어쓰지 않는다. 다시 실행해도 안전하다. 네트워크는 clone 한 번만 쓰고, 패키지를 설치하지 않는다. 모든 스크립트는 파이썬 표준 라이브러리만 쓴다. 위 표 밖에서 손대는 파일은 `.gitignore` 하나다: `preview/`와 `__pycache__/` 두 줄을 없을 때만 덧붙인다(미리보기 산출물이 커밋·diff에 섞이지 않게).

## 흐름

1. `$task-brief` → `notes/brief.md`. 다른 터미널 탭에서 `python3 kit/preview.py --serve`를 띄우면 브라우저 미리보기(출력된 PORT, 기본 8787, URL `/`)에서 README·notes·검증 결과·출력 CSV를 읽을 수 있다. 편집기에는 마크다운 미리보기가 없어서 HTML로 만든다.
2. `$stakeholder-dialog`로 담당자에게 물을 메시지 초안을 받아 내 말로 고쳐 보내고, 답을 `notes/decisions.md`에 적는다. 담당자 역할이 없는 과제면 질문을 가정으로 적고 진행한다.
3. `$data-audit` → 자료 함정 보고 → 규칙 질문.
4. `$grill-me` → 내 구현 계획을 라운드 단위 질문으로 다듬는다(사용자가 직접 부를 때만 뜬다). 결정은 `notes/decisions.md`로, 답하지 못한 질문은 담당자에게. 그다음 합의문.
5. 구현(스크립트).
6. `$verify-harness` → `verify/contract.json`(안내의 근거 문장 포함)과 `verify/custom_checks.py`(파이프라인과 다른 경로의 교차 검증) → `python3 kit/check.py --log`는 사람이 직접 실행.
7. `$handover-docs` → README. 미리보기로 읽어 본다.

## 원칙

- 과제 안내와 작업 폴더에 원래 있던 지시가 항상 우선한다. `AGENTS.md`의 추가 절도 그렇게 적혀 있다.
- Codex는 작업 폴더 루트에서 시작한다. Codex는 루트에서 현재 폴더까지의 `AGENTS.md`와 `.agents/skills` 외에 전역 `~/.codex/AGENTS.md`(있으면 `AGENTS.override.md`), `~/.agents/skills`, `/etc/codex/skills`, 내장 스킬도 읽는다. 전역이 앞, 작업 폴더 파일이 뒤에 이어 붙는다. 환경에 미리 깔린 규칙·스킬이 있는지는 `/status`의 Agents.md 줄과 `/skills` 목록에 kit 것 외의 항목이 있는지로 본다.
- 스킬은 `/skills` 또는 `$이름`으로 부른다. 설명에 맞는 요청이면 Codex가 알아서 고르기도 한다.
- 점검이 통과해도 "검증 완료"라고 쓰지 않는다. 수치로 쓴다.

## 구성

```
setup.sh                 설치 스크립트 (POSIX sh)
AGENTS.md                작업 규칙 절 (작업 폴더 AGENTS.md 뒤에 붙는다)
skills/<이름>/SKILL.md   스킬 6개 (grill-me 폴더에는 원저자 LICENSE 와 agents/openai.yaml 이 같이 있다)
templates/*.md           메모 양식 → notes/
tools/                   도구와 예시 → kit/
```

## 외부 스킬

넣은 것은 `grill-me` 하나다. 출처는 [mattpocock/skills](https://github.com/mattpocock/skills)(MIT). 라이선스 전문을 스킬 폴더에 같이 둔다. 원본은 `grill-me`(진입점)와 `grilling`(본문) 두 스킬인데, 스킬이 스킬을 부르는 연결이 환경에 따라 실패한다고 원저자 문서에 적혀 있어 한 파일로 합쳤다. 원문에서 바꾼 곳은 사실 확인에 하위 에이전트를 쓰라는 문장 하나(직접 읽기 전용 명령으로 확인하도록)이고, 맨 아래 "이 kit에서" 절(사용자 언어, 시간 상한 제안, 끝날 때 결정 표와 미답 질문 출력, 파일 수정 금지)은 추가다. 원저자 문서가 경고하는 실패는 사용자가 "예, 예"만 하는 것이다. 답마다 이유를 말하고, 모르면 모른다고 하고, 적어도 하나는 반박해야 세션이 값을 한다.

넣지 않은 것: 공개된 외부 스킬(openai/skills의 pdf·playwright, anthropics/skills의 pdf·xlsx 등)은 넣지 않았다. pdf·xlsx(anthropics)는 frontmatter에 Proprietary 라이선스라 재배포할 수 없고, 나머지는 pip·npx 설치가 필요해 패키지 설치가 안 되는 환경에서는 쓸 수 없다. 엑셀은 `kit/xlsx2csv.py`로 대신한다. PDF는 `pdftotext` → `python3 -c "import pypdf"` 순으로 있는 것을 쓰고, 없으면 설치 여부를 사용자에게 묻는다. obra/superpowers의 `brainstorming`은 같은 목적이지만 그 프레임워크의 다른 스킬·하위 에이전트·설계 문서 승인 관문에 묶여 있어 짧은 작업에 맞지 않고, `verification-before-completion`은 `AGENTS.md` 4항과 `verify-harness`가 이미 하는 말이라 넣지 않았다.
