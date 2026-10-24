// DRAFT：保存正常快照的原始碼與資料，可選一般按鍵觀測；不改寫 guest。
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"

	"github.com/wicanr2/dosgolem/oracle"
)

func main() {
	check := func(err error) {
		if err != nil {
			panic(err)
		}
	}
	sha := func(b []byte) string { h := sha256.Sum256(b); return hex.EncodeToString(h[:]) }
	if len(os.Args) != 3 && len(os.Args) != 5 {
		panic("用法：ecl-source-probe 正常快照 全新輸出目錄 [一般按鍵請求 observe|control]")
	}
	state, err := os.ReadFile(os.Args[1])
	check(err)
	exe, err := os.ReadFile("/orig/DQK.EXE")
	check(err)
	if sha(exe) != "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58" {
		panic("未知 EXE")
	}
	out := os.Args[2]
	if _, err := os.Stat(out); !os.IsNotExist(err) {
		panic("輸出目錄必須全新")
	}
	check(os.Mkdir(out, 0755))
	o, err := oracle.Load("/orig/DQK.EXE", "/orig")
	check(err)
	defer o.Close()
	check(o.LoadStateFile(os.Args[1]))
	if o.Regs().DS != 0x333e {
		panic("未知資料段")
	}
	var files []map[string]any
	for _, item := range []struct {
		name string
		addr oracle.Addr
		size int
	}{
		{"code.bin", oracle.Addr{Seg: 0x26b4, Off: 0}, 0x8000},
		{"data.bin", oracle.Addr{Seg: 0x333e, Off: 0}, 0x10000},
		{"operand-code.bin", oracle.Addr{Seg: 0x2143, Off: 0}, 0x1800},
	} {
		raw := o.Bytes(item.addr, item.size)
		check(os.WriteFile(filepath.Join(out, item.name), raw, 0644))
		files = append(files, map[string]any{"file": item.name, "runtime_address": item.addr, "bytes": len(raw), "sha256": sha(raw)})
	}
	var events, checkpoints []map[string]any
	var requestHash string
	var shortStateHash string
	if len(os.Args) == 5 {
		observe := os.Args[4] == "observe"
		if !observe && os.Args[4] != "control" {
			panic("未知觀測模式")
		}
		raw, err := os.ReadFile(os.Args[3])
		check(err)
		requestHash = sha(raw)
		var req struct {
			StateSHA string `json:"state_sha256"`
			Start    uint64 `json:"start_steps"`
			Actions  []struct {
				At, End          uint64
				Kind, Key, Label string
			}
		}
		check(json.Unmarshal(raw, &req))
		if req.StateSHA != sha(state) || req.Start != o.Steps() || len(req.Actions) == 0 {
			panic("請求與正常快照不符")
		}
		read := func(off uint16) string {
			var text []byte
			for i := 0; i < 1024; i++ {
				v := o.Byte(oracle.Addr{Seg: 0x333e, Off: off + uint16(i)})
				if v == 0 {
					return string(text)
				}
				text = append(text, v)
			}
			panic("字串未結束")
		}
		if observe {
			for _, point := range []oracle.Addr{{Seg: 0x26b4, Off: 0x1cd3}, {Seg: 0x26b4, Off: 0x1cfc}, {Seg: 0x26b4, Off: 0x1d2d}, {Seg: 0x26b4, Off: 0x1d8c}} {
				point := point
				o.OnCall(point, func(_ *oracle.Oracle) {
					events = append(events, map[string]any{"step": o.Steps(), "point": point, "regs": o.Regs(), "caller": o.Caller(),
						"raw_b216": o.Byte(oracle.Addr{Seg: 0x333e, Off: 0xb216}), "raw_b1c7": o.Byte(oracle.Addr{Seg: 0x333e, Off: 0xb1c7}),
						"data_b1c0": hex.EncodeToString(o.Bytes(oracle.Addr{Seg: 0x333e, Off: 0xb1c0}, 0x80)), "buffer": read(0xb487)})
				})
			}
			o.OnCall(oracle.Addr{Seg: 0xb72, Off: 0x311}, func(_ *oracle.Oracle) {
				if o.Caller().Seg != 0x26b4 {
					return
				}
				events = append(events, map[string]any{"step": o.Steps(), "point": oracle.Addr{Seg: 0xb72, Off: 0x311}, "caller": o.Caller(), "regs": o.Regs(),
					"raw_b216": o.Byte(oracle.Addr{Seg: 0x333e, Off: 0xb216}), "raw_b1c7": o.Byte(oracle.Addr{Seg: 0x333e, Off: 0xb1c7}),
					"source_pointer": oracle.Addr{Seg: o.StackWord(10), Off: o.StackWord(9)}, "buffer": read(0xb487)})
				if shortStateHash == "" && len(read(0xb487)) <= 15 {
					path := filepath.Join(out, "short-source.state")
					check(o.SaveStateFile(path))
					raw, err := os.ReadFile(path)
					check(err)
					shortStateHash = sha(raw)
				}
			})
		}
		for _, a := range req.Actions {
			if a.At < o.Steps() || a.End <= a.At {
				panic("請求順序不符")
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
			ram := make([]byte, 1<<20)
			for i := range ram {
				ram[i] = o.Byte(oracle.Addr{Seg: uint16(i >> 4), Off: uint16(i & 15)})
			}
			checkpoints = append(checkpoints, map[string]any{"step": o.Steps(), "label": a.Label, "regs": o.Regs(), "ram_sha256": sha(ram),
				"indexed_sha256": sha(o.Indexed()), "palette": o.Palette(), "writes": o.Wrote(), "unimplemented": o.Unimplemented()})
			fmt.Printf("checkpoint=%s step=%d\n", a.Label, o.Steps())
		}
	}
	b, err := json.MarshalIndent(map[string]any{
		"draft": true, "state_file": os.Args[1], "state_sha256": sha(state), "exe_sha256": sha(exe),
		"go_version": runtime.Version(), "steps": o.Steps(), "regs": o.Regs(), "files": files,
		"request_sha256": requestHash, "events": events, "checkpoints": checkpoints,
		"short_state_sha256": shortStateHash,
		"address_space":      "dosgolem runtime segment:offset; dump offset starts at each runtime_address",
		"limits":             "只讀正常快照及可選一般按鍵觀測；不改寫 guest，不將動態程式碼套用 resident 位址換算。單獨 dump 不作玩家路徑驗收。",
	}, "", "  ")
	check(err)
	check(os.WriteFile(filepath.Join(out, "receipt.json"), append(b, '\n'), 0644))
}
