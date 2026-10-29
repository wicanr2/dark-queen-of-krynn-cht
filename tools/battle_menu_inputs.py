"""補入收尾抽驗取得的三個精確戰鬥表形；沿既有印字、座標與譯文。"""
import copy
import hashlib
import json
from pathlib import Path
import sys
root,output=map(Path,sys.argv[1:])
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
profile_path=output/'player-profile.json'
profile=json.loads(profile_path.read_text())
assert all(sha(output/n)==h for n,h in profile['Files'].items())
path=output/'inputs.json';config=json.loads(path.read_text())
spec=json.loads((root/'docs/spec/007-battle-menus.json').read_text())
templates={}
for f in config['Fields']:
    if f.get('Pane')=='menu' and f.get('Group')=='footer' and f.get('Caller')==spec['caller']:
        templates.setdefault(f['SHA256'],f)
added=0
for menu in spec['menus']:
    config['Menus'][menu['signature']]='combat'
    for b in menu['buttons']:
        assert b['raw_y'] in [8089,8095] and 8004<=b['raw_x']<=8152
        f=copy.deepcopy(templates[b['source_sha256']])
        f.update(MenuSignature=menu['signature'],RawX=(b['raw_x']-8000)*2,RawY=(b['raw_y']-8000)*2+1)
        assert f['Key']==b['key'] and f['FormatSHA256']==b['source_sha256'] and not f.get('Color')
        if f not in config['Fields']:config['Fields'].append(f);added+=1
path.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
profile['Files']['inputs.json']=sha(path)
profile.setdefault('tools',{})['battle_menu_inputs.py']=sha(root/'tools/battle_menu_inputs.py')
profile['battle_menu_spec_sha256']=sha(root/'docs/spec/007-battle-menus.json')
profile_path.write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(passed=True,menu_forms=3,added_fields=added,profile_sha256=sha(profile_path))))
