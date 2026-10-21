// DRAFT：只讀觀測正常選單、讀取來源與返回，不改 guest 或輸入判定。
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"github.com/wicanr2/dosgolem/oracle"
)

func require(err error) {
	if err != nil {
		panic(err)
	}
}
func hash(data []byte) string { sum := sha256.Sum256(data); return hex.EncodeToString(sum[:]) }

func main() {
	state := flag.String("state", "", "正常冷啟動的239M快照")
	out := flag.String("out", "", "全新隔離研究目錄")
	observe := flag.Bool("observe", true, "啟用唯讀觀測")
	route := flag.String("route", "roundtrip", "roundtrip、begin-empty 或 adventure")
	flag.Parse()
	if *route != "roundtrip" && *route != "begin-empty" && *route != "adventure" {
		panic("未知正常路徑")
	}
	if _, err := os.Stat(*out); !os.IsNotExist(err) {
		panic("研究輸出必須是全新目錄")
	}
	require(os.MkdirAll(*out, 0755))
	exe, err := os.ReadFile("/orig/DQK.EXE")
	require(err)
	if hash(exe) != "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58" {
		panic("未知EXE")
	}
	o, err := oracle.Load("/orig/DQK.EXE", "/orig")
	require(err)
	defer o.Close()
	require(o.LoadStateFile(*state))
	o.SetScratch(filepath.Join(*out, "scratch"))
	if o.Steps() != 239000000 {
		panic("快照步數不符")
	}
	anchor := oracle.Addr{Seg: 0x1212, Off: 0x03a0}
	if hex.EncodeToString(o.Bytes(anchor, 11)) != "558becff760a0ee830ff59" {
		panic("文字入口bytes不符")
	}
	stack := func() []uint16 {
		words := make([]uint16, 24)
		for i := range words {
			words[i] = o.StackWord(i)
		}
		return words
	}
	var events []map[string]any
	var lifecycle []map[string]any
	seenLifecycle := map[string]bool{}
	writers := map[uint32]map[string]any{}
	if *observe {
		for _, point := range []struct {
			off  uint16
			kind string
		}{{0x151f, "render-entry"}, {0x1585, "render-return"}, {0x15e3, "input-entry"}, {0x17b8, "input-return"}} {
			point := point
			o.OnCall(oracle.Addr{Seg: 0x1bb6, Off: point.off}, func(_ *oracle.Oracle) {
				r := o.Regs()
				count := o.Word(oracle.Addr{Seg: r.DS, Off: 0xdac0})
				ptr := oracle.Addr{Seg: o.Word(oracle.Addr{Seg: r.DS, Off: 0xdac9}), Off: o.Word(oracle.Addr{Seg: r.DS, Off: 0xdac7})}
				if count > 64 {
					panic("選單表超出研究界限")
				}
				raw := o.Bytes(ptr, int(count)*32)
				header := hex.EncodeToString(o.Bytes(oracle.Addr{Seg: r.DS, Off: 0xdac0}, 17))
				phase := 0
				if o.Steps() >= 260000000 {
					phase = 1
				}
				if o.Steps() >= 275000000 {
					phase = 2
				}
				id := fmt.Sprintf("%d-%s-%s-%s", phase, point.kind, hash(raw), header)
				if seenLifecycle[id] && !(point.kind == "input-return" && r.AX != 0xffff) {
					return
				}
				seenLifecycle[id] = true
				if len(lifecycle) > 1000 {
					panic("選單生命週期事件超出研究界限")
				}
				lifecycle = append(lifecycle, map[string]any{"step": o.Steps(), "kind": point.kind, "regs": r, "stack": stack(),
					"count": count, "table_pointer": ptr, "table_hex": hex.EncodeToString(raw), "menu_header_hex": header, "oracle_runtime_ip": o.IP()})
			})
		}
		o.OnCall(anchor, func(_ *oracle.Oracle) {
			s := stack()
			r := o.Regs()
			var text []byte
			terminated := false
			for i := 0; i < 255; i++ {
				c := o.Byte(oracle.Addr{Seg: s[6], Off: s[5] + uint16(i)})
				if c == 0 {
					terminated = true
					break
				}
				if c < 32 || c > 126 {
					return
				}
				text = append(text, c)
			}
			if !terminated || len(text) == 0 {
				return
			}
			if len(events) >= 1000 {
				panic("文字事件超出研究上限")
			}
			bpWords := make([]uint16, 12)
			for i := range bpWords {
				bpWords[i] = o.Word(oracle.Addr{Seg: r.SS, Off: r.BP + uint16(i*2)})
			}
			caller := o.Caller()
			events = append(events, map[string]any{"step": o.Steps(), "source": string(text), "stack": s, "regs": r,
				"far_return_candidate": caller, "near_return_candidate": o.NearCaller(), "bp_words": bpWords,
				"return_bytes": hex.EncodeToString(o.Bytes(caller, 32))})
		})
		// OnWrite.At 屬 Oracle 的位址空間；另存該工具的基底，避免冒充 IDA linear。
		o.OnWrite(0xa0000, 0xaffff, func(_ *oracle.Oracle, hit oracle.WriteHit) {
			if hit.Old == hit.Val {
				return
			}
			row, ok := writers[hit.At]
			if !ok {
				if len(writers) >= 128 {
					panic("顯存寫入來源超出研究上限")
				}
				row = map[string]any{"oracle_at": hit.At, "runtime_linear": hit.At - o.ToIDA(oracle.Addr{}),
					"first_step": o.Steps(), "first_address": hit.Addr, "regs": o.Regs(), "stack": stack(), "count": uint64(0)}
				writers[hit.At] = row
			}
			row["count"] = row["count"].(uint64) + 1
			row["last_step"] = o.Steps()
		})
	}
	var checkpoints []map[string]any
	capture := func(name string) {
		ram := make([]byte, 1<<20)
		for i := range ram {
			ram[i] = o.Byte(oracle.Addr{Seg: uint16(i >> 4), Off: uint16(i & 15)})
		}
		require(o.WritePNG(filepath.Join(*out, name+".png")))
		require(o.SaveStateFile(filepath.Join(*out, name+".state")))
		checkpoints = append(checkpoints, map[string]any{"name": name, "step": o.Steps(), "regs": o.Regs(),
			"ram_sha256": hash(ram), "indexed_sha256": hash(o.Indexed()), "palette": o.Palette(), "events": len(events),
			"keys_consumed": o.KeysConsumed(), "file_writes": o.Wrote()})
	}
	require(o.Run(2000000))
	require(o.TypeKeys("p"))
	require(o.Run(5000000))
	capture("character-menu")
	require(o.Run(14000000))
	if *route == "begin-empty" {
		require(o.TypeKeys("b"))
		require(o.Run(15000000))
		capture("begin-empty")
	} else {
		require(o.TypeKeys("l"))
		require(o.Run(15000000))
		capture("load-source")
		if *route == "roundtrip" {
			require(o.TypeKeys("e"))
			require(o.Run(15000000))
			capture("returned-menu")
		} else {
			require(o.TypeKeys("t"))
			require(o.Run(15000000))
			capture("load-slots")
			require(o.TypeKeys("a"))
			require(o.Run(16000000))
			capture("loaded-party")
			require(o.TypeKeys("b"))
			require(o.Run(23000000))
			capture("copy-question")
		}
	}
	addresses := make([]uint32, 0, len(writers))
	for at := range writers {
		addresses = append(addresses, at)
	}
	sort.Slice(addresses, func(i, j int) bool { return addresses[i] < addresses[j] })
	var ordered []map[string]any
	for _, at := range addresses {
		ordered = append(ordered, writers[at])
	}
	stateBytes, err := os.ReadFile(*state)
	require(err)
	result := map[string]any{"prototype": true, "observe": *observe, "source_commit": "f79eab6db8c64a524a06535e53e5d32b0bbcf7c8",
		"input_sha256": hash(exe), "initial_state_sha256": hash(stateBytes), "oracle_ida_base": o.ToIDA(oracle.Addr{}),
		"route":         *route,
		"address_space": "Oracle callback address with explicit base; runtime linear is separate; no automatic semantic naming",
		"events":        events, "lifecycle": lifecycle, "video_writers": ordered, "checkpoints": checkpoints, "unimplemented": o.Unimplemented()}
	data, err := json.MarshalIndent(result, "", "  ")
	require(err)
	require(os.WriteFile(filepath.Join(*out, "receipt.json"), append(data, '\n'), 0644))
	fmt.Printf("events=%d video_writers=%d checkpoints=%d steps=%d\n", len(events), len(writers), len(checkpoints), o.Steps())
}
