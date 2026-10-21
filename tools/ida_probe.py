"""IDA 9.4 唯讀證據匯出；對一次性資料庫執行，不改名或加推論型別。"""

import hashlib
import json
from pathlib import Path

import ida_auto
import ida_bytes
import ida_funcs
import ida_ida
import ida_kernwin
import ida_loader
import ida_nalt
import ida_segment
import idautils
import idc


ida_auto.auto_wait()
source = Path(ida_nalt.get_input_file_path())
segments = []
for ea in idautils.Segments():
    seg = ida_segment.getseg(ea)
    segments.append({"name": ida_segment.get_segm_name(seg),
                     "start": seg.start_ea, "end": seg.end_ea,
                     "base": ida_segment.get_segm_base(seg), "bitness": seg.bitness})
strings = []
for item in idautils.Strings():
    value = str(item)
    if any(term in value.upper() for term in (
        "CREATE", "CHARACTER", "SAVED GAME", "PLAY", "DARK QUEEN", "VERSION",
        "JOURNAL", "GAME.FON", "HLIB", "ERROR", "ADVENTURE",
    )):
        refs = []
        for xref in idautils.XrefsTo(item.ea):
            function = ida_funcs.get_func(xref.frm)
            refs.append({"from": xref.frm, "type": xref.type,
                         "function": function.start_ea if function else None})
        strings.append({"ea": item.ea, "file_offset": ida_loader.get_fileregion_offset(item.ea),
                        "value": value, "xrefs": refs})
report = {
    "schema": 1, "input": source.name,
    "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    "ida_version": ida_kernwin.get_kernel_version(),
    "address_space": "IDA linear address; segment base reported separately",
    "min_ea": ida_ida.inf_get_min_ea(), "max_ea": ida_ida.inf_get_max_ea(),
    "functions": len(list(idautils.Functions())), "segments": segments, "strings": strings,
    "entries": [{"ea": ea, "name": name} for _, _, ea, name in idautils.Entries()],
}
Path("/out/ida-probe.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
idc.qexit(0)
