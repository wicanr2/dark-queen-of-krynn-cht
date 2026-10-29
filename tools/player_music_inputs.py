"""核對固定的兩個解碼依賴，建立本作modfile，不改SDK。"""
import hashlib
from pathlib import Path
import sys
import zipfile

sdk, deps, output = map(Path,sys.argv[1:])
LOCK = {
    'oggvorbis': ('v1.0.5','f3530ac150af7922e607f238b80478ea236dbff0ff857d79b9844d2d8baf61b0'),
    'vorbis': ('v1.0.2','fcf9717a3c4e98ebb22f8f60dd3b9b4d68df0f5f70659940c05d1122052a5b9d'),
}
mod = (sdk/'go.mod').read_text()
assert 'module github.com/wicanr2/dosgolem\n' in mod
for name,(version,digest) in LOCK.items():
    module=f'github.com/jfreymuth/{name}'
    archive=deps/f'cache/download/{module}/@v/{version}.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==digest
    directory=deps/f'{module}@{version}'
    with zipfile.ZipFile(archive) as source:
        for member in source.infolist():
            if not member.is_dir():
                relative=Path(member.filename).relative_to(f'{module}@{version}')
                assert (directory/relative).read_bytes()==source.read(member), relative
    assert (directory/'LICENSE').is_file()
    mod+=f'\nrequire {module} {version}\nreplace {module} => /music-deps/{module}@{version}\n'
bridge=Path('/tools/windowbridge')
assert (bridge/'go.mod').read_text().startswith('module github.com/wicanr2/dqk-windowbridge\n')
mod+='\nrequire github.com/wicanr2/dqk-windowbridge v0.0.0\nreplace github.com/wicanr2/dqk-windowbridge => /tools/windowbridge\n'
(output/'audio-go.mod').write_text(mod)
(output/'audio-go.sum').write_bytes((sdk/'go.sum').read_bytes())
