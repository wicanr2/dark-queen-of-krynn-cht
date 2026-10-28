"""擷取固定版本SSI攻略PDF內的JPEG，供人工校圖；不作閱讀器成品。

只接受已盤點的檔案與直接DCT串流，不嘗試實作通用PDF閱讀器。
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re

from PIL import Image

SOURCE_SHA256 = 'b866541812647947a34eed7a636d8d3c7ed50b5926f576258a3dc72bdb38170d'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    data = args.source.read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCE_SHA256
    assert not args.output.exists()
    pattern = rb'<<([^<>]*?/Name/background_Page_(\d+)[^<>]*?)>>\s*stream(?:\r\n|\r|\n)'
    found = []
    for ordinal, match in enumerate(re.finditer(pattern, data)):
        dictionary = match[1]
        assert b'/Filter/DCTDecode' in dictionary and b'/ColorSpace/DeviceRGB' in dictionary
        values = {key: int(re.search(rb'/' + key.encode() + rb'\s*(\d+)', dictionary)[1])
                  for key in ('Length', 'Width', 'Height', 'BitsPerComponent')}
        assert values['BitsPerComponent'] == 8
        offset = match.end()
        image_bytes = data[offset:offset+values['Length']]
        assert image_bytes.startswith(b'\xff\xd8\xff') and image_bytes.endswith(b'\xff\xd9')
        with Image.open(io.BytesIO(image_bytes)) as image:
            assert image.format == 'JPEG' and image.size == (values['Width'], values['Height'])
            image.load()
        found.append((ordinal, image_bytes, dict(image_ordinal=ordinal, pdf_page_index=None,
            object_name=f'background_Page_{int(match[2])}', pdf_byte_offset=offset,
            bytes=len(image_bytes), width=values['Width'], height=values['Height'],
            file=f'image-{ordinal:02}.jpg', sha256=hashlib.sha256(image_bytes).hexdigest())))
    assert sorted(x[0] for x in found) == list(range(32))
    args.output.mkdir()
    for _, image_bytes, row in found:
        (args.output/row['file']).write_bytes(image_bytes)
    manifest = dict(source_sha256=SOURCE_SHA256, coordinate_space='zero-based raw PDF byte offsets',
        ordering='原檔影像串流順序，非PDF頁序；Name均重複，不拿名稱推定頁碼。',
        source_only=True, runtime_ready=False, pages=[x[2] for x in sorted(found)],
        tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (args.output/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(images=len(found), bytes=sum(len(x[1]) for x in found))))


if __name__ == '__main__':
    main()
