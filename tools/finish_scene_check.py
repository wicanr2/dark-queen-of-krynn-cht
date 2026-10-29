"""兩輪中的fixture只驗實際重畫、HD切換與未完成交易，不冒充正常入口。"""
from pathlib import Path
import hashlib
import json
import sys
from PIL import Image,ImageChops

out,mode=Path(sys.argv[1]),sys.argv[2]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
for p in out.glob('*.ppm'):Image.open(p).save(p.with_suffix('.png'))
d=read(out/'session/ui-diagnostics.json');c=read(out/'session/render-counts.json')['Counts'];controls=read(out/'session/controls.json')
assert d['reader_stable'] and not d['renderer']['pending'] and not any(d['list_pending'].values()) and not d['cold_fills'] and not d['footer_transition']
assert all(c.get(key,0)==0 for key in ['native_writes','unexpected_owned_native_writes','image_native_fallback'])
assert [x['hd'] for x in controls if x['action']=='hd']==[False,True]
assert Image.open(out/'07-scale3.png').size==(960,600)
assert ImageChops.difference(Image.open(out/'05-hd-off.png'),Image.open(out/'06-hd-on.png')).getbbox()
assert 'panic:' not in (out/'player.log').read_text()
injection=read(out/'session/injection.json');assert injection['state_injection']
proof=dict(passed=True,state_injection=True,mode=mode,snapshot_sha256=injection['snapshot_sha256'],
           source={p.name:sha(p) for p in (out/'code').glob('*.go')},binary_sha256=sha(out/'scene-player'),
           counts=c,controls=controls,diagnostics_sha256=sha(out/'session/ui-diagnostics.json'),
           screenshots={p.name:sha(p) for p in out.glob('*.png')},
           scope=['fresh redraw after original snapshot','HD off/on','2x/3x','zero original pixel writes','zero pending render/UI'],
           limitations=['not a cold-entry or complete-playthrough receipt'])
(out/'checks.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(passed=True,mode=mode,native_pixel_writes=0,pending=0)))
