"""彙整現行中文、開頭與閱讀資料；不執行原版、不重跑抽驗。"""
import argparse
import base64
import csv
import hashlib
import json
import shutil
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def catalog(path):
    with path.open() as file:
        return {r['key']: r['text'] for r in csv.DictReader(file, delimiter='\t', quoting=csv.QUOTE_NONE)}


def save_catalog(path, data):
    path.write_text('key\ttext\n' + ''.join(k + '\t' + v + '\n' for k, v in data.items()))


def prepare(root, output):
    current = root / 'workplace/probe/shared-feedback-20261025/inputs-r3'
    startup = root / 'workplace/probe/startup-captions-20261023-r3/ui-inputs'
    assert current.is_dir() and startup.is_dir()
    assert output.parent.is_dir() and output.parent.stat().st_uid == 1000
    assert not output.exists(), '沿用已封存來源，只寫新的整合目錄'
    output.mkdir()
    for source, target in [(current, output), (startup, output / 'startup')]:
        target.mkdir(exist_ok=True)
        for path in source.iterdir():
            assert path.is_file() and path.stat().st_uid == 1000, path
            shutil.copyfile(path, target / path.name)
    shutil.copyfile(root / 'text/toolbar.zh-TW.tsv', output / 'toolbar.zh-TW.tsv')
    # 最後兩個已觀測語境沿既有冷啟動收據，不啟動新的遊戲抽驗。
    # 兩者的 wrapper→formatter、原始座標、色號及首字形已在正常冷讀收據中保存。
    formal = catalog(root / 'workplace/translation/zh-TW.tsv')
    cold = output / 'startup'
    en, zh = catalog(cold / 'en.tsv'), catalog(cold / 'zh-TW.tsv')
    bindings = json.loads((cold / 'bindings.json').read_text())
    additions = [
        ('startup.title', 'ui.27336f5196d31de3a6a7', 'The Dark Queen of Krynn', 0xcf, 8032, 8020),
        ('startup.version', 'ui.a22067070b60cae9437f', 'Version 1.1        July 29,1992', 0xeb, 8016, 8024),
    ]
    source_glyphs = json.loads((output / 'glyphs-16.json').read_text())['glyphs']
    cold_glyphs = json.loads((cold / 'glyphs-16.json').read_text())
    for key, formal_key, source, off, raw_x, raw_y in additions:
        assert key not in en and key not in zh
        en[key], zh[key] = source, formal[formal_key]
        assert '\\u3000' not in zh[key], '正式來源仍有未解碼空白，須先修正正式 TSV'
        for ch in zh[key]:
            assert ch in source_glyphs, (key, ch)
            if ch in cold_glyphs['glyphs']:
                assert cold_glyphs['glyphs'][ch] == source_glyphs[ch]
            cold_glyphs['glyphs'][ch] = source_glyphs[ch]
        digest = hashlib.sha256(source.encode()).hexdigest()
        bindings['Bindings'].append(dict(Key=key, Group='opening-title', SourceSHA256=digest,
            FormatSHA256=hashlib.sha256(b'%s').hexdigest(), Caller=dict(Seg=0xb72, Off=0x27c),
            UpperCaller=dict(Seg=0x20f9, Off=off), UpperFormatSHA256=digest, MenuSignature='',
            RawX=raw_x, RawY=raw_y, X=(raw_x-8000)*2, Y=(raw_y-8000)*2,
            Width=len(source)*8, Background=23, Button=False, Color=0x87))
    save_catalog(cold / 'en.tsv', en)
    save_catalog(cold / 'zh-TW.tsv', zh)
    (cold / 'bindings.json').write_text(json.dumps(bindings, ensure_ascii=False, indent=2) + '\n')
    (cold / 'glyphs-16.json').write_text(json.dumps(cold_glyphs, ensure_ascii=False, separators=(',', ':')) + '\n')
    (cold / 'provenance.json').rename(cold / 'source-provenance.json')
    (cold / 'provenance.json').write_text(json.dumps({
        'source': str(startup.relative_to(root)),
        'source_provenance_sha256': sha(cold / 'source-provenance.json'),
        'new_gameplay_verification': False,
        'additions': [row[0] for row in additions],
        'outputs': {name: sha(cold / name) for name in ['bindings.json', 'en.tsv', 'zh-TW.tsv', 'glyphs-16.json']},
    }, ensure_ascii=False, indent=2) + '\n')
    (output / 'profile-sources.json').write_text(json.dumps({
        'version': 1,
        'scope': '中文整合開發入口；未執行新增遊戲抽驗，正式版面及HD另行接入',
        'gameplay': str(current.relative_to(root)),
        'gameplay_evidence': sha(current.parent / 'evidence.json'),
        'startup': str(startup.relative_to(root)),
        'startup_additions': [row[0] for row in additions],
        'startup_additions_evidence': 'workplace/probe/load-prompts-20261023/observe-cold-r1/receipt.json',
        'formal_catalog_sha256': sha(root / 'workplace/translation/zh-TW.tsv'),
        'exe_sha256': '3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58',
        'sdk_commit': 'f79eab6db8c64a524a06535e53e5d32b0bbcf7c8',
        'game_replay': False, 'gui_sampling': False,
    }, ensure_ascii=False, indent=2) + '\n')


def finish(root, output):
    assert not (output / 'player-profile.json').exists()
    for name in ['glyphs-16.json', 'glyphs-20.json', 'toolbar-glyphs-16.json']:
        data = json.loads((output / name).read_text())
        # Go 的字模欄位不分大小寫；產生器目前用小寫欄名。
        glyphs = data.get('Glyphs', data.get('glyphs'))
        size = data.get('Size', data.get('size'))
        height = data.get('Height', data.get('height'))
        assert glyphs and height == size + 4
        assert all(len(base64.b64decode(v, validate=True) if isinstance(v, str) else v)
                   == size * height for v in glyphs.values())
    with (output / 'toolbar.zh-TW.tsv').open() as file:
        rows = list(csv.DictReader(file, delimiter='\t', quoting=csv.QUOTE_NONE))
    assert len({r['key'] for r in rows}) == len(rows) == 13
    assert max(len(r['text']) for r in rows) <= 38
    # 不解釋原版狀態，不移動舊收據，只核對整合內容及來源。
    files = {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob('*')) if p.is_file()}
    result = {'Version': 1, 'Files': files, 'draft': True,
              'new_gameplay_verification': False, 'new_gui_sampling': False,
              'tools': {n: sha(root / 'tools' / n) for n in ['player_inputs.py', 'player.sh']}}
    (output / 'player-profile.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'profile_files': len(files), 'draft': True, 'gameplay_replayed': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'finish'])
    parser.add_argument('root', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    globals()[args.mode](args.root, args.output)
