"""在 dkk-inventory 容器內盤點本機輸入，不改原始壓縮檔。"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    source, output = map(Path, sys.argv[1:3])
    output.mkdir(parents=True, exist_ok=True)
    if output.stat().st_uid != __import__("os").getuid():
        raise RuntimeError("輸出目錄擁有權不符")
    archives = [
        ("The Dark Queen of Krynn (1992).zip", "dos"),
        ("珍181-克萊恩黑暗之后.rar", "manual-zh"),
    ]
    reports = []
    for name, folder in archives:
        archive = source / name
        listing = json.loads(subprocess.check_output(["lsar", "-j", str(archive)]))
        members = listing["lsarContents"]
        names = set()
        for member in members:
            path = PurePosixPath(member["XADFileName"].replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
                raise ValueError(f"不安全的成員路徑：{path}")
            if member.get("XADIsLink") or member.get("XADIsSymbolicLink"):
                raise ValueError(f"拒絕連結：{path}")
            if str(path) in names:
                raise ValueError(f"重複成員：{path}")
            names.add(str(path))
        if sum(m.get("XADFileSize", 0) for m in members) > 512 * 1024 * 1024:
            raise ValueError("解壓大小超出本次盤點上限")
        destination = output / folder
        if destination.exists():
            raise FileExistsError(f"已有輸出，請先核對，拒絕覆寫：{destination}")
        destination.mkdir()
        subprocess.run(
            ["unar", "-q", "-D", "-o", str(destination), str(archive)], check=True
        )
        files = []
        for path in sorted(destination.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"拒絕解壓連結：{path}")
            if path.is_file():
                relative = path.relative_to(destination).as_posix()
                if relative not in names:
                    raise ValueError(f"未列於壓縮檔索引：{relative}")
                files.append({"path": relative, "size": path.stat().st_size,
                              "sha256": sha256(path)})
        expected = sum(not m.get("XADIsDirectory", False) for m in members)
        if len(files) != expected:
            raise ValueError(f"成員數不符：{len(files)} != {expected}")
        report = {"archive": name, "sha256": sha256(archive),
                  "format": listing["lsarFormatName"], "members": members,
                  "files": files}
        (output / f"{folder}-inventory.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
        reports.append({k: report[k] for k in ("archive", "sha256", "format")})
        print(name, report["sha256"], "files", len(files))
        for item in files:
            print(item["size"], item["sha256"][:16], item["path"])
    (output / "archives.json").write_text(
        json.dumps(reports, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
