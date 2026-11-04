#!/bin/sh
# 처음부터 다시 실행하고 점검한다. verify/run.sh 로 복사해 과제에 맞게 고친다.
# 사용: sh verify/run.sh   (작업 폴더 루트에서)
set -e
cd "$(dirname "$0")/.."            # 작업 폴더 루트
mkdir -p output                   # 원문·사용자 파일을 보존. 생성 파일 갱신은 build.py에서 명시적으로 처리한다.
python3 scripts/build.py            # 파이프라인 (과제에 맞게 고친다)
python3 kit/check.py verify/contract.json --log
