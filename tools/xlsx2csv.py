#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""엑셀(.xlsx) 시트를 CSV로 뽑는다. 표준 라이브러리만 쓴다(pandas·openpyxl 불필요).

사용: python3 kit/xlsx2csv.py <파일.xlsx> [...] [--out 폴더] [--serial-dates]
  시트마다 <폴더>/<파일이름>__<시트>.csv (UTF-8)를 만든다. 기본 폴더는 파일이 있는 곳.
  --serial-dates: 열 이름에 날짜·일자·일시·시각·date·time 이 들어가고 값이 엑셀 날짜 일련번호(20000~80000)로 보이면
                  YYYY-MM-DD[ HH:MM:SS]로 바꾼다. 그 밖의 날짜 서식은 읽지 않으므로 숫자로 남는다.
공유 문자열·인라인 문자열·숫자·수식의 캐시 값을 읽는다. 병합 셀은 왼쪽 위 칸에만 값이 있다.
"""
import csv
import os
import re
import sys
import zipfile
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

DATE_COL = re.compile(r"(날짜|일자|일시|시각|시간|date|time)", re.I)


def col_index(letters):
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch.upper()) - 64)
    return n - 1


def read_xlsx(path):
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
            rows.append([cells.get(k, "") for k in range(max(cells) + 1)] if cells else [])
        out.append((s.get("name") or "sheet%d" % (i + 1), rows))
    return out


def serial_to_date(v):
    try:
        f = float(v)
    except ValueError:
        return v
    if not (20000 <= f <= 80000):
        return v
    d = datetime(1899, 12, 30) + timedelta(days=f)
    return d.strftime("%Y-%m-%d") if abs(f - round(f)) < 1e-9 else d.strftime("%Y-%m-%d %H:%M:%S")


def main(argv):
    files, out_dir, serial = [], None, False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--out":
            out_dir = argv[i + 1]; i += 1
        elif a == "--serial-dates":
            serial = True
        elif a in ("-h", "--help"):
            print(__doc__); return 0
        else:
            files.append(a)
        i += 1
    if not files:
        print(__doc__); return 1
    print("| 파일 | 시트 | 행 | 열 | CSV |")
    print("| --- | --- | --- | --- | --- |")
    for f in files:
        try:
            sheets = read_xlsx(f)
        except Exception as e:
            print("| %s | (읽기 실패: %s: %s) | | | |" % (f, type(e).__name__, e))
            continue
        dest = out_dir or os.path.dirname(os.path.abspath(f))
        os.makedirs(dest, exist_ok=True)
        stem = os.path.splitext(os.path.basename(f))[0]
        for name, rows in sheets:
            width = max((len(r) for r in rows), default=0)
            rows = [r + [""] * (width - len(r)) for r in rows]
            if serial and rows:
                header = rows[0]
                for ci, h in enumerate(header):
                    if DATE_COL.search(str(h)):
                        for r in rows[1:]:
                            r[ci] = serial_to_date(r[ci])
            safe = re.sub(r"[^\w가-힣.-]+", "_", name)
            path = os.path.join(dest, "%s__%s.csv" % (stem, safe))
            with open(path, "w", encoding="utf-8", newline="") as fh:
                csv.writer(fh).writerows(rows)
            print("| %s | %s | %d | %d | %s |" % (f, name, max(len(rows) - 1, 0), width, path))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
