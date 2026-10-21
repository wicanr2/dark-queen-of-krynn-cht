// DRAFT：按實際 X11 操作收據的虛擬步數重播無覆繪原版，不注入狀態。
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"reflect"

	"github.com/wicanr2/dosgolem/oracle"
)

func replayMust(err error) {
	if err != nil {
		panic(err)
	}
}
func replayHash(b []byte) string { h := sha256.Sum256(b); return hex.EncodeToString(h[:]) }
func main() {
	if len(os.Args) != 3 {
		panic("用法：interactive-replay receipt.json 全新輸出目錄")
	}
	input, err := os.ReadFile(os.Args[1])
	replayMust(err)
	var raw map[string]json.RawMessage
	replayMust(json.Unmarshal(input, &raw))
	var r struct {
		ColdBoot     bool   `json:"cold_boot"`
		Steps        uint64 `json:"steps"`
		SourceCommit string `json:"source_commit"`
		Inputs       []struct {
			Step  uint64 `json:"step"`
			Kind  string `json:"kind"`
			Value string `json:"value"`
		} `json:"inputs"`
		Checkpoints []map[string]json.RawMessage `json:"checkpoints"`
	}
	replayMust(json.Unmarshal(input, &r))
	if !r.ColdBoot || r.SourceCommit != "f79eab6db8c64a524a06535e53e5d32b0bbcf7c8" {
		panic("非本輪固定來源的冷啟動 GUI 收據")
	}
	out := os.Args[2]
	if _, err := os.Stat(out); !os.IsNotExist(err) {
		panic("輸出必須全新")
	}
	replayMust(os.MkdirAll(out, 0755))
	exe, err := os.ReadFile("/orig/DQK.EXE")
	replayMust(err)
	if replayHash(exe) != "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58" {
		panic("未知 EXE")
	}
	o, err := oracle.Load("/orig/DQK.EXE", "/orig")
	replayMust(err)
	defer o.Close()
	o.SetCmdLine("SB220 SI7 RB330")
	o.SetScratch(filepath.Join(out, "scratch"))
	for _, key := range r.Inputs {
		if key.Step < o.Steps() || key.Step > r.Steps {
			panic("輸入步數不單調或超出收據")
		}
		replayMust(o.Run(key.Step - o.Steps()))
		switch key.Kind {
		case "text":
			replayMust(o.TypeKeys(key.Value))
		case "named":
			replayMust(o.SendKeys(key.Value))
		default:
			panic("未知輸入種類")
		}
	}
	replayMust(o.Run(r.Steps - o.Steps()))
	ram := make([]byte, 1<<20)
	for i := range ram {
		ram[i] = o.Byte(oracle.Addr{Seg: uint16(i >> 4), Off: uint16(i & 15)})
	}
	actual := map[string]any{"steps": o.Steps(), "regs": o.Regs(), "ram_sha256": replayHash(ram), "indexed_sha256": replayHash(o.Indexed()), "palette": o.Palette(), "keys_consumed": o.KeysConsumed(), "file_writes": o.Wrote(), "unimplemented": o.Unimplemented()}
	for _, field := range []string{"steps", "regs", "ram_sha256", "indexed_sha256", "palette"} {
		var expected, got any
		replayMust(json.Unmarshal(raw[field], &expected))
		b, err := json.Marshal(actual[field])
		replayMust(err)
		replayMust(json.Unmarshal(b, &got))
		if !reflect.DeepEqual(expected, got) {
			panic("GUI 與原版重播不同：" + field)
		}
	}
	if len(r.Checkpoints) != 1 {
		panic("缺少互動結束檢查點")
	}
	for _, field := range []string{"keys_consumed", "file_writes"} {
		var expected, got any
		replayMust(json.Unmarshal(r.Checkpoints[0][field], &expected))
		b, err := json.Marshal(actual[field])
		replayMust(err)
		replayMust(json.Unmarshal(b, &got))
		if !reflect.DeepEqual(expected, got) {
			panic("GUI 與重播不同：" + field)
		}
	}
	if len(o.Unimplemented()) != 0 {
		panic("重播出現未實作服務")
	}
	actual["input_receipt_sha256"] = replayHash(input)
	actual["draft"] = true
	actual["matched_gui_guest"] = true
	actual["input_count"] = len(r.Inputs)
	b, err := json.MarshalIndent(actual, "", "  ")
	replayMust(err)
	replayMust(os.WriteFile(filepath.Join(out, "comparison.json"), append(b, '\n'), 0644))
	replayMust(o.WritePNG(filepath.Join(out, "guest.png")))
	fmt.Printf("GUI 原版重播相符：inputs=%d steps=%d RAM=%s\n", len(r.Inputs), o.Steps(), replayHash(ram))
}
