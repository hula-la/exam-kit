#!/bin/sh
# 사용: sh /kit-source/setup.sh [작업 폴더]
set -eu
KIT_SOURCE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' 'Python 3이 필요합니다. 설치 없이 guide/index.html과 prompts/를 사용할 수 있습니다.' >&2
  exit 2
fi
exec python3 "$KIT_SOURCE/install.py" "${1:-$PWD}"
