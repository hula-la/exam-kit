# 표준 라이브러리 작업 도구

| 명령 | 용도 |
|---|---|
| `python3 kit/profile.py <자료>` | 원문을 고치지 않고 구조·단위·누락·중복 등을 점검 |
| `python3 kit/xlsx2csv.py 파일.xlsx --out 작업폴더` | XLSX를 별도 위치의 CSV로 변환. 원본 옆 출력은 피함 |
| `python3 kit/check.py [verify/contract.json] [--run] [--log [경로.md]]` | 형식 계약·선택적 교차 검증 → verify/last_result.md. --log 기본은 notes/work.md |
| `python3 kit/preview.py [경로…] [--serve [PORT]] [--host HOST]` | README·notes·검증·output을 읽는 HTML → preview/index.html |

check 종료 코드: **0 실행한 검사 모두 통과**, **1 실패**, **2 보류·검사 없음·설정 오류**. `run`을 적고 `--run`을 주지 않으면 실행 보류로 표시합니다. `--run`은 계약의 명령을 실행하므로 자신의 승인된 코드인지 확인합니다. `custom`도 Python 코드를 실행합니다. 형식 검사는 의미·권한·알고리즘 최적성을 대신 검증하지 않습니다.

`contract.example.json`, `custom_checks.example.py`, `run.example.sh`는 예시입니다. 실제 과제·합의한 규칙에 맞춰 verify/ 아래에 필요한 것만 사용합니다. 예시 run은 output/을 일괄 삭제하지 않습니다.

미리보기 서버 기본은 **127.0.0.1:8787**입니다. 웹 IDE가 외부 바인딩을 요구하고 해당 환경에서 허용된 경우에만 `--host 0.0.0.0`을 지정합니다. 서버를 열지 않아도 생성 HTML을 읽을 수 있습니다. 작업 경로를 지정하면 기본 목록 대신 그 경로만 표시합니다.

요청문은 kit/prompts/, 범용 가이드는 kit/guide/index.html, 선택 양식은 kit/templates/에 있습니다.
