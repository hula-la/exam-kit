#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""노트·결과물을 HTML 한 장으로 만들어 브라우저 미리보기에서 읽는다. 표준 라이브러리만 쓴다.

사용: python3 kit/preview.py [경로...] [--out preview] [--serve [PORT]] [--host HOST] [--rows 200] [--title 제목]
기본 경로(있는 것만): README.md notes verify/last_result.md output
  경로를 하나라도 주면 기본 경로 대신 그것만 본다. 출력 폴더가 output/ 이 아니면 전부 적는다:
  python3 kit/preview.py README.md notes verify/last_result.md <출력 폴더> --serve
  .md → 렌더(제목, 목록, 표, 코드, 인용, 굵게, 링크)   .csv/.tsv → 표(앞 --rows 행)   .json/.txt/.log → 그대로
--serve: 기본 127.0.0.1:8787. 웹 IDE에서 외부 바인딩이 필요하고 허용된 경우 --host 0.0.0.0을 지정한다. / 를 열 때마다 다시 만든다.
"""
import csv
import html
import io
import os
import re
import sys
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

DEFAULT_PATHS = ["README.md", "notes", "verify/last_result.md", "output"]
EXTS = (".md", ".csv", ".tsv", ".json", ".txt", ".log")
ENCODINGS = ("utf-8", "cp949", "euc-kr", "latin-1")
MAX_FILES = 60
MAX_BYTES = 3 * 1024 * 1024
CONFIG = {"paths": DEFAULT_PATHS, "out": "preview", "rows": 200, "title": "작업 미리보기"}

INLINE_CODE = re.compile(r"`([^`]+)`")
BOLD = re.compile(r"\*\*(.+?)\*\*")
ITALIC = re.compile(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])")
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
CSS = """
body{font-family:-apple-system,"Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",sans-serif;line-height:1.55;color:#1b1f23;background:#f6f7f9;margin:0}
main{max-width:1040px;margin:0 auto;padding:16px 20px 60px}
nav{position:sticky;top:0;background:#fff;border-bottom:1px solid #d8dbe0;padding:8px 20px;font-size:14px}
nav a{margin-right:14px;color:#0b57d0;text-decoration:none}
section{background:#fff;border:1px solid #e1e4e8;border-radius:8px;padding:18px 22px;margin:18px 0}
section>h2.file{font-size:15px;color:#555;margin:-6px 0 12px;font-weight:600}
h1{font-size:24px}h2{font-size:20px}h3{font-size:17px}
table{border-collapse:collapse;margin:10px 0;font-size:14px;max-width:100%;display:block;overflow-x:auto}
th,td{border:1px solid #d0d4da;padding:5px 9px;vertical-align:top;white-space:nowrap}th{background:#f0f2f5}
td.wrap,th.wrap{white-space:normal}
pre{background:#f0f2f5;padding:10px 12px;overflow-x:auto;border-radius:6px;font-size:13px}
code{background:#f0f2f5;padding:1px 4px;border-radius:4px;font-size:0.92em}
pre code{background:none;padding:0}
blockquote{border-left:4px solid #c9ced6;margin:8px 0;padding:4px 12px;color:#444}
.note{color:#666;font-size:13px}
.pass{color:#137333;font-weight:600}.fail{color:#c5221f;font-weight:600}.hold{color:#9a6700;font-weight:600}
footer{color:#777;font-size:12px;margin-top:30px}
"""


def read_text(path):
    raw = open(path, "rb").read()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig", "replace"), "utf-8 (BOM)"
    for enc in ENCODINGS:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace"), "utf-8(대체)"


def safe_link(match):
    label, url = match.group(1), html.unescape(match.group(2))
    try:
        scheme = urlsplit(url).scheme.lower()
    except ValueError:
        return label
    if scheme not in ('', 'http', 'https', 'mailto') or any(ord(c) < 32 for c in url) or '\\' in url:
        return label
    return '<a href="%s">%s</a>' % (html.escape(url, quote=True), label)


def inline(s):
    s = html.escape(s, quote=False)
    s = INLINE_CODE.sub(lambda m: "<code>%s</code>" % m.group(1), s)
    s = BOLD.sub(r"<strong>\1</strong>", s)
    s = ITALIC.sub(r"<em>\1</em>", s)
    s = LINK.sub(safe_link, s)
    s = s.replace("[ ]", "☐").replace("[x]", "☑").replace("[X]", "☑")
    for word, cls in (("통과", "pass"), ("실패", "fail"), ("보류", "hold"), ("PASS", "pass"), ("FAIL", "fail")):
        if s.strip() == word:
            s = '<span class="%s">%s</span>' % (cls, word)
    return s


def split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def render_table(header, rows, wrap=True):
    cls = ' class="wrap"' if wrap else ""
    out = ["<table><thead><tr>" + "".join("<th%s>%s</th>" % (cls, inline(c)) for c in header) + "</tr></thead><tbody>"]
    for r in rows:
        cells = list(r) + [""] * (len(header) - len(r))
        out.append("<tr>" + "".join("<td%s>%s</td>" % (cls, inline(c)) for c in cells[:max(len(header), 1)]) + "</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def md_to_html(text):
    lines = text.splitlines()
    out, para, stack = [], [], []  # stack: (indent, tag)
    i, n = 0, len(lines)

    def flush_para():
        if para:
            out.append("<p>%s</p>" % inline(" ".join(para)))
            del para[:]

    def close_lists(to_indent=-1):
        while stack and stack[-1][0] > to_indent:
            out.append("</%s>" % stack.pop()[1])

    while i < n:
        line = lines[i]
        s = line.strip()
        if s.startswith("```"):
            flush_para(); close_lists()
            lang = s[3:].strip()
            buf = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1
            out.append('<pre><code class="%s">%s</code></pre>' % (html.escape(lang), html.escape("\n".join(buf))))
            continue
        if not s:
            flush_para(); close_lists(); i += 1; continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            flush_para(); close_lists()
            lvl = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (lvl, inline(m.group(2)), lvl)); i += 1; continue
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
            flush_para(); close_lists(); out.append("<hr>"); i += 1; continue
        if s.startswith(">"):
            flush_para(); close_lists()
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip()); i += 1
            out.append("<blockquote>%s</blockquote>" % inline(" ".join(buf))); continue
        if s.startswith("|") and i + 1 < n and re.match(r"^\|?\s*:?-{2,}", lines[i + 1].strip()):
            flush_para(); close_lists()
            header = split_row(s)
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i])); i += 1
            out.append(render_table(header, rows)); continue
        m = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line)
        if m:
            flush_para()
            indent = len(m.group(1).expandtabs(4))
            tag = "ol" if m.group(2)[0].isdigit() else "ul"
            if stack and indent < stack[-1][0]:
                close_lists(indent)
            if not stack or indent > stack[-1][0]:
                out.append("<%s>" % tag); stack.append((indent, tag))
            out.append("<li>%s</li>" % inline(m.group(3))); i += 1; continue
        para.append(s); i += 1
    flush_para(); close_lists()
    return "\n".join(out)


def render_file(path, rows_cap):
    ext = os.path.splitext(path)[1].lower()
    size = os.path.getsize(path)
    if size > MAX_BYTES:
        return '<p class="note">%s bytes: 너무 커서 표시하지 않음</p>' % format(size, ",")
    text, enc = read_text(path)
    if ext == ".md":
        return md_to_html(text)
    if ext in (".csv", ".tsv"):
        delim = "\t" if ext == ".tsv" else ","
        try:
            delim = csv.Sniffer().sniff("\n".join(text.splitlines()[:20]), delimiters=",\t;|").delimiter
        except csv.Error:
            pass
        rows = [r for r in csv.reader(io.StringIO(text), delimiter=delim)]
        header = rows[0] if rows else []
        body = rows[1:]
        note = "%s행 × %d열, 인코딩 %s" % (format(len(body), ","), len(header), enc)
        if len(body) > rows_cap:
            note += " (앞 %d행만 표시)" % rows_cap
        return '<p class="note">%s</p>\n' % note + render_table(header, body[:rows_cap], wrap=False)
    return '<p class="note">인코딩 %s</p><pre>%s</pre>' % (enc, html.escape(text))


def collect(paths, out_dir):
    files = []
    out_abs = os.path.abspath(out_dir)
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, names in os.walk(p):
                dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "__pycache__" and os.path.abspath(os.path.join(root, d)) != out_abs)
                for nme in sorted(names):
                    if not nme.startswith(".") and nme.lower().endswith(EXTS):
                        files.append(os.path.join(root, nme))
        elif os.path.isfile(p):
            files.append(p)
    seen, uniq = set(), []
    for f in files:
        if f not in seen:
            seen.add(f); uniq.append(f)
    return uniq[:MAX_FILES], len(uniq) > MAX_FILES


def build(cfg):
    files, truncated = collect(cfg["paths"], cfg["out"])
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nav = " ".join('<a href="#f%d">%s</a>' % (k, html.escape(os.path.basename(f))) for k, f in enumerate(files))
    sections = []
    for k, f in enumerate(files):
        try:
            body = render_file(f, cfg["rows"])
        except Exception as e:  # 한 파일이 깨져도 나머지는 보여 준다
            body = '<p class="note">표시 실패: %s: %s</p>' % (type(e).__name__, html.escape(str(e)))
        sections.append('<section id="f%d"><h2 class="file">%s</h2>\n%s\n</section>' % (k, html.escape(f), body))
    if not files:
        sections.append('<section><p class="note">표시할 파일이 없음. 경로: %s</p></section>' % html.escape(", ".join(cfg["paths"])))
    doc = ("<!doctype html>\n<html lang=\"ko\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
           "<title>%s</title><style>%s</style></head><body>\n<nav><strong>%s</strong> &nbsp; %s</nav>\n<main>\n%s\n"
           "<footer>만든 시각 %s · 파일 %d개%s · 새로고침하면 다시 만든다</footer></main></body></html>\n"
           % (html.escape(cfg["title"]), CSS, html.escape(cfg["title"]), nav, "\n".join(sections), now, len(files),
              " (최대 %d개까지만)" % MAX_FILES if truncated else ""))
    os.makedirs(cfg["out"], exist_ok=True)
    out_path = os.path.join(cfg["out"], "index.html")
    open(out_path, "w", encoding="utf-8").write(doc)
    return out_path, len(files)


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/index.html"):
            try:
                build(CONFIG)
            except Exception as e:
                sys.stderr.write("다시 만들기 실패: %s\n" % e)
        return SimpleHTTPRequestHandler.do_GET(self)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (datetime.now().strftime("%H:%M:%S"), fmt % args))


def main(argv):
    cfg = dict(CONFIG)
    paths, serve, port, host = [], False, 8787, "127.0.0.1"
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--out":
            cfg["out"] = argv[i + 1]; i += 1
        elif a == "--rows":
            cfg["rows"] = int(argv[i + 1]); i += 1
        elif a == "--title":
            cfg["title"] = argv[i + 1]; i += 1
        elif a == "--host":
            host = argv[i + 1]; i += 1
        elif a == "--serve":
            serve = True
            if i + 1 < len(argv) and argv[i + 1].isdigit():
                port = int(argv[i + 1]); i += 1
        elif a in ("-h", "--help"):
            print(__doc__); return 0
        else:
            paths.append(a)
        i += 1
    cfg["paths"] = paths or list(DEFAULT_PATHS)  # 없는 경로는 build 때마다 거른다(서버 시작 뒤 생긴 파일도 보이게)
    CONFIG.update(cfg)
    out_path, count = build(cfg)
    print("만듦: %s (파일 %d개)" % (out_path, count))
    if not serve:
        print("브라우저 미리보기로 보려면: python3 kit/preview.py --serve   (다른 터미널 탭에서. 기본 PORT 8787, URL /)")
        return 0
    handler = partial(Handler, directory=os.path.abspath(cfg["out"]))
    try:
        srv = ThreadingHTTPServer((host, port), handler)
    except OSError as e:
        print("포트 %d 를 열 수 없음: %s. 다른 포트: python3 kit/preview.py --serve 8788" % (port, e)); return 1
    print("미리보기 서버 켜짐: %s:%d → URL / · 새로고침하면 다시 만든다. 끄기: Ctrl+C" % (host, srv.server_port))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n미리보기 서버 끔")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
