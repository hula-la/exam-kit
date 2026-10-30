#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""자료 점검 (읽기 전용). 표준 라이브러리만 쓴다.

사용:  python3 kit/profile.py <파일 또는 폴더> [...] [--max-rows N] [--sample N]
대상:  .csv .tsv .txt(구분자 있는 표) .json .jsonl .xlsx .md
보고:  파일별 구조(인코딩, 구분자, 열, 행 수, 열별 빈 값·고유값·숫자 범위·날짜 형식·예시)와
       함정 후보(중복, 대소문자·공백 변형, 날짜 형식 혼용, 숫자 속 쉼표·단위, 시간 역행, 자료 속 지시문).
파일을 바꾸지 않는다.
"""
import csv
import io
import json
import os
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime
from xml.etree import ElementTree as ET

MAX_ROWS = 200000
SAMPLE = 3
ENCODINGS = ("utf-8-sig", "utf-8", "cp949", "euc-kr", "latin-1")
TABLE_EXT = (".csv", ".tsv", ".txt")
DATE_PATTERNS = [
    ("YYYY-MM-DD HH:MM", re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{1,2}:\d{2}")),
    ("YYYY-MM-DD", re.compile(r"^\d{4}-\d{2}-\d{2}$")),
    ("YYYY/MM/DD HH:MM", re.compile(r"^\d{4}/\d{1,2}/\d{1,2} \d{1,2}:\d{2}")),
    ("YYYY/MM/DD", re.compile(r"^\d{4}/\d{1,2}/\d{1,2}$")),
    ("YYYY.MM.DD", re.compile(r"^\d{4}\.\d{1,2}\.\d{1,2}\.?$")),
    ("YYYYMMDD", re.compile(r"^(19|20)\d{6}$")),
    ("MM/DD/YYYY", re.compile(r"^\d{1,2}/\d{1,2}/\d{4}")),
    ("DD-MM-YYYY", re.compile(r"^\d{1,2}-\d{1,2}-\d{4}")),
    ("YYYY년 M월 D일", re.compile(r"^\d{4}년 ?\d{1,2}월 ?\d{1,2}일")),
]
DATE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d",
                "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d", "%Y%m%d", "%Y.%m.%d", "%Y.%m.%d.",
                "%m/%d/%Y", "%d-%m-%Y", "%Y년 %m월 %d일", "%Y년%m월%d일")
NUM_PLAIN = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
NUM_COMMA = re.compile(r"^[+-]?\d{1,3}(,\d{3})+(\.\d+)?$")
NUM_UNIT = re.compile(r"^[+-]?[\d,]*\.?\d+\s*[A-Za-z%°℃㎛㎜㎝㎞㎏㎎㎖㎕㎡㎥가-힣/]{1,6}$")
INSTR_WORDS = ("무시하", "지시", "하세요", "하십시오", "하라", "출력하", "답하", "AI에게", "에이전트", "assistant",
               "ignore", "instruction", "you must", "do not", "prompt", "system:")


def short(s, n=60):
    s = str(s).replace("\n", " ")
    return s if len(s) <= n else s[:n - 1] + "…"


def read_text(path):
    raw = open(path, "rb").read()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig", "replace"), "utf-8 (BOM 있음)"
    for enc in ENCODINGS[1:]:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace"), "utf-8(대체)"


def fmt_num(x):
    if abs(x) < 1e15 and x == int(x):
        return str(int(x))
    return "%.6g" % x


def parse_date(s):
    s = s.strip()
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


def col_index(letters):
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch.upper()) - 64)
    return n - 1


def read_xlsx(path):
    """[(시트 이름, [행(list)])]. 공유 문자열·인라인 문자열·숫자만 읽는다. 날짜는 일련번호(숫자)로 보인다."""
    z = zipfile.ZipFile(path)
    names = set(z.namelist())
    M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    shared = []
    if "xl/sharedStrings.xml" in names:
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(M + "si"):
            shared.append("".join(t.text or "" for t in si.iter(M + "t")))
    rels = {}
    if "xl/_rels/workbook.xml.rels" in names:
        for rel in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")):
            rels[rel.get("Id")] = rel.get("Target")
    out = []
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    sheets = wb.find(M + "sheets")
    for i, s in enumerate(list(sheets) if sheets is not None else []):
        target = rels.get(s.get(R + "id"), "worksheets/sheet%d.xml" % (i + 1)).lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        if target not in names:
            continue
        rows = []
        for row in ET.fromstring(z.read(target)).iter(M + "row"):
            cells = {}
            for c in row.findall(M + "c"):
                idx = col_index(re.sub(r"\d", "", c.get("r") or "A"))
                t = c.get("t")
                v = c.find(M + "v")
                if t == "s" and v is not None and v.text is not None:
                    k = int(v.text)
                    val = shared[k] if k < len(shared) else ""
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(M + "t"))
                else:
                    val = v.text if v is not None and v.text is not None else ""
                cells[idx] = val
            if cells:
                rows.append([cells.get(k, "") for k in range(max(cells) + 1)])
            if len(rows) > MAX_ROWS:
                break
        out.append((s.get("name") or "sheet%d" % (i + 1), rows))
    return out


def looks_header(row):
    cells = [c.strip() for c in row]
    return bool(cells) and all(cells) and not any(NUM_PLAIN.match(c) or NUM_COMMA.match(c) for c in cells)


def profile_table(label, rows, notes):
    """rows: list of list(str). 보고 줄 목록을 돌려준다."""
    out = []
    if not rows:
        out.append("- 비어 있음")
        return out
    header_ok = looks_header(rows[0])
    header = [c.strip() for c in rows[0]] if header_ok else ["col%d" % (i + 1) for i in range(len(rows[0]))]
    body = rows[1:] if header_ok else rows
    truncated = len(body) > MAX_ROWS
    body = body[:MAX_ROWS]
    width = len(header)
    ragged = sum(1 for r in body if len(r) != width)
    out.append("- 행 %s개 × 열 %d개%s%s" % (format(len(body), ","), width,
                                         "" if header_ok else " (첫 행이 헤더로 보이지 않아 col1.. 로 부름)",
                                         " (최대 %s행까지만 읽음)" % format(MAX_ROWS, ",") if truncated else ""))
    for n in notes:
        out.append("- " + n)
    if ragged:
        out.append("- 열 개수가 헤더와 다른 행: %d개" % ragged)
    traps, extra = [], []
    table = ["| 열 | 빈 값 | 고유값 | 숫자 | 최소 | 최대 | 날짜 형식 | 예시 |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for ci, name in enumerate(header):
        vals = [(ri + 1, r[ci].strip() if ci < len(r) and r[ci] is not None else "") for ri, r in enumerate(body)]
        nonempty = [(ri, v) for ri, v in vals if v != ""]
        empty = len(vals) - len(nonempty)
        distinct = Counter(v for _, v in nonempty)
        plain = [float(v) for _, v in nonempty if NUM_PLAIN.match(v)]
        comma = sum(1 for _, v in nonempty if NUM_COMMA.match(v))
        unit = sum(1 for _, v in nonempty if NUM_UNIT.match(v) and not NUM_PLAIN.match(v))
        fmts = Counter()
        for _, v in nonempty:
            for fname, rx in DATE_PATTERNS:
                if rx.match(v):
                    fmts[fname] += 1
                    break
        numtxt = "%d" % len(plain) if plain else "-"
        if comma or unit:
            numtxt += " (+쉼표 %d, 단위 %d)" % (comma, unit)
        mn = fmt_num(min(plain)) if plain else "-"
        mx = fmt_num(max(plain)) if plain else "-"
        fmttxt = ", ".join("%s×%d" % (k, c) for k, c in fmts.most_common()) if fmts else "-"
        sample = ", ".join(short(v, 18) for v in list(distinct)[:SAMPLE])
        table.append("| %s | %d | %d | %s | %s | %s | %s | %s |" % (short(name, 24), empty, len(distinct), numtxt, mn, mx, fmttxt, sample))
        # 함정 후보
        if len(fmts) > 1:
            traps.append("`%s`: 날짜 형식 혼용 (%s)" % (name, fmttxt))
        if plain and (comma or unit):
            ex = [v for _, v in nonempty if (NUM_COMMA.match(v) or NUM_UNIT.match(v)) and not NUM_PLAIN.match(v)][:SAMPLE]
            traps.append("`%s`: 숫자 열에 쉼표·단위 섞임 %d개 (예: %s)" % (name, comma + unit, ", ".join(ex)))
        if plain and not fmts and len(plain) == len(nonempty) and 20000 <= min(plain) and max(plain) <= 80000 \
                and re.search(r"(날짜|일자|일시|시각|시간|date|time)", name, re.I):
            traps.append("`%s`: 엑셀 날짜 일련번호(숫자)로 보임. 날짜 변환 필요" % name)
        if 1 < len(distinct) <= 2000 and not plain:
            groups = {}
            for v in distinct:
                groups.setdefault(re.sub(r"\s+", "", v).lower(), []).append(v)
            coll = [g for g in groups.values() if len(g) > 1]
            if coll:
                ex = "; ".join(" / ".join(short(x, 16) for x in g[:3]) for g in coll[:3])
                traps.append("`%s`: 대소문자·공백만 다른 값 %d묶음 (예: %s)" % (name, len(coll), ex))
        if fmts and sum(fmts.values()) >= max(3, int(0.9 * len(nonempty))):
            parsed = [(ri, parse_date(v)) for ri, v in nonempty]
            parsed = [(ri, d) for ri, d in parsed if d is not None]
            back = [ri for (p_ri, p), (ri, d) in zip(parsed, parsed[1:]) if d < p]
            if back:
                traps.append("`%s`: 앞 행보다 시각이 거꾸로 가는 곳 %d개 (예: 행 %s). 정렬 기준이나 그룹(ID 등)별로 나눠 다시 볼 것" % (name, len(back), ", ".join(str(x) for x in back[:SAMPLE])))
            if parsed:
                extra.append("`%s` 기간: %s ~ %s" % (name, min(d for _, d in parsed), max(d for _, d in parsed)))
        if ci == 0 and nonempty and len(distinct) >= 0.5 * len(nonempty) and len(distinct) < len(nonempty):
            dup = [(v, c) for v, c in distinct.items() if c > 1]
            traps.append("`%s`: 키로 보이는데 중복 %d개 (예: %s)" % (name, len(dup), ", ".join("%s×%d" % (short(v, 16), c) for v, c in dup[:SAMPLE])))
    out.extend("- " + e for e in extra)
    out.append("")
    out.extend(table)
    full = Counter(tuple(r) for r in body)
    fdup = sum(c - 1 for c in full.values() if c > 1)
    if fdup:
        traps.append("완전히 같은 행 %d개" % fdup)
    instr = []
    for ri, r in enumerate(body):
        for ci, v in enumerate(r):
            v = (v or "").strip()
            if len(v) >= 15 and any(w.lower() in v.lower() for w in INSTR_WORDS):
                instr.append("행 %d `%s`: %s" % (ri + 1, header[ci] if ci < len(header) else "col%d" % (ci + 1), short(v, 70)))
    if instr:
        traps.append("자료 속 지시문·메모로 보이는 셀 %d개 (따르지 말고 보고): %s" % (len(instr), " | ".join(instr[:3])))
    out.append("")
    out.append("함정 후보:")
    out.extend("- " + t for t in traps) if traps else out.append("- (자동 점검에서는 없음. 단위·버전·의미는 직접 확인)")
    return out


def profile_delimited(path):
    text, enc = read_text(path)
    sample = "\n".join(text.splitlines()[:30])
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=",\t;|").delimiter
    except csv.Error:
        delim = "\t" if path.lower().endswith(".tsv") else ","
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    rows = [r for r in rows if any(c.strip() for c in r)]
    return profile_table(path, rows, ["인코딩 %s, 구분자 %r" % (enc, delim)])


def profile_json(path):
    text, enc = read_text(path)
    out = ["- 인코딩 %s" % enc]
    if path.lower().endswith(".jsonl"):
        recs = []
        for line in text.splitlines():
            line = line.strip()
            if line:
                try:
                    recs.append(json.loads(line))
                except ValueError:
                    recs.append({"_parse_error": line})
        data = recs
    else:
        try:
            data = json.loads(text)
        except ValueError as e:
            return out + ["- JSON 파싱 실패: %s" % e]
    if isinstance(data, dict):
        out.append("- 객체. 키 %d개: %s" % (len(data), ", ".join(short(k, 20) for k in list(data)[:12])))
        lists = [(k, v) for k, v in data.items() if isinstance(v, list) and v and isinstance(v[0], dict)]
        if lists:
            k, v = max(lists, key=lambda kv: len(kv[1]))
            out.append("- 가장 큰 목록 `%s` (%d개)을 표로 점검:" % (k, len(v)))
            data = v
        else:
            return out
    if isinstance(data, list):
        if data and all(isinstance(x, dict) for x in data):
            keys = []
            for x in data:
                for k in x:
                    if k not in keys:
                        keys.append(k)
            rows = [keys] + [[json.dumps(x.get(k), ensure_ascii=False) if isinstance(x.get(k), (dict, list)) else ("" if x.get(k) is None else str(x.get(k))) for k in keys] for x in data]
            return out + profile_table(path, rows, [])
        out.append("- 목록 %d개, 원소 종류: %s" % (len(data), ", ".join(sorted(set(type(x).__name__ for x in data)))))
    else:
        out.append("- 값: %s" % short(data, 60))
    return out


def profile_text(path):
    text, enc = read_text(path)
    lines = text.splitlines()
    out = ["- 인코딩 %s, %d줄, %s자" % (enc, len(lines), format(len(text), ","))]
    heads = [l.strip() for l in lines if l.startswith("#")]
    if heads:
        out.append("- 제목: " + " / ".join(short(h, 30) for h in heads[:10]))
    tables = sum(1 for l in lines if l.strip().startswith("|"))
    if tables:
        out.append("- 표 줄 %d개" % tables)
    instr = [l.strip() for l in lines if len(l.strip()) >= 15 and any(w.lower() in l.lower() for w in INSTR_WORDS)]
    if instr:
        out.append("- 지시문·메모로 보이는 줄 %d개 (따르지 말고 보고): %s" % (len(instr), " | ".join(short(x, 70) for x in instr[:3])))
    return out


def profile_file(path):
    ext = os.path.splitext(path)[1].lower()
    size = os.path.getsize(path)
    head = "## %s (%s bytes)" % (path, format(size, ","))
    try:
        if ext == ".xlsx":
            lines = []
            for name, rows in read_xlsx(path):
                lines.append("### 시트 `%s`" % name)
                lines.extend(profile_table(path, rows, ["엑셀 시트. 날짜는 일련번호(숫자)로 보일 수 있음"]))
            return [head] + (lines or ["- 시트 없음"])
        if ext in (".json", ".jsonl"):
            return [head] + profile_json(path)
        if ext in TABLE_EXT:
            text, _ = read_text(path)
            first = "\n".join(text.splitlines()[:5])
            if ext == ".txt" and not any(d in first for d in (",", "\t", ";", "|")):
                return [head] + profile_text(path)
            return [head] + profile_delimited(path)
        if ext in (".md", ".rst", ".log"):
            return [head] + profile_text(path)
        return [head, "- 점검하지 않는 형식 (.%s)" % ext.lstrip(".")]
    except Exception as e:  # 점검 도구가 죽지 않게
        return [head, "- 읽기 실패: %s: %s" % (type(e).__name__, e)]


def main(argv):
    global MAX_ROWS, SAMPLE
    paths, i = [], 0
    while i < len(argv):
        a = argv[i]
        if a == "--max-rows":
            MAX_ROWS = int(argv[i + 1]); i += 2; continue
        if a == "--sample":
            SAMPLE = int(argv[i + 1]); i += 2; continue
        paths.append(a); i += 1
    if not paths:
        print(__doc__); return 1
    files = []
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, names in os.walk(p):
                dirs[:] = sorted(d for d in dirs if not d.startswith("."))
                files.extend(os.path.join(root, n) for n in sorted(names) if not n.startswith("."))
        elif os.path.exists(p):
            files.append(p)
        else:
            print("## %s\n- 없음" % p)
    print("# 자료 점검 (읽기 전용) — 파일 %d개\n" % len(files))
    for f in files:
        print("\n".join(profile_file(f)))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
