#!/usr/bin/env python3
"""Install/upgrade only known kit files. No network, model call, or package install."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
from datetime import datetime

VERSION = '2.0.0'
ROOT = Path(__file__).resolve().parent
BEGIN, END = b'<!-- exam-kit:begin', b'<!-- exam-kit:end -->'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def install(workspace):
    ws = Path(workspace).expanduser().resolve()
    if not ws.is_dir():
        raise ValueError('작업 폴더가 없습니다: ' + str(ws))
    if ws == ROOT or ROOT in ws.parents:
        raise ValueError('킷 소스 자체가 아닌 과제 작업 폴더를 지정하세요.')

    def target(name):
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('허용하지 않는 대상 경로: ' + name)
        p = ws / relative
        for part in [p, *p.parents]:
            if part == ws:
                break
            if part.is_symlink():
                raise ValueError('심볼릭 링크 대상은 수정하지 않습니다: ' + str(part))
        return p

    # Fail before mutations if metadata or any planned destination traverses a symlink.
    managed = {}
    for source in sorted((ROOT/'skills').rglob('*')):
        if source.is_file():
            managed['.agents/skills/'+str(source.relative_to(ROOT/'skills'))] = source
    for folder in ['tools', 'prompts', 'guide', 'templates']:
        for source in sorted((ROOT/folder).rglob('*')):
            if source.is_file() and '__pycache__' not in source.parts:
                name = str(source.relative_to(ROOT/folder))
                managed['kit/'+(name if folder == 'tools' else folder+'/'+name)] = source
    for name in [*managed, 'AGENTS.md', '.gitignore', 'notes/spec.md', 'notes/work.md', '.exam-kit/manifest.json', '.exam-kit/backups', '.exam-kit/incoming']:
        target(name)
    metadata = target('.exam-kit/manifest.json')
    prior = json.loads(metadata.read_text()) if metadata.exists() else {}
    previous_hashes = prior.get('files', {})
    if not isinstance(previous_hashes, dict):
        raise ValueError('설치 기록의 files 형식이 올바르지 않습니다.')
    legacy = json.loads((ROOT/'legacy-hashes.json').read_text())
    installed = dict(previous_hashes)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    counts = {'created': 0, 'updated': 0, 'preserved': 0, 'conflicts': 0}

    def write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name+'.exam-kit-tmp')
        if temp.exists() or temp.is_symlink():
            raise ValueError('임시 파일이 이미 있습니다: '+str(temp))
        try:
            with temp.open('xb') as f:
                f.write(data)
            if path.exists():
                os.chmod(temp, path.stat().st_mode & 0o777)
            os.replace(temp, path)
        finally:
            if temp.exists():
                temp.unlink()

    def backup(name, data):
        p = target('.exam-kit/backups/'+stamp+'/'+name)
        write(p, data)

    def conflict(name, data):
        write(target('.exam-kit/incoming/'+name), data)
        counts['conflicts'] += 1
        print('충돌 보존:', name, '→ .exam-kit/incoming/'+name)

    def known(name, data):
        h = digest(data)
        return h == previous_hashes.get(name) or h in legacy.get(name, [])

    for name, source in managed.items():
        p, new = target(name), source.read_bytes()
        if not p.exists():
            write(p,new); counts['created'] += 1; installed[name] = digest(new)
        elif not p.is_file():
            conflict(name,new)
        else:
            old=p.read_bytes()
            if old == new:
                counts['preserved'] += 1; installed[name] = digest(new)
            elif known(name,old):
                backup(name,old); write(p,new); counts['updated'] += 1; installed[name] = digest(new)
            else:
                conflict(name,new)

    name='AGENTS.md'; p=target(name); new=(ROOT/name).read_bytes().rstrip(b'\r\n')
    old=p.read_bytes() if p.exists() else b''
    if p.exists() and not p.is_file():
        raise ValueError('AGENTS.md가 파일이 아닙니다.')
    block = re.search(rb'<!-- exam-kit:begin\b.*?<!-- exam-kit:end -->',old,re.S)
    if BEGIN not in old and END not in old:
        replacement=old+(b'\n\n' if old else b'')+new+b'\n'
    elif old.count(BEGIN)!=1 or old.count(END)!=1 or not block:
        conflict(name,new+b'\n'); replacement=None
    elif block.group()==new:
        installed[name]=digest(new); replacement=None; counts['preserved']+=1
    elif known(name,block.group()) or known(name,block.group()+b'\n'):
        replacement=old[:block.start()]+new+old[block.end():]
    else:
        conflict(name,new+b'\n'); replacement=None
    if replacement is not None:
        if p.exists():backup(name,old)
        write(p,replacement); installed[name]=digest(new)
        counts['updated' if old else 'created']+=1

    # Task notes are user data after creation, even if they still resemble templates.
    for name in ['spec.md','work.md']:
        p=target('notes/'+name)
        if p.exists():counts['preserved']+=1
        else:write(p,(ROOT/'templates'/name).read_bytes());counts['created']+=1

    p=target('.gitignore'); old=p.read_bytes() if p.exists() else b''
    lines=old.decode('utf-8',errors='replace').splitlines()
    additions=[s for s in ['preview/','__pycache__/','.exam-kit/'] if s not in lines]
    if additions:
        if p.exists():backup('.gitignore',old)
        write(p,old+(b'\n' if old and not old.endswith(b'\n') else b'')+('\n'.join(additions)+'\n').encode())
    record={'version':VERSION,'files':installed,'last_run':stamp,'conflicts':counts['conflicts']}
    write(metadata,(json.dumps(record,ensure_ascii=False,indent=2)+'\n').encode())
    print('exam-kit', VERSION, json.dumps(counts,ensure_ascii=False))
    print('가이드: kit/guide/index.html · 첫 요청: kit/prompts/01-start.md')
    print('다음 답변마다: kit/prompts/02-answer-update.md (전체 대화 재전달 불필요)')
    print('기존 notes 문서는 보존됩니다. AI가 유효한 내용만 spec/work와 연결하게 하세요.')
    return 3 if counts['conflicts'] else 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace',nargs='?',default='.')
    args=parser.parse_args()
    try:
        return install(args.workspace)
    except (OSError,ValueError) as e:
        print('설치 중단:',e)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
