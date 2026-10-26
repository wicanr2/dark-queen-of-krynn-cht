// 研究專用覆層，不連入玩家建置。由原版函式產生獨立 ABI 收據。
package oracle

import (
	"crypto/sha256"
	"fmt"
	"github.com/wicanr2/dosgolem/internal/cpu"
)

type RenderProbeCPU struct {
	Regs        Regs
	Hi          [8]uint16
	FS, GS, FPU uint16
	Halted      bool
	Cycles      uint64
}

func (o *Oracle) RenderProbePrepare(entry, ret Addr, args []uint16, dosCost bool) {
	c := o.m.CPU
	c.R = [8]uint16{0x1357, 0x3579, 0x468a, 0x2468, 0xe000, 0x79bd, 0x579b, 0x68ac}
	c.Seg[cpu.SS] = 0x333e
	c.Seg[cpu.DS] = 0x333e
	c.Seg[cpu.ES] = 0x333e
	c.Seg[cpu.CS] = entry.Seg
	c.IP = entry.Off
	c.SetFlags(0x246)
	c.Halted = false
	c.DOSBoxCost = dosCost
	o.m.IRQ0Every = 0
	o.m.VGAFrameEvery = 0
	o.m.CycleClock = false
	o.m.Steps = 0
	c.Cycles = 0
	for i, v := range append([]uint16{ret.Off, ret.Seg}, args...) {
		o.WriteU16(Addr{Seg: 0x333e, Off: 0xe000 + uint16(i*2)}, v)
	}
	for _, item := range [][2]uint16{{0xca33, 0xa000}, {0xcb85, 31*80 + 2}, {0xcb6c, 80}, {0xcb83, 0x4000}, {0xcb80, 0}, {0xca41, 15}, {0xcb63, 2}, {0xcd9e, 4}, {0xcdae, 0}, {0xcdb9, 200}, {0xcdb3, 0}, {0xcdb5, 320}} {
		o.WriteU16(Addr{Seg: 0x333e, Off: item[0]}, item[1])
	}
	for _, item := range [][2]uint16{{5, 0x40}, {8, 255}, {1, 0}, {3, 0}, {4, 0}} {
		o.m.Out8(0x3ce, byte(item[0]))
		o.m.Out8(0x3cf, byte(item[1]))
	}
	o.m.Out8(0x3c4, 2)
	o.m.Out8(0x3c5, 15)
}
func (o *Oracle) RenderProbeCPU() RenderProbeCPU {
	c := o.m.CPU
	return RenderProbeCPU{o.Regs(), c.Hi, c.FSeg, c.GSeg, c.FPUCW, c.Halted, c.Cycles}
}

func (o *Oracle) RenderProbeStackSS(seg uint16) {
	r := o.Regs()
	data := o.Bytes(Addr{Seg: r.SS, Off: r.SP}, 64)
	o.WriteBytes(Addr{Seg: seg, Off: r.SP}, data)
	o.m.CPU.Seg[cpu.SS] = seg
}
func (o *Oracle) RenderProbeRAM() []byte { return append([]byte(nil), o.m.Mem...) }

func (o *Oracle) RenderProbePlaneMask(mask byte) {
	o.m.Out8(0x3c4, 2)
	o.m.Out8(0x3c5, mask)
}

func (o *Oracle) RenderProbeVideoMode(mode, readPlane byte) {
	o.m.Out8(0x3ce, 5)
	o.m.Out8(0x3cf, mode)
	o.m.Out8(0x3ce, 4)
	o.m.Out8(0x3cf, readPlane)
}

func (o *Oracle) RenderProbeVideoRegisters() [28]byte {
	gc, seq, latch := o.m.VGA.Regs()
	var result [28]byte
	copy(result[:16], gc[:])
	copy(result[16:24], seq[:])
	copy(result[24:], latch[:])
	return result
}

type RenderProbeFrame struct {
	Step          uint64
	IndicesSHA256 string
	CPU           RenderProbeCPU
	Video         [28]byte
}

func (o *Oracle) RenderProbeFrameAt(step uint64) *[]RenderProbeFrame {
	o.m.RenderProbeFrameAt(step)
	events := new([]RenderProbeFrame)
	o.m.SetOnFrame(func() {
		_, _, px := o.Screen()
		sum := sha256.Sum256(px)
		*events = append(*events, RenderProbeFrame{o.Steps(), fmt.Sprintf("%x", sum), o.RenderProbeCPU(), o.RenderProbeVideoRegisters()})
	})
	return events
}

func (o *Oracle) RenderProbeIRQAt(step uint64) *[]RenderProbeFrame {
	o.m.RenderProbeIRQAt(step)
	events := new([]RenderProbeFrame)
	o.m.SetOnTick(func() {
		_, _, px := o.Screen()
		sum := sha256.Sum256(px)
		*events = append(*events, RenderProbeFrame{o.Steps(), fmt.Sprintf("%x", sum), o.RenderProbeCPU(), o.RenderProbeVideoRegisters()})
	})
	return events
}
