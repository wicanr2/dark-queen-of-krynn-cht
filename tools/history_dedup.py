"""合併內容相同的歷史圖像；保留路徑、內容雜湊及可拆分的原始時間紀錄。"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys

ROOT = Path('/project')
PROBE = ROOT / 'workplace/probe'


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def allowed(name):
    p = Path(name)
    return (p.parts[:2] == ('workplace', 'probe') and len(p.parts) > 3
            and p.parts[2] != 'player-current' and '20261030' not in p.parts[2]
            and p.suffix.lower() in {'.png', '.ppm', '.idx'})


def member(name):
    p = ROOT / name
    assert not Path(name).is_absolute() and p.resolve().is_relative_to(PROBE.resolve())
    assert allowed(name) and not p.is_symlink() and p.is_file()
    assert p.stat().st_uid == p.stat().st_gid == 1000
    return p


def load(p):
    with gzip.open(p, 'rt', encoding='utf-8') as f:
        return json.load(f)


def save(p, value):
    assert not p.exists() and p.parent.stat().st_uid == 1000
    with gzip.open(p, 'xt', encoding='utf-8', compresslevel=1) as f:
        json.dump(value, f, ensure_ascii=False)


def signature(p):
    s = p.stat()
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns


def plan(inventory, destination):
    rows = (load(inventory) if inventory.suffix == '.gz' else json.loads(inventory.read_text()))['files']
    nodes = {}
    for row in rows:
        nodes.setdefault((row['dev'], row['ino']), []).append(row)
    sizes = {}
    for aliases in nodes.values():
        if not all(allowed(r['path']) for r in aliases) or aliases[0]['nlink'] != len(aliases):
            continue
        row = aliases[0]
        if row['bytes'] > 0:
            sizes.setdefault(row['bytes'], []).append(aliases)
    content = {}
    hashed = 0
    for aliases in (v for group in sizes.values() if len(group) > 1 for v in group):
        row = aliases[0]
        p = member(row['path'])
        assert signature(p) == (row['dev'], row['ino'], row['bytes'], row['mtime_ns'])
        if os.listxattr(p):
            continue
        mode = stat.S_IMODE(p.stat().st_mode)
        for alias in aliases:
            alias['mode'] = mode
        key = sha(p), mode
        content.setdefault(key, []).append(aliases)
        hashed += 1
        if hashed % 20000 == 0:
            print('hashed', hashed, flush=True)
    groups = []
    freed = 0
    for (digest, mode), nodes in content.items():
        if len(nodes) < 2:
            continue
        nodes.sort(key=lambda n: n[0]['path'])
        groups.append(dict(sha256=digest, mode=mode, source=nodes[0], targets=nodes[1:]))
        freed += sum(n[0]['allocated'] for n in nodes[1:])
    save(destination, dict(schema=1, scope='immutable historical images only; no current runtime or external hardlinks',
                           hashed_inodes=hashed, estimated_freed_bytes=freed, groups=groups))
    print(json.dumps(dict(groups=len(groups), hashed=hashed, estimated_freed_bytes=freed)), flush=True)


def apply(p):
    data = load(p)
    log = p.with_name('dedup-applied.jsonl')
    changed = 0
    with log.open('a', encoding='utf-8') as journal:
        for group in data['groups']:
            source = member(group['source'][0]['path'])
            assert sha(source) == group['sha256']
            for aliases in group['targets']:
                first = member(aliases[0]['path'])
                if signature(first)[:2] != signature(source)[:2]:
                    expected = aliases[0]
                    assert signature(first) == (expected['dev'], expected['ino'], expected['bytes'], expected['mtime_ns'])
                    assert sha(first) == group['sha256']
                for row in aliases:
                    target = member(row['path'])
                    if signature(target)[:2] == signature(source)[:2]:
                        continue
                    assert signature(target) == (row['dev'], row['ino'], row['bytes'], row['mtime_ns'])
                    assert stat.S_IMODE(target.stat().st_mode) == group['mode']
                    temporary = target.with_name(target.name + '.dedup-partial')
                    assert not temporary.exists()
                    os.link(source, temporary)
                    os.replace(temporary, target)
                    journal.write(json.dumps(dict(path=row['path'], source=str(source.relative_to(ROOT)),
                                                  sha256=group['sha256']), ensure_ascii=False) + '\n')
                    changed += 1
                    if changed % 10000 == 0:
                        journal.flush()
                        os.fsync(journal.fileno())
                        print('linked', changed, flush=True)
        journal.flush()
        os.fsync(journal.fileno())
    print('linked paths', changed, flush=True)


def verify(p):
    data = load(p)
    paths = 0
    for group in data['groups']:
        source = member(group['source'][0]['path'])
        assert sha(source) == group['sha256']
        for aliases in group['targets']:
            for row in aliases:
                target = member(row['path'])
                # 已拆分的副本也可驗內容；正常合併路徑以相同inode驗完整位元組。
                if signature(target)[:2] != signature(source)[:2]:
                    assert sha(target) == group['sha256']
                paths += 1
    print(json.dumps(dict(passed=True, groups=len(data['groups']), preserved_paths=paths)), flush=True)


def detach(p, selection):
    data = load(p)
    found = 0
    for group in data['groups']:
        for aliases in [group['source']] + group['targets']:
            for row in aliases:
                if row['path'] != selection and not row['path'].startswith(selection.rstrip('/') + '/'):
                    continue
                target = member(row['path'])
                assert sha(target) == group['sha256']
                temporary = target.with_name(target.name + '.detach-partial')
                assert not temporary.exists()
                shutil.copyfile(target, temporary)
                assert sha(temporary) == group['sha256']
                os.chmod(temporary, row['mode'])
                os.utime(temporary, ns=(row['mtime_ns'], row['mtime_ns']))
                os.replace(temporary, target)
                found += 1
    assert found, '索引無此歷史路徑'
    print('detached', found, flush=True)


if __name__ == '__main__':
    assert os.getuid() == os.getgid() == 1000
    command = sys.argv[1]
    if command == 'plan':
        plan(Path(sys.argv[2]), Path(sys.argv[3]))
    elif command in {'apply', 'verify'}:
        globals()[command](Path(sys.argv[2]))
    elif command == 'detach':
        detach(Path(sys.argv[2]), sys.argv[3])
    else:
        raise SystemExit('plan inventory.json plan.json.gz | apply plan.json.gz | verify plan.json.gz | detach plan.json.gz 歷史路徑')
