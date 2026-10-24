"""船長對話開引號的 DRAFT 來源及前文限制，全文只留本機。"""
import ast
import copy
import csv
import json
from pathlib import Path
import shutil
import sys
import tempfile

from literal_catalog import catalog, digest, read, sha, windows
from text_catalog import write_tsv

BASE = 'victory-text-20261025/inputs-r3'
STUDY = 'captain-dialogue-20261025'
SOURCE = STUDY + '/observe-r2/receipt.json'
REVIEW = 'captain-quote-review.tsv'
FORMAL = ('en.tsv', 'zh-TW.tsv', 'catalog.json', 'glossary.tsv', 'glossary-additions.tsv')
QUOTE = 'ecl.265fda17a34611b1533d'
PREVIOUS = 'ecl.437aee976a56a4f37a63'


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def native(root, output):
    a, b = [read(output/f'{mode}-r2/receipt.json') for mode in ('observe', 'control')]
    for key in ('source_commit', 'go_version', 'exe_sha256', 'probe_sha256', 'state_sha256', 'request_sha256', 'request', 'checkpoints'):
        assert a[key] == b[key], key
    assert a['observe'] and not b['observe'] and len(a['checkpoints']) == 19
    assert a['source_commit'] == 'f79eab6db8c64a524a06535e53e5d32b0bbcf7c8'
    assert a['exe_sha256'] == '3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58'
    probe = root/'workplace/probe'
    assert a['probe_sha256'] == sha(probe/'combat-aim-route-20261024/programs-r3/ui-context-probe')
    assert a['state_sha256'] == sha(probe/'victory-text-20261025/post-observe-r7/final.state')
    assert a['request_sha256'] == sha(output/'request-r2.json')
    assert not any(v for k, v in a.items() if k.startswith('pending'))
    previous = read(output/'observe-r1/receipt.json')
    for key in ('calls', 'paragraphs', 'wrappers', 'fill_events', 'display_changes', 'menus', 'list_events'):
        assert a[key] == previous[key], key
    assert a['paragraphs'][:3] == read(probe/'victory-text-20261025/post-observe-r8/receipt.json')['paragraphs']
    for cp in a['checkpoints']:
        assert not cp['file_writes'] and not cp['unimplemented']
        for suffix in ('.idx', '.png'):
            name = cp['label']+suffix
            assert sha(output/'observe-r2'/name) == sha(output/'control-r2'/name)
    final = sha(output/'control-r2/final.state')
    assert final == sha(output/'observe-r2/final.state') == sha(output/'control-r1/final.state')
    write(output/'native-check.json', dict(checkpoints=len(a['checkpoints']), source_path=SOURCE,
        source_sha256=sha(output/'observe-r2/receipt.json'), final_state_sha256=final))


def derive(probe, texts):
    trace = read(probe/SOURCE)
    rows = list(csv.DictReader((texts/REVIEW).open(), delimiter='\t', quoting=csv.QUOTE_NONE))
    assert len(rows) == 1
    row, = rows
    assert row['key'] == QUOTE and row['key'] == 'ecl.'+digest(row['source'])[:20]
    assert len(row['source']) == len(row['text']) == 1 and row['predecessor_key'] == PREVIOUS
    assert row['evidence'] == 'victory-text-20261025/post-observe-r8/receipt.json:5191701481'
    first, quote, following, next_page = trace['paragraphs']
    assert 'ecl.'+digest(first['source']['text'])[:20] == PREVIOUS and first['clear'] == 1
    assert quote['source']['text'] == row['source'] and quote['source']['nul_terminated']
    assert quote['caller'] == dict(Seg=0x26b4, Off=0x1d53)
    assert (quote['foreground'], quote['background'], quote['clear']) == (3, 0, 0)
    assert quote['native_box'] == [8, 136, 312, 184]
    assert first['return_step'] < quote['step'] < quote['first_glyph'] < quote['return_step'] < following['step']
    assert following['clear'] == 0 and next_page['clear'] == 1
    binding = dict(Key=QUOTE, SHA256=digest(row['source']), Caller=quote['caller'], NativeBox=quote['native_box'],
        Foreground=3, Background=0, Clear=0, PredecessorKey=PREVIOUS)
    config = copy.deepcopy(read(probe/BASE/'inputs.json'))
    assert not any(p['Key'] == QUOTE for p in config['Paragraphs'])
    assert any(p['Key'] == PREVIOUS and p['Clear'] == 1 for p in config['Paragraphs'])
    config['Paragraphs'].append(binding)
    config['fine_windows'] = windows(trace)
    validation = dict(source_path=SOURCE, source_sha256=sha(probe/SOURCE))
    data = dict(row=row, binding=binding, records=[], page_validation=validation)
    return config, data


