// Go build -overlay：只提供通用視訊存取點，不包含遊戲位址。
package machine

import "fmt"

func (m *Machine) SetPresentationVideoAccess(fn func(uint32, bool, bool)) {
	m.presentationVideoAccess = fn
}
func (m *Machine) PresentationVideoState() [6]byte {
	return [6]byte{m.VGA.gc[5], m.VGA.gc[8], m.VGA.gc[1], m.VGA.gc[3], m.VGA.seq[2], m.VGA.gc[4]}
}

// 沿 MM3 dosgolem-host-work.patch 的通用事件契約；此固定 SDK 尚無 MPU 裝置。
func (m *Machine) PresentationWorkBudget(limit uint64) uint64 {
	if limit == 0 || m.CycleClock || m.CPU.Halted || m.CPU.Flags&0x100 != 0 || m.irq0Pending || len(m.cbQueue) != 0 || len(m.keyQueue) != 0 || len(m.timedKeys) != 0 || len(m.wordWatches) != 0 || m.Coverage != nil || m.TraceSegs || m.WatchDSOn || m.rWatchLo <= m.rWatchHi {
		return 0
	}
	before := func(on bool, next uint64) {
		if on {
			if next <= m.Steps {
				limit = 0
			} else if next-m.Steps < limit {
				limit = next - m.Steps
			}
		}
	}
	before(m.IRQ0Every > 0, m.nextIRQ0)
	before(m.VGAFrameEvery > 0, m.nextFrame)
	before(m.periodic.on, m.periodic.next)
	return limit
}
func (m *Machine) CommitPresentationWork(instructions, cycles uint64) error {
	if instructions == 0 || instructions > m.PresentationWorkBudget(instructions) || ^uint64(0)-m.Steps < instructions || ^uint64(0)-m.CPU.Cycles < cycles {
		return fmt.Errorf("呈現替換超過機器事件或計數邊界")
	}
	m.Steps += instructions
	m.CPU.Cycles += cycles
	return nil
}
