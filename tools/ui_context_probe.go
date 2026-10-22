// DRAFT：以一般按鍵觀測介面文字；原文及暫存緩衝區在呼叫當下快照。
// 不翻譯、不修改 guest，vararg 只記候選，不視為完整格式解析器。
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

func must(err error) {
	if err != nil {
		panic(err)
	}
}
func digest(b []byte) string { h := sha256.Sum256(b); return hex.EncodeToString(h[:]) }
func writeJSON(path string, value any) {
	b, err := json.MarshalIndent(value, "", "  ")
	must(err)
	must(os.WriteFile(path, append(b, '\n'), 0644))
}

type action struct {
	At    uint64 `json:"at"`
	End   uint64 `json:"end"`
	Kind  string `json:"kind"`
	Key   string `json:"key"`
	Label string `json:"label"`
}
type request struct {
	StateSHA string   `json:"state_sha256"`
	Start    uint64   `json:"start_steps"`
	Actions  []action `json:"actions"`
}
type textSnapshot struct {
	Segment uint16 `json:"segment"`
	Offset  uint16 `json:"offset"`
	Hex     string `json:"hex"`
	Text    string `json:"text"`
	NUL     bool   `json:"nul_terminated"`
}
type call struct {
	Step       uint64       `json:"step"`
	Return     uint64       `json:"return_step,omitempty"`
	Glyph      uint64       `json:"first_glyph,omitempty"`
	Caller     oracle.Addr  `json:"caller"`
	SS         uint16       `json:"ss"`
	SP         uint16       `json:"sp"`
	Stack      []uint16     `json:"stack"`
	Format     textSnapshot `json:"format"`
	Candidate1 textSnapshot `json:"vararg_1_candidate"`
	Candidate2 textSnapshot `json:"vararg_2_candidate"`
}
type pendingCall struct {
	index  int
	addr   oracle.Addr
	ss, sp uint16
}