def generate(root, target):
    probe, texts = root/'workplace/probe', root/'workplace/translation'
    base = probe/BASE
    config, data = derive(probe, texts)
    values = {n: catalog(base/n) for n in ('en.tsv', 'zh-TW.tsv', 'font-zh-TW.tsv')}
    row = data['row']
    assert row['key'] not in values['en.tsv']
    values['en.tsv'][row['key']] = row['source']
    for name in ('zh-TW.tsv', 'font-zh-TW.tsv'):
        values[name][row['key']] = row['text']
    glyphs = read(base/'glyphs-16.json')
    assert row['text'] in glyphs['glyphs'], 'new glyphs required'
    shutil.copytree(base, target)
    proof = read(base/'provenance.json')
    proof['captain_extension'] = dict(base=BASE, base_files={p.name: sha(p) for p in base.iterdir()},
        source_path=SOURCE, source_sha256=sha(probe/SOURCE), review_sha256=sha(texts/REVIEW),
        formal_files={n: sha(texts/n) for n in FORMAL}, data=data)
    for name, value in values.items():
        write_tsv(target/name, ['key', 'text'], value.items())
    write(target/'inputs.json', config)
    write(target/'provenance.json', proof)


def check_sources(inputs, config, provenance, en, zh, glyphs):
    probe, texts = inputs.parent.parent, Path('/catalogs')
    base = probe/BASE
    proof = provenance['captain_extension']
    assert proof['base'] == BASE and proof['source_path'] == SOURCE
    assert proof['source_sha256'] == sha(probe/SOURCE)
    assert proof['review_sha256'] == sha(texts/REVIEW)
    assert proof['formal_files'] == {n: sha(texts/n) for n in FORMAL}
    assert proof['base_files'] == {p.name: sha(p) for p in base.iterdir()}
    expected, data = derive(probe, texts)
    assert config == expected, 'captain config'
    assert proof['data'] == data, 'captain provenance'
    parent = read(base/'provenance.json')
    assert {k: v for k, v in provenance.items() if k != 'captain_extension'} == parent
    old_en, old_zh, old_font = [catalog(base/n) for n in ('en.tsv', 'zh-TW.tsv', 'font-zh-TW.tsv')]
    assert en == dict(old_en, **{QUOTE: data['row']['source']})
    assert zh == dict(old_zh, **{QUOTE: data['row']['text']})
    assert catalog(inputs/'font-zh-TW.tsv') == dict(old_font, **{QUOTE: data['row']['text']})
    assert glyphs == read(base/'glyphs-16.json')
    for name in set(proof['base_files'])-{'en.tsv', 'zh-TW.tsv', 'font-zh-TW.tsv', 'inputs.json', 'provenance.json'}:
        assert (inputs/name).read_bytes() == (base/name).read_bytes(), name
    return base, read(base/'inputs.json'), parent, old_en, old_zh, read(base/'glyphs-16.json')


