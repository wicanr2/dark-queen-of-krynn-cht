// 已接管命令跳過原版像素迴圈；只提交選定的中文、HD 或原版畫面。
// 已列 primitive 的來源與界線見規格 005，完整 TLB 命令接管仍另列。
package main

import (
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"image"
	"os"
	"path/filepath"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/wicanr2/dosgolem/oracle"
)

type renderPrimitive struct {
	Name    string `json:"name"`
	Kind    string `json:"kind"`
	Segment uint16 `json:"segment"`
	Offset  uint16 `json:"offset"`
	Prefix  string `json:"prefix"`
}

type renderTransaction struct {
	Return     paintReturn
	Origin     oracle.Addr
	Step       uint64
	Image      *renderImageSource
	Owned      *ownedDriver
	Kind       string
	TextCopies []*ownedPrint
}

type renderImageSource struct {
	Command sourceTileCommand
	Bound   bool
}

type playerRenderOwner struct {
	Oracle       *oracle.Oracle
	Pending      []renderTransaction
	ShadowRGB    []byte
	Front, Back  *ebiten.Image
	Text         *playerTextOwner
	Scene        renderScene
	HD           playerHDRenderer
	Backend      sceneBackend
	Counters     map[string]uint64
	Assets       map[string]*sceneAsset
	LayerKey     string
	Rects        []sceneRect
	PictureText  *pictureTextLayer
	PictureRects []sceneRect
	PictureBoxes [][4]int
	PictureKey   string
}

func init() { playerRenderLoader = loadPlayerRenderOwner }

