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
}

func (o *Oracle) OnVideoWriteEvent(fn func(VideoWriteEvent)) {
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
