# kit/

공개 저장소 github.com/hula-la/exam-kit 에서 가져온 범용 점검 도구. 과제 내용과 무관하고, 표준 라이브러리만 쓴다.

| 명령 | 하는 일 |
| --- | --- |
| `python3 kit/profile.py <자료 폴더 또는 파일>` | 자료 점검(읽기 전용): 인코딩, 열·행, 중복, 날짜 형식 혼용, 단위, 시간 역행, 자료 속 지시문. 문서(MD, TXT)는 분량·제목·지시문 |
| `python3 kit/xlsx2csv.py 파일.xlsx --out /tmp/xlsx [--serial-dates]` | 엑셀 시트를 CSV로(pandas·openpyxl 없이). `--out`이 없으면 원본 옆에 생기므로 자료 폴더 밖을 지정한다 |
| `python3 kit/check.py [verify/contract.json] [--run] [--log]` | 출력 계약 점검 → `verify/last_result.md`. `--log`면 `notes/verification.md`에 한 줄 추가(다른 파일에 쓰려면 `--log 경로.md`). 계약에 `run`이 있고 `--run`을 안 주면 '실행 N개' 항목이 보류 한 줄로 나온다(정상. `--run`을 주면 그 명령을 먼저 실행하고 출력을 덮어쓴다). 처음부터 다시 만들어 점검하려면 `sh verify/run.sh`(예시는 `output/`을 지우고 다시 만든다. 지우면 안 되는 파일이 거기 있으면 `rm -rf output &&` 부분만 뺀다) |
| `python3 kit/preview.py [경로...] [--serve [PORT]]` | README·notes·verify·output을 HTML 한 장으로(경로를 주면 그것만 본다. 출력 폴더가 `output/`이 아니면 `README.md notes verify/last_result.md <출력 폴더>`처럼 전부 적는다). `--serve`면 PORT(기본 8787)로 브라우저 미리보기에서 본다 |

예시 파일: `contract.example.json`, `custom_checks.example.py`, `run.example.sh` → `verify/` 아래에 복사해 과제에 맞게 고친다.
