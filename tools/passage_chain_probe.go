// DRAFT：一般按鍵下擷取 ECL 游標與原始 script segment，不改寫遊戲。
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/wicanr2/dosgolem/oracle"
)

func main() {
	check := func(err error) {
		if err != nil {
			panic(err)
		}
	}
	sha := func(raw []byte) string { h := sha256.Sum256(raw); return hex.EncodeToString(h[:]) }
	if len(os.Args) != 5 {
		panic("用法：passage-chain-probe 正常快照 一般按鍵請求 全新輸出 observe|control")
	}
	state, err := os.ReadFile(os.Args[1])
	check(err)
	requestBytes, err := os.ReadFile(os.Args[2])
	check(err)
	var req struct {
		StateSHA string `json:"state_sha256"`
		Start    uint64 `json:"start_steps"`
		Actions  []struct {
			At, End          uint64
			Kind, Key, Label string
		}
	}
	check(json.Unmarshal(requestBytes, &req))
	if req.StateSHA != sha(state) || len(req.Actions) == 0 {
		panic("快照與請求不符")
	}
	observe := os.Args[4] == "observe"
	if !observe && os.Args[4] != "control" {
		panic("未知模式")
	}
	var passageBook struct {
		SourceSHA   string                 `json:"source_sha256"`
		Occurrences []passageSourceBinding `json:"occurrences"`
	}
	passageSources := map[string]string{}
	passageBookFiles := map[string]string{}
	if path := os.Getenv("DQK_PASSAGE_BOOK"); path != "" {
		raw, err := os.ReadFile(path)
		check(err)
		check(json.Unmarshal(raw, &passageBook))
		if passageBook.SourceSHA != "40542071e42d3cd125eabcead11456a99942bf55a7736fdb79f66a3c27c3664d" || len(passageBook.Occurrences) == 0 || len(passageBook.Occurrences) > 4096 {
			panic("整句來源索引不符")
		}
		passageBookFiles["registry_sha256"] = sha(raw)
		raw, err = os.ReadFile(os.Getenv("DQK_PASSAGE_EN"))
		check(err)
		passageBookFiles["en_sha256"] = sha(raw)
		lines := strings.Split(strings.TrimSuffix(string(raw), "\n"), "\n")
		if len(lines) < 2 || lines[0] != "key\ttext" {
			panic("整句來源 TSV 標頭不符")
		}
		for _, line := range lines[1:] {
			cols := strings.Split(line, "\t")
			if len(cols) != 2 || cols[0] != "passage."+sha([]byte(cols[1]))[:20] || passageSources[cols[0]] != "" {
				panic("整句來源 TSV 不符")
			}
			passageSources[cols[0]] = cols[1]
		}
		used := map[string]bool{}
		for _, binding := range passageBook.Occurrences {
			if passageSources[binding.Key] == "" {
				panic("整句來源缺 key")
			}
			used[binding.Key] = true
		}
		if len(used) != len(passageSources) {
			panic("整句來源有孤兒 key")
		}
	}
	out := os.Args[3]
	if _, err := os.Stat(out); !os.IsNotExist(err) {
		panic("輸出須全新")
	}
	check(os.Mkdir(out, 0755))
	exe, err := os.ReadFile("/orig/DQK.EXE")
	check(err)
	if sha(exe) != "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58" {
		panic("未知 EXE")
	}
	o, err := oracle.Load("/orig/DQK.EXE", "/orig")
	check(err)
	defer o.Close()
	check(o.LoadStateFile(os.Args[1]))
	o.SetScratch(filepath.Join(out, "scratch"))
	if o.Steps() != req.Start {
		panic("起點步數不符")
	}
	read := func(ptr oracle.Addr) string {
		var raw []byte
		for i := 0; i < 1024; i++ {
			if int(ptr.Off)+i >= 0x10000 || ptr.Linear()+uint32(i) >= 0xa0000 {
				panic("字串越界")
			}
			v := o.Byte(oracle.Addr{Seg: ptr.Seg, Off: ptr.Off + uint16(i)})
			if v == 0 {
				return string(raw)
			}
			raw = append(raw, v)
		}
		panic("字串未結束")
	}
	var handler map[string]any
	handlerFresh := false
	var paragraphs []map[string]any
	passageMatchCount := 0
	pending := -1
	var pendingSS, pendingSP uint16
	files := map[string]map[string]any{}
	if observe {
		o.OnCall(oracle.Addr{Seg: 0x26b4, Off: 0x1cd3}, func(_ *oracle.Oracle) {
			if sha(o.Bytes(oracle.Addr{Seg: 0x26b4, Off: 0x1cd3}, 0xba)) != "c61ccaba966f4c04eea49304ea633c61c02566cd8ca8e93105412d50e7f239c9" {
				handler = nil
				handlerFresh = false
				return
			}
			r := o.Regs()
			handlerFresh = true
			handler = map[string]any{"step": o.Steps(), "ss": r.SS, "sp": r.SP, "caller": o.Caller(),
				"raw_b7f9": o.Word(oracle.Addr{Seg: 0x333e, Off: 0xb7f9}),
				"raw_ae5c": oracle.Addr{Seg: o.Word(oracle.Addr{Seg: 0x333e, Off: 0xae5e}), Off: o.Word(oracle.Addr{Seg: 0x333e, Off: 0xae5c})}}
		})
		o.OnCall(oracle.Addr{Seg: 0xb72, Off: 0x311}, func(_ *oracle.Oracle) {
			caller := o.Caller()
			if caller.Seg != 0x26b4 || (caller.Off != 0x1d53 && caller.Off != 0x1d81) {
				return
			}
			r := o.Regs()
			ptr := oracle.Addr{Seg: o.StackWord(10), Off: o.StackWord(9)}
			if pending >= 0 {
				if r.SS == pendingSS && r.SP+4 == pendingSP && paragraphs[pending]["caller"] == caller {
					return
				}
				panic("段落來源未配對")
			}
			if handler == nil || !handlerFresh {
				return
			}
			handlerFresh = false
			base := oracle.Addr{Seg: o.Word(oracle.Addr{Seg: 0x333e, Off: 0xae5e}), Off: o.Word(oracle.Addr{Seg: 0x333e, Off: 0xae5c})}
			p := map[string]any{"step": o.Steps(), "caller": caller, "regs": r, "handler": handler, "source_pointer": ptr, "source": read(ptr),
				"raw_ae5c": base, "raw_b7f9": o.Word(oracle.Addr{Seg: 0x333e, Off: 0xb7f9}),
				"raw_b216": o.Byte(oracle.Addr{Seg: 0x333e, Off: 0xb216}), "raw_b1c7": o.Byte(oracle.Addr{Seg: 0x333e, Off: 0xb1c7}),
				"native_box": [4]int{int(byte(o.StackWord(2))) * 8, int(byte(o.StackWord(3))) * 8, (int(byte(o.StackWord(4))) + 1) * 8, (int(byte(o.StackWord(5))) + 1) * 8},
				"foreground": byte(o.StackWord(6)), "background": byte(o.StackWord(7)), "clear": byte(o.StackWord(8))}
			if uint32(base.Seg)*16+0x8000 <= 0xa0000 {
				raw := o.Bytes(oracle.Addr{Seg: base.Seg, Off: 0}, 0x8000)
				h := sha(raw)
				name := "script-" + h + ".bin"
				if _, ok := files[h]; !ok {
					check(os.WriteFile(filepath.Join(out, name), raw, 0644))
					files[h] = map[string]any{"file": name, "sha256": h, "runtime_start": oracle.Addr{Seg: base.Seg, Off: 0}, "bytes": len(raw)}
				}
				p["script_sha256"] = h
				if len(passageBook.Occurrences) > 0 {
					view := passageSourceObservation{DS: r.DS, PointerSeg: ptr.Seg, PointerOff: ptr.Off, CallerSeg: caller.Seg, CallerOff: caller.Off,
						RawBaseOffset: base.Off, RawCursorAfter: p["raw_b7f9"].(uint16), Kind: p["raw_b216"].(byte), Opcode: p["raw_b1c7"].(byte), Clear: p["clear"].(byte), Script: raw, Source: p["source"].(string)}
					matches := []passageSourceCandidate{}
					for _, binding := range passageBook.Occurrences {
						for part := range binding.Fragments {
							if candidate, ok := matchPassageSource(binding, passageSources, part, view); ok {
								matches = append(matches, candidate)
							}
						}
					}
					p["passage_candidates"] = matches
					passageMatchCount += len(matches)
				}
			} else {
				p["script_unavailable"] = "超出傳統記憶體的界線，未讀取"
			}
			pending = len(paragraphs)
			pendingSS, pendingSP = r.SS, r.SP+4
			paragraphs = append(paragraphs, p)
			if len(paragraphs) > 10000 {
				panic("超出觀測上限")
			}
		})
		o.OnCall(oracle.Addr{Seg: 0x13c7, Off: 0xc96}, func(_ *oracle.Oracle) {
			if pending >= 0 {
				p := paragraphs[pending]
				if _, ok := p["first_glyph"]; !ok {
					p["first_glyph"] = o.Steps()
				}
			}
		})
		for _, off := range []uint16{0x1d53, 0x1d81} {
			off := off
			o.OnCall(oracle.Addr{Seg: 0x26b4, Off: off}, func(_ *oracle.Oracle) {
				if pending < 0 {
					return
				}
				r := o.Regs()
				p := paragraphs[pending]
				if p["caller"] == (oracle.Addr{Seg: 0x26b4, Off: off}) && r.SS == pendingSS && r.SP == pendingSP {
					p["return_step"] = o.Steps()
					pending = -1
				}
			})
		}
	}
	var checkpoints []map[string]any
	for _, a := range req.Actions {
		if a.At < o.Steps() || a.End <= a.At || a.Label == "" || filepath.Base(a.Label) != a.Label {
			panic("請求順序或標籤不符")
		}
		check(o.Run(a.At - o.Steps()))
		if a.Kind == "text" {
			check(o.TypeKeys(a.Key))
		} else if a.Kind == "named" {
			check(o.SendKeys(a.Key))
		} else {
			panic("未知按鍵種類")
		}
		check(o.Run(a.End - o.Steps()))
		check(o.WritePNG(filepath.Join(out, a.Label+".png")))
		ram := o.Bytes(oracle.Addr{}, 1<<20)
		checkpoints = append(checkpoints, map[string]any{"label": a.Label, "step": o.Steps(), "regs": o.Regs(), "ram_sha256": sha(ram), "indexed_sha256": sha(o.Indexed()), "palette": o.Palette(), "keys_consumed": o.KeysConsumed(), "file_writes": o.Wrote(), "unimplemented": o.Unimplemented()})
		fmt.Printf("checkpoint=%s step=%d paragraphs=%d\n", a.Label, o.Steps(), len(paragraphs))
	}
	check(o.SaveStateFile(filepath.Join(out, "final.state")))
	self, err := os.Executable()
	check(err)
	binary, err := os.ReadFile(self)
	check(err)
	pendingCount := 0
	if pending >= 0 {
		pendingCount = 1
	}
	result := map[string]any{"draft": true, "observe": observe, "exe_sha256": sha(exe), "state_sha256": sha(state), "request_sha256": sha(requestBytes), "probe_sha256": sha(binary), "source_commit": "f79eab6db8c64a524a06535e53e5d32b0bbcf7c8", "go_version": runtime.Version(), "request": req, "paragraphs": paragraphs, "pending_paragraphs": pendingCount, "script_files": files, "checkpoints": checkpoints,
		"limits": "正常快照及一般按鍵；原始游標與 script bytes 只供追查，不推定相鄰資料必依序執行，不作中文或 GUI 驗收。"}
	if len(passageBook.Occurrences) > 0 {
		result["passage_source_files"] = passageBookFiles
		result["passage_candidate_parts"] = passageMatchCount
	}
	b, err := json.MarshalIndent(result, "", "  ")
	check(err)
	check(os.WriteFile(filepath.Join(out, "receipt.json"), append(b, '\n'), 0644))
}
