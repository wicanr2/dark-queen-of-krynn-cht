// DQK.EXE 1.1 的 Mode X 單次繪圖路由。定位與副作用契約見規格 005。
package main

import (
	"encoding/binary"
	"encoding/json"
	"fmt"
	"math/bits"
	"os"
	"path/filepath"

	"github.com/wicanr2/dosgolem/oracle"
)

type ownedDriver struct {
	X, Y, W, H, Base      int
	Kind                  string
	LastSteps, LastCycles uint64
	Asset                 *sceneAsset
	Page                  uint32
	Fallback              bool
	Transfers             int
}

var renderOwners = map[*oracle.Oracle]*playerRenderOwner{}

// 已證實的三支記憶體搬移也服務純RAM；純RAM操作不形成畫面交易。
func renderTransactionTouchesVideo(o *oracle.Oracle, origin uint32) bool {
	touches := func(seg, off uint16, count uint32) bool {
		// SI／DI 跨越16位元段落時保留原交易，不把未知的環繞跨度判成純RAM。
		if uint32(off)+count > 0x10000 {
			return true
		}
		base := (uint32(seg)*16 + uint32(off)) & 0xfffff
		return count != 0 && base < 0xc0000 && base+count > 0xa0000
	}
	switch origin {
	case 0x11632, 0x11688:
		count := uint32(o.Arg(4))
		return touches(o.Arg(1), o.Arg(0), count) || touches(o.Arg(3), o.Arg(2), count)
	case 0x116c6:
		return touches(o.Arg(0), 0, 0x4000) || touches(o.Arg(1), 0, 0x4000)
	default:
		return true
	}
}

func (p *playerRenderOwner) indexAt(page uint32, i int) byte {
	return p.Scene.page(page, p.Oracle.PresentationPlane).Index[i]
}

// 非標準頁距／分割畫面只用原版一次。僅在布局交界補舊色號，不能每幀先畫原版底圖。
func (p *playerRenderOwner) releaseScene() {
	for page, model := range p.Scene.Pages {
		if model == nil {
			continue
		}
		for i, c := range model.Cells {
			if c.Asset != nil && c.Visible {
				off := uint32(page)*0x4000 + uint32(i/320*80+(i%320)/4)
				p.Oracle.SetPresentationPlane(i&3, off, c.Asset.Index[c.Source])
				p.Counters["layout_fallback_plane_bytes"]++
			}
		}
	}
	p.Scene = renderScene{}
	p.LayerKey = ""
}
func (p *playerRenderOwner) CanTranslate(r [4]int) bool {
	page, ok := nativeVisiblePage(p.Oracle)
	return ok && p.Scene.page(page, p.Oracle.PresentationPlane).safe(r)
}
func (p *playerRenderOwner) Close(directory string) {
	p.Backend.close()
	p.Oracle.SetPresentationVideo(nil, nil, nil)
	p.Oracle.OnVideoWriteEvent(nil)
	delete(renderOwners, p.Oracle)
	raw, err := json.MarshalIndent(struct {
		Version  int
		Coverage string
		Counts   map[string]uint64
	}{1, "Mode X 完整10h/12h/15h影像、8x8字形、純色填滿；不是全遊戲接管收據", p.Counters}, "", "  ")
	must(err)
	must(os.WriteFile(filepath.Join(directory, "render-counts.json"), append(raw, '\n'), 0644))
}
func (p *playerRenderOwner) inReadback() bool {
	for _, v := range p.Pending {
		if v.Kind == "readback-scope" {
			return true
		}
	}
	return false
}
func (p *playerRenderOwner) pending(linear uint32, frame bool) *renderTransaction {
	r := p.Oracle.Regs()
	for i := len(p.Pending) - 1; i >= 0; i-- {
		v := &p.Pending[i]
		if v.Origin.Linear()+0xef00 != linear || v.Return.SS != r.SS {
			continue
		}
		if frame && r.BP+6 != v.Return.SP {
			continue
		}
		return v
	}
	return nil
}
func (p *playerRenderOwner) guard() bool {
	return p.Oracle.Regs().Flags&0x400 == 0 && p.modeXGuard()
}
func (p *playerRenderOwner) modeXGuard() bool {
	o := p.Oracle
	s := o.PresentationVideoState()
	return nativePageLayout(o) &&
		p.global(0xca41) == 15 && p.global(0xcb6c) == 80 &&
		s[0] == 0x40 && s[1] == 255 && s[2] == 0 && s[3] == 0
}
func (p *playerRenderOwner) word(off uint16) uint16 {
	r := p.Oracle.Regs()
	return p.Oracle.Word(oracle.Addr{Seg: r.SS, Off: r.BP + off})
}
func (p *playerRenderOwner) global(off uint16) uint16 {
	return p.Oracle.Word(oracle.Addr{Seg: 0x333e, Off: off})
}
func (p *playerRenderOwner) jump(ea uint32) {
	r := p.Oracle.Regs()
	base := uint32(r.CS)*16 + 0xef00
	if ea < base || ea-base > 65535 {
		panic("繪圖跳轉跨越原 code segment")
	}
	p.Oracle.JumpPresentationIP(uint16(ea - base))
}
func (p *playerRenderOwner) cache(key string, a *sceneAsset) *sceneAsset {
	if v := p.Assets[key]; v != nil {
		return v
	}
	if len(p.Assets) >= 2048 {
		p.Assets = map[string]*sceneAsset{}
	}
	p.Assets[key] = a
	return a
}
func (p *playerRenderOwner) record(a *sceneAsset, x, y int, page uint32, kind string) {
	model := p.Scene.page(page, p.Oracle.PresentationPlane)
	if p.inReadback() {
		p.Scene.temporaryRecord(model, a, x, y, page, p.Oracle.SetPresentationPlane)
		p.Counters["temporary_canvas_commands"]++
	} else {
		p.Scene.record(model, a, x, y)
		// 事件切開圖片命令時仍保留同一素材身分，不因小區塊搬移丟失 HD。
		if kind == "source_blit" || kind == "boundary_span" || kind == "masked_blit" {
			for i := len(p.Pending) - 1; i >= 0; i-- {
				d := p.Pending[i].Owned
				if d == nil || d.Kind != "image" || d.Fallback || d.Page != page {
					continue
				}
				for yy := 0; yy < a.H; yy++ {
					for xx := 0; xx < a.W; xx++ {
						src := yy*a.W + xx
						if len(a.Alpha) > 0 && a.Alpha[src] == 0 {
							continue
						}
						px, py := x+xx, y+yy
						if px < d.X || py < d.Y || px >= d.X+d.W || py >= d.Y+d.H {
							continue
						}
						original := (py-d.Y)*d.W + px - d.X
						if (len(d.Asset.Alpha) == 0 || d.Asset.Alpha[original] != 0) && d.Asset.Index[original] == a.Index[src] {
							model.Cells[py*320+px] = sceneCell{Asset: d.Asset, Source: original, Visible: true}
						}
					}
				}
				break
			}
		}
	}
	p.Counters["owned_"+kind]++
	// 保留舊 UI 的清框／換頁追蹤；這些是邏輯通知，不是 guest VGA 寫入。
	for yy := 0; yy < a.H; yy++ {
		for xx := 0; xx < a.W; xx += 4 {
			if kind == "fill" {
				mask := byte(0)
				for k := 0; k < 4; k++ {
					if a.Alpha[(yy*a.W)+xx+k] != 0 {
						mask |= 1 << uint((x+xx+k)&3)
					}
				}
				if mask != 0 {
					p.Oracle.EmitPresentationWrite(page+uint32((y+yy)*80+(x+xx)/4), a.Index[yy*a.W+xx], mask)
					p.Counters["logical_writes"]++
				}
			} else {
				for k := 0; k < 4; k++ {
					n := yy*a.W + xx + k
					if len(a.Alpha) > 0 && a.Alpha[n] == 0 {
						continue
					}
					p.Oracle.EmitPresentationWrite(page+uint32((y+yy)*80+(x+xx+k)/4), a.Index[n], 1<<uint((x+xx+k)&3))
					p.Counters["logical_writes"]++
				}
			}
		}
	}
}
func (p *playerRenderOwner) installOwnedDrivers(steps []renderPrimitive) {
	o := p.Oracle
	renderOwners[o] = p
	o.SetPresentationVideo(func(off uint32, write, after bool) {
		if !nativePageLayout(o) {
			p.releaseScene()
			return
		}
		if !after {
			if write {
				for _, v := range p.Pending {
					if v.Owned != nil {
						if v.Owned.Kind == "glyph-compat" {
							continue
						}
						if v.Owned.Kind == "image" {
							p.fallbackImage(v.Owned)
							continue
						}
						p.Counters["unexpected_owned_native_writes"]++
						panic("已接管繪圖仍寫入原版像素，停止重複繪製")
					}
				}
			}
			p.Counters["readback_plane_bytes"] += uint64(p.Scene.materialize(off, o.SetPresentationPlane))
			return
		}
		p.Counters["native_writes"]++
		glyph := p.pending(0x12ee1, false) != nil && !p.inReadback()
		if off < 65536 && off&0x3fff < 16000 {
			p.Scene.page(off&0xc000, o.PresentationPlane)
		}
		p.Scene.nativeWrite(off, o.PresentationVideoState()[4], p.inReadback(), glyph, o.PresentationPlane)
	}, func() []byte {
		page, ok := nativeVisiblePage(o)
		if !ok {
			return nil
		}
		return p.Scene.page(page, o.PresentationPlane).Index[:]
	}, func() {
		p.Scene = renderScene{}
		p.LayerKey = ""
		if p.Text != nil {
			p.Text.Words = nil
		}
	})
	for _, point := range steps {
		ea := uint32(point.Segment)*16 + uint32(point.Offset) + 0xef00
		o.OnCall(oracle.Addr{Seg: point.Segment, Off: point.Offset}, func(*oracle.Oracle) { p.step(ea) })
	}
}
func (p *playerRenderOwner) step(ea uint32) {
	o := p.Oracle
	r := o.Regs()
	switch ea {
	case 0x26bbc, 0x26dc2:
		p.image(ea == 0x26dc2)
	case 0x26d7b:
		p.imagePacket()
	case 0x10fd6, 0x11017, 0x12ebf:
		p.imageTransfer(ea)
	case 0x12ef8:
		p.glyph()
	case 0x12fa1:
		if v := p.pending(0x12ee1, true); v != nil && v.Owned != nil && v.Owned.Kind == "glyph" {
			must(o.CommitPresentationWork(v.Owned.LastSteps, v.Owned.LastCycles))
			p.Counters["virtual_instructions"] += v.Owned.LastSteps
			p.jump(0x12faa)
		} else {
			o.QueuePresentationInstruction(func() bool { return p.glyphInstruction(ea) })
		}
	case 0x12f0d, 0x12f13, 0x12f22, 0x12f28, 0x12f37, 0x12f3d, 0x12f4c, 0x12f52,
		0x12f62, 0x12f68, 0x12f77, 0x12f7d, 0x12f8c, 0x12f92, 0x12fa7:
		o.QueuePresentationInstruction(func() bool { return p.glyphInstruction(ea) })
	case 0x110c5, 0x110f8:
		p.fill(ea == 0x110f8)
	case 0x11187:
		if !p.patternRow() {
			o.QueuePresentationInstruction(func() bool { return p.storeInstruction(ea, 2, true) })
		}
	case 0x1104c:
		p.maskedBlit(2)
	case 0x11099:
		p.maskedBlit(1)
	case 0x1113e:
		p.maskFill()
	case 0x11abd:
		p.maskColumn()
	case 0x11944:
		p.shiftedMaskedBlit()
	case 0x11664, 0x1167f, 0x116b1, 0x116bd:
		if !p.videoCopy(ea, false) && !p.ramUpload(ea, false) {
			o.QueuePresentationInstruction(func() bool { return p.videoCopy(ea, true) || p.ramUpload(ea, true) })
		}
	case 0x1165f, 0x11678:
		o.QueuePresentationInstruction(func() bool { return p.copyByteInstruction(ea) })
	case 0x119cf, 0x11b51, 0x113c2, 0x113cf:
		if !p.rawTransfer(ea, false) {
			o.QueuePresentationInstruction(func() bool { return p.rawTransfer(ea, true) })
		}
	case 0x1162c:
		o.QueuePresentationInstruction(p.clearInstruction)
	case 0x11054, 0x1197b, 0x11145, 0x11aca:
		o.QueuePresentationInstruction(func() bool { return p.storeInstruction(ea, 2, false) })
	case 0x12ec4, 0x110a0, 0x113f2, 0x1140d:
		o.QueuePresentationInstruction(func() bool { return p.storeInstruction(ea, 1, false) })
	case 0x110d6, 0x11421, 0x11428:
		o.QueuePresentationInstruction(func() bool { return p.storeInstruction(ea, 1, true) })
	case 0x113e5, 0x11400:
		p.maskedRLESpan(ea)
	case 0x1110b:
		o.QueuePresentationInstruction(func() bool { return p.storeInstruction(ea, 2, true) })
	case 0x110d2, 0x11107:
		origin, tail := uint32(0x110b8), uint32(0x110d8)
		if ea == 0x11107 {
			origin, tail = 0x110eb, 0x1110d
		}
		if v := p.pending(origin, false); v != nil && v.Owned != nil && r.SP+10 == v.Return.SP {
			d := v.Owned
			count := d.W / 4
			if ea == 0x11107 {
				count /= 2
			}
			steps := uint64(8*d.H - 5)
			cycles := uint64((7+5*count)*d.H + 24*(d.H-1))
			if o.PresentationDOSCost() {
				cycles = steps + uint64(count*d.H)
			}
			must(o.CommitPresentationWork(steps, cycles))
			p.Counters["virtual_instructions"] += steps
			last := d.Base + (d.H-1)*80
			o.SetRegs(oracle.CallRegs{SI: uint16(last), DI: uint16(last + d.W/4), CX: 0, DX: 1, SetSI: true, SetDI: true, SetCX: true, SetDX: true})
			p.jump(tail)
		}
	}
}

