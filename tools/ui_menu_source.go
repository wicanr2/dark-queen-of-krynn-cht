// DRAFT：只讀原版已觀測的按鈕表，不改選單、按鍵或 guest 記憶體。
package main

import (
	"encoding/binary"
	"encoding/hex"
	"encoding/json"

	"github.com/wicanr2/dosgolem/oracle"
)

type menuSourceButton struct {
	Index         int
	SourcePointer oracle.Addr
	SourceHex     string
	SHA256        string
	RawX, RawY    uint16
}
type menuSourceSnapshot struct {
	Count     int
	Pointer   oracle.Addr
	RawHex    string
	Buttons   []menuSourceButton
	Signature string
}

func readMenuSource(o *oracle.Oracle) (menuSourceSnapshot, bool) {
	r := o.Regs()
	n := int(o.Word(oracle.Addr{Seg: r.DS, Off: 0xdac0}))
	p := oracle.Addr{Seg: o.Word(oracle.Addr{Seg: r.DS, Off: 0xdac9}), Off: o.Word(oracle.Addr{Seg: r.DS, Off: 0xdac7})}
	if n < 1 || n > 64 || uint32(p.Off)+uint32(n*32) > 0x10000 || uint32(p.Seg)*16+uint32(p.Off)+uint32(n*32) > 0xa0000 {
		return menuSourceSnapshot{}, false
	}
	raw := o.Bytes(p, n*32)
	result := menuSourceSnapshot{Count: n, Pointer: p, RawHex: hex.EncodeToString(raw)}
	var signature []any
	for i := 0; i < n; i++ {
		record := raw[i*32 : (i+1)*32]
		if binary.LittleEndian.Uint16(record) != 0x008e || binary.LittleEndian.Uint16(record[2:]) != 0x0ceb {
			continue
		}
		button := menuSourceButton{Index: i, SourcePointer: oracle.Addr{Off: binary.LittleEndian.Uint16(record[12:]), Seg: binary.LittleEndian.Uint16(record[14:])},
			RawX: binary.LittleEndian.Uint16(record[18:]), RawY: binary.LittleEndian.Uint16(record[16:])}
		var text []byte
		terminated := false
		for j := 0; j < 256; j++ {
			if uint32(button.SourcePointer.Off)+uint32(j) >= 0x10000 || uint32(button.SourcePointer.Seg)*16+uint32(button.SourcePointer.Off)+uint32(j) >= 0xa0000 {
				return menuSourceSnapshot{}, false
			}
			c := o.Byte(oracle.Addr{Seg: button.SourcePointer.Seg, Off: button.SourcePointer.Off + uint16(j)})
			if c == 0 {
				terminated = true
				break
			}
			if c < 32 || c > 126 {
				return menuSourceSnapshot{}, false
			}
			text = append(text, c)
		}
		if !terminated || len(text) == 0 {
			return menuSourceSnapshot{}, false
		}
		button.SourceHex, button.SHA256 = hex.EncodeToString(text), digest(text)
		result.Buttons = append(result.Buttons, button)
		signature = append(signature, []any{i, button.SHA256, button.RawX, button.RawY})
	}
	if len(result.Buttons) == 0 {
		return menuSourceSnapshot{}, false
	}
	encoded, err := json.Marshal([]any{n, signature})
	if err != nil {
		panic(err)
	}
	result.Signature = digest(encoded)
	return result, true
}