def guards(root, output):
    source = output/'inputs-r1'
    def check(p):
        check_sources(p, read(p/'inputs.json'), read(p/'provenance.json'), catalog(p/'en.tsv'), catalog(p/'zh-TW.tsv'), read(p/'glyphs-16.json'))
    check(source)
    rejected = []
    for name in ('missing-predecessor', 'wrong-predecessor', 'caller', 'clear', 'translation', 'glyph'):
        with tempfile.TemporaryDirectory(dir=output, prefix='guard-') as directory:
            p = Path(directory)
            shutil.copytree(source, p, dirs_exist_ok=True)
            c = read(p/'inputs.json')
            binding = c['Paragraphs'][-1]
            if name == 'missing-predecessor':
                binding.pop('PredecessorKey')
            elif name == 'wrong-predecessor':
                binding['PredecessorKey'] = 'ecl.93facbfe1b03675657da'
            elif name == 'caller':
                binding['Caller']['Off'] += 1
            elif name == 'clear':
                binding['Clear'] = 1
            elif name == 'translation':
                values = catalog(p/'zh-TW.tsv'); values[QUOTE] += 'x'
                write_tsv(p/'zh-TW.tsv', ['key', 'text'], values.items())
            else:
                g = read(p/'glyphs-16.json'); g['glyphs'].pop(next(iter(g['glyphs'])))
                write(p/'glyphs-16.json', g)
            write(p/'inputs.json', c)
            # 同步變造 provenance 不得繞過原版來源重建。
            proof = read(p/'provenance.json')
            proof['captain_extension']['data']['binding'] = binding
            write(p/'provenance.json', proof)
            try:
                check(p)
            except AssertionError:
                rejected.append(name)
            else:
                raise AssertionError(name)
    with tempfile.TemporaryDirectory(dir=output, prefix='rebuild-') as directory:
        target = Path(directory)/'inputs'
        generate(root, target)
        assert {p.name: sha(p) for p in target.iterdir()} == {p.name: sha(p) for p in source.iterdir()}
    write(output/'guards.json', dict(rejected=rejected, rebuilt_files=len(list(source.iterdir()))))


def review(root, output):
    assert read(output/'main-check-r1.json')['all_submitted_pixels_equal_expected']
    trace = read(output/'observe-r2/receipt.json')
    en, zh = [read(output/f'main-{lang}-r1/receipt.json') for lang in ('en', 'zh')]
    assert len(en['frames']) == len(zh['frames'])
    expected = ['ecl.'+digest(p['source']['text'])[:20] for p in trace['paragraphs']]
    entries = [e for e in zh['list_events'] if e['Kind'] == 'paragraph-before-glyph']
    assert [e['detail']['page']['Key'] for e in entries] == expected
    assert not any(e['Kind'] == 'unknown-paragraph-original' for e in zh['list_events'])
    intro, quote, following, next_page = [e['detail']['page'] for e in entries]
    assert quote['Components'] == [PREVIOUS, QUOTE]
    assert following['Components'] == expected[:3] and following['ComponentColors'] == [7, 3, 3]
    assert next_page['Components'] == expected[3:]
    visible = []
    for key in expected:
        frames = [f for f, state in zip(zh['frames'], zh['list_frames'])
            if not f['held'] and state.get('paragraph') and key in state['paragraph']['Components']]
        assert frames, ('paragraph invisible', key)
        visible.append(dict(key=key, samples=len(frames), first_file=frames[0]['File'], last_file=frames[-1]['File']))
    final = zh['list_frames'][-1]['paragraph']
    assert final['Components'] == expected[3:] and not set(final['Components']) & set(expected[:3])
    write(output/'visibility-review.json', dict(paragraphs=visible, mixed_colors=[7, 3, 3],
        previous_page_removed=True, next_page=expected[-1], english_intermediate_frames=False,
        limits='首字元前來源及連續 GPU 完整比較；不外推其餘敘事、實體鍵盤或正式入口。'))


def next_source(root, output):
    a, b = [read(output/f'next-{mode}-r1/receipt.json') for mode in ('observe', 'control')]
    for key in ('source_commit', 'go_version', 'exe_sha256', 'probe_sha256', 'state_sha256', 'request_sha256', 'request', 'checkpoints'):
        assert a[key] == b[key], key
    assert a['observe'] and not b['observe']
    assert a['state_sha256'] == sha(output/'control-r2/final.state')
    assert a['request_sha256'] == sha(output/'next-request-r1.json')
    assert not any(v for k, v in a.items() if k.startswith('pending'))
    assert len(a['checkpoints']) == 1
    for cp in a['checkpoints']:
        assert not cp['file_writes'] and not cp['unimplemented']
        for suffix in ('.idx', '.png'):
            name = cp['label']+suffix
            assert sha(output/'next-observe-r1'/name) == sha(output/'next-control-r1'/name)
    assert sha(output/'next-observe-r1/final.state') == sha(output/'next-control-r1/final.state')
    paragraph, = a['paragraphs']
    en = catalog(output/'inputs-r1/en.tsv')
    bindings = [item for item in read(output/'inputs-r1/inputs.json')['Paragraphs']
        if en[item['Key']] == paragraph['source']['text'] and item['Caller'] == paragraph['caller']
        and item['NativeBox'] == paragraph['native_box'] and all(item[k] == paragraph[v]
            for k, v in (('Foreground', 'foreground'), ('Background', 'background'), ('Clear', 'clear')))]
    binding, = bindings
    assert binding['JournalEntry'] == 59 and binding['Key'] == 'message.'+digest(paragraph['source']['text'])[:20]
    write(output/'next-source-check-r2.json', dict(checkpoints=1, source_path='next-observe-r1/receipt.json',
        source_sha256=sha(output/'next-observe-r1/receipt.json'), binding=binding, registered=True,
        next_state_sha256=sha(output/'next-control-r1/final.state'), normal_gui_conformance=False,
        correction='r1 只用 ecl 前綴計算候選；實際 caller 26B4:3320 應查既有 message 綁定，沒有新漏譯。'))