// word 搬移的奇數 byte 前綴。只攔目的顯存，RAM 邏輯保持原樣。
func (p *playerRenderOwner) copyByteInstruction(ea uint32) bool {
	o := p.Oracle
	r := o.Regs()
	s := o.PresentationVideoState()
	if !nativePageLayout(o) || (s[0] != 0x40 && s[0] != 0x41) || s[1] != 255 || s[2] != 0 || s[3] != 0 ||
		r.ES < 0xa000 || r.ES > 0xac00 || (r.ES-0xa000)%0x400 != 0 || r.DI >= 16000 {
		return false
	}
	fromVideo := r.DS >= 0xa000 && r.DS <= 0xac00 && (r.DS-0xa000)%0x400 == 0 && r.SI < 16000
	if !fromVideo && (uint32(r.DS)*16+uint32(r.SI) >= 0xa0000 || s[0] == 0x41) {
		return false
	}
	page := uint32(r.ES-0xa000) * 16
	value := o.Byte(oracle.Addr{Seg: r.DS, Off: r.SI})
	a := &sceneAsset{W: 4, H: 1, Index: []byte{value, value, value, value}, Alpha: make([]byte, 4)}
	var source *scenePage
	if fromVideo {
		source = p.Scene.page(uint32(r.DS-0xa000)*16, o.PresentationPlane)
	}
	var cells [4]sceneCell
	for plane := 0; plane < 4; plane++ {
		if s[4]&(1<<uint(plane)) == 0 {
			continue
		}
		a.Alpha[plane] = 255
		if source != nil {
			readPlane := int(s[5] & 3)
			if s[0] == 0x41 {
				readPlane = plane
			}
			cells[plane] = source.Cells[int(r.SI)*4+readPlane]
			a.Index[plane] = source.Index[int(r.SI)*4+readPlane]
		}
	}
	a = p.cache("copy-prefix:"+digest(a.Index)+":"+digest(a.Alpha), a)
	p.record(a, int(r.DI%80)*4, int(r.DI/80), page, "source_blit")
	if source != nil && !p.inReadback() {
		model := p.Scene.page(page, o.PresentationPlane)
		for plane, c := range cells {
			if a.Alpha[plane] != 0 {
				model.Cells[int(r.DI)*4+plane] = c
				if c.Asset == nil || !c.Visible {
					o.SetPresentationPlane(plane, page+uint32(r.DI), a.Index[plane])
				}
			}
		}
	}
	cycles := uint64(7)
	if o.PresentationDOSCost() {
		cycles = 2
	}
	o.CommitPresentationInstructionCycles(cycles)
	p.Counters["virtual_instructions"]++
	p.Counters["owned_copy_prefix"]++
	delta := uint16(1)
	if r.Flags&0x400 != 0 {
		delta = 0xffff
	}
	o.SetRegs(oracle.CallRegs{SI: r.SI + delta, DI: r.DI + delta, SetSI: true, SetDI: true})
	p.jump(ea + 1)
	return true
}

