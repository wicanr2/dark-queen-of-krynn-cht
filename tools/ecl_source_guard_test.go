package main

import (
	"os"
	"testing"

	"github.com/wicanr2/dosgolem/oracle"
)

// 真實首字形前快照提供相同原文及呼叫堆疊；變造只屬測試，不執行遊戲。
func TestShortECLSourceGuard(t *testing.T) {
	state := os.Getenv("DQK_SHORT_SOURCE_STATE")
	if state == "" {
		t.Skip("缺少原版正常短敘事快照")
	}
	o, err := oracle.Load("/orig/DQK.EXE", "/orig")
	if err != nil {
		t.Fatal(err)
	}
	defer o.Close()
	cases := []struct {
		name    string
		kind    int
		corrupt oracle.Addr
		off     uint16
		want    bool
	}{
		{"original", -1, oracle.Addr{}, 0xb487, true},
		{"type-1", 1, oracle.Addr{}, 0xb487, false},
		{"type-2", 2, oracle.Addr{}, 0xb487, false},
		{"type-3", 3, oracle.Addr{}, 0xb487, false},
		{"type-81", 0x81, oracle.Addr{}, 0xb487, false},
		{"wrong-pointer", -1, oracle.Addr{}, 0xb488, false},
		{"handler-bytes", -1, oracle.Addr{Seg: 0x26b4, Off: 0x1cd3}, 0xb487, false},
		{"operand-bytes", -1, oracle.Addr{Seg: 0x2143, Off: 0x13}, 0xb487, false},
		{"wrong-opcode", -1, oracle.Addr{Seg: 0x333e, Off: 0xb1c7}, 0xb487, false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if err := o.LoadStateFile(state); err != nil {
				t.Fatal(err)
			}
			if o.IP() != (oracle.Addr{Seg: 0xb72, Off: 0x311}) || o.StackWord(9) != 0xb487 || o.StackWord(10) != 0x333e {
				t.Fatal("不是原版段落入口")
			}
			if c.kind >= 0 {
				o.SetByte(oracle.Addr{Seg: 0x333e, Off: 0xb216}, uint8(c.kind))
			}
			if c.corrupt.Seg != 0 {
				o.SetByte(c.corrupt, o.Byte(c.corrupt)^1)
			}
			before := digest(o.Bytes(oracle.Addr{}, 0xa0000))
			regs, steps := o.Regs(), o.Steps()
			proof, ok := shortECLLiteralSource(o, oracle.Addr{Seg: 0x333e, Off: c.off}, o.Caller())
			if ok != c.want || (ok && proof["raw_b216"] != uint8(0x80)) {
				t.Fatalf("guard=%t want=%t proof=%v", ok, c.want, proof)
			}
			if o.Regs() != regs || o.Steps() != steps || digest(o.Bytes(oracle.Addr{}, 0xa0000)) != before {
				t.Fatal("來源判斷改寫原版狀態")
			}
		})
	}
}
