"""彙整使用者指定的兩輪抽驗，保留正常入口與快照的證據界線。"""
import hashlib
import json
from pathlib import Path
import sys

root,player,out=map(Path,sys.argv[1:])
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
build=read(player/'build-info.json')
assert build['state']=='READY' and sha(player/'dqk-player')==build['binary_sha256']
coverage=read(player/'catalog-coverage.json')
assert coverage['passed'] and coverage['missing_runtime_bindings']==0 and coverage['formal_translations']==7730
rounds=[]
for normal,scene in [('player-sample-completion-final-r1','finish-scene-completion-r1-ready'),('player-sample-completion-final-r2','finish-scene-completion-r2')]:
    normal,scene=[root/'workplace/probe'/n for n in [normal,scene]]
    normal_proof,scene_proof=read(normal/'checks.json'),read(scene/'checks.json')
    assert normal_proof['passed'] and scene_proof['passed'] and scene_proof['state_injection']
    assert read(normal/'build-info-at-start.json')['binary_sha256']==build['binary_sha256']
    for name,want in scene_proof['source'].items():
        if name!='zz_finish_scene_inject.go':assert sha(root/'tools'/name)==want,name
    for sample in [normal,scene]:
        c=read(sample/'session/render-counts.json')['Counts']
        assert all(c.get(n,0)==0 for n in ['native_writes','unexpected_owned_native_writes','image_native_fallback'])
    rounds.append(dict(passed=True,normal_receipt=str(normal/'checks.json'),normal_sha256=sha(normal/'checks.json'),scene_receipt=str(scene/'checks.json'),scene_sha256=sha(scene/'checks.json'),state_injection_only_in_scene=True))
ammo=[json.loads(x) for x in (out/'ammo-tests.json').read_text().splitlines()]
menu=read(out/'battle-menu-checks.json')
assert menu['passed'] and menu['added_fields']==23
assert len([x for x in ammo if x['Action']=='pass' and x.get('Test')])==3
assert not any(x['Action'] in ['fail','skip'] for x in ammo)
kept={}
for name in ['scene-hd-20261029-final/checks.json','player-sample-exploration-20261029-r4/checks.json']:
    p=root/'workplace/probe'/name
    assert read(p)['passed']
    kept[name]=sha(p)
result=dict(passed=True,round_count=2,binary_sha256=build['binary_sha256'],profile_sha256=build['profile_sha256'],catalog_coverage_sha256=sha(player/'catalog-coverage.json'),rounds=rounds,ammo_tests_sha256=sha(out/'ammo-tests.json'),battle_menu_fix_sha256=sha(out/'battle-menu-checks.json'),scene_profile_scope='沿用相同Go來源的場景收據；只有23個新增戰鬥資料綁定，差額與針對性回驗另列battle-menu-checks',retained_receipts=kept,hd_manifest_sha256=sha(root/'workplace/probe/player-current/hd/hd.json'),limitations=['代表抽驗，不是逐房或全程通關','快照中未重繪像素不計入新中文或HD證據','macOS交叉建置不代表真機驗收','音樂技術輸出不代表人耳聽驗'])
(out/'two-round-checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(passed=True,round_count=2,binary_sha256=build['binary_sha256'])))
