"""對一次性正常快照程式碼做窄範圍 IDA 匯出，不改原名或正式資料庫。"""
import hashlib
import json
import os
from pathlib import Path

import ida_auto
import ida_bytes
import ida_funcs
import ida_ida
import ida_kernwin
import ida_lines
import ida_nalt
import ida_segment
import idautils
import idc

ida_auto.auto_wait()
source=Path(ida_nalt.get_input_file_path())
raw=source.read_bytes()
source_hash=hashlib.sha256(raw).hexdigest()
operand=os.environ.get("DQK_IDA_OPERAND")=="1"
expected="071f664a608452867245e16908603093737970b3f5bbf1ac5a3cc7936e0bbfda" if operand else "0d24c211c1ea4f196a672a1a1c7cc1f2b2c7fcb01e1c57d6ac27a40b9da19a15"
assert source_hash==expected
assert ida_ida.inf_get_min_ea()==0 and ida_bytes.get_bytes(0,len(raw))==raw
assert ida_segment.set_segm_addressing(ida_segment.getseg(0),0)
low,high=(0x13,0x112) if operand else (0x1cd3,0x1d8d)
assert raw[low:low+3]==bytes.fromhex("558bec") and raw[high:high+3]==bytes.fromhex("558bec")
ida_bytes.del_items(low,ida_bytes.DELIT_SIMPLE,high-low)
assert idc.create_insn(low)>0
ida_funcs.add_func(low,high)
ida_auto.auto_wait()
function=ida_funcs.get_func(low)
assert function and function.start_ea==low and function.end_ea==high
result=dict(input_file=source.name,input_sha256=source_hash,ida_version=ida_kernwin.get_kernel_version(),
    address_space="IDA binary dump linear base 0; dump offset equals captured runtime segment offset only",
    runtime_segment=0x2143 if operand else 0x26b4,
    function=dict(start=low,end=high,name=idc.get_func_name(low),boundary_status="candidate; requires runtime entry/return evidence"),
    items=[dict(ea=ea,code=ida_bytes.is_code(ida_bytes.get_full_flags(ea)),bytes=ida_bytes.get_bytes(ea,idc.get_item_size(ea)).hex(),
        disasm=ida_lines.tag_remove(idc.generate_disasm_line(ea,0) or "")) for ea in idautils.Heads(low,high)],
    xrefs=[dict(source=x.frm,type=x.type) for x in idautils.XrefsTo(low)])
target=Path("/out/ida-operand-r1.json" if operand else "/out/ida-handler-r2.json")
assert not target.exists()
target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
idc.qexit(0)
