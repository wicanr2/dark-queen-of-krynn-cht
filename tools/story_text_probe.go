// DRAFT：沿正常查驗輸入記錄劇情繪製前的原始參數，不翻譯、不改規則。
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
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
		panic("用法：story-probe state output [control|sequence|sequence-control|enter-sequence|enter-sequence-control|hall-sequence|hall-sequence-control|city-state|save-sequence|save-sequence-control|camp-lifecycle]")
	}
	observe, sequence, enter, hall := true, false, false, false
	cityState := false
	saveSequence := false
	campLifecycle := false
	var exitCode *uint8
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
		case "hall-sequence":
			sequence = true
			enter = true
			hall = true
		case "hall-sequence-control":
			sequence = true
			enter = true
			hall = true
			observe = false
		case "city-state":
			sequence = true
			enter = true
			observe = false
			cityState = true
		case "save-sequence", "save-sequence-control", "camp-lifecycle":
			sequence = true
			enter = true
			saveSequence = true
			observe = os.Args[3] != "save-sequence-control"
			campLifecycle = os.Args[3] == "camp-lifecycle"
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
	var menuEvents []map[string]any
	activeLabel := -1
	var labelSS, labelSP uint16
	if campLifecycle {
		for _, p := range []struct {
			addr oracle.Addr
			sig  string
			kind string
		}{
			{oracle.Addr{Seg: 0x1bb6, Off: 0x151f}, "558bec83ec0456803ec2da00751833c0", "render-entry"},
			{oracle.Addr{Seg: 0x1bb6, Off: 0x1585}, "cb558bec56803ecfda00750e1eb811a2", "render-return"},
			{oracle.Addr{Seg: 0x1bb6, Off: 0x17b8}, "cb558bec83ec085657168d46fe50168d", "selection-return"},
		} {
			if hex.EncodeToString(o.Bytes(p.addr, len(p.sig)/2)) != p.sig {
				panic("營地選單研究入口 bytes 不符")
			}
			seen := map[string]bool{}
			o.OnCall(p.addr, func(_ *oracle.Oracle) {
				if o.Steps() < 640000000 || (p.kind == "selection-return" && o.Regs().AX == 0xffff) {
					return
				}
				r := o.Regs()
				header := o.Bytes(oracle.Addr{Seg: r.DS, Off: 0xdac0}, 17)
				count := o.Word(oracle.Addr{Seg: r.DS, Off: 0xdac0})
				if count > 64 {
					panic("營地選單表超出研究界限")
				}
				ptr := oracle.Addr{Seg: o.Word(oracle.Addr{Seg: r.DS, Off: 0xdac9}), Off: o.Word(oracle.Addr{Seg: r.DS, Off: 0xdac7})}
				data := o.Bytes(ptr, int(count)*32)
				hash := sha256.Sum256(data)
				id := hex.EncodeToString(header) + hex.EncodeToString(hash[:])
				if seen[id] && p.kind != "selection-return" {
					return
				}
				seen[id] = true
				menuEvents = append(menuEvents, map[string]any{"step": o.Steps(), "kind": p.kind, "regs": r, "stack": stack(), "header_hex": hex.EncodeToString(header), "count": count, "table_pointer": ptr, "table_hex": hex.EncodeToString(data)})
				if len(menuEvents) > 2000 {
					panic("營地選單事件超出研究界限")
				}
			})
		}
		o.OnCall(oracle.Addr{Seg: 0x0ceb, Off: 0x01be}, func(_ *oracle.Oracle) {
			if activeLabel >= 0 && o.Regs().SS == labelSS && o.Regs().SP == labelSP {
				calls[activeLabel]["return_step"] = o.Steps()
				activeLabel = -1
			}
		})
	}
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
				if saveSequence {
					panic("存檔路徑文字超出研究上限")
				}
				return
			}
			s := stack()
			calls = append(calls, map[string]any{"step": o.Steps(), "stack": s, "regs": o.Regs(), "format": read(s[6], s[5]), "vararg_1_candidate": read(s[8], s[7]), "cursor_x": o.Word(oracle.Addr{Seg: o.Regs().DS, Off: 0xca12}), "cursor_y": o.Word(oracle.Addr{Seg: o.Regs().DS, Off: 0xca14})})
			if campLifecycle && s[0] == 0x01be && s[1] == 0x0ceb && s[2] == 189 && o.Steps() >= 640000000 {
				if activeLabel >= 0 {
					panic("重疊的營地標籤印字")
				}
				activeLabel, labelSS, labelSP = len(calls)-1, o.Regs().SS, o.Regs().SP+4
			}
		})
		o.OnCall(oracle.Addr{Seg: 0x13c7, Off: 0x0c96}, func(_ *oracle.Oracle) {
			if activeLabel >= 0 {
				if _, ok := calls[activeLabel]["first_glyph"]; !ok {
					calls[activeLabel]["first_glyph"] = o.Steps()
				}
			}
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
			if saveSequence {
				checkpoints[len(checkpoints)-1]["unimplemented"] = append([]string{}, o.Unimplemented()...)
			}
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
		if hall {
			storyCheck(o.TypeKeys("h"))
			storyCheck(o.Run(50000000))
			capture("hall")
		}
		if cityState {
			storyCheck(o.SaveStateFile(filepath.Join(out, "city.state")))
		}
		if saveSequence {
			for _, action := range []struct {
				key, label string
				end        uint64
			}{
				{"l", "leave", 600000000},
				{"Return", "returned-city", 615000000},
				{"i", "inn", 640000000},
				{"Return", "camp", 665000000},
				{"s", "save-menu", 690000000},
				{"j", "saved-j", 715000000},
			} {
				storyCheck(o.Run(1000000))
				if action.key == "Return" {
					storyCheck(o.SendKeys(action.key))
				} else {
					storyCheck(o.TypeKeys(action.key))
				}
				storyCheck(o.Run(action.end - o.Steps()))
				capture(action.label)
			}
			storyCheck(o.SaveStateFile(filepath.Join(out, "saved-j.state")))
			storyCheck(o.Run(1000000))
			storyCheck(o.TypeKeys("y"))
			err := o.Run(24000000)
			var ended *oracle.ExitError
			if !errors.As(err, &ended) || ended.Code != 0 {
				panic(fmt.Sprintf("正常離開 DOS 失敗：%v", err))
			}
			exitCode = &ended.Code
			capture("exit-dos")
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
		"evidence_level": "raw observation; vararg candidate is not a proven parser", "calls": calls, "glyphs": glyphs, "paragraphs": paragraphs, "steps": o.Steps(), "regs": o.Regs(), "sequence": sequence, "enter_sequence": enter, "save_sequence": saveSequence, "menu_events": menuEvents, "exit_code": exitCode, "checkpoints": checkpoints, "unimplemented": o.Unimplemented()}, "", "  ")
	storyCheck(err)
	storyCheck(os.WriteFile(filepath.Join(out, "trace.json"), append(b, '\n'), 0644))
	storyCheck(o.WritePNG(filepath.Join(out, "final.png")))
	fmt.Printf("calls=%d glyphs=%d steps=%d\n", len(calls), len(glyphs), o.Steps())
}