// 完整矩形／遮罩命令遇事件時，只接管當下的寫入，原版仍維持機器效果。
func (p *playerRenderOwner) storeInstruction(ea uint32, unit int, repeat bool) bool {
	o := p.Oracle
	r := o.Regs()
	if !p.guard() || r.ES < 0xa000 || r.ES > 0xac00 || (r.ES-0xa000)%0x400 != 0 {
		return false
	}
	count := 1
	if repeat {
		count = int(r.CX)
	}
	n := count * unit
	if int(r.DI)+n > 16000 {
		return false
	}
	page, mask := uint32(r.ES-0xa000)*16, o.PresentationVideoState()[4]&15
	for at := 0; at < n; {
		off := int(r.DI) + at
		width := min(n-at, 80-off%80)
		a := &sceneAsset{W: width * 4, H: 1, Index: make([]byte, width*4), Alpha: make([]byte, width*4)}
		for i := range a.Index {
			a.Index[i] = byte(r.AX >> uint(((at+i/4)%unit)*8))
			if mask&(1<<uint(i&3)) != 0 {
				a.Alpha[i] = 255
			}
		}
		a = p.cache("boundary-store:"+digest(a.Index)+":"+digest(a.Alpha), a)
		p.record(a, off%80*4, off/80, page, "boundary_span")
		at += width
	}
	cycles := uint64(7)
	if repeat {
		cycles = uint64(3 + 5*count)
	}
	if o.PresentationDOSCost() {
		cycles = 2
		if repeat {
			cycles = uint64(1 + count)
		}
	}
	if ea == 0x11aca && o.PresentationDOSCost() {
		cycles = 1
	}
	o.CommitPresentationInstructionCycles(cycles)
	p.Counters["virtual_instructions"]++
	u := oracle.CallRegs{DI: r.DI + uint16(n), SetDI: true}
	if ea == 0x11aca {
		u.SetDI = false
	}
	if repeat {
		u.CX = 0
		u.SetCX = true
	}
	o.SetRegs(u)
	length := uint32(1)
	if repeat {
		length = 2
	}
	if ea == 0x11aca {
		length = 3
	}
	p.jump(ea + length)
	return true
}

// 事件附近保留原控制流程，像素仍取預先解碼的字形命令，跳過 guest MOV。
func (p *playerRenderOwner) glyphInstruction(ea uint32) bool {
	o := p.Oracle
	r := o.Regs()
	v := p.pending(0x12ee1, true)
	if v == nil || v.Owned == nil || v.Owned.Kind != "glyph-compat" || !p.guard() {
		return false
	}
	d := v.Owned
	if r.ES < 0xa000 || uint32(r.ES-0xa000)*16 != d.Page || r.DI >= 16000 {
		return false
	}
	mask := o.PresentationVideoState()[4] & 15
	model := p.Scene.page(d.Page, o.PresentationPlane)
	for plane := 0; plane < 4; plane++ {
		if mask&(1<<uint(plane)) == 0 {
			continue
		}
		x, y := int(r.DI%80)*4+plane, int(r.DI/80)
		if x < d.X || x >= d.X+8 || y < d.Y || y >= d.Y+8 {
			return false
		}
		source, at := (y-d.Y)*8+x-d.X, y*320+x
		value := d.Asset.Index[source]
		if p.inReadback() {
			cell := &model.Cells[at]
			cell.Visible = cell.Asset != nil && cell.Asset.Index[cell.Source] == value
			o.SetPresentationPlane(plane, d.Page+uint32(r.DI), value)
		} else {
			model.Cells[at] = sceneCell{Asset: d.Asset, Source: source, Visible: true}
		}
		model.Index[at] = value
		o.EmitPresentationWrite(d.Page+uint32(r.DI), value, 1<<uint(plane))
		p.Counters["logical_writes"]++
	}
	p.Scene.Revision++
	cycles := uint64(7)
	if o.PresentationDOSCost() {
		cycles = 1
	}
	o.CommitPresentationInstructionCycles(cycles)
	p.Counters["virtual_instructions"]++
	p.Counters["owned_glyph_boundary_pixels"]++
	p.jump(ea + 3)
	return true
}

// IDA 1162Ch 的 REP STOSW。事件仍按原 Machine.Step 順序派送。
func (p *playerRenderOwner) clearInstruction() bool {
	o := p.Oracle
	r := o.Regs()
	s := o.PresentationVideoState()
	n := int(r.CX) * 2
	if r.Flags&0x400 != 0 || !nativePageLayout(o) || (s[0] != 0 && s[0] != 0x40) || s[1] != 255 || s[2] != 0 || s[3] != 0 ||
		r.ES < 0xa000 || r.ES > 0xac00 || (r.ES-0xa000)%0x400 != 0 || int(r.DI)+n > 16000 {
		return false
	}
	page := uint32(r.ES-0xa000) * 16
	for at := 0; at < n; {
		off := int(r.DI) + at
		count := min(n-at, 80-off%80)
		a := &sceneAsset{W: count * 4, H: 1, Index: make([]byte, count*4), Alpha: make([]byte, count*4)}
		for i := range a.Index {
			a.Index[i] = byte(r.AX >> uint(((at+i/4)&1)*8))
			if s[4]&(1<<uint(i&3)) != 0 {
				a.Alpha[i] = 255
			}
		}
		a = p.cache("clear:"+digest(a.Index)+":"+digest(a.Alpha), a)
		p.record(a, off%80*4, off/80, page, "clear")
		at += count
	}
	cycles := uint64(3 + int(r.CX)*5)
	if o.PresentationDOSCost() {
		cycles = uint64(1 + int(r.CX))
	}
	o.CommitPresentationInstructionCycles(cycles)
	p.Counters["virtual_instructions"]++
	p.Counters["owned_clear_rep"]++
	o.SetRegs(oracle.CallRegs{DI: r.DI + uint16(n), CX: 0, SetDI: true, SetCX: true})
	p.jump(0x1162e)
	return true
}