def evidence(root, output):
    for name in ('main-check-r1.json', 'native-check.json', 'guards.json', 'visibility-review.json',
                 'predecessor-test.log', 'parent-equality.json', 'rebuild-check.json', 'next-source-check-r2.json'):
        assert (output/name).is_file(), name
    names = {'captain_ui_inputs.py', 'ui_list_live_check.py', 'research_storage.py'}
    pending = list(names)
    while pending:
        name = pending.pop()
        for node in ast.walk(ast.parse((root/'tools'/name).read_text())):
            modules = [node.module] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names] if isinstance(node, ast.Import) else []
            for module in modules:
                candidate = (module or '').split('.')[0]+'.py'
                if candidate not in names and (root/'tools'/candidate).is_file():
                    names.add(candidate)
                    pending.append(candidate)
    names.update(p.name for p in (output/'programs-r1').glob('*.go'))
    names.update(('oracle_video_observer.go', 'oracle_input_modifier.go'))
    snapshots = output/'tool-snapshots'
    assert not snapshots.exists()
    snapshots.mkdir()
    for name in sorted(names):
        shutil.copyfile(root/'tools'/name, snapshots/name)
    probe = root/'workplace/probe'
    sources = list((probe/BASE).iterdir())
    sources.extend(root/'workplace/translation'/n for n in (*FORMAL, REVIEW))
    sources.extend(root/'workplace/input/dos/drkqueen'/n for n in ('DQK.EXE', 'DISK3/ECL.GLB'))
    sources.extend(probe/'victory-text-20261025'/n for n in ('evidence.json', 'post-observe-r7/final.state',
        'post-observe-r8/receipt.json', 'quote-diagnostic.json', 'quote-control-r1/ram.bin',
        'programs-r1/ui-list-live', 'continuous-en-r1/receipt.json', 'continuous-zh-r1/receipt.json'))
    sources.append(probe/'combat-aim-route-20261024/programs-r3/ui-context-probe')
    def record(p):
        stat = p.stat()
        assert (stat.st_uid, stat.st_gid) == (1000, 1000), p
        return dict(bytes=stat.st_size, sha256=sha(p), uid=stat.st_uid, gid=stat.st_gid)
    assert not (output/'evidence.json').exists()
    write(output/'evidence.json', dict(draft=True, runtime_integrated=False,
        rights='原版、全文、字模及畫格只留本機',
        engine_commit='f79eab6db8c64a524a06535e53e5d32b0bbcf7c8',
        go_image='sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581',
        pillow_image='sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48',
        effective=dict(inputs='inputs-r1', source='observe/control-r2', gpu='main-en/zh-r1',
            program='programs-r1', checks='main-check-r1.json', next_state='control-r2/final.state',
            limits='正常 Explain、開引號、自介及一頁 Return；完整繁中及正式入口尚未完成。'),
        tools={name: sha(root/'tools'/name) for name in sorted(names)},
        sources={str(p): record(p) for p in sources},
        artifacts={str(p.relative_to(output)): record(p) for p in sorted(output.rglob('*')) if p.is_file()}))


if __name__ == '__main__':
    mode = sys.argv[1]
    root, output = map(Path, sys.argv[2:4])
    if mode == 'native': native(root, output)
    elif mode == 'prepare':
        native(root, output)
        generate(root, output/'inputs-r1')
    elif mode == 'guards': guards(root, output)
    elif mode == 'review': review(root, output)
    elif mode == 'next': next_source(root, output)
    elif mode == 'evidence': evidence(root, output)
    elif mode == 'audit':
        from combat_finish_inputs import audit
        audit(root, output)
    else: raise AssertionError(mode)
