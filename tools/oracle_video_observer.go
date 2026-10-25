// DRAFT 觀測橋接。僅由 Go build -overlay 掛入固定 dosgolem 的 oracle package。
// 不修改來源樹或 guest，沿用 Machine 已有的逐次視訊寫入 observer。
package oracle

import "github.com/wicanr2/dosgolem/internal/machine"

type VideoWriteEvent struct {
	Step               uint64
	CS, IP             uint16
	Offset             uint32
	Value, WriteMode   uint8
	Mode, MapMask      uint8
	Unchained          bool
	DisplayStart       uint32
	Pitch, LineCompare int
	Presentation       bool
}

var presentationWriteObservers = map[*Oracle]func(VideoWriteEvent){}

func (o *Oracle) EmitPresentationWrite(off uint32, value, mask byte) {
	if fn := presentationWriteObservers[o]; fn != nil {
		v := o.VideoLayoutState()
		r := o.Regs()
		v.Step = o.Steps()
		v.CS = r.CS
		v.IP = r.IP
		v.Offset = off
		v.Value = value
		v.MapMask = mask
		v.Presentation = true
		fn(v)
	}
}

func (o *Oracle) OnVideoWriteEvent(fn func(VideoWriteEvent)) {
	if fn == nil {
		delete(presentationWriteObservers, o)
	} else {
		presentationWriteObservers[o] = fn
	}
	if fn == nil {
		o.m.ObserveVideoWrites(nil)
		return
	}
	o.m.ObserveVideoWrites(func(v machine.VideoWrite) {
		fn(VideoWriteEvent{Step: v.Step, CS: v.CS, IP: v.IP, Offset: v.Offset, Value: v.Value, WriteMode: v.WriteMode,
			Mode: o.m.VideoMode(), MapMask: o.m.MapMask(), Unchained: o.m.Unchained(), DisplayStart: o.m.DisplayStart(), Pitch: o.m.VGA.Pitch(320), LineCompare: o.m.VGA.LineCompare()})
	})
}

func (o *Oracle) VideoLayoutState() VideoWriteEvent {
	return VideoWriteEvent{Mode: o.m.VideoMode(), MapMask: o.m.MapMask(), Unchained: o.m.Unchained(),
		DisplayStart: o.m.DisplayStart(), Pitch: o.m.VGA.Pitch(320), LineCompare: o.m.VGA.LineCompare()}
}

// TrimPresentationHistory 只限制主機診斷歷程，不寫入 guest、VGA 或計時器狀態。
// 互動入口不產生研究收據；保留最近 65536 筆埠操作，避免長時間遊玩無界累積。
func (o *Oracle) TrimPresentationHistory() {
	const keep = 65536
	if len(o.m.PortLog) > keep*2 {
		log := make([]machine.PortWrite, keep)
		copy(log, o.m.PortLog[len(o.m.PortLog)-keep:])
		o.m.PortLog = log
	}
}
