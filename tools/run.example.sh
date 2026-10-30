#!/bin/sh
# 처음부터 다시 실행하고 점검한다. verify/run.sh 로 복사해 과제에 맞게 고친다.
# 사용: sh verify/run.sh   (작업 폴더 루트에서)
set -e
cd "$(dirname "$0")/.."            # 작업 폴더 루트
rm -rf output && mkdir -p output    # 이전 출력 삭제 (계약에 없는 파일이 섞이지 않게). output/ 에 과제가 준 파일이 있거나 산출물 폴더가 다르면 이 줄을 고쳐 내 스크립트가 만든 파일만 지운다
python3 scripts/build.py            # 파이프라인 (과제에 맞게 고친다)
python3 kit/check.py verify/contract.json --log
