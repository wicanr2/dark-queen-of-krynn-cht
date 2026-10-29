"""建立本機完整版及無原版資料的引擎包，並核對ZIP內容與UTF-8。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import stat
import time
import zipfile


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while data:=f.read(1024*1024):h.update(data)
    return h.hexdigest()


def copy_tree(source,target):
    assert source.is_dir() and not target.exists()
    assert not any(p.is_symlink() for p in source.rglob('*'))
    shutil.copytree(source,target)


def readme(version,platform,full):
    return f'''# 黑暗之后 HD＋繁體中文 {version}

平台：{platform}
內容：{'本機完整版，含合法持有的原版及本機衍生素材，只限本機保存。' if full else '引擎包，不含原版、翻譯全文、HD、音樂或掃描。'}

{'Windows雙擊「啟動.bat」；Linux執行 ./啟動.sh；macOS開啟「黑暗之后.app」。' if full else '先從您本機已準備的完整資料匯入 data/ 與 original/，再啟動。可使用 import-local.py 來源資料夾 本封包資料夾。原版ZIP本身不包含本專案的翻譯與HD，不能冒充完整中文資料。'}
存檔位於使用者資料目錄，更新程式不覆寫存檔。Windows使用LOCALAPPDATA，Linux使用XDG_DATA_HOME或~/.local/share，macOS使用~/Library/Application Support。
macOS的data與original位於「黑暗之后.app/Contents/Resources/」；匯入工具的來源與目的地皆指定這一層。

F2縮放；F12繁中／原版；工具列HD獨立切換；F5手札、F6說明、F7攻略、F8音樂；F10截圖、F11全螢幕。示範可按Esc中斷。

Linux x86_64需要glibc 2.36以上及X11／OpenGL／ALSA桌面函式庫。Windows x86_64有Wine啟動收據，原生Windows仍需實機確認。macOS universal含x86_64及arm64，未簽章、未公證，未完成真機驗收。

完成門檻為使用者指定的兩輪代表抽驗，正常入口與場景fixture分列；不宣稱逐房走訪、全程通關或所有平台真機通過。音樂保留原版8段樂譜，改用取樣樂器，技術輸出與聽感確認分列。

自有部分採RRSAL-1.0；第三方授權見licenses/。原版及衍生素材的權利另列，完整版不得作為公開發行包。詳見package-manifest.json。
'''


IMPORTER='''import hashlib,shutil,sys
from pathlib import Path
src,dst=map(lambda x:Path(x).resolve(),sys.argv[1:])
assert src!=dst and src not in dst.parents and dst not in src.parents
assert (src/'data/inputs/player-profile.json').is_file()
assert hashlib.sha256((src/'original/DQK.EXE').read_bytes()).hexdigest()=='3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58'
for name in ['data','original']:
    assert not (dst/name).exists()
    assert not any(p.is_symlink() for p in (src/name).rglob('*'))
    shutil.copytree(src/name,dst/name)
print('Imported local prepared data; no files uploaded.')
'''


def launchers(base,platform):
    if platform=='windows-amd64':
        (base/'啟動.bat').write_bytes(b'@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\n"%~dp0DarkQueen.exe" -player "%~dp0data\\inputs" -original "%~dp0original" -saves "%LOCALAPPDATA%\\DarkQueenOfKrynn"\r\n')
    elif platform=='linux-amd64':
        p=base/'啟動.sh'
        p.write_text('#!/bin/sh\nset -eu\nHERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\nexec "$HERE/dqk-player" -player "$HERE/data/inputs" -original "$HERE/original" -saves "${XDG_DATA_HOME:-$HOME/.local/share}/DarkQueenOfKrynn"\n')
        p.chmod(0o755)


def notices(root,player,modules,deps,font,base,full):
    out=base/'licenses';out.mkdir()
    shutil.copy2(root/'LICENSE',out/'LICENSE-project.txt')
    shutil.copy2(player/'go-toolchain-license.txt',out/'LICENSE-Go.txt')
    shutil.copy2(root/'workplace/dosgolem/LICENSE',out/'LICENSE-dosgolem.txt')
    shutil.copy2(root/'tools/LICENSE-Gold-Box-Explorer.txt',out/'LICENSE-Gold-Box-Explorer.txt')
    names=['github.com/hajimehoshi/ebiten/v2@v2.9.9','github.com/ebitengine/oto/v3@v3.4.0','github.com/ebitengine/purego@v0.9.0','github.com/ebitengine/gomobile@v0.0.0-20250923094054-ea854a63cce1','github.com/ebitengine/hideconsole@v1.0.0','github.com/jezek/xgb@v1.1.1','golang.org/x/sys@v0.36.0','golang.org/x/sync@v0.17.0']
    for name in names:
        source=modules/name
        files=[p for p in source.glob('LICENSE*') if p.is_file()]
        assert files,name
        target=out/name.replace('/','_');target.mkdir()
        for p in files:shutil.copy2(p,target/p.name)
    for name in ['oggvorbis@v1.0.5','vorbis@v1.0.2']:
        shutil.copy2(deps/'github.com/jfreymuth'/name/'LICENSE',out/(name+'.txt'))
    if full:
        shutil.copy2(font/'LICENSE-open-huninn.txt',out/'LICENSE-open-huninn.txt')
        shutil.copy2(root/'workplace/probe/music-hd-20261029/soundfont-license.txt',out/'LICENSE-FluidR3-samples.txt')


def archive(base,path):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:
        for p in sorted(base.rglob('*')):
            if p.is_file():
                # PNG／Ogg已自行壓縮。直接封存，避免三平台反覆壓縮同一批美術及音樂。
                method=zipfile.ZIP_STORED if p.suffix.lower() in {'.png','.jpg','.jpeg','.ogg'} else zipfile.ZIP_DEFLATED
                z.write(p,str(Path(base.name)/p.relative_to(base)),compress_type=method,compresslevel=1)
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            assert not info.filename.startswith('/') and '..' not in Path(info.filename).parts
            if not info.filename.isascii():assert info.flag_bits&0x800
        manifests=[x for x in z.namelist() if x.endswith('/package-manifest.json')]
        assert len(manifests)==1
        manifest=json.loads(z.read(manifests[0]))
        prefix=base.name+'/'
        for name,want in manifest['files'].items():
            h=hashlib.sha256()
            with z.open(prefix+name) as source:
                while chunk:=source.read(1024*1024):h.update(chunk)
            assert h.hexdigest()==want,name
        if manifest['platform']=='windows-amd64':
            assert z.read(prefix+'README.txt').startswith(b'\xef\xbb\xbf')
        if manifest['kind']=='patch':
            assert not any('/data/' in n or '/original/' in n or Path(n).suffix.upper() in {'.GLB','.TLB','.XMI','.VOC','.SAV'} for n in z.namelist())
    return dict(file=path.name,bytes=path.stat().st_size,sha256=sha(path),platform=manifest['platform'],kind=manifest['kind'],zip_utf8_verified=True,content_hashes_verified=True)


def main(args):
    root,player,stage,delivery=args.root,args.player,args.stage,args.output
    assert re.fullmatch(r'v\.\d+\.\d+\.\d+-\d{8}',args.version) and re.fullmatch(r'[0-9a-f]{40}',args.commit)
    assert stage.parent.is_dir() and delivery.parent.is_dir() and not stage.exists() and not delivery.exists()
    stage.mkdir();delivery.mkdir()
    for name in ['full-local','patch','promo','smoke']:(delivery/name).mkdir()
    builds={'linux-amd64':player/'dqk-player','windows-amd64':player/'bin/dqk-windows-amd64.exe','macos-universal':player/'bin/dqk-macos-universal'}
    rows=[]
    for platform,binary in builds.items():
        assert binary.is_file()
        for kind in ['full-local','patch']:
            name=f'黑暗之后-{args.version}-{platform}-{kind}'
            base=stage/name;base.mkdir()
            resource=base
            if platform=='macos-universal':
                app=base/'黑暗之后.app/Contents';(app/'MacOS').mkdir(parents=True);resource=app/'Resources';resource.mkdir()
                shutil.copy2(binary,app/'MacOS/dqk-player')
                launcher=app/'MacOS/launch';launcher.write_text('#!/bin/sh\nset -eu\nHERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\nexec "$HERE/dqk-player" -player "$HERE/../Resources/data/inputs" -original "$HERE/../Resources/original" -saves "$HOME/Library/Application Support/DarkQueenOfKrynn"\n');launcher.chmod(0o755)
                numeric=args.version.split('-')[0][2:]
                (app/'Info.plist').write_bytes(plistlib.dumps(dict(CFBundleExecutable='launch',CFBundleIdentifier='org.wicanr2.darkqueen',CFBundleName='黑暗之后',CFBundleDisplayName='黑暗之后',CFBundlePackageType='APPL',CFBundleShortVersionString=numeric,CFBundleVersion=numeric,DQKFullVersion=args.version,NSHighResolutionCapable=True,LSMinimumSystemVersion='11.0')))
            else:shutil.copy2(binary,base/('DarkQueen.exe' if platform=='windows-amd64' else 'dqk-player'))
            launchers(base,platform)
            if kind=='full-local':
                data=resource/'data';data.mkdir()
                for directory in ['inputs','picture-text','music']:copy_tree(player/directory,data/directory)
                copy_tree(player/'hd',data/'hd')
                copy_tree(root/'workplace/input/dos/drkqueen',resource/'original')
            else:
                (resource/'import-local.py').write_text(IMPORTER)
            notices(root,player,args.modules,args.deps,args.font,base,kind=='full-local')
            text=readme(args.version,platform,kind=='full-local')
            if platform=='windows-amd64':(base/'README.txt').write_bytes(b'\xef\xbb\xbf'+text.replace('\n','\r\n').encode())
            else:(base/'README.md').write_text(text)
            manifest=dict(schema=1,version=args.version,source_commit=args.commit,platform=platform,kind=kind,binary_sha256=sha(binary),rights='local-only-original-and-derived-assets' if kind=='full-local' else 'engine-only-no-game-data',macos_hardware_verified=False,files={str(p.relative_to(base)):sha(p) for p in base.rglob('*') if p.is_file()})
            (base/'package-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
            result=archive(base,delivery/kind/(name+'.zip'));rows.append(result);print(json.dumps(result),flush=True)
    result=dict(schema=1,version=args.version,source_commit=args.commit,packages=rows,public_upload=False)
    (delivery/'SHA256SUMS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['root','player','stage','output','modules','deps','font']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--version',required=True);p.add_argument('--commit',required=True)
    main(p.parse_args())
