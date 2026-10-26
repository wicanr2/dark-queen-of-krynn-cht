#!/usr/bin/env python3
"""固定 SDK 的最小呈現橋接；不修改 SDK 工作樹。失配立即停止。"""
import hashlib
import json
from pathlib import Path
import sys

sdk, output = map(Path, sys.argv[1:])
output.mkdir(exist_ok=True)
hashes = {
    "internal/machine/machine.go": "4b52b42007485e2b464bc47ada00146186ad6f88379af03be397cb051d677f6c",
    "oracle/oracle.go": "981de8928693af9700f6448eb832a2fe74d24a7ff9361ba476df044e7d0f4d74",
    "oracle/run.go": "5a1b5dcc799bf2cd67a189a739addc5bde9b1faea6a144a1dc3380d739ea97eb",
}
replace = {}
def change(text, before, after):
    if text.count(before) != 1:
        raise ValueError(f"SDK 橋接位置失配：{before[:70]}")
    return text.replace(before, after, 1)

for name, sha in hashes.items():
    raw = (sdk / name).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError(f"SDK 原始碼雜湊失配：{name}")
    text = raw.decode()
    if name.startswith("internal"):
        text = change(text, "type Machine struct {", "type Machine struct {\n\tpresentationInstruction func() bool\n\tpresentationVideoAccess func(uint32, bool, bool)")
        if text.count("err := m.CPU.Step()") != 2:
            raise ValueError("SDK 單指令呈現橋接位置失配")
        text = text.replace("err := m.CPU.Step()", "err := m.stepPresentationInstruction()")
        text = change(text, "return m.VGA.Read(a - vgaLo)", "if m.presentationVideoAccess != nil { m.presentationVideoAccess(a-vgaLo, false, false) }; return m.VGA.Read(a - vgaLo)")
        text = change(text, "if m.onVideoWrite != nil && a >= vgaLo && a < vgaHi {", "if m.presentationVideoAccess != nil && m.planarOn && a >= vgaLo && a < vgaHi { m.presentationVideoAccess(a-vgaLo, true, false) }; if m.onVideoWrite != nil && a >= vgaLo && a < vgaHi {")
        text = change(text, "m.VGA.Write(a-vgaLo, v)", "m.VGA.Write(a-vgaLo, v); if m.presentationVideoAccess != nil { m.presentationVideoAccess(a-vgaLo, true, true) }")
    elif name == "oracle/run.go":
        text = change(text, "deadline := o.m.Steps + cfg.budget", "deadline := o.m.Steps + cfg.budget\n previousPresentationDeadline:=o.presentationRunDeadline; o.presentationRunDeadline=deadline; if cfg.budget>0 {o.presentationRunDeadline--}; defer func(){o.presentationRunDeadline=previousPresentationDeadline}()")
    else:
        text = change(text, "type Oracle struct {", "type Oracle struct {\n\tpresentationRunDeadline uint64\n\tpresentationIndices func() []byte")
        text = change(text, "func (o *Oracle) Indexed() []uint8 { return o.m.Indexed() }", "func (o *Oracle) Indexed() []uint8 { if o.presentationIndices != nil { if p := o.presentationIndices(); p != nil { return p } }; return o.m.Indexed() }")
        text = change(text, "func (o *Oracle) Screen() (w, h int, px []uint8) {", "func (o *Oracle) Screen() (w, h int, px []uint8) {\n if o.presentationIndices != nil { if p := o.presentationIndices(); p != nil { return 320,200,p } }")
    target = output / Path(name).name
    target.write_text(text)
    replace["/src/" + name] = "/out/build-overlay/" + target.name

for name, source in {
    "internal/machine/dqk_presentation_video.go": "machine_presentation_video.go",
    "oracle/dqk_presentation_video.go": "oracle_presentation_video.go",
    "oracle/dqk_video_observer.go": "oracle_video_observer.go",
    "oracle/dqk_input_modifier.go": "oracle_input_modifier.go",
}.items():
    replace["/src/" + name] = "/tools/" + source
(output / "overlay.json").write_text(json.dumps({"Replace": replace}, indent=2) + "\n")
