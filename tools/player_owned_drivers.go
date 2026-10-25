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
	o := p.Oracle
	r := o.Regs()
	s := o.PresentationVideoState()
	return r.SS == 0x333e && r.Flags&0x400 == 0 && nativePageLayout(o) &&
		o.Word(oracle.Addr{Seg: r.SS, Off: 0xca41}) == 15 && o.Word(oracle.Addr{Seg: r.SS, Off: 0xcb6c}) == 80 &&
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
	p.Scene.record(p.Scene.page(page, p.Oracle.PresentationPlane), a, x, y)
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
	case 0x10fd6, 0x11017, 0x12ebf:
		p.imageTransfer(ea)
	case 0x12ef8:
		p.glyph()
	case 0x12fa1:
		if v := p.pending(0x12ee1, true); v != nil && v.Owned != nil && v.Owned.Kind == "glyph" {
			must(o.CommitPresentationWork(v.Owned.LastSteps, v.Owned.LastCycles))
			p.Counters["virtual_instructions"] += v.Owned.LastSteps
			p.jump(0x12faa)
		}
	case 0x110c5, 0x110f8:
		p.fill(ea == 0x110f8)
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

func (p *playerRenderOwner) glyph() {
	o := p.Oracle
	r := o.Regs()
	v := p.pending(0x12ee1, true)
	if v == nil || !p.guard() || p.inReadback() {
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
	p.Scene.record(p.Scene.page(d.Page, p.Oracle.PresentationPlane), d.Asset, d.X, d.Y)
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
	if v == nil || !p.guard() || p.inReadback() || r.DS != r.SS || r.ES < 0xa000 || r.ES > 0xac00 || (r.ES-0xa000)%0x400 != 0 || r.SI >= 16000 {
		return
	}
	h, width, color := int(p.word(6)), int(p.word(8)), p.word(10)
	x, y := int(r.SI%80)*4, int(r.SI/80)
	if h < 1 || width < 1 || x+width*4 > 320 || y+h > 200 || int(r.SI)+h*80 > int(p.global(0xcb83)) {
		return
	}
	if word && (width%2 != 0 || byte(color) != byte(color>>8)) {
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
	key := fmt.Sprintf("fill:%d:%d:%d:%d", width, h, byte(color), mask)
	a := p.Assets[key]
	if a == nil {
		a = &sceneAsset{W: width * 4, H: h, Index: make([]byte, width*4*h), Alpha: make([]byte, width*4*h)}
		for i := range a.Index {
			a.Index[i] = byte(color)
			if mask&(1<<uint(i%a.W&3)) != 0 {
				a.Alpha[i] = 255
			}
		}
		a = p.cache(key, a)
	}
	v.Owned = &ownedDriver{X: x, Y: y, W: width * 4, H: h, Base: int(r.SI), Kind: "fill"}
	p.record(a, x, y, uint32(r.ES-0xa000)*16, "fill")
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
	if v == nil || !p.guard() || p.inReadback() || r.DS != r.SS || v.Return.Addr != (oracle.Addr{Seg: 0x162e, Off: ret}) {
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
		if c.Header[7] != 18 || w%8 != 0 || p.word(6) != uint16(c.Y) || p.word(8) != uint16(c.X) || p.word(10) != uint16(h) || p.word(12) != uint16(w/4) || p.word(14) != 4 || p.word(16) != 0 || p.word(18) != 0 || p.word(20) != 0 || p.word(22) != c.Source.Off || p.word(24) != c.Source.Seg || p.word(26) != 0 {
			return
		}
	} else {
		if (c.Header[7] != 16 && c.Header[7] != 21) || p.word(6) != c.Source.Off || p.word(8) != c.Source.Seg || p.word(10) != uint16(c.Y) || p.word(12) != uint16(c.X) || p.word(14) != uint16(w*h/4) || p.word(16) != uint16(h) || p.word(18) != uint16(w/4) || p.word(20) != 4 || p.word(22) != 0 || p.word(24) != uint16(c.Header[7]&15) {
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

// 保留原版解壓與所有外層控制流，僅替換一個事件區間內的實際像素搬移。
func (p *playerRenderOwner) imageTransfer(ea uint32) {
	var d *ownedDriver
	for i := len(p.Pending) - 1; i >= 0; i-- {
		if v := p.Pending[i].Owned; v != nil && v.Kind == "image" {
			d = v
			break
		}
	}
	if d == nil || d.Fallback {
		return
	}
	o := p.Oracle
	r := o.Regs()
	s := o.PresentationVideoState()
	mask := s[4] & 15
	if !p.guard() || mask == 0 || mask&(mask-1) != 0 || r.ES < 0xa000 || uint32(r.ES-0xa000)*16 != d.Page || r.DI >= 16000 {
		p.fallbackImage(d)
		return
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
			return
		}
	}
	plane := bits.TrailingZeros8(mask)
	x, y := int(r.DI%80)*4+plane, int(r.DI/80)
	if n < 1 || x < d.X || y < d.Y || x+(n-1)*4 >= d.X+d.W || y >= d.Y+d.H || uint32(r.SI)+uint32(n) > 65536 || uint32(r.DS)*16+uint32(r.SI)+uint32(n) > 0xa0000 {
		p.fallbackImage(d)
		return
	}
	data := o.Bytes(oracle.Addr{Seg: r.DS, Off: r.SI}, n)
	opaque := 0
	for i, v := range data {
		src := (y-d.Y)*d.W + x + i*4 - d.X
		if v != d.Asset.Index[src] {
			p.fallbackImage(d)
			return
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
	if o.PresentationWorkBudget(steps+1) != steps+1 {
		p.Counters["image_budget_fallback"]++
		p.fallbackImage(d)
		return
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
}