func loadPlayerRenderOwner(o *oracle.Oracle, profile string, hd playerHDRenderer) playerFrameRenderer {
	raw, err := os.ReadFile(filepath.Join(profile, "render-hooks.json"))
	must(err)
	var bindings struct {
		Version              int
		ExecutableSHA256     string
		Hooks                []renderPrimitive
		NativeSteps          []renderPrimitive
		ImageSource          renderPrimitive
		TextGlyph            renderPrimitive
		ImagePosition        renderPrimitive
		ImagePositionCallers []oracle.Addr
	}
	must(json.Unmarshal(raw, &bindings))
	if bindings.Version != 2 || bindings.ExecutableSHA256 != "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58" || len(bindings.Hooks) != 36 || len(bindings.NativeSteps) != 65 {
		panic("繪圖掛勾資料與原版版本不符")
	}
	owner := &playerRenderOwner{Oracle: o, ShadowRGB: make([]byte, 320*200*3),
		Front: ebiten.NewImage(960, 600), Back: ebiten.NewImage(960, 600), HD: hd, Counters: map[string]uint64{}, Assets: map[string]*sceneAsset{}}
	seen := map[oracle.Addr]bool{}
	// 先完整驗證，避免掛上半份邊界後才發現版本失配。
	for _, hook := range append(append([]renderPrimitive(nil), bindings.Hooks...), bindings.NativeSteps...) {
		entry := oracle.Addr{Seg: hook.Segment, Off: hook.Offset}
		want, err := hex.DecodeString(hook.Prefix)
		must(err)
		if hook.Name == "" || hook.Kind == "" || len(want) != 8 || seen[entry] || hex.EncodeToString(o.Bytes(entry, 8)) != hook.Prefix {
			panic(fmt.Sprintf("繪圖入口失配：%s %04X:%04X", hook.Name, entry.Seg, entry.Off))
		}
		seen[entry] = true
	}
	imageSource := oracle.Addr{Seg: bindings.ImageSource.Segment, Off: bindings.ImageSource.Offset}
	if imageSource != (oracle.Addr{Seg: 0x162e, Off: 0x229e}) || len(bindings.ImageSource.Prefix) != 16 ||
		hex.EncodeToString(o.Bytes(imageSource, 8)) != bindings.ImageSource.Prefix {
		panic("影像來源掛勾失配")
	}
	textGlyph := oracle.Addr{Seg: bindings.TextGlyph.Segment, Off: bindings.TextGlyph.Offset}
	if textGlyph != (oracle.Addr{Seg: 0x13c7, Off: 0xcb6}) || len(bindings.TextGlyph.Prefix) != 16 ||
		hex.EncodeToString(o.Bytes(textGlyph, 8)) != bindings.TextGlyph.Prefix {
		panic("字形來源掛勾失配")
	}
	position := oracle.Addr{Seg: bindings.ImagePosition.Segment, Off: bindings.ImagePosition.Offset}
	if position != (oracle.Addr{Seg: 0x13c7, Off: 0x178b}) || len(bindings.ImagePosition.Prefix) != 16 ||
		hex.EncodeToString(o.Bytes(position, 8)) != bindings.ImagePosition.Prefix || len(bindings.ImagePositionCallers) != 10 {
		panic("影像目的頁掛勾失配")
	}
	callers := map[oracle.Addr]bool{}
	for _, caller := range bindings.ImagePositionCallers {
		if caller.Seg != 0x162e || callers[caller] {
			panic("影像目的頁呼叫者失配")
		}
		callers[caller] = true
	}
	o.OnCall(imageSource, func(_ *oracle.Oracle) {
		r := o.Regs()
		if r.AX|r.DX == 0 {
			return
		}
		var command sourceTileCommand
		copy(command.Header[:], o.Bytes(oracle.Addr{Seg: r.SS, Off: r.BP - 18}, 8))
		command.Source = oracle.Addr{Seg: r.DX, Off: r.AX}
		command.Y = int(int16(o.Word(oracle.Addr{Seg: r.SS, Off: r.BP + 6}))) - int(int16(binary.LittleEndian.Uint16(command.Header[2:4])))
		command.X = int(int16(o.Word(oracle.Addr{Seg: r.SS, Off: r.BP + 8}))) - int(int16(binary.LittleEndian.Uint16(command.Header[4:6])))
		// header 已取得；實際目的頁須等座標函式完成才能綁定。
		for i := len(owner.Pending) - 1; i >= 0; i-- {
			if owner.Pending[i].Origin == (oracle.Addr{Seg: 0x162e, Off: 0x226c}) {
				owner.Pending[i].Image = &renderImageSource{Command: command}
				break
			}
		}
	})
	returns := map[oracle.Addr]bool{}
	for _, hook := range bindings.Hooks {
		owner.observeTransaction(oracle.Addr{Seg: hook.Segment, Off: hook.Offset}, hook.Kind, returns)
	}
	owner.installOwnedDrivers(bindings.NativeSteps)
	owner.Text = loadPlayerTextOwner(o, profile, textGlyph)
	owner.loadPictureText(profile)
	return owner
}

func (owner *playerRenderOwner) observeTransaction(entry oracle.Addr, kind string, returns map[oracle.Addr]bool) {
	o := owner.Oracle
	o.OnCall(entry, func(_ *oracle.Oracle) {
		r := o.Regs()
		mark := paintReturn{o.Caller(), r.SS, r.SP + 4}
		for _, pending := range owner.Pending {
			if pending.Origin == entry && pending.Return == mark {
				owner.Counters["transaction_entry_revisit"]++
				return
			}
		}
		if !renderTransactionTouchesVideo(o, entry.Linear()+0xef00) {
			owner.Counters["nonvideo_copy"]++
			return
		}
		if len(owner.Pending) >= 256 {
			panic("繪圖交易超過有界容量，停止提交半成品")
		}
		target := mark.Addr
		var textCopies []*ownedPrint
		if owner.Text != nil && !owner.inReadback() {
			textCopies = owner.Text.copyTransaction(entry.Linear() + 0xef00)
		}
		owner.Pending = append(owner.Pending, renderTransaction{
			Return: mark, Origin: entry, Step: o.Steps(), Kind: kind, TextCopies: textCopies})
		if returns[target] {
			return
		}
		returns[target] = true
		o.OnCall(target, func(_ *oracle.Oracle) {
			r := o.Regs()
			for i := len(owner.Pending) - 1; i >= 0; i-- {
				p := owner.Pending[i].Return
				if p.Addr == target && p.SS == r.SS && p.SP == r.SP {
					owner.finishDriver(owner.Pending[i].Owned)
					if owner.Text != nil {
						owner.Text.finishCopies(owner.Pending[i].TextCopies)
					}
					// 同一返回點可被不同呼叫重用，以實際堆疊身分配對。
					owner.Pending = append(owner.Pending[:i], owner.Pending[i+1:]...)
					return
				}
			}
		})
	})
}

