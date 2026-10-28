"""核對r3來源與正式HD，分列既定原生例外；不代表正常玩家路徑驗收。"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from PIL import Image


APPROVED_INVENTORY = "e47bfaf243226c8834383e421c6fe287a42b5a3788adb698213f05037c4bd6c6"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checked(root, name, expected):
    path = (root / name).resolve()
    require(path.is_relative_to(root.resolve()), f"路徑越界：{name}")
    data = path.read_bytes()
    require(sha(data) == expected, f"雜湊失配：{name}")
    return path


def native_policy(record, foreground, colors):
    """只分類已接受的r3例外；其他非HD來源一律保留未解決。"""
    key, source = record["key"], record["source"]
    w, h = record["width"], record["height"]
    if record["method"] == 24 and w == 0:
        return "palette_resource"
    if record["method"] == 25 and record.get("composite_children"):
        return "child_commands"
    if key == "PICC.15.1":
        return "generation_rejected"
    if foreground == 0:
        return "empty"
    if colors == 1:
        return "solid_color"
    if source in ("8X8DB", "8X8DC") and (min(w, h) < 8 or foreground < 64):
        return "small_wall_geometry"
    if source in ("PICB", "PICC") and foreground < 64:
        return "sparse_overlay"
    if source == "ALWAYS" and w <= 16 and h <= 16:
        return "cursor_geometry"
    if source == "TOPVIEW" and w == h == 8:
        return "map_geometry"
    if key in {f"COMSPR..{n}" for n in range(32, 36)} and w == h == 24:
        return "ui_geometry"
    if key in {f"DUNGCOM.{n}.26" for n in range(1, 6)} and w == h == 24:
        return "tactical_marker"
    if source == "FRAME" and w == 8 and h <= 11:
        return "ui_geometry"
    if key == "TITLE.1.1":
        return "title_gradient"
    if key == "PICC.26.1" and (w, h, foreground, colors) == (88, 88, 7744, 6):
        return "dark_edge_geometry"
    if key in {"TITLE.4.2", "TITLE.9.1", "TITLE.9.2", "TITLE.10.1", "TITLE.10.2"}:
        return "legal_credits_text"
    return "unresolved_art"


def audit(inventory_root, theme_root, original_root):
    inventory_raw = (inventory_root / "inventory.json").read_bytes()
    require(sha(inventory_raw) == APPROVED_INVENTORY, "來源盤點版本未經處置規格確認")
    inventory = json.loads(inventory_raw)
    manifest_raw = (theme_root / "hd.json").read_bytes()
    manifest = json.loads(manifest_raw)
    require(manifest.get("Ready") is True and manifest.get("Version") == 1 and manifest.get("Scale") == 3,
            "HD主題未就緒")
    records = {r["key"]: r for r in inventory["records"]}
    assets = {a["Key"]: a for a in manifest["Assets"]}
    require(len(records) == len(inventory["records"]) == 1831, "原始來源數量或鍵重複")
    require(len(assets) == len(manifest["Assets"]) and assets.keys() <= records.keys(), "HD有重複或孤兒鍵")
    sources = {}
    for item in inventory["input_files"]:
        path = checked(original_root, item["path"], item["sha256"])
        sources[Path(item["path"]).stem] = (item, path.read_bytes())
    rows = []
    for key, record in records.items():
        source, data = sources[record["source"]]
        offset, count = record["offset"], record["bytes"]
        block = data[offset:offset+count]
        require(offset >= 0 and len(block) == count and sha(block) == record["sha256"], f"原始區塊失配：{key}")
        row = {"key": key, "source": source["path"], "offset": offset,
               "source_block_sha256": record["sha256"], "method": record["method"],
               "native_size": [record["width"], record["height"]]}
        foreground = colors = 0
        original = None
        if record.get("image"):
            path = checked(inventory_root, record["image"], record["image_sha256"])
            original = Image.open(path).convert("RGBA")
            require(original.size == tuple(row["native_size"]), f"原圖尺寸失配：{key}")
            pixels = list(original.getdata())
            require(all(p[3] in (0, 255) for p in pixels), f"原圖透明度失配：{key}")
            visible = [p[:3] for p in pixels if p[3]]
            foreground, colors = len(visible), len(set(visible))
            row.update(foreground_pixels=foreground, visible_colors=colors)
        if key in assets:
            a = assets[key]
            require(original is not None and record["method"] != 25, f"非獨立圖片列為HD：{key}")
            expected = {"source_file": source["path"], "source_file_sha256": source["sha256"],
                        "source_offset": offset, "source_block_bytes": count,
                        "source_block_sha256": record["sha256"], "source_header_hex": block[:8].hex(),
                        "OriginalSHA256": record["image_sha256"], "IndexedSHA256": record["indexed_sha256"]}
            require(all(a.get(k) == v for k, v in expected.items()), f"HD來源紀錄失配：{key}")
            require(a.get("review_round") in (1, 2), f"HD審查超過兩輪：{key}")
            for name, digest_name in (("Original", "OriginalSHA256"), ("Image", "SHA256"),
                                      ("Indexed", "IndexedSHA256"), ("master", "master_sha256")):
                checked(theme_root, a[name], a[digest_name])
            painted = Image.open(theme_root / a["Image"]).convert("RGBA")
            require(painted.size == (original.width*3, original.height*3), f"HD尺寸失配：{key}")
            mask = original.getchannel("A").resize(painted.size, Image.Resampling.NEAREST)
            require(mask.tobytes() == painted.getchannel("A").tobytes(), f"HD越出原圖遮罩：{key}")
            row.update(disposition="hd", painted_sha256=a["SHA256"])
        else:
            row["disposition"] = native_policy(record, foreground, colors)
        rows.append(row)
    by_key = {row["key"]: row for row in rows}
    for record in records.values():
        if record["method"] != 25:
            continue
        for child in record["composite_children"]:
            require(child["key"] in records and records[child["key"]]["sha256"] == child["sha256"],
                    f"組圖參照失配：{record['key']}")
        by_key[record["key"]]["children"] = [
            {"key": c["key"], "disposition": by_key[c["key"]]["disposition"]}
            for c in record["composite_children"]]
    counts = dict(sorted(Counter(row["disposition"] for row in rows).items()))
    return {"version": 1, "scope": "1831筆原始來源與正式HD處置核對；不是全遊戲走訪或原版同狀態驗收",
            "inventory_sha256": sha(inventory_raw), "theme_sha256": sha(manifest_raw),
            "original_files_verified": len(sources), "source_records": len(records),
            "dispositions": counts, "unresolved_keys": [r["key"] for r in rows if r["disposition"] == "unresolved_art"],
            "passed": "unresolved_art" not in counts, "new_art_review": False,
            "new_normal_player_replay": False, "whole_game_hd_complete": False, "records": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--theme", required=True, type=Path)
    parser.add_argument("--original", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    require(args.out.parent.is_dir() and not args.out.exists(), "收據父目錄須存在，且不得覆寫舊收據")
    result = audit(args.inventory, args.theme, args.original)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "records"}, ensure_ascii=False))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
