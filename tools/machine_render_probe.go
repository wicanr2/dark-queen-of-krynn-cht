// 研究專用，建立已知的下一個畫面事件，不連入玩家建置。
package machine

func (m *Machine) RenderProbeFrameAt(step uint64) *[]uint64 {
	events := new([]uint64)
	m.VGAFrameEvery = 1_000_000
	m.nextFrame = step
	m.SetOnFrame(func() { *events = append(*events, m.Steps) })
	return events
}

func (m *Machine) RenderProbeIRQAt(step uint64) {
	m.IRQ0Every = 1_000_000
	m.nextIRQ0 = step
	m.irq0Pending = false
}
