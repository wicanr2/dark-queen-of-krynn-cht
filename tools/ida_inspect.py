"""在一次性 IDA 資料庫查原始檔偏移、直接交叉參照與原始函式。"""

import hashlib
import json
from pathlib import Path

import ida_auto
import ida_bytes
import ida_funcs
import ida_kernwin
import ida_lines
import ida_loader
import ida_nalt
import ida_segment
import idautils
import idc


ida_auto.auto_wait()
source = Path(ida_nalt.get_input_file_path())
data = source.read_bytes()
request = json.loads(Path("/out/request.json").read_text())
result = {"schema": 1, "input": source.name,
          "sha256": hashlib.sha256(data).hexdigest(),
          "ida_version": ida_kernwin.get_kernel_version(),
          "address_space": "IDA linear address; file_offset is original input offset",
          "queries": [], "segments": []}
for start in idautils.Segments():
    seg = ida_segment.getseg(start)
    result["segments"].append({"name": ida_segment.get_segm_name(seg),
                               "ea": start, "end": seg.end_ea,
                               "file_offset": ida_loader.get_fileregion_offset(start)})
for needle in request.get("strings", []):
    offset = data.find(needle.encode("ascii"))
    ea = ida_loader.get_fileregion_ea(offset) if offset >= 0 else idc.BADADDR
    row = {"needle": needle, "file_offset": offset, "ea": ea, "xrefs": []}
    if ea != idc.BADADDR:
        for ref in idautils.XrefsTo(ea):
            f = ida_funcs.get_func(ref.frm)
            row["xrefs"].append({"from": ref.frm, "type": ref.type,
                                 "function": f.start_ea if f else None})
    result["queries"].append(row)
result["functions"] = []
for address in request.get("functions", []):
    f = ida_funcs.get_func(address)
    if not f:
        result["functions"].append({"requested": address, "missing": True})
        continue
    result["functions"].append({
        "requested": address, "start": f.start_ea, "end": f.end_ea,
        "name": idc.get_func_name(f.start_ea),
        "xrefs": [{"from": x.frm, "type": x.type} for x in idautils.XrefsTo(f.start_ea)],
        "items": [{"ea": ea, "file_offset": ida_loader.get_fileregion_offset(ea),
                   "bytes": (ida_bytes.get_bytes(ea, idc.get_item_size(ea)) or b"").hex(),
                   "disasm": ida_lines.tag_remove(idc.generate_disasm_line(ea, 0) or "")}
                  for ea in idautils.FuncItems(f.start_ea)]})
result["ranges"] = []
for low, high in request.get("ranges", []):
    result["ranges"].append({"start": low, "end": high,
                            "items": [{"ea": ea,
                                       "bytes": (ida_bytes.get_bytes(ea, idc.get_item_size(ea)) or b"").hex(),
                                       "disasm": ida_lines.tag_remove(idc.generate_disasm_line(ea, 0) or "")}
                                      for ea in idautils.Heads(low, high)]})
Path("/out/result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
idc.qexit(0)
