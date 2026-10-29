// 原版音樂只讀觀察器。位址與機器碼證據見研究008。
package main

import (
	"bytes"
	"fmt"
	"strings"

	"github.com/wicanr2/dosgolem/oracle"
)

type musicCue struct {
	Kind, Key string
	Volume    int
	Step      uint64
}
type musicCall struct {
	SS, SP uint16
	Cue    musicCue
}

func musicKey(source string, sequence int) string {
	source = strings.ToUpper(source)
	if len(source) != 9 || source[2:4] != "DQ" || source[5:] != ".XMI" {
		return ""
	}
	if source[:2] != "AD" && source[:2] != "RO" && source[:2] != "TY" && source[:2] != "PC" {
		return ""
	}
	group := source[4]
	if group < '1' || group > '3' || sequence < 0 || sequence >= 6 || group != '2' && sequence != 0 {
		return ""
	}
	return fmt.Sprintf("RODQ%c-%d", group, sequence)
}

func observeMusic(o *oracle.Oracle, emit func(musicCue)) error {
	for _, h := range []struct {
		kind       string
		entry, ret uint16
		signature  []byte
	}{
		{"start", 0x0265, 0x04ca, []byte{0x55, 0x8b, 0xec, 0x83, 0xec, 0x1c, 0x56, 0x57, 0x8b, 0x7e, 0x0a}},
		{"volume", 0x04cb, 0x061f, []byte{0x55, 0x8b, 0xec, 0x83, 0xec, 0x1a, 0x56, 0x57, 0x33, 0xf6}},
		{"stop", 0x07ab, 0x08da, []byte{0x55, 0x8b, 0xec, 0x83, 0xec, 0x1c, 0x56, 0x57, 0x33, 0xff}},
	} {
		h := h
		entry, ret := oracle.Addr{Seg: 0x0f66, Off: h.entry}, oracle.Addr{Seg: 0x0f66, Off: h.ret}
		if !bytes.Equal(o.Bytes(entry, len(h.signature)), h.signature) || o.Bytes(ret, 1)[0] != 0xcb {
			return fmt.Errorf("音樂掛勾機器碼失配：%s", h.kind)
		}
	}
	for _, h := range []struct {
		kind       string
		entry, ret uint16
	}{{"start", 0x0265, 0x04ca}, {"volume", 0x04cb, 0x061f}, {"stop", 0x07ab, 0x08da}} {
		h := h
		pending := []musicCall{}
		o.OnCall(oracle.Addr{Seg: 0x0f66, Off: h.entry}, func(_ *oracle.Oracle) {
			r := o.Regs()
			arg := func(offset uint16) uint16 { return o.Word(oracle.Addr{Seg: r.SS, Off: r.SP + 4 + offset}) }
			raw := o.Bytes(oracle.Addr{Seg: arg(2), Off: arg(0)}, 64)
			name := ""
			if end := bytes.IndexByte(raw, 0); end >= 0 {
				name = string(raw[:end])
			}
			key := musicKey(name, int(arg(4)))
			volume := 100
			if h.kind != "stop" {
				volume = int(arg(6))
			}
			if volume > 100 {
				key = ""
			}
			if len(pending) >= 16 {
				pending = nil
			}
			pending = append(pending, musicCall{r.SS, r.SP, musicCue{h.kind, key, volume, o.Steps()}})
		})
		o.OnCall(oracle.Addr{Seg: 0x0f66, Off: h.ret}, func(_ *oracle.Oracle) {
			r := o.Regs()
			for i := len(pending) - 1; i >= 0; i-- {
				p := pending[i]
				if p.SS != r.SS || p.SP != r.SP {
					continue
				}
				pending = append(pending[:i], pending[i+1:]...)
				if r.AX == 0 && p.Cue.Key != "" {
					p.Cue.Step = o.Steps()
					emit(p.Cue)
				}
				break
			}
		})
	}
	return nil
}
