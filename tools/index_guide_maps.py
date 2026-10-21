"""把人工圖區盤點與掃描雜湊合併成研究索引。不是地圖解碼器。"""

import argparse
import hashlib
import json
from pathlib import Path


def build(source, annotations):
    records = []
    seen = set()
    for page in annotations["pages"]:
        relative = Path(page["source"])
        path = (source / relative).resolve()
        if not path.is_relative_to(source.resolve()) or not path.is_file():
            raise ValueError(f"來源缺失或超出範圍：{relative}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        for number, title in enumerate(page["figures"], start=1):
            key = f'{page["issue"]}-{page["printed_page"]}-{number}'
            if key in seen:
                raise ValueError(f"重複圖區：{key}")
            seen.add(key)
            records.append({"key": key, "source": relative.as_posix(),
                "source_sha256": digest, "issue": page["issue"],
                "printed_page": page["printed_page"], "figure": number,
                "title_draft": title, "geometry_status": "not digitized",
                "title_status": "visual inventory; spelling needs review",
                "game_status": "not verified"})
    return {"prototype_inventory": True, "counting_unit": annotations["counting_unit"],
            "pages_reviewed": len(annotations["pages"]), "figures": len(records),
            "annotation_sha256": hashlib.sha256(json.dumps(annotations, ensure_ascii=False,
                sort_keys=True).encode()).hexdigest(), "records": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = build(args.source, json.loads(args.annotations.read_text()))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"pages":result["pages_reviewed"],"figures":result["figures"],
        "sha256":hashlib.sha256(args.output.read_bytes()).hexdigest()}))