// 本作已證實的 Mode X 頁面契約；不更改 CRTC 或借換頁來讀隱藏頁。
func nativePageLayout(o *oracle.Oracle) bool {
	v := o.VideoLayoutState()
	return v.Mode == 0x13 && v.Unchained && v.Pitch == 80 && v.LineCompare >= 400
}

func nativeRenderPage(o *oracle.Oracle) (uint32, bool) {
	if !nativePageLayout(o) {
		return 0, false
	}
	segment := o.Word(oracle.Addr{Seg: o.Regs().DS, Off: 0xca33})
	if segment < 0xa000 || segment > 0xac00 || (segment-0xa000)%0x400 != 0 {
		return 0, false
	}
	return uint32(segment-0xa000) * 16, true
}

func nativeVisiblePage(o *oracle.Oracle) (uint32, bool) {
	v := o.VideoLayoutState()
	return v.DisplayStart, nativePageLayout(o) && v.DisplayStart <= 0xc000 && v.DisplayStart%0x4000 == 0
}

func nativeTextRegion(o *oracle.Oracle, page uint32, w listWord) []byte {
	if !nativePageLayout(o) || page > 0xc000 || page%0x4000 != 0 {
		return nil
	}
	region := make([]byte, w.Width*8)
	for y := 0; y < 8; y++ {
		for x := 0; x < w.Width; x++ {
			xx := w.X + x
			off := page + uint32((w.Y+y)*80+(xx>>2))
			if owner := renderOwners[o]; owner != nil {
				region[y*w.Width+x] = owner.indexAt(page, (w.Y+y)*320+xx)
			} else {
				region[y*w.Width+x] = o.EGAPlane(xx & 3)[off]
			}
		}
	}
	return region
}

func (p *playerRenderOwner) Busy() bool {
	if len(p.Pending) != 0 {
		return true
	}
	if p.Text != nil {
		for _, run := range p.Text.Runs {
			if run.Valid {
				return true
			}
		}
	}
	return false
}

func (p *playerRenderOwner) Diagnostics() any {
	pending := make([]map[string]any, 0, len(p.Pending))
	for _, v := range p.Pending {
		pending = append(pending, map[string]any{"origin": v.Origin, "return": v.Return, "kind": v.Kind, "step": v.Step})
	}
	result := map[string]any{"pending": pending, "registers": p.Oracle.Regs()}
	if p.Text != nil {
		result["text_commands"] = p.Text.Counters
		result["text_unclaimed"] = p.Text.Unmatched
		var words []map[string]any
		for _, w := range p.Text.Words {
			words = append(words, map[string]any{"source": w.Source, "text": w.Text, "word": w.Word, "page": w.Page})
		}
		result["text_words"] = words
	}
	result["native_pixel_writes"] = p.Counters["native_writes"]
	result["image_native_fallback"] = p.Counters["image_native_fallback"]
	return result
}

