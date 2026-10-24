"""無損封存大型歷史重播；原始邏輯路徑及內容雜湊保存在獨立索引。"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import time

ROOT=Path('/project')
PROBE=ROOT/'workplace/probe'
INDEX=PROBE/'storage-index.json'
KEEP={'combat-effects-20261024','passage-chain-live-20261024','combat-finish-20261024','combat-movement-20261024'}
CHUNK=1024*1024


def digest(path, compressed=False):
    h=hashlib.sha256();size=0
    with (gzip.open(path,'rb') if compressed else path.open('rb')) as f:
        while data:=f.read(CHUNK):h.update(data);size+=len(data)
    return h.hexdigest(),size


def load():
    if not INDEX.exists():return {'version':1,'entries':{},'cache_cleanup':[]}
    result=json.loads(INDEX.read_text());assert result['version']==1
    return result


def save(index):
    tmp=INDEX.with_suffix('.json.tmp')
    assert not tmp.exists()
    with tmp.open('x') as f:
        json.dump(index,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,INDEX)


def member(relative):
    p=ROOT/relative
    assert not Path(relative).is_absolute() and p.resolve().is_relative_to(PROBE.resolve())
    assert p.name=='receipt.json' and not p.is_symlink()
    return p


def archive(index,p):
    relative=str(p.relative_to(ROOT));before=p.stat()
    assert (before.st_uid,before.st_gid)==(os.getuid(),os.getgid())
    packed=p.with_suffix('.json.gz');tmp=p.with_suffix('.json.gz.partial')
    assert not packed.exists() and not tmp.exists()
    h=hashlib.sha256();size=0
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,stat.S_IMODE(before.st_mode))
    with p.open('rb') as source,os.fdopen(fd,'wb') as raw:
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,compresslevel=1,mtime=0) as target:
            while data:=source.read(CHUNK):h.update(data);size+=len(data);target.write(data)
        raw.flush();os.fsync(raw.fileno())
    original=(h.hexdigest(),size)
    assert digest(tmp,True)==original,'壓縮內容不符'
    current=p.stat()
    assert (before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(current.st_size,current.st_mtime_ns,current.st_ctime_ns),'來源在封存中變更'
    if tmp.stat().st_size>=before.st_size:
        tmp.unlink();print('skip incompressible',relative,flush=True);return 0
    row={'original_sha256':original[0],'original_bytes':size,'gzip_path':str(packed.relative_to(ROOT)),
         'gzip_sha256':digest(tmp)[0],'gzip_bytes':tmp.stat().st_size,'mode':stat.S_IMODE(before.st_mode),
         'uid':before.st_uid,'gid':before.st_gid,'mtime_ns':before.st_mtime_ns,'atime_ns':before.st_atime_ns,
         'state':'archived','updated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    previous=index['entries'].get(relative)
    if previous:assert previous['original_sha256']==row['original_sha256'],'已索引來源內容變更'
    os.replace(tmp,packed)
    index['entries'][relative]=row;save(index)
    p.unlink()
    freed=before.st_blocks*512-packed.stat().st_blocks*512
    print('archived',relative,'saved MiB',round(freed/1024**2,1),flush=True)
    return freed


def pack(index,selection=None):
    if selection:
        paths=[member(selection)]
    else:
        paths=[p for p in PROBE.rglob('receipt.json') if not p.is_symlink() and p.stat().st_size>=16*1024**2
               and p.relative_to(PROBE).parts[0] not in KEEP]
        paths.sort(key=lambda p:p.stat().st_size,reverse=True)
    freed=0
    for p in paths:freed+=archive(index,p)
    print('freed GiB',round(freed/1024**3,3),flush=True)


def verify(index):
    total=0
    for relative,row in index['entries'].items():
        p=member(relative);packed=p.with_suffix('.json.gz')
        assert str(packed.relative_to(ROOT))==row['gzip_path']
        if row['state']=='archived':
            assert digest(packed)==(row['gzip_sha256'],row['gzip_bytes']),packed
            assert digest(packed,True)==(row['original_sha256'],row['original_bytes']),packed
        else:assert digest(p)==(row['original_sha256'],row['original_bytes']),p
        total+=1
    print('verified',total,'original byte streams',flush=True)


def restore(index,selection):
    matches=[(rel,row) for rel,row in index['entries'].items() if rel==selection or rel.startswith(selection.rstrip('/')+'/')]
    assert matches,'索引沒有此路徑；請使用 list 列出邏輯路徑'
    for rel,row in matches:
        p=member(rel)
        packed=p.with_suffix('.json.gz');assert str(packed.relative_to(ROOT))==row['gzip_path']
        if row['state']=='restored':
            assert digest(p)==(row['original_sha256'],row['original_bytes'])
            if packed.exists():
                assert digest(packed)==(row['gzip_sha256'],row['gzip_bytes']);packed.unlink()
            continue
        assert digest(packed)==(row['gzip_sha256'],row['gzip_bytes'])
        assert not p.exists(),'不覆寫現有檔案'
        assert shutil.disk_usage(PROBE).free>row['original_bytes']+256*1024**2,'可用空間不足以還原此檔案'
        tmp=p.with_suffix('.json.restore-partial');assert not tmp.exists()
        fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,row['mode'])
        with gzip.open(packed,'rb') as source,os.fdopen(fd,'wb') as target:
            shutil.copyfileobj(source,target,CHUNK);target.flush();os.fsync(target.fileno())
        assert digest(tmp)==(row['original_sha256'],row['original_bytes'])
        os.chmod(tmp,row['mode']);os.utime(tmp,ns=(row['atime_ns'],row['mtime_ns']))
        os.replace(tmp,p)
        assert (p.stat().st_uid,p.stat().st_gid)==(row['uid'],row['gid'])
        row['state']='restored';save(index);packed.unlink()
        print('restored',rel,flush=True)


def cache(index):
    p=PROBE/'gocache';assert p.is_dir() and not p.is_symlink()
    assert (p.stat().st_uid,p.stat().st_gid)==(os.getuid(),os.getgid())
    for f in p.rglob('*'):
        assert f.lstat().st_uid==os.getuid(),f
    size=sum(f.stat().st_blocks*512 for f in p.rglob('*') if f.is_file() and not f.is_symlink())
    for f in p.iterdir():
        if f.is_symlink() or f.is_file():f.unlink()
        else:shutil.rmtree(f)
    index['cache_cleanup'].append({'path':str(p.relative_to(ROOT)),'allocated_bytes':size})
    save(index);print('cleared own Go cache MiB',round(size/1024**2,1),flush=True)


if __name__=='__main__':
    assert PROBE.is_dir() and PROBE.stat().st_uid==os.getuid()
    index=load();command=sys.argv[1]
    if command=='pack':pack(index,sys.argv[2] if len(sys.argv)>2 else None)
    elif command=='verify':verify(index)
    elif command=='restore':restore(index,sys.argv[2])
    elif command=='cache':cache(index)
    elif command=='list':
        for rel,row in index['entries'].items():print(row['state'],row['original_bytes'],rel)
    else:raise SystemExit('用法：pack [邏輯檔案] | list | verify | restore 邏輯檔案或目錄 | cache')