func (p *playerRenderOwner) shiftedMaskedBlit() {
	o := p.Oracle
	r := o.Regs()
	if p.pending(0x1192c, true) == nil || !p.guard() || r.ES < 0xa000 || r.ES > 0xac00 || (r.ES-0xa000)%0x400 != 0 {
		return
	}
	n := int(byte(p.word(16)))
	if n < 1 || n > 79 || int(r.DI)+n+1 > 16000 || int(r.SI)+n > 65536 || int(r.BX)+n > 65536 ||
		uint32(r.DS)*16+uint32(r.SI)+uint32(n) > 0xa0000 || uint32(r.DS)*16+uint32(r.BX)+uint32(n) > 0xa0000 {
		return
	}
	steps, cycles := uint64(18*n+10), uint64(60*n+45)
	if n == 1 {
		steps, cycles = 27, 103
	}
	if o.PresentationDOSCost() {
		cycles = steps + uint64(n*2)
	}
	if o.PresentationWorkBudget(steps+1) != steps+1 {
		return
	}
	color := o.Bytes(oracle.Addr{Seg: r.DS, Off: r.SI}, n)
	mask := o.Bytes(oracle.Addr{Seg: r.DS, Off: r.BX}, n)
	page := uint32(r.ES-0xa000) * 16
	state := o.PresentationVideoState()
	a, ax, dx := p.Scene.page(page, o.PresentationPlane).shiftedMaskedBlit(mask, color, int(r.DI), int(state[5]&3), state[4]&15, byte(p.word(20)), byte(p.word(22)), byte(r.CX))
	o.Bytes(oracle.Addr{Seg: r.ES, Off: r.DI + uint16(n)}, 1)
	for at := 0; at < n+1; {
		off := int(r.DI) + at
		count := min(n+1-at, 80-off%80)
		row := &sceneAsset{W: count * 4, H: 1, Index: a.Index[at*4 : (at+count)*4], Alpha: a.Alpha[at*4 : (at+count)*4]}
		row = p.cache("shifted-mask:"+digest(row.Index)+":"+digest(row.Alpha), row)
		p.record(row, off%80*4, off/80, page, "shifted_mask")
		at += count
	}
	must(o.CommitPresentationWork(steps, cycles))
	p.Counters["virtual_instructions"] += steps
	p.Counters["owned_shifted_mask_rows"]++
	o.SetPresentationArithmeticFlags(0x94)
	o.SetRegs(oracle.CallRegs{AX: ax, DX: dx, BX: r.BX + uint16(n), SI: r.SI + uint16(n), DI: r.DI + uint16(n), CX: 0xff00 | r.CX&255,
		SetAX: true, SetDX: true, SetBX: true, SetSI: true, SetDI: true, SetCX: true})
	p.jump(0x11991)
}

func sceneLogicFlags(value uint16) uint16 {
	flags := uint16(0)
	if value == 0 {
		flags |= 0x40
	}
	if value&0x8000 != 0 {
		flags |= 0x80
	}
	if bits.OnesCount8(byte(value))%2 == 0 {
		flags |= 4
	}
	return flags
}

// 壓縮圖的已解碼遮罩封包。封包控制與裁切仍由原資料解析器負責。
func (p *playerRenderOwner) maskedRLESpan(ea uint32) {
	o := p.Oracle
	r := o.Regs()
	n := int(r.CX)
	if !p.guard() || n == 0 || r.ES < 0xa000 || r.ES > 0xac00 || (r.ES-0xa000)%0x400 != 0 ||
		int(r.DI)+n > 16000 || int(r.DI%80)+n > 80 || int(r.SI)+n > 65536 || int(r.BX)+n > 65536 ||
		uint32(r.DS)*16+uint32(r.SI)+uint32(n) > 0xa0000 || uint32(r.DS)*16+uint32(r.BX)+uint32(n) > 0xa0000 {
		return
	}
	steps := uint64(n * 9)
	if o.PresentationWorkBudget(steps+3) != steps+3 {
		return
	}
	masks := o.Bytes(oracle.Addr{Seg: r.DS, Off: r.SI}, n)
	colors := o.Bytes(oracle.Addr{Seg: r.DS, Off: r.BX}, n)
	keep, ink := make([]byte, n), make([]byte, n)
	for i, m := range masks {
		keep[i] = ^m
		ink[i] = m & colors[i]
	}
	s := o.PresentationVideoState()
	page := uint32(r.ES-0xa000) * 16
	a := p.Scene.page(page, o.PresentationPlane).maskedBlit(keep, ink, int(r.DI), int(s[5]&3), s[4]&15)
	o.Bytes(oracle.Addr{Seg: r.ES, Off: r.DI + uint16(n) - 1}, 1)
	a = p.cache("masked-rle:"+digest(a.Index)+":"+digest(a.Alpha), a)
	p.record(a, int(r.DI%80)*4, int(r.DI/80), page, "masked_rle")
	cycles := uint64(n * 37)
	if o.PresentationDOSCost() {
		cycles = uint64(n * 11)
	}
	must(o.CommitPresentationWork(steps, cycles))
	p.Counters["virtual_instructions"] += steps
	value := a.Index[(n-1)*4]
	flags := sceneLogicFlags(uint16(value))
	if value&128 != 0 {
		flags |= 128
	}
	o.SetPresentationArithmeticFlags(flags)
	o.SetRegs(oracle.CallRegs{AX: uint16(ink[n-1])<<8 | uint16(value), CX: 0, SI: r.SI + uint16(n), BX: r.BX + uint16(n), DI: r.DI + uint16(n), SetAX: true, SetCX: true, SetSI: true, SetBX: true, SetDI: true})
	if ea == 0x113e5 {
		p.jump(0x113f5)
	} else {
		p.jump(0x11410)
	}
}

// 原背景與常量遮罩的矩形命令，保留原版列控制及讀回鎖存器。
func (p *playerRenderOwner) maskFill() {
	o := p.Oracle
	r := o.Regs()
	if p.pending(0x11120, false) == nil || !p.guard() || r.ES < 0xa000 || r.ES > 0xac00 || (r.ES-0xa000)%0x400 != 0 || r.CX == 0 {
		return
	}
	budget := o.PresentationWorkBudget(uint64(r.CX)*5 + 1)
	if budget < 6 {
		return
	}
	words := min(int(r.CX), int((budget-1)/5))
	n := words * 2
	if int(r.DI)+n > 16000 || int(r.DI%80)+n > 80 {
		return
	}
	mask, color := make([]byte, n), make([]byte, n)
	for i := range mask {
		mask[i] = byte(r.BX >> uint((i&1)*8))
		color[i] = byte(r.DX >> uint((i&1)*8))
	}
	s := o.PresentationVideoState()
	page := uint32(r.ES-0xa000) * 16
	a := p.Scene.page(page, o.PresentationPlane).maskedBlit(mask, color, int(r.DI), int(s[5]&3), s[4]&15)
	o.Bytes(oracle.Addr{Seg: r.ES, Off: r.DI + uint16(n) - 1}, 1)
	a = p.cache("mask-fill:"+digest(a.Index)+":"+digest(a.Alpha), a)
	p.record(a, int(r.DI%80)*4, int(r.DI/80), page, "mask_fill")
	cycles := uint64(words * 20)
	if o.PresentationDOSCost() {
		cycles = uint64(words * 6)
	}
	must(o.CommitPresentationWork(uint64(words*5), cycles))
	p.Counters["virtual_instructions"] += uint64(words * 5)
	last := uint16(a.Index[(n-2)*4]) | uint16(a.Index[(n-1)*4])<<8
	o.SetPresentationArithmeticFlags(sceneLogicFlags(last))
	o.SetRegs(oracle.CallRegs{AX: last, CX: r.CX - uint16(words), DI: r.DI + uint16(n), SetAX: true, SetCX: true, SetDI: true})
	if words == int(r.CX) {
		p.jump(0x11148)
	} else {
		p.jump(0x1113e)
	}
}

// 16列圖樣的遮罩直條。來源是資料 word，Go 合成，不執行原寫入。
func (p *playerRenderOwner) maskColumn() {
	o := p.Oracle
	r := o.Regs()
	if p.pending(0x11aa1, true) == nil || !p.guard() || r.ES < 0xa000 || r.ES > 0xac00 || (r.ES-0xa000)%0x400 != 0 || r.DI >= 15999 || r.DI%80 == 79 ||
		uint32(r.DS)*16+uint32(r.SI)+uint32(r.BX)+2 > 0xa0000 || uint32(r.SI)+uint32(r.BX)+2 > 65536 || o.PresentationWorkBudget(8) != 8 {
		return
	}
	source := o.Word(oracle.Addr{Seg: r.DS, Off: r.SI + r.BX}) & r.DX
	mask := []byte{byte(^r.DX), byte(^r.DX >> 8)}
	color := []byte{byte(source), byte(source >> 8)}
	s := o.PresentationVideoState()
	page := uint32(r.ES-0xa000) * 16
	a := p.Scene.page(page, o.PresentationPlane).maskedBlit(mask, color, int(r.DI), int(s[5]&3), s[4]&15)
	o.Bytes(oracle.Addr{Seg: r.ES, Off: r.DI + 1}, 1)
	a = p.cache("mask-column:"+digest(a.Index)+":"+digest(a.Alpha), a)
	p.record(a, int(r.DI%80)*4, int(r.DI/80), page, "mask_column")
	cycles := uint64(28)
	if o.PresentationDOSCost() {
		cycles = 7
	}
	must(o.CommitPresentationWork(7, cycles))
	p.Counters["virtual_instructions"] += 7
	last := uint16(a.Index[0]) | uint16(a.Index[4])<<8
	o.SetPresentationArithmeticFlags(sceneLogicFlags(last))
	o.SetRegs(oracle.CallRegs{AX: last, CX: source, SetAX: true, SetCX: true})
	p.jump(0x11acd)
}

