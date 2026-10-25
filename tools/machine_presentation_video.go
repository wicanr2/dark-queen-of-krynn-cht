// Go build -overlay：只提供通用視訊存取點，不包含遊戲位址。
package machine

func (m *Machine) SetPresentationVideoAccess(fn func(uint32, bool, bool)) {
	m.presentationVideoAccess = fn
}
func (m *Machine) PresentationVideoState() [6]byte {
	return [6]byte{m.VGA.gc[5], m.VGA.gc[8], m.VGA.gc[1], m.VGA.gc[3], m.VGA.seq[2], m.VGA.gc[4]}
}