func (p *playerRenderOwner) Source(g *liveGame) (int, int, []byte) {
	if !p.Busy() {
		page, ok := nativeVisiblePage(p.Oracle)
		if !ok {
			p.releaseScene()
			p.PictureRects, p.PictureBoxes, p.PictureKey = nil, nil, ""
			// 啟動／模式交界由自有畫布留黑，不讀取原版整張 RGB 畫面。
			clear(p.ShadowRGB)
			p.Counters["non_canvas_layout_frames"]++
		} else {
			model := p.Scene.page(page, p.Oracle.PresentationPlane)
			pal := p.Oracle.Palette()
			blocked := [64000]bool{}
			textBlend := [64000]bool{}
			if g.translate {
				for _, r := range g.playerTextInkRectangles() {
					for y := r[1]; y < r[3]; y++ {
						for x := r[0]; x < r[2]; x++ {
							textBlend[y*320+x] = true
						}
					}
				}
				p.Text.prune()
				for _, r := range append(g.playerProtectedRectangles(), p.Text.Rectangles(g.playerProtectedRectangles())...) {
					if r[0] < 0 || r[1] < 0 || r[2] > 320 || r[3] > 200 {
						panic("不透明中文框越界")
					}
					for y := r[1]; y < r[3]; y++ {
						for x := r[0]; x < r[2]; x++ {
							blocked[y*320+x] = true
						}
					}
				}
			}
			pictureProtected := [][4]int(nil)
			if g.translate {
				pictureProtected = append(g.playerProtectedRectangles(), p.Text.Rectangles(g.playerProtectedRectangles())...)
				pictureProtected = append(pictureProtected, g.playerTextInkRectangles()...)
			}
			p.preparePictureText(g, page, pictureProtected)
			for _, r := range p.PictureBoxes {
				for y := r[1]; y < r[3]; y++ {
					for x := r[0]; x < r[2]; x++ {
						blocked[y*320+x] = true
					}
				}
			}
			omitted := uint64(0)
			for i, c := range model.Cells {
				d := i * 3
				if blocked[i] || c.Asset != nil && c.Visible && !textBlend[i] {
					clear(p.ShadowRGB[d : d+3])
					omitted++
				} else {
					col := pal[model.Index[i]]
					copy(p.ShadowRGB[d:d+3], col[:])
				}
			}
			p.Counters["base_rgb_omitted_pixels"] += omitted
		}
	}
	return 320, 200, p.ShadowRGB
}

func (p *playerRenderOwner) ComposeText(px []byte, g *liveGame, rgb []byte) {
	if g.translate && !p.Busy() {
		p.Text.Compose(px, g, rgb)
		p.restoreCursor(px, g)
	}
}

// 盾形／劍形游標由原版讀回範圍暫存繪製；落在中文框內的像素會被中文底色與字墨蓋住。
// 暫存寫入保留底層素材而只把Visible設為false，永久寫入會清除Asset，
// 所以Asset仍在且不可見的像素就是暫存寫入的結果（同retainedTextPixel的判準）。
// 所有中文合成之後，把目前游標附近這類像素的原版色號放回最上層，並清除該處高清字墨。
// 底層不是自有素材的像素維持現狀。圖片文字另有同紋理游標合成，閱讀器開啟時原版游標
// 不在操作中，兩者都不處理。
func (p *playerRenderOwner) restoreCursor(px []byte, g *liveGame) {
	if g.reader != nil && g.reader.Mode != "" {
		return
	}
	page, ok := nativeVisiblePage(p.Oracle)
	if !ok {
		return
	}
	cx, cy := dqkMouseGamePixel(p.Oracle.Mouse())
	protected := append(g.playerProtectedRectangles(), p.Text.Rectangles(g.playerProtectedRectangles())...)
	protected = append(protected, g.playerTextInkRectangles()...)
	model := p.Scene.page(page, p.Oracle.PresentationPlane)
	pal := p.Oracle.Palette()
	for _, run := range temporaryCursorRuns(model, cx, cy, protected) {
		y := run[0]
		for x := run[1]; x < run[2]; x++ {
			col := pal[model.Index[y*320+x]]
			for yy := 0; yy < 2; yy++ {
				for xx := 0; xx < 2; xx++ {
					at := ((y*2+yy)*640 + x*2 + xx) * 4
					copy(px[at:at+3], col[:])
				}
			}
		}
		g.sharpClear(image.Rect(run[1]*2, y*2, run[2]*2, (y+1)*2))
		p.Counters["cursor_restored_pixels"] += uint64(run[2] - run[1])
	}
}

