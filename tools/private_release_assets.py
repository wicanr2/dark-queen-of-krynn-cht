"""私人 Release 分段的核對與原 ZIP 還原；在離線 Docker 執行。"""
import hashlib
import base64
import gzip
import json
import os
from pathlib import Path
import sys
import struct
import zipfile

ROOT = Path('/project')
MANIFEST = ROOT / 'docs/private-release-assets.json'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def checked(path, row):
    assert not path.is_symlink() and path.is_file(), str(path)
    assert path.stat().st_size == row['bytes'], str(path)
    assert digest(path) == row['sha256'], str(path)


def archive(data, platform):
    assert platform in {'linux-amd64', 'windows-amd64', 'macos-universal'}
    matches = [row for row in data['archives'] if f'-{platform}-' in row['path']]
    assert len(matches) == 1
    return matches[0]


def cache(data, platform):
    return ROOT / 'workplace/probe' / f'private-release-download-{data["version"]}-{platform}'


def remote(data, path):
    release = json.loads(path.read_text())
    assert release['id'] == data['release_id'] and release['tag_name'] == data['version']
    assets = {row['name']: row for row in release['assets']}
    count = 0
    for package in data['archives']:
        for part in package.get('parts', [package.get('delta')]):
            row = assets[part['name']]
            assert row['state'] == 'uploaded' and row['size'] == part['bytes']
            assert row['digest'] == 'sha256:' + part['sha256'], part['name']
            count += 1
    print(json.dumps(dict(passed=True, verified_parts=count)))


def payload(stream, info):
    stream.seek(info.header_offset + 26)
    name, extra = struct.unpack('<HH', stream.read(4))
    return info.header_offset + 30 + name + extra


def delta(source, target, destination):
    """保存ZIP的原始壓縮區塊參照與差異，還原時不重新壓縮。"""
    assert not destination.exists()
    index = {}
    with source.open('rb') as stream, zipfile.ZipFile(source) as packed:
        for info in packed.infolist():
            if not info.compress_size:
                continue
            offset = payload(stream, info)
            stream.seek(offset)
            block = stream.read(info.compress_size)
            index[hashlib.sha256(block).hexdigest()] = (offset, len(block))
    operations = []
    with target.open('rb') as stream, zipfile.ZipFile(target) as packed:
        cursor = 0
        for info in packed.infolist():
            if not info.compress_size:
                continue
            offset = payload(stream, info)
            stream.seek(offset)
            block = stream.read(info.compress_size)
            match = index.get(hashlib.sha256(block).hexdigest())
            if not match or match[1] != len(block):
                continue
            if offset > cursor:
                stream.seek(cursor)
                operations.append(dict(literal=base64.b64encode(stream.read(offset-cursor)).decode('ascii')))
            operations.append(dict(copy=list(match)))
            cursor = offset + len(block)
        stream.seek(cursor)
        operations.append(dict(literal=base64.b64encode(stream.read()).decode('ascii')))
    value = dict(schema=1, source_sha256=digest(source), target_sha256=digest(target),
                 target_bytes=target.stat().st_size, operations=operations)
    with gzip.open(destination, 'xt', encoding='utf-8', compresslevel=6) as output:
        json.dump(value, output, separators=(',', ':'))
    print(json.dumps(dict(name=destination.name, bytes=destination.stat().st_size,
                          sha256=digest(destination), copied_blocks=sum('copy' in op for op in operations))))


def restore_delta(source, patch, temporary, output):
    with gzip.open(patch, 'rt', encoding='utf-8') as stream:
        value = json.load(stream)
    assert digest(source) == value['source_sha256']
    whole = hashlib.sha256()
    with source.open('rb') as stream:
        for operation in value['operations']:
            if 'copy' in operation:
                offset, length = operation['copy']
                assert 0 <= offset <= source.stat().st_size and 0 < length <= source.stat().st_size - offset
                stream.seek(offset)
                block = stream.read(length)
            else:
                block = base64.b64decode(operation['literal'], validate=True)
            output.write(block)
            whole.update(block)
    output.flush()
    os.fsync(output.fileno())
    assert output.tell() == value['target_bytes'] and whole.hexdigest() == value['target_sha256']


def prepare(data, platform):
    row = archive(data, platform)
    target = ROOT / row['path']
    assert target.resolve().is_relative_to(ROOT / 'dist-all' / data['version'] / 'full-local')
    target.parent.mkdir(parents=True, exist_ok=True)
    assert target.parent.stat().st_uid == os.getuid()
    if target.exists():
        checked(target, row)
    parts = cache(data, platform)
    parts.mkdir(parents=True, exist_ok=True)
    assert parts.stat().st_uid == os.getuid()
    print(str(parts.relative_to(ROOT)))


def join(data, platform):
    row = archive(data, platform)
    target = ROOT / row['path']
    assert target.resolve().is_relative_to(ROOT / 'dist-all' / data['version'] / 'full-local')
    parts = cache(data, platform)
    if target.exists():
        checked(target, row)
    else:
        temporary = target.with_name(target.name + '.partial')
        created = False
        try:
            with temporary.open('xb') as output:
                created = True
                if 'delta' in row:
                    base = next(r for r in data['archives'] if r['path'] == row['base_archive'])
                    checked(ROOT / base['path'], base)
                    checked(parts / row['delta']['name'], row['delta'])
                    restore_delta(ROOT / base['path'], parts / row['delta']['name'], temporary, output)
                else:
                    whole = hashlib.sha256()
                    for part in row['parts']:
                        assert Path(part['name']).name == part['name']
                        source = parts / part['name']
                        checked(source, part)
                        with source.open('rb') as stream:
                            while block := stream.read(1024 * 1024):
                                output.write(block)
                                whole.update(block)
                    output.flush()
                    os.fsync(output.fileno())
                    assert output.tell() == row['bytes'] and whole.hexdigest() == row['sha256']
            checked(temporary, row)
            os.replace(temporary, target)
        except BaseException:
            # 僅清本次建立的暫存；保留已下載片段供續傳。
            if created and temporary.exists() and temporary.stat().st_uid == os.getuid():
                temporary.unlink()
            raise
    for part in row.get('parts', [row.get('delta')]):
        source = parts / part['name']
        if source.exists():
            checked(source, part)
            source.unlink()
    print(json.dumps(dict(passed=True, path=row['path'], sha256=row['sha256']), ensure_ascii=False))


if __name__ == '__main__':
    data = json.loads(MANIFEST.read_text())
    assert os.getuid() == os.getgid() == 1000 and data['private_only']
    if sys.argv[1] == 'delta':
        delta(*(Path(p) for p in sys.argv[2:5]))
    elif sys.argv[1] == 'remote':
        remote(data, Path(sys.argv[2]))
    elif sys.argv[1] in {'prepare', 'join'}:
        globals()[sys.argv[1]](data, sys.argv[2])
    else:
        raise SystemExit('prepare 平台 | join 平台 | remote Release回讀JSON')