func (p *playerRenderOwner) maskedBlit(unit int) {
	o := p.Oracle
	r := o.Regs()
	if !p.guard() || r.CX == 0 || r.ES < 0xa000 || r.ES > 0xac00 || (r.ES-0xa000)%0x400 != 0 {
		return
	}
	perSteps, perCycles, tail, head := 7, 33, uint32(0x11057), uint32(0x1104c)
	if unit == 1 {
		perSteps, perCycles, tail, head = 6, 31, 0x110a3, 0x11099
	}
	budget := o.PresentationWorkBudget(uint64(r.CX)*uint64(perSteps) + 1)
	if budget < uint64(perSteps+1) {
		return
	}
	words := min(int(r.CX), int((budget-1)/uint64(perSteps)))
	n := words * unit
	if int(r.SI)+n > 65536 || int(r.BX)+n > 65536 || int(r.DI)+n > 16000 || int(r.DI%80)+n > 80 ||
		uint32(r.DS)*16+uint32(r.SI)+uint32(n) > 0xa0000 || uint32(r.DS)*16+uint32(r.BX)+uint32(n) > 0xa0000 {
		return
	}
	mask := o.Bytes(oracle.Addr{Seg: r.DS, Off: r.SI}, n)
	color := o.Bytes(oracle.Addr{Seg: r.DS, Off: r.BX}, n)
	s := o.PresentationVideoState()
	page := uint32(r.ES-0xa000) * 16
	model := p.Scene.page(page, o.PresentationPlane)
	a := model.maskedBlit(mask, color, int(r.DI), int(s[5]&3), s[4]&15)
	// 最後一次目的word讀取在寫入前載入四平面鎖存器。
	o.Bytes(oracle.Addr{Seg: r.ES, Off: r.DI + uint16(n) - 1}, 1)
	a = p.cache("masked-blit:"+digest(a.Index)+":"+digest(a.Alpha), a)
	p.record(a, int(r.DI%80)*4, int(r.DI/80), page, "masked_blit")
	cycles := uint64(words * perCycles)
	if o.PresentationDOSCost() {
		cycles = uint64(words * (perSteps + 2))
	}
	must(o.CommitPresentationWork(uint64(words*perSteps), cycles))
	p.Counters["virtual_instructions"] += uint64(words * perSteps)
	last := uint16(a.Index[(n-1)*4]) | r.AX&0xff00
	if unit == 2 {
		last = uint16(a.Index[(n-2)*4]) | uint16(a.Index[(n-1)*4])<<8
	}
	bx := r.BX + uint16(n)
	flags := uint16(0)
	if bits.OnesCount8(byte(bx))%2 == 0 {
		flags |= 4
	}
	if bx&15 == 0 {
		flags |= 0x10
	}
	if bx == 0 {
		flags |= 0x40
	}
	if bx&0x8000 != 0 {
		flags |= 0x80
	}
	if bx == 0x8000 {
		flags |= 0x800
	}
	o.SetPresentationArithmeticFlags(flags)
	o.SetRegs(oracle.CallRegs{AX: last, BX: bx, SI: r.SI + uint16(n), DI: r.DI + uint16(n), CX: r.CX - uint16(words),
		SetAX: true, SetBX: true, SetSI: true, SetDI: true, SetCX: true})
	if words == int(r.CX) {
		p.jump(tail)
	} else {
		p.jump(head)
	}
}

// 已證實的跨頁REP。來源歸屬與色號一起搬移，最後一次VGA讀取保留鎖存器。
func (p *playerRenderOwner) videoCopy(ea uint32, atomic bool) bool {
	o := p.Oracle
	r := o.Regs()
	origin, unit := uint32(0x11688), 1
	if ea == 0x11664 || ea == 0x1167f {
		origin, unit = 0x11632, 2
	}
	s := o.PresentationVideoState()
	if p.pending(origin, true) == nil || r.SS != 0x333e || !nativePageLayout(o) ||
		p.global(0xca41) != 15 || p.global(0xcb6c) != 80 ||
		(s[0] != 0x40 && s[0] != 0x41) || s[1] != 255 || s[2] != 0 || s[3] != 0 || r.CX == 0 ||
		r.DS < 0xa000 || r.DS > 0xac00 || (r.DS-0xa000)%0x400 != 0 ||
		r.ES < 0xa000 || r.ES > 0xac00 || (r.ES-0xa000)%0x400 != 0 {
		return false
	}
	n, direction := int(r.CX)*unit, 1
	source, destination := int(r.SI), int(r.DI)
	if r.Flags&0x400 != 0 {
		direction = -1
		source, destination = source-n+unit, destination-n+unit
	}
	mask := s[4] & 15
	if source < 0 || source+n > 16000 || destination < 0 || destination+n > 16000 || mask == 0 || (!atomic && o.PresentationWorkBudget(2) != 2) {
		return false
	}
	sourcePage, destinationPage := uint32(r.DS-0xa000)*16, uint32(r.ES-0xa000)*16
	from := p.Scene.page(sourcePage, o.PresentationPlane)
	to := p.Scene.page(destinationPage, o.PresentationPlane)
	if sourcePage == destinationPage {
		copyOfSource := *from
		from = &copyOfSource
	}
	temporary := p.inReadback()
	// MOVSW先讀完word再寫；模式1兩個寫入均使用第二byte讀取後的鎖存器。
	last := source + n - 1
	if direction < 0 {
		last = source + unit - 1
	}
	o.Bytes(oracle.Addr{Seg: r.DS, Off: uint16(last)}, 1)
	for i := 0; i < n; i++ {
		sourceOff := source + i
		if s[0] == 0x41 && unit == 2 {
			sourceOff = source + i/2*2 + 1
		}
		for plane := 0; plane < 4; plane++ {
			if mask&(1<<uint(plane)) == 0 {
				continue
			}
			readPlane := plane
			if s[0] == 0x40 {
				readPlane = int(s[5] & 3)
			}
			src, dst := sourceOff*4+readPlane, (destination+i)*4+plane
			value, cell := from.Index[src], from.Cells[src]
			if temporary {
				cell = to.Cells[dst]
				if cell.Asset != nil {
					cell.Visible = value == cell.Asset.Index[cell.Source]
				} else {
					cell = sceneCell{}
				}
			}
			if temporary || cell.Asset == nil || !cell.Visible {
				if !temporary {
					cell = sceneCell{Unsafe: cell.Unsafe}
				}
				o.SetPresentationPlane(plane, destinationPage+uint32(destination+i), value)
			}
			to.Index[dst], to.Cells[dst] = value, cell
			o.EmitPresentationWrite(destinationPage+uint32(destination+i), value, 1<<uint(plane))
			p.Counters["logical_writes"]++
		}
	}
	p.Scene.Revision++
	cycles := uint64(3 + 5*int(r.CX))
	if o.PresentationDOSCost() {
		cycles = uint64(1 + int(r.CX))
	}
	if atomic {
		o.CommitPresentationInstructionCycles(cycles)
	} else {
		must(o.CommitPresentationWork(1, cycles))
	}
	p.Counters["virtual_instructions"]++
	p.Counters["owned_video_copy_rep"]++
	p.Counters["owned_video_copy_bytes"] += uint64(n)
	o.SetRegs(oracle.CallRegs{SI: uint16(int(r.SI) + direction*n), DI: uint16(int(r.DI) + direction*n), CX: 0, SetSI: true, SetDI: true, SetCX: true})
	p.jump(ea + 2)
	return true
}

