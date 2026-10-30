"""封包正常啟動、角色管理、說明及乾淨退出的最小驗收。"""
import hashlib
import json
from pathlib import Path
import sys
from PIL import Image, ImageChops
out, mode = Path(sys.argv[1]),sys.argv[2]
launcher=mode=='windows-launcher'
if launcher:mode='windows'
session=out/('userdata/DarkQueenOfKrynn' if mode=='linux' or launcher else 'session')
for p in out.glob('*.ppm'):Image.open(p).save(p.with_suffix('.png'))
assert all((out/(n+'.png')).is_file() for n in ['01-title','02-role','03-manual'])
assert ImageChops.difference(Image.open(out/'02-role.png'),Image.open(out/'03-manual.png')).getbbox()
d=json.loads((session/'ui-diagnostics.json').read_text())
c=json.loads((session/'render-counts.json').read_text())['Counts']
assert d['reader_stable'] and not d['renderer']['pending'] and not any(d['list_pending'].values())
assert all(c.get(n,0)==0 for n in ['native_writes','unexpected_owned_native_writes','image_native_fallback'])
assert 'panic:' not in (out/'player.log').read_text(errors='replace')
result=dict(passed=True,platform=mode,execution='Linux native in container' if mode=='linux' else 'Windows executable under Wine; not Windows hardware',state_injection=False,scope=['packaged executable','cold title','normal role management','manual','clean close','zero original pixel writes'],counts=c,screenshots={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob('*.png')})
if launcher:result['scope']+=['shipped 啟動.bat entry','LOCALAPPDATA save directory']
if (out/'04-map-fullscreen.png').exists():
    assert Image.open(out/'04-map-fullscreen.png').size==(1280,900)
    for name in ['04-map-fullscreen.png','05-map-zoom.png']:
        with Image.open(out/name) as picture:
            assert sum(r>100 and g>100 and b>50 for r,g,b in picture.convert('RGB').getdata())>10000, '地圖圖稿尚未提交，不能用空視窗與載入完成的差異當縮放證據'
    assert ImageChops.difference(Image.open(out/'04-map-fullscreen.png'),Image.open(out/'05-map-zoom.png')).getbbox()
    events=[x for x in d['reader_events'] if x.get('action') in ('map-window-open','map-window-close')]
    assert [x['action'] for x in events]==['map-window-open','map-window-close']
    assert events[0]['step']==events[1]['step'] and events[0]['fullscreen']
    assert [x['key'] for x in d['manual_events']]==['F6','Right','Down','Return','Esc']
    assert d['manual_events'][-1]['page']['Mode']=='manual-index'
    with Image.open(out/'06-map-index.png') as restored:
        scale=restored.width/640
        header=restored.convert('RGB').crop(tuple(round(n*scale) for n in (32,16,624,32)))
        assert sum(r>180 and g>160 and b<140 for r,g,b in header.getdata())>30, '返回後主視窗仍為黑畫面'
    method=(out/'map-close-method.txt').read_text().strip() if (out/'map-close-method.txt').exists() else 'escape'
    assert method in ('escape','window-close','win32-close')
    result['map_close_method']=method
    result['scope']+=['packaged child process','independent fullscreen map','zoom',method+' returns to index','guest paused during map']
(out/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(passed=True,platform=mode)))
