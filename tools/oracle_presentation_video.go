// Go build -overlay：原版只在實際讀回時取得最小相容色號。
package oracle

import (
	"fmt"
	"github.com/wicanr2/dosgolem/internal/machine"
)

func (o *Oracle) SetPresentationVideo(fn func(uint32, bool, bool), indices func() []byte, reset func()) {
	o.m.SetPresentationVideoAccess(fn)
	o.presentationIndices = indices
	if reset == nil {
		o.m.ObserveModeChanges(nil)
	} else {
		o.m.ObserveModeChanges(func(machine.ModeChange) { reset() })
	}
}
func (o *Oracle) PresentationVideoState() [6]byte                    { return o.m.PresentationVideoState() }
func (o *Oracle) PresentationPlane(plane int, off uint32) byte       { return o.m.VGA.Planes[plane][off] }
func (o *Oracle) SetPresentationPlane(plane int, off uint32, v byte) { o.m.VGA.Planes[plane][off] = v }

// 跳到同一 code segment 的已核對指令；由原 epilogue 還原堆疊，不能偽造 retf。
func (o *Oracle) JumpPresentationIP(ip uint16) { o.m.CPU.IP = ip }

func (o *Oracle) PresentationWorkBudget(limit uint64) uint64 {
	if o.presentationRunDeadline <= o.m.Steps {
		return 0
	}
	if remain := o.presentationRunDeadline - o.m.Steps; limit > remain {
		limit = remain
	}
	return o.m.PresentationWorkBudget(limit)
}
func (o *Oracle) CommitPresentationWork(steps, cycles uint64) error {
	if steps > o.PresentationWorkBudget(steps) {
		return fmt.Errorf("呈現替換超過呼叫端配額")
	}
	return o.m.CommitPresentationWork(steps, cycles)
}
func (o *Oracle) PresentationDOSCost() bool { return o.m.CPU.DOSBoxCost }

// 不在 OnCall 提前派送事件，也不變更原版的 Step／stub 順序。
func (o *Oracle) QueuePresentationInstruction(fn func() bool) {
	r := o.Regs()
	o.m.SetPresentationInstruction(func() bool {
		now := o.Regs()
		if now.CS != r.CS || now.IP != r.IP || now.SS != r.SS || now.SP != r.SP || o.m.CPU.Halted || now.Flags&0x100 != 0 {
			return false
		}
		return fn()
	})
}
func (o *Oracle) CommitPresentationInstructionCycles(cycles uint64) {
	o.m.CommitPresentationInstructionCycles(cycles)
}

// 已驗證呈現效果只可更新六個算術旗標，不改中斷、方向或追蹤旗標。
func (o *Oracle) SetPresentationArithmeticFlags(flags uint16) {
	const arithmetic = uint16(0x8d5)
	o.m.CPU.SetFlags((o.m.CPU.Flags &^ arithmetic) | (flags & arithmetic))
}