func main() {
	if len(os.Args) != 5 || (os.Args[4] != "observe" && os.Args[4] != "control") {
		panic("用法：ui-context-probe 原版快照 request.json 全新輸出目錄 observe|control")
	}
	stateBytes, err := os.ReadFile(os.Args[1])
	must(err)
	requestBytes, err := os.ReadFile(os.Args[2])
	must(err)
	var req request
	must(json.Unmarshal(requestBytes, &req))
	if digest(stateBytes) != req.StateSHA || len(req.Actions) == 0 {
		panic("輸入快照或動作不符")
	}
	last := req.Start
	labels := map[string]bool{}
	for _, a := range req.Actions {
		if a.At < last || a.End <= a.At || a.Label == "" || filepath.Base(a.Label) != a.Label || labels[a.Label] {
			panic("動作必須依步數排序，標籤必須唯一且不是路徑")
		}
		if a.Kind != "text" && a.Kind != "named" {
			panic("未知鍵盤輸入種類")
		}
		last = a.End
		labels[a.Label] = true
	}
	out := os.Args[3]
	if _, err := os.Stat(out); !os.IsNotExist(err) {
		panic("輸出目錄必須全新")
	}
	exe, err := os.ReadFile("/orig/DQK.EXE")
	must(err)
	if digest(exe) != "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58" {
		panic("未知 EXE")
	}
	must(os.Mkdir(out, 0755))
	o, err := oracle.Load("/orig/DQK.EXE", "/orig")
	must(err)
	defer o.Close()
	must(o.LoadStateFile(os.Args[1]))
	o.SetScratch(filepath.Join(out, "scratch"))
	if o.Steps() != req.Start {
		panic("快照步數不符")
	}
	entry := oracle.Addr{Seg: 0x1212, Off: 0x03a0}
	glyph := oracle.Addr{Seg: 0x13c7, Off: 0x0c96}
	if hex.EncodeToString(o.Bytes(entry, 11)) != "558becff760a0ee830ff59" {
		panic("印字入口不符")
	}
	if hex.EncodeToString(o.Bytes(glyph, 3)) != hex.EncodeToString(exe[0x15c06:0x15c09]) {
		panic("字元入口不符")
	}
	read := func(seg, off uint16) textSnapshot {
		s := textSnapshot{Segment: seg, Offset: off}
		var raw []byte
		for i := 0; i < 256; i++ {
			if uint32(off)+uint32(i) > 0xffff || uint32(seg)*16+uint32(off)+uint32(i) >= 0xa0000 {
				break
			}
			v := o.Byte(oracle.Addr{Seg: seg, Off: off + uint16(i)})
			if v == 0 {
				s.NUL = true
				break
			}
			raw = append(raw, v)
		}
		s.Hex = hex.EncodeToString(raw)
		s.Text = string(raw)
		return s
	}
	var calls []call
	var pending []pendingCall
	registered := map[oracle.Addr]bool{}
	observe := os.Args[4] == "observe"
	if observe {
		o.OnCall(entry, func(_ *oracle.Oracle) {
			if len(calls) >= 10000 {
				panic("超出文字觀測上限")
			}
			r := o.Regs()
			s := make([]uint16, 16)
			for i := range s {
				s[i] = o.Word(oracle.Addr{Seg: r.SS, Off: r.SP + uint16(i*2)})
			}
			target := oracle.Addr{Seg: s[1], Off: s[0]}
			calls = append(calls, call{Step: o.Steps(), Caller: target, SS: r.SS, SP: r.SP, Stack: s, Format: read(s[6], s[5]), Candidate1: read(s[8], s[7]), Candidate2: read(s[10], s[9])})
			pending = append(pending, pendingCall{len(calls) - 1, target, r.SS, r.SP + 4})
			if !registered[target] {
				registered[target] = true
				o.OnCall(target, func(_ *oracle.Oracle) {
					if len(pending) == 0 {
						return
					}
					p := pending[len(pending)-1]
					r := o.Regs()
					if p.addr == target && p.ss == r.SS && p.sp == r.SP {
						calls[p.index].Return = o.Steps()
						pending = pending[:len(pending)-1]
					}
				})
			}
		})
		o.OnCall(glyph, func(_ *oracle.Oracle) {
			if len(pending) > 0 {
				c := &calls[pending[len(pending)-1].index]
				if c.Glyph == 0 {
					c.Glyph = o.Steps()
				}
			}
		})
	}
	ramSnapshot := func() []byte {
		ram := make([]byte, 1<<20)
		for i := range ram {
			ram[i] = o.Byte(oracle.Addr{Seg: uint16(i >> 4), Off: uint16(i & 15)})
		}
		return ram
	}
	var checkpoints []map[string]any
	for _, a := range req.Actions {
		must(o.Run(a.At - o.Steps()))
		if a.Kind == "text" {
			must(o.TypeKeys(a.Key))
		} else {
			must(o.SendKeys(a.Key))
		}
		must(o.Run(a.End - o.Steps()))
		must(o.WritePNG(filepath.Join(out, a.Label+".png")))
		checkpoints = append(checkpoints, map[string]any{"label": a.Label, "step": o.Steps(), "regs": o.Regs(), "ram_sha256": digest(ramSnapshot()), "indexed_sha256": digest(o.Indexed()), "palette": o.Palette(), "keys_consumed": o.KeysConsumed(), "file_writes": o.Wrote(), "unimplemented": o.Unimplemented()})
	}
	must(o.SaveStateFile(filepath.Join(out, "final.state")))
	must(os.WriteFile(filepath.Join(out, "ram.bin"), ramSnapshot(), 0644))
	self, err := os.Executable()
	must(err)
	binary, err := os.ReadFile(self)
	must(err)
	var matches []int
	for i, c := range calls {
		if strings.Contains(strings.ToLower(c.Format.Text+" "+c.Candidate1.Text), "shield") {
			matches = append(matches, i)
		}
	}
	writeJSON(filepath.Join(out, "receipt.json"), map[string]any{"draft": true, "observe": observe, "source_commit": "f79eab6db8c64a524a06535e53e5d32b0bbcf7c8", "go_version": runtime.Version(), "exe_sha256": digest(exe), "state_sha256": digest(stateBytes), "request_sha256": digest(requestBytes), "probe_sha256": digest(binary), "request": req, "calls": calls, "shield_candidate_indices": matches, "pending_calls": len(pending), "checkpoints": checkpoints, "limits": "Original normal key input from a normal-route snapshot; no translation or GUI claim. Candidate varargs are raw pointers, not a complete formatter."})
	fmt.Printf("observe=%t calls=%d shield_candidates=%d checkpoints=%d pending=%d\n", observe, len(calls), len(matches), len(checkpoints), len(pending))
}
