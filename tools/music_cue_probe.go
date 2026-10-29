// 唯讀觀察原版音樂入口；不改寫暫存器、記憶體、亂數或輸入判定。
package main

import (
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/wicanr2/dosgolem/oracle"
)

func main() {
	original, out := os.Args[1], os.Args[2]
	o, err := oracle.Load(filepath.Join(original, "DQK.EXE"), original)
	if err != nil {
		panic(err)
	}
	defer o.Close()
	o.SetCmdLine("SB220 SI7 RB330")
	o.SetScratch(filepath.Join(out, "scratch"))
	rows := []map[string]any{}
	typed := []musicCue{}
	if err = observeMusic(o, func(c musicCue) { typed = append(typed, c) }); err != nil {
		panic(err)
	}
	counts := map[string]int{}
	farArg := func(offset uint16) uint16 {
		r := o.Regs()
		return o.Word(oracle.Addr{Seg: r.SS, Off: r.SP + 4 + offset})
	}
	record := func(kind string, data map[string]any) {
		counts[kind]++
		if counts[kind] > 100 {
			return
		}
		data["kind"], data["step"], data["regs"] = kind, o.Steps(), o.Regs()
		rows = append(rows, data)
	}
	o.OnCall(oracle.Addr{Seg: 0x011c, Off: 0x0c4d}, func(_ *oracle.Oracle) {
		record("loop-api", map[string]any{"stack": hex.EncodeToString(o.Bytes(oracle.Addr{Seg: o.Regs().SS, Off: o.Regs().SP}, 16))})
	})
	o.OnFileOpen(func(name string) {
		if strings.HasSuffix(strings.ToUpper(name), ".XMI") {
			record("file", map[string]any{"file": name})
		}
	})
	o.OnCall(oracle.Addr{Seg: 0x10e3, Off: 0x0176}, func(_ *oracle.Oracle) {
		record("dispatch", map[string]any{"cue": farArg(0), "tables": hex.EncodeToString(o.Bytes(oracle.Addr{Seg: o.Regs().DS, Off: 0x1f21}, 32))})
	})
	for _, hook := range []struct {
		kind string
		off  uint16
	}{{"start", 0x0265}, {"stop", 0x07ab}} {
		hook := hook
		o.OnCall(oracle.Addr{Seg: 0x0f66, Off: hook.off}, func(_ *oracle.Oracle) {
			ptr := oracle.Addr{Seg: farArg(2), Off: farArg(0)}
			data := map[string]any{"source_bytes": hex.EncodeToString(o.Bytes(ptr, 64)), "sequence": farArg(4), "stack": hex.EncodeToString(o.Bytes(oracle.Addr{Seg: o.Regs().SS, Off: o.Regs().SP}, 16))}
			if hook.kind == "start" {
				data["volume"] = farArg(6)
			}
			record(hook.kind, data)
		})
	}
	for _, hook := range []struct {
		kind string
		off  uint16
	}{{"start-return", 0x04ca}, {"stop-return", 0x08da}} {
		hook := hook
		o.OnCall(oracle.Addr{Seg: 0x0f66, Off: hook.off}, func(_ *oracle.Oracle) { record(hook.kind, map[string]any{"ax": o.Regs().AX}) })
	}
	for _, action := range []struct {
		steps uint64
		key   string
	}{{250000000, ""}, {100000000, "Return"}, {100000000, "d"}, {100000000, "Esc"}} {
		if action.key != "" {
			if action.key == "d" {
				err = o.TypeKeys("d")
			} else {
				err = o.SendKeys(action.key)
			}
			if err != nil {
				panic(err)
			}
		}
		if err = o.Run(action.steps); err != nil {
			panic(err)
		}
	}
	normalTyped := len(typed)
	if len(os.Args) > 3 && os.Args[3] == "--all-cues" {
		for _, cue := range []uint16{32, 33, 34, 35, 36, 37, 38, 39} {
			result, err := o.CallBudget(1000000, oracle.Addr{Seg: 0x10e3, Off: 0x0176}, cue)
			if err != nil || uint16(result) != 0 {
				panic(fmt.Sprintf("原版cue %d: result=%x error=%v", cue, result, err))
			}
		}
		for _, volume := range []uint16{0, 90, 100} {
			result, err := o.Call(oracle.Addr{Seg: 0x0f66, Off: 0x04cb}, 0x1f12, o.Regs().DS, 0, volume)
			if err != nil || uint16(result) != 0 {
				panic(fmt.Sprintf("音量%d: %x %v", volume, result, err))
			}
		}
		before := len(typed)
		result, err := o.Call(oracle.Addr{Seg: 0x0f66, Off: 0x0265}, 0x1f12, o.Regs().DS, 99, 100)
		if err != nil || uint16(result) != 0xfffb || len(typed) != before {
			panic("無效序列未被原版及觀察器拒絕")
		}
		for _, cue := range []uint16{41, 40, 255} {
			result, err := o.Call(oracle.Addr{Seg: 0x10e3, Off: 0x0176}, cue)
			if err != nil || uint16(result) != 0 {
				panic(fmt.Sprintf("控制cue %d: %x %v", cue, result, err))
			}
		}
	}
	raw, err := json.MarshalIndent(map[string]any{"schema": 1, "method": "normal-entry-observer; optional original-function injection explicitly separated", "counts": counts, "events": rows, "typed": typed, "normal_typed_count": normalTyped, "steps": o.Steps()}, "", "  ")
	if err != nil {
		panic(err)
	}
	if err = os.WriteFile(filepath.Join(out, "cues.json"), append(raw, '\n'), 0644); err != nil {
		panic(err)
	}
	fmt.Println(string(raw))
}
