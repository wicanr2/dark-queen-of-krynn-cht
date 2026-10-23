// DRAFT：獨立原版冷讀控制組，只送正常鍵盤，不安裝呈現掛勾。
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"github.com/wicanr2/dosgolem/oracle"
	"os"
	"path/filepath"
	"runtime"
)

func main() {
	if len(os.Args) != 4 {
		panic("用法：cold-load-probe 請求 唯讀存檔目錄 全新輸出")
	}
	must := func(e error) {
		if e != nil {
			panic(e)
		}
	}
	sha := func(b []byte) string { h := sha256.Sum256(b); return hex.EncodeToString(h[:]) }
	if _, e := os.Stat(os.Args[3]); !os.IsNotExist(e) {
		panic("輸出必須全新")
	}
	must(os.MkdirAll(filepath.Join(os.Args[3], "scratch", "SAVE"), 0755))
	data, e := os.ReadFile(os.Args[1])
	must(e)
	var req struct {
		Actions []struct {
			At, End          uint64
			Kind, Key, Label string
		}
		QuizStep, Handoff uint64
		QuizSHA256        string
		SaveFiles         map[string]struct {
			Bytes           int
			SHA256          string
			ModTimeUnixNano int64
		}
	}
	must(json.Unmarshal(data, &req))
	if req.QuizStep != 355000000 || req.Handoff != 355000000 || len(req.Actions) < 12 || len(req.Actions) > 32 || len(req.SaveFiles) != 2 {
		panic("未知冷讀請求")
	}
	for _, name := range []string{"SavGamJ.qsv", "VaultJ.DAT"} {
		b, e := os.ReadFile(filepath.Join(os.Args[2], name))
		must(e)
		spec, ok := req.SaveFiles[name]
		if !ok || len(b) != spec.Bytes || sha(b) != spec.SHA256 {
			panic("存檔來源不符")
		}
		must(os.WriteFile(filepath.Join(os.Args[3], "scratch", "SAVE", name), b, 0644))
		info, e := os.Stat(filepath.Join(os.Args[2], name))
		must(e)
		if info.ModTime().UnixNano() != spec.ModTimeUnixNano {
			panic("存檔時間來源不符")
		}
		must(os.Chtimes(filepath.Join(os.Args[3], "scratch", "SAVE", name), info.ModTime(), info.ModTime()))
	}
	exe, e := os.ReadFile("/orig/DQK.EXE")
	must(e)
	if sha(exe) != "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58" {
		panic("未知 EXE")
	}
	o, e := oracle.Load("/orig/DQK.EXE", "/orig")
	must(e)
	defer o.Close()
	o.SetCmdLine("SB220 SI7 RB330")
	o.SetScratch(filepath.Join(os.Args[3], "scratch"))
	ram := func() []byte {
		b := make([]byte, 1<<20)
		for i := range b {
			b[i] = o.Byte(oracle.Addr{Seg: uint16(i >> 4), Off: uint16(i & 15)})
		}
		return b
	}
	var checkpoints []map[string]any
	for _, a := range req.Actions {
		if a.At < o.Steps() || a.End <= a.At || (a.Kind != "text" && a.Kind != "named") {
			panic("動作不符")
		}
		must(o.Run(a.At - o.Steps()))
		if a.Kind == "text" {
			must(o.TypeKeys(a.Key))
		} else {
			must(o.SendKeys(a.Key))
		}
		must(o.Run(a.End - o.Steps()))
		if a.End == req.QuizStep && sha(o.Indexed()) != req.QuizSHA256 {
			panic("查驗頁不符，不輸入答案")
		}
		if filepath.Base(a.Label) != a.Label || a.Label == "" {
			panic("標籤不符")
		}
		must(o.WritePNG(filepath.Join(os.Args[3], a.Label+".png")))
		must(os.WriteFile(filepath.Join(os.Args[3], a.Label+".idx"), o.Indexed(), 0644))
		checkpoints = append(checkpoints, map[string]any{"step": o.Steps(), "label": a.Label, "regs": o.Regs(), "ram_sha256": sha(ram()), "indexed_sha256": sha(o.Indexed()), "palette": o.Palette(), "keys_consumed": o.KeysConsumed(), "file_writes": o.Wrote(), "unimplemented": o.Unimplemented()})
	}
	if o.Steps() != req.Handoff {
		panic("交接步數不符")
	}
	state := filepath.Join(os.Args[3], "handoff.state")
	must(o.SaveStateFile(state))
	b, e := os.ReadFile(state)
	must(e)
	result := map[string]any{"draft": true, "cold_boot": true, "snapshot_loaded": false, "source_commit": "f79eab6db8c64a524a06535e53e5d32b0bbcf7c8", "go_version": runtime.Version(), "exe_sha256": sha(exe), "request_sha256": sha(data), "bridge_state_sha256": sha(b), "checkpoints": checkpoints, "unimplemented": o.Unimplemented()}
	out, e := json.MarshalIndent(result, "", "  ")
	must(e)
	must(os.WriteFile(filepath.Join(os.Args[3], "receipt.json"), append(out, '\n'), 0644))
	fmt.Printf("cold_boot checkpoints=%d steps=%d bridge=%s\n", len(checkpoints), o.Steps(), sha(b))
}