// 保留反向memmove的準備與返回，僅替換來源為RAM的單條REP。
func (p *playerRenderOwner) ramUpload(ea uint32, atomic bool) bool {
	if ea != 0x1167f && ea != 0x116bd {
		return false
	}
	o := p.Oracle
	r := o.Regs()
	origin, unit := uint32(0x11688), 1
	if ea == 0x1167f {
		origin, unit = 0x11632, 2
	}
	if p.pending(origin, true) == nil || !p.modeXGuard() || r.Flags&0x400 == 0 || r.CX == 0 ||
		r.ES < 0xa000 || r.ES > 0xac00 || (r.ES-0xa000)%0x400 != 0 {
		return false
	}
	n := int(r.CX) * unit
	source, destination := int(r.SI)-n+unit, int(r.DI)-n+unit
	if source < 0 || source+n > 65536 || destination < 0 || destination+n > 16000 ||
		uint32(r.DS)*16+uint32(source+n) > 0xa0000 {
		return false
	}
	mask := o.PresentationVideoState()[4] & 15
	if mask == 0 || (!atomic && o.PresentationWorkBudget(2) != 2) {
		return false
	}
	data := o.Bytes(oracle.Addr{Seg: r.DS, Off: uint16(source)}, n)
	page := uint32(r.ES-0xa000) * 16
	for at := 0; at < n; {
		off := destination + at
		count := min(n-at, 80-off%80)
		row := data[at : at+count]
		key := fmt.Sprintf("upload:%d:%s", mask, digest(row))
		a := p.Assets[key]
		if a == nil {
			a = &sceneAsset{W: count * 4, H: 1, Index: make([]byte, count*4), Alpha: make([]byte, count*4)}
			for i := range a.Index {
				a.Index[i] = row[i/4]
				if mask&(1<<uint(i&3)) != 0 {
					a.Alpha[i] = 255
				}
			}
			a = p.cache(key, a)
		}
		p.record(a, off%80*4, off/80, page, "ram_upload")
		at += count
	}
	cycles := uint64(3 + 5*int(r.CX))
	if o.PresentationDOSCost() {
		cycles = uint64(1 + int(r.CX))
	}
	if atomic {
		o.CommitPresentationInstructionCycles(cycles)
	} else {
		must(o.CommitPresentationWork(1, cycles))
	}
	p.Counters["virtual_instructions"]++
	p.Counters["owned_ram_upload_rep"]++
	p.Counters["owned_ram_upload_bytes"] += uint64(n)
	o.SetRegs(oracle.CallRegs{SI: r.SI - uint16(n), DI: r.DI - uint16(n), CX: 0, SetSI: true, SetDI: true, SetCX: true})
	p.jump(ea + 2)
	return true
}

// sub_1115E 保留圖樣取值、行號、參數遞減與列尾，只替換當列 REP STOSW。
func (p *playerRenderOwner) patternRow() bool {
	o := p.Oracle
	r := o.Regs()
	if p.pending(0x1115e, true) == nil || !p.guard() ||
		r.ES < 0xa000 || r.ES > 0xac00 || (r.ES-0xa000)%0x400 != 0 || r.CX == 0 {
		return false
	}
	x, y, width := int(r.DI%80)*4, int(r.DI/80), int(r.CX)*8
	mask := o.PresentationVideoState()[4] & 15
	if mask == 0 || x+width > 320 || y >= 200 || o.PresentationWorkBudget(2) != 2 {
		return false
	}
	key := fmt.Sprintf("pattern:%d:%04x:%d", width, r.AX, mask)
	a := p.Assets[key]
	if a == nil {
		a = &sceneAsset{W: width, H: 1, Index: make([]byte, width), Alpha: make([]byte, width)}
		for i := range a.Index {
			a.Index[i] = byte(r.AX >> uint((i/4%2)*8))
			if mask&(1<<uint(i&3)) != 0 {
				a.Alpha[i] = 255
			}
		}
		a = p.cache(key, a)
	}
	p.record(a, x, y, uint32(r.ES-0xa000)*16, "fill")
	cycles := uint64(3 + 5*int(r.CX))
	if o.PresentationDOSCost() {
		cycles = uint64(1 + int(r.CX))
	}
	must(o.CommitPresentationWork(1, cycles))
	p.Counters["virtual_instructions"]++
	p.Counters["owned_pattern_rows"]++
	o.SetRegs(oracle.CallRegs{DI: r.DI + r.CX*2, CX: 0, SetDI: true, SetCX: true})
	p.jump(0x11189)
	return true
}

func (p *playerRenderOwner) glyph() {
	o := p.Oracle
	r := o.Regs()
	v := p.pending(0x12ee1, true)
	if v == nil || !p.guard() {
		return
	}
	if r.ES < 0xa000 || r.ES > 0xac00 || (r.ES-0xa000)%0x400 != 0 || r.DI >= 16000 {
		return
	}
	x, y := int(r.DI%80)*4, int(r.DI/80)
	if x+8 > 320 || y+8 > 200 {
		return
	}
	addr := oracle.Addr{Seg: r.DS, Off: r.SI}
	if addr.Linear()+8 > 0xa0000 || r.SI > 0xfff8 {
		return
	}
	font := o.Bytes(addr, 8)
	ones := 0
	for _, row := range font {
		ones += bits.OnesCount8(row)
	}
	lastSteps, lastCycles := uint64(2), uint64(14)
	prefixOnes := ones
	if font[7]&1 != 0 {
		prefixOnes--
		lastSteps, lastCycles = 1, 12
	}
	steps := uint64(691 - prefixOnes)
	cycles := uint64(3886 - 2*prefixOnes)
	if o.PresentationDOSCost() {
		cycles = steps + 8
		lastCycles = lastSteps
	}
	reserve := steps + lastSteps + 64
	fast := o.PresentationWorkBudget(reserve) == reserve
	key := fmt.Sprintf("glyph:%x:%04x", font, r.BX)
	a := p.Assets[key]
	if a == nil {
		a = &sceneAsset{W: 8, H: 8, Index: make([]byte, 64)}
		for yy, row := range font {
			for xx := 0; xx < 8; xx++ {
				col := byte(r.BX)
				if row&(128>>xx) != 0 {
					col = byte(r.BX >> 8)
				}
				a.Index[yy*8+xx] = col
			}
		}
		a = p.cache(key, a)
	}
	v.Owned = &ownedDriver{X: x, Y: y, W: 8, H: 8, Kind: "glyph", LastSteps: lastSteps, LastCycles: lastCycles, Asset: a, Page: uint32(r.ES-0xa000) * 16}
	if !fast {
		v.Owned.Kind = "glyph-compat"
		p.Counters["glyph_budget_fallback"]++
		return
	}
	p.record(a, x, y, uint32(r.ES-0xa000)*16, "glyph")
	must(o.CommitPresentationWork(steps, cycles))
	p.Counters["virtual_instructions"] += steps
	o.SetRegs(oracle.CallRegs{AX: 0, DX: 0x3c4, CX: 1, DI: r.DI + 7*80 + 1, SetAX: true, SetDX: true, SetCX: true, SetDI: true})
	p.jump(0x12f95)
}

func (p *playerRenderOwner) finishDriver(d *ownedDriver) {
	if d == nil || d.Kind != "glyph-compat" {
		return
	}
	// 原版只產生必要索引相容資料；最終原字形或中文仍由同一來源命令擇一畫一次。
	if !p.inReadback() {
		p.Scene.record(p.Scene.page(d.Page, p.Oracle.PresentationPlane), d.Asset, d.X, d.Y)
	}
	p.Counters["compatibility_glyph"]++
}

