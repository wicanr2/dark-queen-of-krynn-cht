"""彙整現行中文、開頭與閱讀資料；不執行原版、不重跑抽驗。"""
import argparse
import base64
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from text_catalog import decode6, hlib


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def catalog(path):
    with path.open() as file:
        return {r['key']: r['text'] for r in csv.DictReader(file, delimiter='\t', quoting=csv.QUOTE_NONE)}


def save_catalog(path, data):
    path.write_text('key\ttext\n' + ''.join(k + '\t' + v + '\n' for k, v in data.items()))


FRAGMENT_OUTPUTS = ['en.tsv', 'zh-TW.tsv', 'font-zh-TW.tsv', 'glyphs-16.json', 'inputs.json']
FRAGMENT_FILES = FRAGMENT_OUTPUTS + ['fragment-provenance.json']


def fragments(root, output, font):
    """只接已實際解碼的原位元串，完整段落優先；不預測控制指令。"""
    assert output.is_dir() and output.stat().st_uid == 1000 and font.is_file()
    origin = json.loads((output / 'profile-sources.json').read_text())
    base = (root / origin['gameplay']).resolve()
    base.relative_to(root.resolve())
    assert base.is_dir() and base != output.resolve()
    old = output / 'fragment-provenance.json'
    expected = json.loads(old.read_text())['outputs'] if old.exists() else {n: sha(base / n) for n in FRAGMENT_OUTPUTS}
    for name in FRAGMENT_OUTPUTS:
        assert (output / name).stat().st_uid == 1000 and sha(output / name) == expected[name], name
    if old.exists():
        assert old.stat().st_uid == 1000
    en, zh = catalog(base / 'en.tsv'), catalog(base / 'zh-TW.tsv')
    config = json.loads((base / 'inputs.json').read_text())
    covered = {f['key'] for group in config['PassageGroups'] for f in group['fragments']}
    texts = root / 'workplace/translation'
    source, formal = catalog(texts / 'en.tsv'), catalog(texts / 'zh-TW.tsv')
    candidates = json.loads((texts / 'passage-candidates.json').read_text())
    library = root / 'workplace/input/dos/drkqueen/DISK3/ECL.GLB'
    raw = library.read_bytes()
    assert sha(library) == candidates['source_sha256'] == '40542071e42d3cd125eabcead11456a99942bf55a7736fdb79f66a3c27c3664d'
    blocks = hlib(raw)
    evidence = {}
    for group in candidates['groups']:
        for occurrence in group['sources']:
            for fragment in occurrence['fragments']:
                key = fragment['key']
                if key in covered or key in zh or key not in formal:
                    continue
                start, length = fragment['file_offset'], fragment['packed_length']
                low, high = blocks[fragment['chunk']]
                assert low <= start < start+2+length <= high
                assert raw[start:start+2] == bytes([0x80, length])
                literal = decode6(raw[start+2:start+2+length])
                assert literal == source[key] and key == 'ecl.' + hashlib.sha256(literal.encode()).hexdigest()[:20]
                assert 2 <= len(literal) <= 1024 and all(32 <= ord(ch) <= 126 for ch in literal)
                assert '%' not in literal and '\\' not in literal+formal[key] and 'JOURNAL ENTRY' not in literal
                assert formal[key] and len(formal[key]) <= 144 and not any(ch in formal[key] for ch in '\t\r\n')
                evidence.setdefault(key, []).append({'chunk': fragment['chunk'], 'file_offset': start, 'packed_length': length})
    wanted = {k for k in formal if k.startswith('ecl.') and k not in zh and k not in covered}
    assert set(evidence) == wanted and len(wanted) == 375
    glyphs = json.loads((base / 'glyphs-16.json').read_text())
    original = dict(glyphs['glyphs'])
    missing = sorted(set(''.join(formal[k] for k in wanted))-set(original))
    additions, generated = output / 'fragment-font-additions.tmp.tsv', output / 'fragment-added-glyphs.tmp.json'
    assert not additions.exists() and not generated.exists()
    if missing:
        save_catalog(additions, {'font.fragments': ''.join(missing)})
        try:
            subprocess.run([sys.executable, str(root / 'tools/menu_glyphs.py'), str(font), str(additions), str(generated), '16'], check=True)
            extra = json.loads(generated.read_text())
            assert extra['size'] == 16 and extra['height'] == 20
            glyphs['glyphs'].update(extra['glyphs'])
        finally:
            additions.unlink(missing_ok=True)
            generated.unlink(missing_ok=True)
    assert all(glyphs['glyphs'][k] == v for k, v in original.items())
    words = catalog(base / 'font-zh-TW.tsv')
    for key in sorted(wanted):
        en[key], zh[key], words[key] = source[key], formal[key], formal[key]
        for offset, color, clear in [(0x1d81, 3, 1), (0x1d81, 7, 1), (0x1d53, 3, 0), (0x1d53, 7, 0)]:
            config['Paragraphs'].append(dict(Key=key, SHA256=hashlib.sha256(source[key].encode()).hexdigest(),
                Caller=dict(Seg=0x26b4, Off=offset), NativeBox=[8, 136, 312, 184],
                Foreground=color, Background=0, Clear=clear, LiteralFragment=True))
    for name, data in [('en.tsv', en), ('zh-TW.tsv', zh), ('font-zh-TW.tsv', words)]:
        save_catalog(output / name, data)
    (output / 'inputs.json').write_text(json.dumps(config, ensure_ascii=False, indent=2)+'\n')
    (output / 'glyphs-16.json').write_text(json.dumps(glyphs, ensure_ascii=False, separators=(',', ':'))+'\n')
    provenance = dict(base=origin['gameplay'], base_files={n: sha(base / n) for n in FRAGMENT_OUTPUTS},
        formal_sha256=sha(texts / 'zh-TW.tsv'), source_sha256=sha(texts / 'en.tsv'),
        candidate_sha256=sha(texts / 'passage-candidates.json'), library_sha256=sha(library),
        keys=sorted(wanted), occurrences=evidence, added_bindings=len(wanted)*4, added_glyphs=missing,
        outputs={n: sha(output / n) for n in FRAGMENT_OUTPUTS},
        scope='只接當下已解碼的80h原位元串；既有完整段落優先，不前瞻控制指令', new_gameplay_sampling=False)
    (output / 'fragment-provenance.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(literal_fragments=len(wanted), added_glyphs=len(missing), en=len(en), zh=len(zh), new_gameplay_sampling=False)))


def display(root, output, font):
    """只衍生完整 UI／名稱來源，不把片段或語意鍵倒入完整句子路徑。"""
    assert output.is_dir() and output.stat().st_uid == 1000 and font.is_file()
    camp_save_prompts(root, output)
    for name in DISPLAY_FILES:
        if (output / name).exists():
            assert (output / name).stat().st_uid == 1000
    formal_path = root / 'workplace/translation/zh-TW.tsv'
    source_path = root / 'workplace/translation/en.tsv'
    formal, sources = catalog(formal_path), catalog(source_path)
    # 背包／商店的單複數名稱是既有正式資料，帶變數的句子也要使用同一份名稱。
    profile_sources, profile_text = catalog(output / 'en.tsv'), catalog(output / 'zh-TW.tsv')
    for key, source in profile_sources.items():
        if key.startswith(('inventory.', 'service.item.')) and key in profile_text:
            assert key not in sources or sources[key] == source
            assert key not in formal or formal[key] == profile_text[key]
            sources[key], formal[key] = source, profile_text[key]
    changed_profile = False
    for key, source in sources.items():
        if key.startswith(('ui.', 'name.')) and '%' in source and profile_sources.get(key) == source and key in formal:
            if profile_text.get(key) != formal[key]:
                profile_text[key] = formal[key]
                changed_profile = True
    if changed_profile:
        save_catalog(output / 'zh-TW.tsv', profile_text)
    candidates = {}
    for key, text in sorted(formal.items()):
        source = sources.get(key, '')
        if not key.startswith(('ui.', 'name.', 'inventory.', 'service.item.')) or not 2 <= len(source) <= 128:
            continue
        if '%' in source or any(not 32 <= ord(ch) <= 126 for ch in source):
            continue
        if text == source or not text or any(ch in text for ch in '\t\r\n') or '\\n' in text:
            continue
        candidates.setdefault(source, []).append((key, text))
    ambiguous = {source for source, rows in candidates.items() if len({text for _, text in rows}) != 1}
    rows = [(items[0][0], source, items[0][1]) for source, items in sorted(candidates.items()) if source not in ambiguous]
    formats = {}
    for key, text in sorted(formal.items()):
        source = sources.get(key, '')
        if key.startswith(('ui.', 'name.')) and '%' in source and source != text:
            formats.setdefault(source, []).append((key, text))
    format_rows = [(items[0][0], source, items[0][1]) for source, items in sorted(formats.items())
                   if len({text for _, text in items}) == 1]
    save_catalog(output / 'display-source.en.tsv', {key: source for key, source, _ in rows})
    save_catalog(output / 'display.zh-TW.tsv', {key: text for key, _, text in rows})
    save_catalog(output / 'display-format.en.tsv', {key: source for key, source, _ in format_rows})
    save_catalog(output / 'display-format.zh-TW.tsv', {key: text for key, _, text in format_rows})
    base = json.loads((output / 'glyphs-16.json').read_text())
    original_glyphs = dict(base['glyphs'])
    missing = sorted(set(''.join(text for _, _, text in rows + format_rows) +
                         ''.join(chr(n) for n in range(32, 127))) - set(original_glyphs))
    save_catalog(output / 'display-font-additions.tsv', {'font.display': ''.join(missing)})
    if missing:
        extra_path = output / 'display-added-glyphs-16.json'
        assert not extra_path.exists()
        subprocess.run([sys.executable, str(root / 'tools/menu_glyphs.py'), str(font),
                        str(output / 'display-font-additions.tsv'), str(extra_path), '16'], check=True)
        extra = json.loads(extra_path.read_text())
        assert extra['size'] == 16 and extra['height'] == 20
        base['glyphs'].update(extra['glyphs'])
        extra_path.unlink()
    assert all(base['glyphs'][ch] == value for ch, value in original_glyphs.items())
    for value in base['glyphs'].values():
        pixels = base64.b64decode(value, validate=True) if isinstance(value, str) else value
        assert len(pixels) == 320 and not any(pixels[256:]), '短標籤字墨超過原生八列'
    (output / 'display-glyphs-16.json').write_text(json.dumps(base, ensure_ascii=False, separators=(',', ':'))+'\n')
    provenance = {'formal_sha256': sha(formal_path), 'source_sha256': sha(source_path), 'font_sha256': sha(font),
                  'base_glyphs_sha256': sha(output / 'glyphs-16.json'), 'rows': len(rows),
                  'ambiguous_sources_skipped': len(ambiguous), 'new_glyphs': len(missing),
                  'format_sources': len(format_rows),
                  'scope': '完整短字串來源；尚未逐項走訪，不包含ECL片段', 'new_gameplay_sampling': False}
    (output / 'display-provenance.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'display_sources': len(rows), 'new_glyphs': len(missing), 'new_gameplay_sampling': False}))


DISPLAY_FILES = ['display-source.en.tsv', 'display.zh-TW.tsv', 'display-glyphs-16.json',
                 'display-font-additions.tsv', 'display-provenance.json',
                 'display-format.en.tsv', 'display-format.zh-TW.tsv']


def camp_save_prompts(root, output):
    """原版包裝器的完整顯示來源；譯文仍取正式主表，不改遊戲鍵值。"""
    formal = catalog(root / 'workplace/translation/zh-TW.tsv')
    en, zh = catalog(output / 'en.tsv'), catalog(output / 'zh-TW.tsv')
    config = json.loads((output / 'inputs.json').read_text())
    glyphs = json.loads((output / 'glyphs-16.json').read_text())['glyphs']
    for source, formal_key in [('save which game:', 'ui.b79e25a28abaa9602b5c'),
                               ('Exit to DOS? ', 'ui.99fd52d933e6d59c667b')]:
        digest = hashlib.sha256(source.encode()).hexdigest()
        key = 'session-save.' + digest[:20]
        field = dict(Pane='callsite', Group='footer', Key=key, SHA256=digest,
                     FormatSHA256=hashlib.sha256(b'%s').hexdigest(), Start=0,
                     Length=len(source), Width=len(source)*8-4, RawX=8004, RawY=189,
                     Caller=dict(Seg=0xb72, Off=0x27c), UpperCaller=dict(Seg=0xceb, Off=0x995),
                     UpperNative=[0, 192], Color=0x70, BackgroundOverride=7,
                     UpperFormatSHA256=hashlib.sha256(b'%s').hexdigest())
        previous = [f for f in config['Fields'] if f['Key'] == key]
        assert not previous or previous == [field], '既有儲存提示與已驗證欄位不符'
        if not previous:
            config['Fields'].append(field)
        assert key not in en or en[key] == source
        en[key], zh[key] = source, formal[formal_key]
        assert len(zh[key])*8 <= field['Width'] and all(ch in glyphs for ch in zh[key])
    save_catalog(output / 'en.tsv', en)
    save_catalog(output / 'zh-TW.tsv', zh)
    (output / 'inputs.json').write_text(json.dumps(config, ensure_ascii=False, indent=2)+'\n')


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
    shutil.copyfile(root / 'docs/spec/005-render-hooks.json', output / 'render-hooks.json')
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
        'scope': '已定稿介面的中文整合入口；未執行新增遊戲抽驗，HD另行接入',
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


def finish(root, output, replace=False):
    assert replace or not (output / 'player-profile.json').exists()
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
    assert len({r['key'] for r in rows}) == len(rows) == 14
    assert max(len(r['text']) for r in rows) <= 38
    # 不解釋原版狀態，不移動舊收據，只核對整合內容及來源。
    files = {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob('*'))
             if p.is_file() and p.name not in ['player-profile.json', 'player-profile.json.tmp']}
    approved = root / 'docs/spec/003-toolbar-approved.json'
    ui = json.loads(approved.read_text())
    assert ui['approved_date'] == '2026-10-25' and ui['geometry_fixed']
    assert ui['approved_toolbar_png_sha256'] == sha(root / 'docs/spec/003-toolbar-approved.png')
    result = {'Version': 1, 'Files': files, 'state': 'READY', 'interface_approved': True,
              'approved_interface_sha256': sha(approved),
              'new_gameplay_verification': False, 'new_gui_sampling': False,
              'tools': {n: sha(root / 'tools' / n) for n in ['player_inputs.py', 'player.sh']}}
    temporary = output / 'player-profile.json.tmp'
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(output / 'player-profile.json')
    print(json.dumps({'profile_files': len(files), 'state': 'READY', 'gameplay_replayed': False}))


def refresh(root, output, font):
    assert output.is_dir() and output.stat().st_uid == 1000
    assert (output / 'player-profile.json').is_file() and font.is_file()
    owned = ['toolbar.zh-TW.tsv', 'toolbar-glyphs-16.json', 'player-profile.json', 'render-hooks.json', 'en.tsv', 'zh-TW.tsv', 'inputs.json'] + DISPLAY_FILES + FRAGMENT_FILES
    for name in owned:
        if (output / name).exists():
            assert (output / name).stat().st_uid == 1000
    unchanged = {str(p.relative_to(output)): sha(p) for p in output.rglob('*')
                 if p.is_file() and str(p.relative_to(output)) not in owned}
    shutil.copyfile(root / 'text/toolbar.zh-TW.tsv', output / 'toolbar.zh-TW.tsv')
    shutil.copyfile(root / 'docs/spec/005-render-hooks.json', output / 'render-hooks.json')
    subprocess.run([sys.executable, str(root / 'tools/menu_glyphs.py'), str(font),
                    str(output / 'toolbar.zh-TW.tsv'), str(output / 'toolbar-glyphs-16.json'), '16'], check=True)
    fragments(root, output, font)
    display(root, output, font)
    finish(root, output, replace=True)
    assert all(sha(output / name) == digest for name, digest in unchanged.items())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'finish', 'refresh', 'display', 'fragments'])
    parser.add_argument('root', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--font', type=Path)
    args = parser.parse_args()
    if args.mode in ['refresh', 'display', 'fragments']:
        assert args.font is not None
        globals()[args.mode](args.root, args.output, args.font)
    else:
        globals()[args.mode](args.root, args.output)
