// DRAFT：沿正常查驗輸入記錄劇情繪製前的原始參數，不翻譯、不改規則。
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"github.com/wicanr2/dosgolem/oracle"
)

func storyCheck(err error) {
	if err != nil {
		panic(err)
	}
}
func main() {
	if len(os.Args) < 3 || len(os.Args) > 4 {
		panic("用法：story-probe state output [control|sequence|sequence-control|enter-sequence|enter-sequence-control]")
	}
	observe, sequence, enter := true, false, false
	if len(os.Args) == 4 {
		switch os.Args[3] {
		case "control":
			observe = false
		case "sequence":
			sequence = true
		case "sequence-control":
			sequence = true
			observe = false
		case "enter-sequence":
			sequence = true
			enter = true
		case "enter-sequence-control":
			sequence = true
			enter = true
			observe = false
		default:
			panic("未知模式")
		}
	}
	out := os.Args[2]
	if sequence {
		if _, err := os.Stat(out); !os.IsNotExist(err) {
			panic("連續劇情輸出必須為全新目錄")
		}
	}
	storyCheck(os.MkdirAll(out, 0755))
	b, err := os.ReadFile("/orig/DQK.EXE")
	storyCheck(err)
	h := sha256.Sum256(b)
	if hex.EncodeToString(h[:]) != "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58" {
		panic("EXE 不符")
	}
	o, err := oracle.Load("/orig/DQK.EXE", "/orig")
	storyCheck(err)
	defer o.Close()
	storyCheck(o.LoadStateFile(os.Args[1]))
	o.SetScratch(filepath.Join(out, "scratch"))
	if o.Steps() != 329000000 {
		panic("需正常形成的手札查驗快照 #329M")
	}
	for i, want := range []byte{0x55, 0x8b, 0xec, 0xff, 0x76, 0x0a, 0x0e, 0xe8, 0x30, 0xff, 0x59} {
		if o.Byte(oracle.Addr{Seg: 0x1212, Off: 0x03a0 + uint16(i)}) != want {
			panic("掛勾 bytes 不符")
		}
	}
	for i, want := range []byte{0x55, 0x8b, 0xec, 0x83, 0xec, 0x02, 0x56, 0x57} {
		if o.Byte(oracle.Addr{Seg: 0x0b72, Off: 0x0311 + uint16(i)}) != want {
			panic("段落掛勾 bytes 不符")
		}
	}
	read := func(seg, off uint16) map[string]any {
		if uint32(seg)*16+uint32(off) >= 0xa0000 {
			return map[string]any{"segment": seg, "offset": off, "rejected": "outside conventional RAM"}
		}
		var raw []byte
		terminated := false
		for i := 0; i < 1024; i++ {
			if uint32(seg)*16+uint32(off+uint16(i)) >= 0xa0000 {
				break
			}
			v := o.Byte(oracle.Addr{Seg: seg, Off: off + uint16(i)})
			if v == 0 {
				terminated = true
				break
			}
			raw = append(raw, v)
		}
		return map[string]any{"segment": seg, "offset": off, "raw_hex": hex.EncodeToString(raw), "text": string(raw), "nul_terminated": terminated}
	}
	stack := func() []uint16 {
		r := o.Regs()
		v := make([]uint16, 16)
		for i := range v {
			v[i] = o.Word(oracle.Addr{Seg: r.SS, Off: r.SP + uint16(2*i)})
		}
		return v
	}
	var calls, glyphs, paragraphs []map[string]any
	type pendingReturn struct {
		index  int
		addr   oracle.Addr
		ss, sp uint16
	}
	var pending []pendingReturn
	registered := map[oracle.Addr]bool{}
	if observe {
		o.OnCall(oracle.Addr{Seg: 0x0b72, Off: 0x0311}, func(_ *oracle.Oracle) {
			s := stack()
			paragraphs = append(paragraphs, map[string]any{"step": o.Steps(), "stack": s, "regs": o.Regs(),
				"source": read(s[10], s[9]), "left_column": byte(s[2]), "top_row": byte(s[3]),
				"right_column": byte(s[4]), "bottom_row": byte(s[5]), "foreground": byte(s[6]),
				"background": byte(s[7]), "clear": byte(s[8])})
			if sequence {
				if len(paragraphs) > 128 {
					panic("超過段落研究上限")
				}
				r := o.Regs()
				target := o.Caller()
				pending = append(pending, pendingReturn{len(paragraphs) - 1, target, r.SS, r.SP + 4})
				if !registered[target] {
					registered[target] = true
					o.OnCall(target, func(_ *oracle.Oracle) {
						if len(pending) == 0 {
							return
						}
						p := pending[len(pending)-1]
						r := o.Regs()
						if p.addr != target || p.ss != r.SS || p.sp != r.SP {
							return
						}
						paragraphs[p.index]["return_step"] = o.Steps()
						pending = pending[:len(pending)-1]
					})
				}
			}
		})
		o.OnCall(oracle.Addr{Seg: 0x1212, Off: 0x03a0}, func(_ *oracle.Oracle) {
			if len(calls) >= 4000 {
				return
			}
			s := stack()
			calls = append(calls, map[string]any{"step": o.Steps(), "stack": s, "regs": o.Regs(), "format": read(s[6], s[5]), "vararg_1_candidate": read(s[8], s[7]), "cursor_x": o.Word(oracle.Addr{Seg: o.Regs().DS, Off: 0xca12}), "cursor_y": o.Word(oracle.Addr{Seg: o.Regs().DS, Off: 0xca14})})
		})
		o.OnCall(oracle.Addr{Seg: 0x13c7, Off: 0x0c96}, func(_ *oracle.Oracle) {
			if len(paragraphs) > 0 {
				p := paragraphs[len(paragraphs)-1]
				if _, seen := p["first_glyph"]; !seen {
					p["first_glyph"] = o.Steps()
					p["first_glyph_stack"] = stack()
				}
			}
			if len(glyphs) < 4000 {
				glyphs = append(glyphs, map[string]any{"step": o.Steps(), "stack": stack(), "regs": o.Regs()})
			}
		})
	}
	storyCheck(o.Run(1000000))
	for _, key := range "spells\n" {
		if key == '\n' {
			storyCheck(o.SendKeys("Return"))
		} else {
			storyCheck(o.TypeKeys(string(key)))
		}
		storyCheck(o.Run(500000))
	}
	storyCheck(o.Run(375000000 - o.Steps()))
	var checkpoints []map[string]any
	if sequence {
		capture := func(label string) {
			ram := make([]byte, 1<<20)
			for i := range ram {
				ram[i] = o.Byte(oracle.Addr{Seg: uint16(i >> 4), Off: uint16(i & 15)})
			}
			h := sha256.Sum256(ram)
			pix := sha256.Sum256(o.Indexed())
			checkpoints = append(checkpoints, map[string]any{"label": label, "step": o.Steps(), "regs": o.Regs(), "ram_sha256": hex.EncodeToString(h[:]), "indexed_sha256": hex.EncodeToString(pix[:]), "palette": o.Palette(), "keys_consumed": o.KeysConsumed(), "file_writes": o.Wrote(), "paragraphs": len(paragraphs)})
			storyCheck(o.WritePNG(filepath.Join(out, label+".png")))
		}
		capture("intro")
		for i := 1; i <= 8; i++ {
			label := "space"
			if enter {
				storyCheck(o.SendKeys("Return"))
				label = "return"
			} else {
				storyCheck(o.TypeKeys(" "))
			}
			storyCheck(o.Run(25000000))
			capture(fmt.Sprintf("%s-%02d", label, i))
		}
	}
	ram := make([]byte, 1<<20)
	for i := range ram {
		ram[i] = o.Byte(oracle.Addr{Seg: uint16(i >> 4), Off: uint16(i & 15)})
	}
	ramHash, pixelsHash := sha256.Sum256(ram), sha256.Sum256(o.Indexed())
	b, err = json.MarshalIndent(map[string]any{"prototype": true, "observe": observe,
		"source_commit": "f79eab6db8c64a524a06535e53e5d32b0bbcf7c8", "input_sha256": hex.EncodeToString(h[:]),
		"ram_sha256": hex.EncodeToString(ramHash[:]), "indexed_sha256": hex.EncodeToString(pixelsHash[:]), "palette": o.Palette(),
		"evidence_level": "raw observation; vararg candidate is not a proven parser", "calls": calls, "glyphs": glyphs, "paragraphs": paragraphs, "steps": o.Steps(), "regs": o.Regs(), "sequence": sequence, "enter_sequence": enter, "checkpoints": checkpoints, "unimplemented": o.Unimplemented()}, "", "  ")
	storyCheck(err)
	storyCheck(os.WriteFile(filepath.Join(out, "trace.json"), append(b, '\n'), 0644))
	storyCheck(o.WritePNG(filepath.Join(out, "final.png")))
	fmt.Printf("calls=%d glyphs=%d steps=%d\n", len(calls), len(glyphs), o.Steps())
}