func (p *playerRenderOwner) fill(word bool) {
	o := p.Oracle
	r := o.Regs()
	origin := uint32(0x110b8)
	if word {
		origin = 0x110eb
	}
	v := p.pending(origin, true)
	if v == nil || !p.guard() || r.DS != r.SS || r.ES < 0xa000 || r.ES > 0xac00 || (r.ES-0xa000)%0x400 != 0 || r.SI >= 16000 {
		return
	}
	h, width, color := int(p.word(6)), int(p.word(8)), p.word(10)
	x, y := int(r.SI%80)*4, int(r.SI/80)
	if h < 1 || width < 1 || x+width*4 > 320 || y+h > 200 || int(r.SI)+h*80 > int(p.global(0xcb83)) {
		return
	}
	if word && width%2 != 0 {
		return
	}
	mask := o.PresentationVideoState()[4] & 15
	if mask == 0 {
		return
	}
	if reserve := uint64(8*h + 32); o.PresentationWorkBudget(reserve) != reserve {
		p.Counters["fill_budget_fallback"]++
		return
	}
	key := fmt.Sprintf("fill:%d:%d:%04x:%d:%t", width, h, color, mask, word)
	a := p.Assets[key]
	if a == nil {
		a = &sceneAsset{W: width * 4, H: h, Index: make([]byte, width*4*h), Alpha: make([]byte, width*4*h)}
		for i := range a.Index {
			a.Index[i] = byte(color)
			if word {
				a.Index[i] = byte(color >> uint((i%a.W/4%2)*8))
			}
			if mask&(1<<uint(i%a.W&3)) != 0 {
				a.Alpha[i] = 255
			}
		}
		a = p.cache(key, a)
	}
	v.Owned = &ownedDriver{X: x, Y: y, W: width * 4, H: h, Base: int(r.SI), Kind: "fill"}
	p.record(a, x, y, uint32(r.ES-0xa000)*16, "fill")
}

// 23h 封包圖只附來源身分；原資料解析與裁切控制沿用原路徑，像素仍由 Go 命令繪製。
func (p *playerRenderOwner) imagePacket() {
	o := p.Oracle
	r := o.Regs()
	v := p.pending(0x26d6a, true)
	if v == nil || !p.guard() || p.inReadback() || r.DS != r.SS || v.Return.Addr.Linear() != (oracle.Addr{Seg: 0x162e, Off: 0x273ff - 0x251e0}).Linear() {
		return
	}
	var source *renderImageSource
	for i := len(p.Pending) - 1; i >= 0; i-- {
		if s := p.Pending[i].Image; s != nil && !s.Bound {
			source = s
			break
		}
	}
	if source == nil {
		return
	}
	c := source.Command
	w, h := int(c.Header[6])*4, int(binary.LittleEndian.Uint16(c.Header[:2]))
	if c.Header[7] != 23 || w < 1 || h < 1 || c.X < 0 || c.Y < 0 || c.X%4 != 0 || c.X+w > 320 || c.Y+h > 200 ||
		c.X < int(p.global(0xcdb3)) || c.Y < int(p.global(0xcdae)) || c.X+w > int(p.global(0xcdb5)) || c.Y+h > int(p.global(0xcdb9)) ||
		p.global(0xcb63) != 2 || p.global(0xcd9e) != 4 {
		return
	}
	if p.word(6) != uint16(c.Y) || p.word(8) != uint16(c.X) || p.word(10) != uint16(h) || p.word(12) != uint16(w/4) || p.word(14) != 4 ||
		p.word(16) != 0 || p.word(18) != 0 || p.word(20) != 0 || p.word(22) != 0 || p.word(24) != c.Source.Off || p.word(26) != c.Source.Seg {
		return
	}
	seg := p.global(0xca33)
	if seg < 0xa000 || seg > 0xac00 || (seg-0xa000)%0x400 != 0 {
		return
	}
	c.Page = uint32(seg-0xa000) * 16
	var a *sceneAsset
	if p.HD != nil {
		if asset := p.HD.Lookup(o, c); asset != nil {
			a = p.cache("hd:"+digest(asset.HD), &sceneAsset{W: asset.W, H: asset.H, Index: asset.Index, Alpha: asset.Alpha, HD: asset.HD, Reference: asset.Reference})
		}
	}
	if a == nil {
		if c.Source.Linear() >= 0xa0000 {
			return
		}
		n := min(2*w*h+4*h, int(0xa0000-c.Source.Linear()), 65536-int(c.Source.Off))
		body := o.Bytes(c.Source, n)
		decoded, used, err := decodeSceneImage(c.Header, body)
		if err != nil {
			return
		}
		a = p.cache(fmt.Sprintf("image:%x:%s", c.Header, digest(body[:used])), decoded)
	}
	v.Owned = &ownedDriver{X: c.X, Y: c.Y, W: w, H: h, Kind: "image", Asset: a, Page: c.Page}
	source.Bound = true
}

func (p *playerRenderOwner) image(rle bool) {
	o := p.Oracle
	r := o.Regs()
	origin := uint32(0x26bb4)
	ret := uint16(0x27443 - 0x251e0)
	if rle {
		origin = 0x26db9
		ret = 0x273d3 - 0x251e0
	}
	v := p.pending(origin, true)
	if v == nil || !p.guard() || p.inReadback() || r.DS != r.SS || v.Return.Addr.Linear() != (oracle.Addr{Seg: 0x162e, Off: ret}).Linear() {
		return
	}
	var command *sourceTileCommand
	for i := len(p.Pending) - 1; i >= 0; i-- {
		s := p.Pending[i].Image
		if s != nil && !s.Bound {
			command = &s.Command
			break
		}
	}
	if command == nil {
		return
	}
	c := *command
	h, w := int(binary.LittleEndian.Uint16(c.Header[:2])), int(c.Header[6])*4
	if h < 1 || w < 1 || c.X < 0 || c.Y < 0 || c.X%4 != 0 || c.X+w > 320 || c.Y+h > 200 {
		return
	}
	if c.X < int(p.global(0xcdb3)) || c.Y < int(p.global(0xcdae)) || c.X+w > int(p.global(0xcdb5)) || c.Y+h > int(p.global(0xcdb9)) {
		return
	}
	if p.global(0xcb63) != 2 || p.global(0xcd9e) != 4 {
		return
	}
	if rle {
		if c.Header[7] != 18 || w%8 != 0 || p.word(6) != uint16(c.Y) || p.word(8) != uint16(c.X) || p.word(10) != uint16(h) || p.word(12) != uint16(w/4) || p.word(14) != 4 || p.word(16) != 0 || p.word(18) != 0 || p.word(20) != 0 || p.word(22) != c.Source.Off || p.word(24) != c.Source.Seg || byte(p.word(26)) != 0 {
			return
		}
	} else {
		if (c.Header[7] != 16 && c.Header[7] != 17 && c.Header[7] != 21) || p.word(6) != c.Source.Off || p.word(8) != c.Source.Seg || p.word(10) != uint16(c.Y) || p.word(12) != uint16(c.X) || p.word(14) != uint16(w*h/4) || p.word(16) != uint16(h) || p.word(18) != uint16(w/4) || p.word(20) != 4 || p.word(22) != 0 || byte(p.word(24)) != c.Header[7]&15 {
			return
		}
	}
	segment := p.global(0xca33)
	if segment < 0xa000 || segment > 0xac00 || (segment-0xa000)%0x400 != 0 {
		return
	}
	c.Page = uint32(segment-0xa000) * 16
	var a *sceneAsset
	if p.HD != nil {
		if asset := p.HD.Lookup(o, c); asset != nil {
			a = p.cache("hd:"+digest(asset.HD), &sceneAsset{W: asset.W, H: asset.H, Index: asset.Index, Alpha: asset.Alpha, HD: asset.HD, Reference: asset.Reference})
		}
	}
	if a == nil {
		if c.Source.Linear() >= 0xa0000 {
			return
		}
		n := w * h
		if c.Header[7] == 17 {
			n *= 2
		}
		if rle {
			n = n*2 + 16
		}
		if c.Source.Linear()+uint32(n) > 0xa0000 {
			n = int(0xa0000 - c.Source.Linear())
		}
		body := o.Bytes(c.Source, n)
		decoded, used, err := decodeSceneImage(c.Header, body)
		if err != nil || uint32(c.Source.Off)+uint32(used) > 65536 {
			return
		}
		a = p.cache(fmt.Sprintf("image:%x:%s", c.Header, digest(body[:used])), decoded)
	}
	v.Owned = &ownedDriver{X: c.X, Y: c.Y, W: w, H: h, Kind: "image", Asset: a, Page: c.Page}
	for i := len(p.Pending) - 1; i >= 0; i-- {
		s := p.Pending[i].Image
		if s != nil && s.Command.Source == c.Source {
			s.Bound = true
			break
		}
	}
}

