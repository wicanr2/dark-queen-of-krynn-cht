"""在一次性 IDA 資料庫匯出本作 resident 繪圖分派；不改函式名或正式 DB。"""
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
import idautils
import idc

ida_auto.auto_wait()
source = Path(ida_nalt.get_input_file_path())
digest = hashlib.sha256(source.read_bytes()).hexdigest()
assert digest == '3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58'
addresses = set(idautils.Functions(0x22B70, 0x251E7))
addresses.update(idautils.Functions(0x10D70, 0x137AA))
addresses.update([0x12EE1, 0x23806, 0x212FA, 0x2130C])
for address in [0x26A25, 0x2717A, 0x2744C, 0x27598]:
    function = ida_funcs.get_func(address)
    assert function is not None
    addresses.add(function.start_ea)
result = {'schema': 1, 'input': source.name, 'sha256': digest,
          'ida_version': ida_kernwin.get_kernel_version(),
          'address_space': 'IDA linear; original file offset separately recorded',
          'semantic_level': 'unknown; raw export, no inferred symbol renaming', 'functions': []}
for address in sorted(addresses):
    function = ida_funcs.get_func(address)
    assert function is not None
    result['functions'].append({
        'start': function.start_ea, 'end': function.end_ea,
        'name': idc.get_func_name(function.start_ea),
        'flags': idc.get_func_attr(function.start_ea, idc.FUNCATTR_FLAGS),
        'file_offset': ida_loader.get_fileregion_offset(function.start_ea),
        'xrefs': [{'from': x.frm, 'type': x.type} for x in idautils.XrefsTo(function.start_ea)],
        'items': [{'ea': ea, 'file_offset': ida_loader.get_fileregion_offset(ea),
                   'bytes': (ida_bytes.get_bytes(ea, idc.get_item_size(ea)) or b'').hex(),
                   'disasm': ida_lines.tag_remove(idc.generate_disasm_line(ea, 0) or ''),
                   'code_refs': list(idautils.CodeRefsFrom(ea, False)),
                   'data_refs': list(idautils.DataRefsFrom(ea))}
                  for ea in idautils.FuncItems(function.start_ea)]})
Path('/out/render-functions.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
idc.qexit(0)
