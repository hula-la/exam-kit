#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""출력 계약 점검. 표준 라이브러리만 쓴다.

사용: python3 kit/check.py [verify/contract.json] [--run] [--log [notes/verification.md]] [--out verify/last_result.md] [--root .]

계약(JSON) 예: kit/contract.example.json
  "run":    ["python3 scripts/build.py"]   --run 을 줄 때만 순서대로 실행한다(출력을 덮어쓰므로 기본은 실행 안 함)
  "files":  [{"path": ..., "why": 안내의 근거 문장, "min_bytes", "encoding", "delimiter",
              "columns": [...], "exact_columns": false, "min_rows", "max_rows",
              "unique": [열 또는 [열,열]], "not_empty": [열...], "sorted": [[열, "asc"|"desc"]],
              "contains": [문구...], "json_keys": [키...]}]
  "custom": "verify/custom_checks.py"       def checks() -> [(이름, True|False|None, 근거), ...]
판정: 통과 / 실패 / 보류(None, 판정 불가). 실패가 하나라도 있으면 종료 코드 1.
"""
import csv
import importlib.util
import io
import json
import os
import subprocess
import sys
import time
from datetime import datetime

PASS, FAIL, HOLD = "통과", "실패", "보류"


def mark(ok):
    return HOLD if ok is None else (PASS if ok else FAIL)


def as_num(s):
    try:
        return float(str(s).replace(",", ""))
    except ValueError:
        return None


def check_file(spec, root):
    items = []
    path = spec.get("path", "")
    why = spec.get("why", "")
    full = os.path.join(root, path)

    def add(name, ok, detail):
        items.append(("%s: %s" % (path, name), ok, detail))

    if not os.path.isfile(full):
        add("존재", False, "파일이 없음" + (" (근거: %s)" % why if why else ""))
        return items
    size = os.path.getsize(full)
    add("존재", True, "%s bytes" % format(size, ",") + (" (근거: %s)" % why if why else ""))
    if spec.get("min_bytes") is not None:
        add("크기 ≥ %s" % spec["min_bytes"], size >= spec["min_bytes"], "%s bytes" % format(size, ","))
    enc = spec.get("encoding", "utf-8")
    raw = open(full, "rb").read()
    try:
        text = raw.decode(enc)
        if "encoding" in spec:
            add("인코딩 %s" % enc, True, "디코딩 성공" + (" (BOM 있음)" if text.startswith("﻿") else ""))
    except UnicodeDecodeError as e:
        add("인코딩 %s" % enc, False, "디코딩 실패: %s" % str(e)[:80])
        text = raw.decode(enc, "replace")
    text = text.lstrip("﻿")  # utf-8-sig(엑셀용)로 저장된 파일의 BOM 이 첫 열 이름에 붙지 않게
    for s in spec.get("contains", []):
        add("문구 포함 '%s'" % s, s in text, "있음" if s in text else "없음")
    if spec.get("json_keys") is not None:
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                missing = [k for k in spec["json_keys"] if k not in data]
                add("JSON 키", not missing, ("없는 키: " + ", ".join(missing)) if missing else "모두 있음")
            else:
                add("JSON 키", None, "최상위가 객체가 아님(%s)" % type(data).__name__)
        except ValueError as e:
            add("JSON 파싱", False, str(e)[:80])
    table_keys = ("columns", "min_rows", "max_rows", "unique", "not_empty", "sorted", "delimiter")
    if any(k in spec for k in table_keys):
        delim = spec.get("delimiter") or ("\t" if path.lower().endswith(".tsv") else ",")
        rows = [r for r in csv.reader(io.StringIO(text), delimiter=delim) if any(c.strip() for c in r)]
        if not rows:
            add("표", False, "행이 없음")
            return items
        header = [c.strip() for c in rows[0]]
        body = rows[1:]
        if "columns" in spec:
            want = spec["columns"]
            missing = [c for c in want if c not in header]
            if spec.get("exact_columns"):
                ok = header == want
                add("열 이름(정확히)", ok, "일치" if ok else "실제: %s" % header)
            else:
                add("필수 열", not missing, ("없는 열: " + ", ".join(missing)) if missing else "모두 있음 (열 %d개)" % len(header))
        n = len(body)
        if spec.get("min_rows") is not None:
            add("행 ≥ %s" % spec["min_rows"], n >= spec["min_rows"], "%s행" % format(n, ","))
        if spec.get("max_rows") is not None:
            add("행 ≤ %s" % spec["max_rows"], n <= spec["max_rows"], "%s행" % format(n, ","))
        idx = {h: i for i, h in enumerate(header)}

        def col(r, c):
            return r[idx[c]].strip() if c in idx and idx[c] < len(r) else ""

        for cols in spec.get("unique", []):
            cols = [cols] if isinstance(cols, str) else list(cols)
            label = "고유 " + "+".join(cols)
            if any(c not in idx for c in cols):
                add(label, None, "열이 없음")
                continue
            seen, dups = set(), 0
            for r in body:
                k = tuple(col(r, c) for c in cols)
                if k in seen:
                    dups += 1
                seen.add(k)
            add(label, dups == 0, "중복 %d개" % dups)
        for c in spec.get("not_empty", []):
            if c not in idx:
                add("빈 값 없음 %s" % c, None, "열이 없음")
                continue
            empties = sum(1 for r in body if col(r, c) == "")
            add("빈 값 없음 %s" % c, empties == 0, "빈 값 %d개" % empties)
        for rule in spec.get("sorted", []):
            if isinstance(rule, list):
                c, order = rule[0], (rule[1] if len(rule) > 1 else "asc")
            else:
                c, order = rule, "asc"
            label = "정렬 %s %s" % (c, order)
            if c not in idx:
                add(label, None, "열이 없음")
                continue
            vals = [col(r, c) for r in body]
            nums = [as_num(v) for v in vals]
            keys = nums if nums and all(x is not None for x in nums) else vals
            bad = sum(1 for a, b in zip(keys, keys[1:]) if (a > b if order == "asc" else a < b))
            add(label, bad == 0, "어긋난 곳 %d개" % bad)
    return items


def run_cmds(cmds, root):
    items = []
    for cmd in cmds:
        t = time.time()
        try:
            p = subprocess.run(cmd, shell=True, cwd=root, capture_output=True, text=True, timeout=900)
            tail = (p.stderr or p.stdout).strip().splitlines()[-1:]
            items.append(("실행: %s" % cmd, p.returncode == 0,
                          "rc=%d, %.1f초" % (p.returncode, time.time() - t) + (", " + tail[0][:80] if tail else "")))
        except subprocess.TimeoutExpired:
            items.append(("실행: %s" % cmd, False, "900초 초과"))
    return items


def run_custom(path, root):
    full = os.path.join(root, path)
    if not os.path.isfile(full):
        return [("교차 검증 %s" % path, None, "파일이 없음")]
    sys.dont_write_bytecode = True  # verify/__pycache__ 를 만들지 않는다(git diff 에 섞이지 않게)
    try:
        spec = importlib.util.spec_from_file_location("custom_checks", full)
        mod = importlib.util.module_from_spec(spec)
        cwd = os.getcwd()
        os.chdir(root)
        try:
            spec.loader.exec_module(mod)
            res = list(mod.checks())
        finally:
            os.chdir(cwd)
    except Exception as e:  # 점검 스크립트의 오류는 실패로 기록
        return [("교차 검증 %s" % path, False, "%s: %s" % (type(e).__name__, str(e)[:100]))]
    items = []
    for r in res:
        try:
            name, ok, detail = r[0], r[1], (r[2] if len(r) > 2 else "")
        except (TypeError, IndexError):
            name, ok, detail = str(r), None, "형식 오류((이름, 판정, 근거) 가 아님)"
        items.append(("교차 검증: %s" % name, ok, str(detail)))
    return items


def main(argv):
    contract, root, out, log, do_run = "verify/contract.json", ".", "verify/last_result.md", None, False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--run":
            do_run = True
        elif a == "--root":
            root = argv[i + 1]; i += 1
        elif a == "--out":
            out = argv[i + 1]; i += 1
        elif a == "--log":
            log = "notes/verification.md"
            if i + 1 < len(argv) and argv[i + 1].endswith(".md"):
                log = argv[i + 1]; i += 1
        elif a in ("-h", "--help"):
            print(__doc__); return 0
        else:
            contract = a
        i += 1
    cpath = os.path.join(root, contract)
    if not os.path.isfile(cpath):
        print("계약 파일이 없음: %s  (기준: kit/contract.example.json)" % cpath); return 2
    try:
        c = json.load(open(cpath, encoding="utf-8"))
    except ValueError as e:
        print("계약 JSON 오류: %s" % e); return 2
    items = []
    if c.get("run"):
        items += run_cmds(c["run"], root) if do_run else [("실행 %d개" % len(c["run"]), None, "--run 을 주지 않아 실행하지 않음(출력을 덮어쓰므로)")]
    for spec in c.get("files", []):
        items += check_file(spec, root)
    if c.get("custom"):
        items += run_custom(c["custom"], root)
    n = len(items)
    p = sum(1 for _, ok, _ in items if ok is True)
    f = sum(1 for _, ok, _ in items if ok is False)
    h = n - p - f
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = ["# %s" % c.get("title", "출력 계약 점검"), "", "- 계약: `%s`  - 실행 시각: %s" % (contract, now),
             "- **%d개 중 통과 %d, 실패 %d, 보류 %d**" % (n, p, f, h), "",
             "| # | 항목 | 판정 | 근거 |", "| --- | --- | --- | --- |"]
    for k, (name, ok, detail) in enumerate(items, 1):
        lines.append("| %d | %s | %s | %s |" % (k, name.replace("|", "\\|"), mark(ok), str(detail).replace("|", "\\|").replace("\n", " ")))
    report = "\n".join(lines) + "\n"
    print(report)
    opath = os.path.join(root, out)
    os.makedirs(os.path.dirname(opath) or ".", exist_ok=True)
    open(opath, "w", encoding="utf-8").write(report)
    print("저장: %s" % out)
    if log:
        lpath = os.path.join(root, log)
        os.makedirs(os.path.dirname(lpath) or ".", exist_ok=True)
        if not os.path.exists(lpath):
            open(lpath, "w", encoding="utf-8").write("# 검증 기록\n\n| 시각 | 무엇을 | 방법 | 결과(수치) | 판정 |\n| --- | --- | --- | --- | --- |\n")
        with open(lpath, "a", encoding="utf-8") as fh:
            fh.write("| %s | 출력 계약 점검 | kit/check.py %s | 통과 %d/%d, 실패 %d, 보류 %d | %s |\n" % (now, contract, p, n, f, h, "FAIL" if f else "PASS"))
        print("기록: %s" % log)
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
