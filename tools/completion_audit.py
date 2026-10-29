"""逐項核對正式譯文的執行入口；完整組句中的片段不當作漏接。"""
import csv
import hashlib
import json
from pathlib import Path
import sys

root, profile, output = map(Path,sys.argv[1:])
assert output.is_dir() and output.stat().st_uid==1000
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    rows=list(csv.DictReader(p.open(),delimiter='\t',quoting=csv.QUOTE_NONE))
    assert len({r['key'] for r in rows})==len(rows)
    return {r['key']:r['text'] for r in rows}
formal=read(root/'workplace/translation/zh-TW.tsv')
original=read(root/'workplace/translation/en.tsv')
assert len(formal)==7730 and all(formal.values())
manifest=json.loads((profile/'player-profile.json').read_text())
assert all(sha(profile/n)==h for n,h in manifest['Files'].items())
runtime={}
for en,zh in [('en.tsv','zh-TW.tsv'),('display-source.en.tsv','display.zh-TW.tsv'),('display-format.en.tsv','display-format.zh-TW.tsv')]:
    source,target=read(profile/en),read(profile/zh)
    for key,text in source.items():
        if target.get(key):runtime[key]=(text,target[key],en)
by_source={}
for key,(en,zh,file) in runtime.items():by_source.setdefault(en,[]).append((key,zh,file))
config=json.loads((profile/'inputs.json').read_text())
groups={}
for group in config['PassageGroups']:
    key=group['key']
    assert key in runtime and runtime[key][0]==''.join(original[f['key']] for f in group['fragments'])
    assert all(f['key']=='ecl.'+hashlib.sha256(original[f['key']].encode()).hexdigest()[:20] for f in group['fragments'])
    for fragment in group['fragments']:groups.setdefault(fragment['key'],[]).append(key)
rows=[]
for key,text in formal.items():
    source=original[key]
    if key in runtime and runtime[key][:2]==(source,text):
        route={'mode':'direct','key':key,'file':runtime[key][2]}
    elif any(zh==text for _,zh,_ in by_source.get(source,[])):
        k,_,f=next(x for x in by_source[source] if x[1]==text)
        route={'mode':'source-alias','key':k,'file':f}
    elif key in groups:
        route={'mode':'complete-passage','groups':groups[key]}
    else:
        raise AssertionError(('正式譯文尚未接入',key,source))
    rows.append(dict(key=key,source_sha256=hashlib.sha256(source.encode()).hexdigest(),route=route))
catalog=json.loads((root/'workplace/translation/catalog.json').read_text())
excluded=[e for e in catalog['entries'] if e['key'] not in formal]
observed=[e for e in excluded if e['status']=='observed']
assert len(excluded)==679 and len(observed)==10 and {e['text'] for e in observed}==set('ABCDEFGHIJ')
result=dict(passed=True,formal_translations=len(rows),missing_runtime_bindings=0,empty_translations=0,
            routes={mode:sum(x['route']['mode']==mode for x in rows) for mode in ['direct','source-alias','complete-passage']},
            excluded_candidates=679,observed_exclusions='存檔槽A至J',unproven_name_candidates=['AMT','HNZH'],
            source_sha256=sha(root/'workplace/translation/en.tsv'),formal_sha256=sha(root/'workplace/translation/zh-TW.tsv'),
            profile_sha256=sha(profile/'player-profile.json'),rows=rows,
            scope='靜態串接與來源核對；正常玩家路徑由兩輪抽驗另證，不宣稱全程通關')
(output/'catalog-coverage.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False))