func (p *playerRenderOwner) fallbackImage(d *ownedDriver) {
	if d.Fallback {
		return
	}
	d.Fallback = true
	p.Counters["image_native_fallback"]++
	model := p.Scene.Pages[d.Page/0x4000]
	if model == nil {
		return
	}
	for y := d.Y; y < d.Y+d.H; y++ {
		for x := d.X; x < d.X+d.W; x++ {
			i := y*320 + x
			c := &model.Cells[i]
			if c.Asset != d.Asset || c.Source != (y-d.Y)*d.W+x-d.X {
				continue
			}
			if c.Visible {
				p.Oracle.SetPresentationPlane(x&3, d.Page+uint32(y*80+x/4), c.Asset.Index[c.Source])
			}
			*c = sceneCell{}
		}
	}
	p.Scene.Revision++
}

// 圖片身分已知時保留資產來源；其餘已解碼區塊直接變成Go區塊命令。
func (p *playerRenderOwner) imageTransfer(ea uint32) {
	if !p.imageTransferOwned(ea) {
		if !p.rawTransfer(ea, false) && ea != 0x12ebf {
			p.Oracle.QueuePresentationInstruction(func() bool { return p.rawTransfer(ea, true) })
		}
	}
}

func (p *playerRenderOwner) rawTransfer(ea uint32, atomic bool) bool {
	o := p.Oracle
	r := o.Regs()
	if !p.guard() || r.ES < 0xa000 || r.ES > 0xac00 || (r.ES-0xa000)%0x400 != 0 {
		return false
	}
	n, units := int(r.CX), int(r.CX)
	if ea == 0x10fd6 {
		n *= 2
	}
	transparent := ea == 0x12ebf
	if transparent && (r.CX != r.DX || byte(r.AX>>8) != 255) {
		return false
	}
	if n < 1 || int(r.DI)+n > 16000 || int(r.SI)+n > 65536 || uint32(r.DS)*16+uint32(r.SI)+uint32(n) > 0xa0000 {
		return false
	}
	data := o.Bytes(oracle.Addr{Seg: r.DS, Off: r.SI}, n)
	steps, cycles, reserve := uint64(1), uint64(3+5*units), uint64(2)
	if o.PresentationDOSCost() {
		cycles = uint64(1 + units)
	}
	target := ea + 2
	if transparent {
		opaque := 0
		for _, value := range data {
			if value != 255 {
				opaque++
			}
		}
		steps, cycles, target = uint64(5*n), uint64(20*n), 0x12ec7
		if data[n-1] == 255 {
			steps++
			cycles += 7
		}
		if o.PresentationDOSCost() {
			cycles = steps + uint64(n+opaque)
		}
		reserve = steps + 3
	}
	if atomic && transparent || !atomic && o.PresentationWorkBudget(reserve) != reserve {
		return false
	}
	mask, page := o.PresentationVideoState()[4]&15, uint32(r.ES-0xa000)*16
	for at := 0; at < n; {
		off := int(r.DI) + at
		count := min(n-at, 80-off%80)
		row := data[at : at+count]
		key := fmt.Sprintf("raw-blit:%d:%t:%s", mask, transparent, digest(row))
		a := p.Assets[key]
		if a == nil {
			a = &sceneAsset{W: count * 4, H: 1, Index: make([]byte, count*4), Alpha: make([]byte, count*4)}
			for i := range a.Index {
				a.Index[i] = row[i/4]
				if mask&(1<<uint(i&3)) != 0 && (!transparent || row[i/4] != 255) {
					a.Alpha[i] = 255
				}
			}
			a = p.cache(key, a)
		}
		p.record(a, off%80*4, off/80, page, "source_blit")
		at += count
	}
	if atomic {
		o.CommitPresentationInstructionCycles(cycles)
	} else {
		must(o.CommitPresentationWork(steps, cycles))
	}
	p.Counters["virtual_instructions"] += steps
	p.Counters["owned_source_blit_bytes"] += uint64(n)
	update := oracle.CallRegs{SI: r.SI + uint16(n), DI: r.DI + uint16(n), CX: 0, SetSI: true, SetDI: true, SetCX: true}
	if transparent {
		update.AX, update.SetAX = r.AX&0xff00|uint16(data[n-1]), true
	}
	o.SetRegs(update)
	p.jump(target)
	return true
}

// 保留原版解壓與所有外層控制流，僅替換一個事件區間內的實際像素搬移。
func (p *playerRenderOwner) imageTransferOwned(ea uint32) bool {
	var d *ownedDriver
	for i := len(p.Pending) - 1; i >= 0; i-- {
		if v := p.Pending[i].Owned; v != nil && v.Kind == "image" {
			d = v
			break
		}
	}
	if d == nil || d.Fallback {
		return false
	}
	o := p.Oracle
	r := o.Regs()
	s := o.PresentationVideoState()
	mask := s[4] & 15
	if !p.guard() || mask == 0 || mask&(mask-1) != 0 || r.ES < 0xa000 || uint32(r.ES-0xa000)*16 != d.Page || r.DI >= 16000 {
		p.fallbackImage(d)
		return false
	}
	units := int(r.CX)
	n := units
	if ea == 0x10fd6 {
		n *= 2
	}
	if ea == 0x12ebf {
		n = int(r.DX)
		if r.CX != r.DX || byte(r.AX>>8) != 255 {
			p.fallbackImage(d)
			return false
		}
	}
	plane := bits.TrailingZeros8(mask)
	x, y := int(r.DI%80)*4+plane, int(r.DI/80)
	if n < 1 || x < d.X || y < d.Y || x+(n-1)*4 >= d.X+d.W || y >= d.Y+d.H || uint32(r.SI)+uint32(n) > 65536 || uint32(r.DS)*16+uint32(r.SI)+uint32(n) > 0xa0000 {
		p.fallbackImage(d)
		return false
	}
	data := o.Bytes(oracle.Addr{Seg: r.DS, Off: r.SI}, n)
	opaque := 0
	for i, v := range data {
		src := (y-d.Y)*d.W + x + i*4 - d.X
		if v != d.Asset.Index[src] {
			p.fallbackImage(d)
			return false
		}
		if ea != 0x12ebf || v != 255 {
			opaque++
		}
	}
	steps, cycles := uint64(1), uint64(3+5*units)
	target := ea + 2
	if o.PresentationDOSCost() {
		cycles = uint64(1 + units)
	}
	// 固定 SDK 的 LOOP 只有 base 成本，不加 taken-jump；這是模擬器契約，非硬體週期。
	if ea == 0x12ebf {
		steps = uint64(5 * n)
		cycles = uint64(20 * n)
		target = 0x12ec7
		if data[n-1] == 255 {
			steps++
			cycles += 7
		}
		if o.PresentationDOSCost() {
			cycles = steps + uint64(n+opaque)
		}
	}
	reserve := steps + 1
	if ea == 0x12ebf {
		reserve = steps + 3
	}
	if o.PresentationWorkBudget(reserve) != reserve {
		p.Counters["image_budget_fallback"]++
		return false
	}
	model := p.Scene.page(d.Page, o.PresentationPlane)
	for i, v := range data {
		if ea == 0x12ebf && v == 255 {
			continue
		}
		xx := x + i*4
		at := y*320 + xx
		src := (y-d.Y)*d.W + xx - d.X
		model.Cells[at] = sceneCell{Asset: d.Asset, Source: src, Visible: true}
		model.Index[at] = v
		o.EmitPresentationWrite(d.Page+uint32(y*80+xx/4), v, mask)
		p.Counters["logical_writes"]++
	}
	p.Scene.Revision++
	d.Transfers++
	p.Counters["owned_image_transfers"]++
	must(o.CommitPresentationWork(steps, cycles))
	p.Counters["virtual_instructions"] += steps
	update := oracle.CallRegs{SI: r.SI + uint16(n), DI: r.DI + uint16(n), CX: 0, SetSI: true, SetDI: true, SetCX: true}
	if ea == 0x12ebf {
		update.AX = r.AX&0xff00 | uint16(data[n-1])
		update.SetAX = true
	}
	o.SetRegs(update)
	p.jump(target)
	return true
}
