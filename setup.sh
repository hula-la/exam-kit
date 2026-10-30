#!/bin/sh
# exam-kit setup: 작업 폴더에 작업 규칙(AGENTS.md 절), 스킬, 메모 양식, 점검 도구를 넣는다.
# 사용: sh /tmp/kit/setup.sh [작업 폴더]   (기본: 현재 폴더. 작업 폴더 루트에서 실행한다)
# 기존 파일은 덮어쓰지 않는다. 다시 실행해도 안전하다. 네트워크를 쓰지 않는다.
set -u
KIT=$(cd "$(dirname "$0")" && pwd)
WS=$(cd "${1:-$PWD}" && pwd) || exit 1
cd "$WS" || exit 1
MARK="exam-kit:begin"

say() { printf '%s\n' "$*"; }

say "== 환경 =="
for c in git python3 node codex; do
  if command -v "$c" >/dev/null 2>&1; then
    say "  $c: $("$c" --version 2>&1 | head -1)"
  else
    say "  $c: 없음"
  fi
done
if [ -d .git ]; then say "  git 저장소: 있음 ($WS)"; else say "  git 저장소: 없음 ($WS)"; fi

say "== 설치 =="
# 1. AGENTS.md: 있으면 뒤에 절을 붙이고, 없으면 만든다. 표식이 이미 있으면 건너뛴다.
if [ -f AGENTS.md ] && grep -q "$MARK" AGENTS.md; then
  say "  AGENTS.md: 이미 설치됨"
elif [ -f AGENTS.md ]; then
  { printf '\n\n'; cat "$KIT/AGENTS.md"; } >> AGENTS.md
  say "  AGENTS.md: 기존 파일 뒤에 작업 규칙 절을 추가"
else
  cp "$KIT/AGENTS.md" AGENTS.md
  say "  AGENTS.md: 새로 만듦"
fi

# 2. 스킬 → .agents/skills/<이름>/
mkdir -p .agents/skills
for d in "$KIT"/skills/*/; do
  n=$(basename "$d")
  if [ -e ".agents/skills/$n" ]; then
    say "  skill $n: 이미 있음"
  else
    cp -R "$d" ".agents/skills/$n"
    say "  skill $n: 설치"
  fi
done

# 3. 메모 양식 → notes/
mkdir -p notes
for f in "$KIT"/templates/*.md; do
  n=$(basename "$f")
  if [ -e "notes/$n" ]; then
    say "  notes/$n: 이미 있음"
  else
    cp "$f" "notes/$n"
    say "  notes/$n: 만듦"
  fi
done

# 4. 점검 도구 → kit/
mkdir -p kit
for f in "$KIT"/tools/*; do
  [ -f "$f" ] || continue
  n=$(basename "$f")
  if [ -e "kit/$n" ]; then
    say "  kit/$n: 이미 있음"
  else
    cp "$f" "kit/$n"
    say "  kit/$n: 복사"
  fi
done

# 5. .gitignore: 미리보기 산출물과 파이썬 캐시가 커밋·diff 에 섞이지 않게 (없는 줄만 덧붙인다)
touch .gitignore
# 마지막 줄에 개행이 없으면 보태서, 덧붙이는 규칙이 기존 마지막 규칙에 붙지 않게 한다
[ -s .gitignore ] && [ -n "$(tail -c 1 .gitignore)" ] && printf '\n' >> .gitignore
for p in "preview/" "__pycache__/"; do
  if grep -qx "$p" .gitignore 2>/dev/null; then
    say "  .gitignore: $p 이미 있음"
  else
    printf '%s\n' "$p" >> .gitignore
    say "  .gitignore: $p 추가"
  fi
done

say "== 다음 =="
say "  1. codex 는 작업 폴더 루트($WS)에서 시작한다. 하위 폴더에서 시작하면 AGENTS.md 를 못 읽을 수 있다. setup 전에 켜 둔 codex 는 /quit 로 끄고 다시 켠다(AGENTS.md 는 시작 때 한 번만 읽는다)."
say "  2. 과제 안내를 읽고 notes/requirements.md 를 채운 뒤 notes/checklist.md 순서대로 간다."
say "  3. 자료 파일이 있으면 점검: python3 kit/profile.py <자료 폴더 또는 파일>   (Codex 에 \$data-audit 를 맡겨도 된다. 둘 다 읽기 전용)"
