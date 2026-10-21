// 隔離研究工具：讀取繪製前事件並擷取連續畫格，不改原版暫存器或記憶體。
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/wicanr2/dosgolem/oracle"
)

type event struct {
	Step       uint64 `json:"step"`
	X          int    `json:"x"`
	Y          int    `json:"y"`
	Color      uint16 `json:"color"`
	Text       string `json:"source"`
	Key        string `json:"key"`
	FirstGlyph uint64 `json:"first_glyph,omitempty"`
}

type frame struct {
	Step   uint64 `json:"step"`
	File   string `json:"file"`
	Events int    `json:"events"`
}

func check(err error) {
	if err != nil {
		panic(err)
	}
}

func main() {
	state := flag.String("state", "", "本機 probe 狀態檔")
	out := flag.String("out", "", "本機研究輸出")
	observe := flag.Bool("observe", true, "只觀測，不改 guest")
	flag.Parse()
	check(os.MkdirAll(*out, 0755))
	input, err := os.ReadFile("/orig/DQK.EXE")
	check(err)
	inputHash := sha256.Sum256(input)
	if hex.EncodeToString(inputHash[:]) != "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58" {
		panic("輸入 EXE 雜湊不符")
	}
	o, err := oracle.Load("/orig/DQK.EXE", "/orig")
	check(err)
	check(o.LoadStateFile(*state))
	// Resident 定位要先核對；不在未知 binary 上猜掛勾。
	for i, want := range []byte{0x55, 0x8b, 0xec, 0xff, 0x76, 0x0a, 0x0e, 0xe8, 0x30, 0xff, 0x59} {
		if o.Byte(oracle.Addr{Seg: 0x1212, Off: 0x03a0 + uint16(i)}) != want {
			panic("resident 掛勾 bytes 不符")
		}
	}
	o.SetScratch(filepath.Join(*out, "scratch"))
	word := func(off uint16) uint16 {
		r := o.Regs()
		return o.Word(oracle.Addr{Seg: r.SS, Off: r.SP + off})
	}
	readString := func(seg, off uint16) string {
		var b []byte
		for i := 0; i < 255; i++ {
			v := o.Byte(oracle.Addr{Seg: seg, Off: off + uint16(i)})
			if v == 0 {
				return string(b)
			}
			if v < 32 || v > 126 {
				return ""
			}
			b = append(b, v)
		}
		return ""
	}
	var events []event
	var frames []frame
	if *observe {
		// IDA sub_213C0；三個 resident byte anchors 已與實際 RAM 核對。
		o.OnCall(oracle.Addr{Seg: 0x1212, Off: 0x03a0}, func(_ *oracle.Oracle) {
			text := readString(word(12), word(10))
			if text == "" {
				return
			}
			h := sha256.Sum256([]byte(text))
			events = append(events, event{Step: o.Steps(), Y: int(word(4)), X: int(word(6)), Color: word(8), Text: text, Key: hex.EncodeToString(h[:])})
		})
		// IDA sub_23806：第一次真正進入字元 dispatcher 的時間。
		o.OnCall(oracle.Addr{Seg: 0x13c7, Off: 0x0c96}, func(_ *oracle.Oracle) {
			for i := len(events) - 1; i >= 0; i-- {
				e := &events[i]
				if e.FirstGlyph == 0 && e.Y == int(word(4)) && e.X == int(word(6)) {
					e.FirstGlyph = o.Steps()
					break
				}
			}
		})
	}
	// 從真實冷啟動形成的 #239M 快照接續，等價於 probe 的第 #241M 送 p。
	if o.Steps() != 239000000 {
		panic("預期 #239M 的正常啟動快照")
	}
	check(o.Run(2000000))
	check(o.TypeKeys("p"))
	// 含所有文字建立與逐字繪製期間，每 2,000 道指令擷取一幀。
	for o.Steps() < 242000000 {
		check(o.Run(2000))
		if *observe {
			name := fmt.Sprintf("frame-%09d.png", o.Steps())
			check(o.WritePNG(filepath.Join(*out, name)))
			frames = append(frames, frame{o.Steps(), name, len(events)})
		}
	}
	if o.Steps() < 246000000 {
		check(o.Run(246000000 - o.Steps()))
	}
	ram := make([]byte, 1<<20)
	for i := range ram {
		ram[i] = o.Byte(oracle.Addr{Seg: uint16(i >> 4), Off: uint16(i & 15)})
	}
	ramHash := sha256.Sum256(ram)
	indexedHash := sha256.Sum256(o.Indexed())
	result := map[string]any{"schema": 1, "prototype": true, "source_commit": "f79eab6db8c64a524a06535e53e5d32b0bbcf7c8",
		"initial_state": *state, "steps": o.Steps(), "regs": o.Regs(), "ram_sha256": hex.EncodeToString(ramHash[:]),
		"indexed_sha256": hex.EncodeToString(indexedHash[:]), "palette": o.Palette(), "events": events, "frames": frames,
		"limitations": "plain menu strings only; format templates and text lifecycle are unverified"}
	data, err := json.MarshalIndent(result, "", "  ")
	check(err)
	check(os.WriteFile(filepath.Join(*out, "trace.json"), append(data, '\n'), 0644))
	check(o.WritePNG(filepath.Join(*out, "final.png")))
	plain := 0
	for _, e := range events {
		if !strings.Contains(e.Text, "%") {
			plain++
		}
	}
	fmt.Printf("events=%d plain=%d frames=%d steps=%d RAM=%x\n", len(events), plain, len(frames), o.Steps(), ramHash)
}
