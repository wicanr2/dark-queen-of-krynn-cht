"""組裝及核對含完整遊戲的AppImage；只在Docker內執行。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct

from release_payload import sha

RUNTIME_SHA = '1cc49bcf1e2ccd593c379adb17c9f85a36d619088296504de95b1d06215aebbf'
RUNTIME_BYTES = 944632
EXE_SHA = '3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58'


def tree(base):
    return {str(p.relative_to(base)): sha(p) for p in base.rglob('*') if p.is_file() and not p.is_symlink()}


def platform_binary(data, platform):
    if platform == 'windows-amd64':
        assert data[:2] == b'MZ'
        pe = struct.unpack_from('<I', data, 60)[0]
        assert data[pe:pe+4] == b'PE\0\0' and struct.unpack_from('<H', data, pe+4)[0] == 0x8664
    elif platform == 'macos-universal':
        assert data[:4] == b'\xca\xfe\xba\xbe' and struct.unpack_from('>I',data,4)[0] == 2
        cpus = set()
        for i in range(2):
            cpu, subtype, offset, size, align = struct.unpack_from('>IIIII', data, 8+20*i)
            assert offset+size <= len(data) and data[offset:offset+4] == b'\xcf\xfa\xed\xfe'
            assert struct.unpack_from('<I',data,offset+4)[0] == cpu
            cpus.add(cpu)
        assert cpus == {0x01000007,0x0100000c}
    else:
        assert data[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H',data,18)[0] == 62


def check_resource(base, version, commit):
    manifest = json.loads((base/'package-manifest.json').read_text())
    assert manifest['version'] == version and manifest['source_commit'] == commit and manifest['kind'] == 'full-local'
    for name, expected in manifest['files'].items():
        assert sha(base/name) == expected, name
    resource = base/'黑暗之后.app/Contents/Resources' if manifest['platform']=='macos-universal' else base
    assert sha(resource/'original/DQK.EXE') == EXE_SHA
    profile=json.loads((resource/'data/inputs/player-profile.json').read_text())
    assert len(profile['Files']) == 95
    for name,expected in profile['Files'].items():
        assert sha(resource/'data/inputs'/name)==expected,name
    assert len([p for p in (resource/'data/inputs').rglob('*') if p.is_file()]) == 96
    hd = json.loads((resource/'data/hd/hd.json').read_text())
    # 素材表欄位形狀由既有正式來源核對；不以檔案存在取代全量資料雜湊。
    assert hd and (resource/'data/inputs/player-profile.json').is_file()
    assert (resource/'data/music/manifest.json').is_file()
    assert not (resource/'session').exists()
    return manifest


def main(args):
    assert Path('/.dockerenv').is_file() and os.getuid() == os.getgid() == 1000
    assert re.fullmatch(r'v\.\d+\.\d+\.\d+-\d{8}',args.version)
    root, dist, stage = Path('/project'), Path('/delivery'), Path('/stage')
    assert stage.stat().st_uid == dist.stat().st_uid == 1000
    app = stage/'dqk.AppDir'
    target = dist/'full-local'/f'黑暗之后-{args.version}-linux-amd64-full-local.AppImage'
    index_path = dist/'SHA256SUMS.json'
    index = json.loads(index_path.read_text())
    assert index['version'] == args.version and len(index['packages']) == 2
    commit = index['source_commit']
    if args.phase == 'prepare':
        source = stage/f'黑暗之后-{args.version}-linux-amd64-full-local'
        check_resource(source,args.version,commit)
        assert not app.exists() and not target.exists()
        (app/'usr/lib').mkdir(parents=True)
        shutil.move(source,app/'usr/lib/dqk')
        (app/'AppRun').write_text('''#!/bin/sh
set -eu
appdir=${APPDIR:-}
if [ -z "$appdir" ]; then appdir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P); fi
exec "$appdir/usr/lib/dqk/dqk-player" -player "$appdir/usr/lib/dqk/data/inputs" -original "$appdir/usr/lib/dqk/original" -saves "${XDG_DATA_HOME:-$HOME/.local/share}/DarkQueenOfKrynn" "$@"
''')
        (app/'AppRun').chmod(0o755)
        (app/'dqk.desktop').write_text('[Desktop Entry]\nType=Application\nName=The Dark Queen of Krynn\nName[zh_TW]=黑暗之后\nExec=AppRun\nIcon=dqk\nTerminal=false\nCategories=Game;RolePlaying;\n')
        (app/'dqk.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" rx="32" fill="#17202c"/><path d="M48 40h160v104l-80 76-80-76z" fill="#a68c4d"/><text x="128" y="140" text-anchor="middle" font-family="serif" font-size="54" fill="#17202c">DQK</text></svg>\n')
        (app/'.DirIcon').symlink_to('dqk.svg')
        licenses = app/'usr/share/licenses/AppImage'
        source = root/'tools/appimage-licenses'
        records = json.loads((source/'files.json').read_text())
        for name, info in records.items():
            assert sha(source/name) == info['sha256'] and (source/name).stat().st_size == info['bytes']
        shutil.copytree(source,licenses)
        provenance = dict(version=args.version,source_commit=commit,format='AppImage-type2',bundled_original=True,
                          runtime_sha256=RUNTIME_SHA,runtime_bytes=RUNTIME_BYTES,image_id=args.image_id,
                          save_directory='${XDG_DATA_HOME:-$HOME/.local/share}/DarkQueenOfKrynn',
                          system_libraries=['glibc>=2.36','X11','OpenGL','ALSA'],public_distribution=False)
        (app/'appimage-build.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n')
        (stage/'appimage-files.json').write_text(json.dumps(tree(app),ensure_ascii=False,indent=2)+'\n')
    else:
        with target.open('rb') as f:
            runtime=f.read(RUNTIME_BYTES)
            assert runtime[:4]==b'\x7fELF' and runtime[8:11]==b'AI\x02'
            assert hashlib.sha256(runtime).hexdigest()==RUNTIME_SHA and f.read(4)==b'hsqs'
        assert os.access(target,os.X_OK)
        extracted=stage/'appimage-extracted/squashfs-root'
        expected=json.loads((stage/'appimage-files.json').read_text())
        assert tree(extracted)==expected
        assert (extracted/'.DirIcon').is_symlink() and os.readlink(extracted/'.DirIcon')=='dqk.svg'
        manifest=check_resource(extracted/'usr/lib/dqk',args.version,commit)
        binary=(extracted/'usr/lib/dqk/dqk-player').read_bytes()
        platform_binary(binary,'linux-amd64')
        assert args.version.encode() in binary and commit.encode() in binary
        rows=[]
        for row in index['packages']:
            path=dist/row['kind']/row['file']
            assert sha(path)==row['sha256'] and path.stat().st_size==row['bytes']
            base=stage/path.stem
            m=check_resource(base,args.version,commit)
            binary=base/'DarkQueen.exe' if row['platform']=='windows-amd64' else base/'黑暗之后.app/Contents/MacOS/dqk-player'
            data=binary.read_bytes();platform_binary(data,row['platform'])
            assert args.version.encode() in data and commit.encode() in data
            rows.append(dict(platform=row['platform'],files=len(m['files']),bundled_original=True,binary_sha256=sha(binary)))
        row=dict(file=target.name,bytes=target.stat().st_size,sha256=sha(target),platform='linux-amd64',kind='full-local',
                 format='AppImage-type2',content_hashes_verified=True,runtime_sha256=RUNTIME_SHA)
        index['packages'].append(row)
        assert {r['platform'] for r in index['packages']}=={'linux-amd64','windows-amd64','macos-universal'}
        index_path.write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
        report=dict(passed=True,version=args.version,source_commit=commit,packages=index['packages'],
                    appimage_extracted_files=len(expected),bundled_original=True,platforms=rows,
                    macos_hardware_verified=False,appimage_fuse_mount_verified=False)
        (dist/'smoke/full-package-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(index['packages'],ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=['prepare','finalize'])
    p.add_argument('--version',required=True);p.add_argument('--image-id',required=True)
    main(p.parse_args())
