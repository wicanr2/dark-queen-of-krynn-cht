"""核對經人工審查的 RE 回填索引；缺位址、證據或舊規格標記即失敗。"""

import csv
from pathlib import Path


root = Path(__file__).resolve().parent.parent
seen = set()
with (root / "docs/re/resolutions.tsv").open() as file:
    rows = list(csv.DictReader(file, delimiter="\t"))
if not rows:
    raise ValueError("回填索引為空")
for row in rows:
    if None in row or not all(row.values()):
        raise ValueError("回填索引欄位不完整")
    key = (row["platform_module"], row["address_key"])
    if key in seen:
        raise ValueError(f"重複不可變鍵：{key}")
    seen.add(key)
    if row["level"] not in ("已證實", "強推論", "假說", "未知"):
        raise ValueError("證據等級無效")
    paths = [root / row[column] for column in ("evidence", "older")]
    for path in paths:
        if not path.resolve().is_relative_to(root) or not path.is_file():
            raise ValueError(f"文件不存在或超出專案：{path}")
    evidence, older = [path.read_text() for path in paths]
    platform, image, image_hash, module = row["platform_module"].split(":")
    if len(image_hash) != 64 or any(c not in "0123456789abcdef" for c in image_hash):
        raise ValueError("不可變鍵缺有效輸入雜湊")
    if image not in evidence or image_hash not in evidence:
        raise ValueError("新證據缺輸入檔名或雜湊")
    if row["address_key"] not in evidence:
        raise ValueError("新證據缺原始位址")
    if row["marker"] not in older:
        raise ValueError("舊規格缺回填標記")
    relative_link = str(paths[0].relative_to(root / "docs"))
    if "../" + relative_link not in older:
        raise ValueError("舊規格缺新證據回鏈")
print(f"RE 回填索引通過：{len(rows)} 筆")
