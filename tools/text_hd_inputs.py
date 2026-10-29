"""由既有圓體輪廓重建三倍字模，不更改譯文、邏輯字級或舊字模。"""
import argparse
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_SHA = '9d5bf4932d31fe94c18cd8cfddc98bc1b14ce10f4e354c682179db290a99c825'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def make_glyph(font, ch, size, height):
    pad = size
    im = Image.new('L', (size * 3, height * 3))
    ImageDraw.Draw(im).text((pad, pad), ch, font=font, fill=255, anchor='lt')
    box = im.getbbox()
    out = Image.new('L', (size, height))
    if box is not None:
        ink = im.crop(box)
        # 輪廓的bearing可略超過等寬字格。完整字墨縮入安全框，不切掉筆畫。
        limit_h = size if size == 48 else height
        factor = min(1, size / ink.width, limit_h / ink.height)
        if factor < 1:
            ink = ink.resize((max(1, round(ink.width * factor)), max(1, round(ink.height * factor))), Image.Resampling.LANCZOS)
        out.paste(ink, (max(0, min(box[0] - pad, size - ink.width)), max(0, min(box[1] - pad, height - ink.height))))
    return base64.b64encode(out.tobytes()).decode()


def prepare(inputs, font_path):
    assert inputs.is_dir() and font_path.is_file()
    assert inputs.stat().st_uid == inputs.stat().st_gid == 1000
    assert sha(font_path) == FONT_SHA
    sets = {16: set(chr(n) for n in range(32, 127)), 20: set()}
    source = {}
    for p in sorted(inputs.rglob('*glyph*.json')):
        d = json.loads(p.read_text())
        size = d.get('size', d.get('Size'))
        chars = d.get('glyphs', d.get('Glyphs'))
        if size in sets and chars:
            source[str(p.relative_to(inputs))] = sha(p)
            sets[size].update(chars)
    assert sets[16] and sets[20]
    faces = []
    for logical, chars in sets.items():
        size, height = logical * 3, (logical + 4) * 3
        font = ImageFont.truetype(str(font_path), size)
        faces.append(dict(LogicalSize=logical, Size=size, Height=height,
                          Glyphs={ch: make_glyph(font, ch, size, height) for ch in sorted(chars)}))
    raw = json.dumps(dict(Version=1, Scale=3, FontSHA256=FONT_SHA, Faces=faces), ensure_ascii=False, separators=(',', ':')).encode()
    packed = io.BytesIO()
    with gzip.GzipFile(fileobj=packed, mode='wb', mtime=0) as z:
        z.write(raw)
    output = inputs / 'sharp-text.json.gz'
    output.write_bytes(packed.getvalue())
    provenance = inputs / 'sharp-text-provenance.json'
    provenance.write_text(json.dumps(dict(font_sha256=FONT_SHA, source_files=source,
        generator_sha256=sha(Path(__file__)), logical_sizes=[16, 20], raster_sizes=[48, 60],
        glyph_counts={str(k):len(v) for k,v in sets.items()}, output_sha256=sha(output),
        old_glyphs_unchanged=True, gameplay_changed=False), ensure_ascii=False, indent=2)+'\n')
    for name, digest in source.items():
        assert sha(inputs / name) == digest
    profile = inputs / 'player-profile.json'
    if profile.is_file():
        m = json.loads(profile.read_text())
        for name in ['sharp-text.json.gz', 'sharp-text-provenance.json']:
            m['Files'][name] = sha(inputs / name)
        profile.write_text(json.dumps(m, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(glyphs={str(k):len(v) for k,v in sets.items()}, packed_bytes=output.stat().st_size)))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('inputs', type=Path); p.add_argument('font', type=Path)
    a=p.parse_args(); prepare(a.inputs, a.font)