// temporaryCursorRuns 回游標（cx,cy）±8像素內、位於中文框且屬暫存寫入的連續像素 {y, x0, x1}。
func temporaryCursorRuns(model *scenePage, cx, cy int, protected [][4]int) [][3]int {
	x0, y0, x1, y1 := max(0, cx-8), max(0, cy-8), min(320, cx+8), min(200, cy+8)
	cursor := func(x, y int) bool {
		c := model.Cells[y*320+x]
		if c.Asset == nil || c.Visible {
			return false
		}
		for _, r := range protected {
			if x >= r[0] && x < r[2] && y >= r[1] && y < r[3] {
				return true
			}
		}
		return false
	}
	var runs [][3]int
	for y := y0; y < y1; y++ {
		for x := x0; x < x1; {
			if !cursor(x, y) {
				x++
				continue
			}
			start := x
			for x < x1 && cursor(x, y) {
				x++
			}
			runs = append(runs, [3]int{y, start, x})
		}
	}
	return runs
}

func (p *playerRenderOwner) Present(screen *ebiten.Image, g *liveGame, rgb []byte, held bool) {
	scale := g.playerCanvasScale()
	if p.Front.Bounds().Dx() != 320*scale {
		front, back := ebiten.NewImage(320*scale, 200*scale), ebiten.NewImage(320*scale, 200*scale)
		op := &ebiten.DrawImageOptions{}
		factor := float64(320*scale) / float64(p.Front.Bounds().Dx())
		op.GeoM.Scale(factor, factor)
		front.DrawImage(p.Front, op)
		p.Front.Dispose()
		p.Back.Dispose()
		p.Front, p.Back = front, back
	}
	if !held && !p.Busy() {
		p.Back.Clear()
		op := &ebiten.DrawImageOptions{}
		op.GeoM.Scale(float64(scale)/2, float64(scale)/2)
		p.Back.DrawImage(g.texture, op)
		if page, ok := nativeVisiblePage(p.Oracle); ok {
			protected := [][4]int(nil)
			if g.translate {
				protected = append(g.playerProtectedRectangles(), p.Text.Rectangles(g.playerProtectedRectangles())...)
				protected = append(protected, g.playerTextInkRectangles()...)
				protected = append(protected, p.PictureBoxes...)
			}
			model := p.Scene.page(page, p.Oracle.PresentationPlane)
			pal := p.Oracle.Palette()
			key := fmt.Sprintf("%d:%x:%t:%x:%v", p.Scene.Revision, page, g.player.HDEnabled && g.translate, pal, protected)
			if key != p.LayerKey {
				p.Rects = model.rectangles(g.player.HDEnabled && g.translate, pal, protected)
				p.LayerKey = key
				p.Counters["scene_batch_builds"]++
			}
			builds, draws := p.Backend.submit(p.Back, p.Rects, pal)
			pictureBuilds, pictureDraws := p.Backend.submit(p.Back, p.PictureRects, pal)
			builds += pictureBuilds
			draws += pictureDraws
			p.Counters["scene_texture_builds"] += uint64(builds)
			p.Counters["scene_rectangle_draws"] += uint64(draws)
			p.Counters["scene_submissions"]++
		}
		if g.player.SharpText != nil {
			g.player.SharpText.Draw(p.Back)
		}
		p.Front, p.Back = p.Back, p.Front
	}
	// 視窗永遠只接完整前緩衝，保留期間不重繪原圖或重算 HD。
	screen.DrawImage(p.Front, nil)
}
