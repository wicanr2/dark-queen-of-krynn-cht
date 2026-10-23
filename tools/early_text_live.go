// DRAFT 研究原型：角色選單往返與正常開場劇情，不供正式遊玩。
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"image"
	"image/png"
	"os"
	"path/filepath"
	"runtime"
	"runtime/pprof"
	"sort"
	"strings"
	"unicode/utf8"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/hajimehoshi/ebiten/v2/inpututil"
	"github.com/wicanr2/dosgolem/oracle"
)

type liveEvent struct {
	Step              uint64 `json:"step"`
	X, Y              int
	Color             uint16
	Source, Key, Text string
}
type liveFrame struct {
	Step          uint64 `json:"step"`
	Events        int    `json:"events"`
	File, SHA256  string
	Held          bool          `json:"held"`
	Active        int           `json:"active"`
	CampPalette   *[16][3]uint8 `json:"camp_palette,omitempty"`
	ColdUIWords   []listWord    `json:"cold_ui_words,omitempty"`
	ColdUIEvents  int           `json:"cold_ui_events,omitempty"`
	ColdUIPending bool          `json:"cold_ui_pending,omitempty"`
}
type paintReturn struct {
	Addr   oracle.Addr
	SS, SP uint16
}
type glyphSet struct {
	Size, Height int
	Glyphs       map[string][]byte
}
type storyPage struct {
	Step                   uint64 `json:"step"`
	Key, Source, Text      string
	Box                    [4]int
	Foreground, Background byte
	Lines                  []string
	Clear                  byte
	Components             []string
	ComponentColors        []int `json:"ComponentColors,omitempty"`
}
type liveGame struct {
	o             *oracle.Oracle
	out           string
	translate     bool
	fine          bool
	catalog       map[string]string
	glyphs        glyphSet
	events        []liveEvent
	active        map[[2]int]liveEvent
	frames        []liveFrame
	texture       *ebiten.Image
	textureHash   string
	uploads       int
	finished      bool
	lifecycle     bool
	transition    bool
	renderDepth   int
	paints        []paintReturn
	lastPixels    []byte
	boundaries    []map[string]any
	checkpoints   []map[string]any
	story         bool
	storySequence bool
	page          *storyPage
	pages         []storyPage
	sources       map[string]string
	interactive   bool
	inputs        []map[string]any
	escapePending bool
	escapeStep    uint64
	camp          bool
	campPositions map[[2]int]string
	list          *listState
	reader        *journalReader
	cold          *coldLoad
}

// 研究限定的冷讀重播。角色管理沿用 20px，讀回後才切換既有 16px 列表原型。
type coldLoad struct {
	Actions           []listAction
	QuizStep, Handoff uint64
	QuizSHA256        string
	SaveFiles         map[string]struct {
		Bytes           int
		SHA256          string
		ModTimeUnixNano int64
	}
	action                      int
	sent, ready                 bool
	frames                      []liveFrame
	events                      []liveEvent
	checkpoints                 []map[string]any
	boundaries                  []map[string]any
	catalog                     map[string]string
	glyphs                      glyphSet
	inputs, request, sources    string
	bridgeSHA                   string
	fineWindowsPath             string
	readerCatalog, readerImages string
	ui                          *coldPromptUI
}

func (g *liveGame) updateCold() error {
	c, o := g.cold, g.o
	if o.Steps() == c.Handoff {
		if g.transition || g.renderDepth != 0 || len(g.paints) != 0 {
			panic("冷讀交接仍有未完成角色選單交易")
		}
		if c.ui != nil && (c.ui.held() || len(c.ui.Words) > 0 || len(c.ui.Await) > 0 || c.ui.Wrapper != nil) {
			panic("冷讀提示交接尚未完成")
		}
		bridge := filepath.Join(g.out, "cold-handoff.state")
		must(o.SaveStateFile(bridge))
		data, err := os.ReadFile(bridge)
		must(err)
		c.bridgeSHA = digest(data)
		c.frames, c.events, c.checkpoints, c.boundaries = g.frames, g.events, g.checkpoints, g.boundaries
		g.frames, g.events, g.checkpoints, g.boundaries = nil, nil, nil, nil
		g.active = map[[2]int]liveEvent{}
		g.lifecycle = false
		g.catalog, g.glyphs = c.catalog, c.glyphs
		g.list = &listState{}
		g.installList(c.inputs, c.request, c.sources)
		if c.readerCatalog != "" {
			g.installReader(c.readerCatalog, c.readerImages)
		}
		if g.list.request.StateSHA != c.bridgeSHA {
			panic("冷讀交接與獨立原版快照不符")
		}
		if c.fineWindowsPath != "" {
			raw, err := os.ReadFile(c.fineWindowsPath)
			must(err)
			var windows [][2]uint64
			must(json.Unmarshal(raw, &windows))
			last := c.Handoff
			for _, w := range windows {
				if w[0] < last || w[1] <= w[0] || w[1] > g.list.request.Actions[len(g.list.request.Actions)-1].End {
					panic("冷讀細驗區間不符")
				}
				last = w[1]
			}
			g.list.config.FineWindows = append(g.list.config.FineWindows, windows...)
		}
		c.ready = true
		return g.updateList()
	}
	if c.action >= len(c.Actions) {
		panic("冷讀動作提前結束")
	}
	a := c.Actions[c.action]
	step := o.Steps()
	if !c.sent && step == a.At {
		if a.Kind == "text" {
			must(o.TypeKeys(a.Key))
		} else {
			must(o.SendKeys(a.Key))
		}
		c.sent = true
	}
	next := a.At
	if c.sent {
		next = a.End
	}
	batch := uint64(500000)
	if g.fine {
		for _, a := range c.Actions {
			at := a.At
			if at < 239000000 {
				continue
			}
			if step >= at && step < at+1000000 {
				batch = 2000
			}
		}
	}
	if next-step < batch {
		batch = next - step
	}
	if batch == 0 {
		panic("冷讀步數未前進")
	}
	must(o.Run(batch))
	if o.Steps() == a.End {
		if a.End == c.QuizStep && digest(o.Indexed()) != c.QuizSHA256 {
			panic("讀檔查驗頁不符，不輸入答案")
		}
		g.capture()
		g.checkpoints[len(g.checkpoints)-1]["label"] = a.Label
		c.action++
		c.sent = false
	}
	return nil
}

func must(err error) {
	if err != nil {
		panic(err)
	}
}
func digest(b []byte) string { h := sha256.Sum256(b); return hex.EncodeToString(h[:]) }
func readLiveCatalog(path string) map[string]string {
	data, err := os.ReadFile(path)
	must(err)
	if !utf8.Valid(data) || strings.ContainsRune(string(data), '\r') {
		panic("TSV 必須是 UTF-8 且不含 CR")
	}
	rows := strings.Split(strings.TrimSuffix(string(data), "\n"), "\n")
	if len(rows) < 2 || rows[0] != "key\ttext" {
		panic("TSV 表頭或內容不符")
	}
	result := map[string]string{}
	for _, line := range rows[1:] {
		// 本作 catalog 採 QUOTE_NONE；雙引號是文字，不套用 CSV 引號語法。
		row := strings.Split(line, "\t")
		if len(row) != 2 || row[0] == "" || row[1] == "" {
			panic("TSV 欄數或空值不符")
		}
		if _, ok := result[row[0]]; ok {
			panic("TSV 重複 key")
		}
		result[row[0]] = row[1]
	}
	return result
}

func (g *liveGame) installShortText() {
	o := g.o
	// 控制組同樣觀測事件；translate 只影響 Draw 的呈現資料。
	o.OnCall(oracle.Addr{Seg: 0x1212, Off: 0x03a0}, func(_ *oracle.Oracle) {
		r := o.Regs()
		word := func(off uint16) uint16 { return o.Word(oracle.Addr{Seg: r.SS, Off: r.SP + off}) }
		seg, off := word(12), word(10)
		source := []byte{}
		for i := 0; i < 255; i++ {
			c := o.Byte(oracle.Addr{Seg: seg, Off: off + uint16(i)})
			if c == 0 {
				break
			}
			if c < 32 || c > 126 {
				return
			}
			source = append(source, c)
		}
		key := digest(source)
		if (g.interactive || g.cold != nil) && g.escapePending && string(source) == "%s" && word(4) == 8008 && word(6) == 8068 {
			g.active = map[[2]int]liveEvent{}
			g.transition = false
			g.escapePending = false
			g.boundaries = append(g.boundaries, map[string]any{"kind": "begin-adventure-native-hud", "step": o.Steps(), "selection_step": g.escapeStep, "active": 0})
		}
		text, ok := g.catalog[key]
		if !ok {
			return
		}
		e := liveEvent{Step: o.Steps(), X: int(word(6)), Y: int(word(4)), Color: word(8), Source: string(source), Key: key, Text: text}
		if g.camp && (o.Caller() != (oracle.Addr{Seg: 0x0ceb, Off: 0x01be}) || g.campPositions[[2]int{e.X, e.Y}] != key) {
			return
		}
		g.events = append(g.events, e)
		g.active[[2]int{e.X, e.Y}] = e
	})
}
func (g *liveGame) limit() uint64 {
	if g.cold != nil && !g.cold.ready {
		return g.cold.Handoff + 1
	}
	if g.list != nil {
		return g.list.request.Actions[len(g.list.request.Actions)-1].End
	}
	if g.camp {
		return 715000000
	}
	if g.story {
		if g.storySequence {
			return 575000000
		}
		return 375000000
	}
	if g.lifecycle {
		return 290000000
	}
	return 246000000
}
func (g *liveGame) capture() {
	ram := make([]byte, 1<<20)
	for i := range ram {
		ram[i] = g.o.Byte(oracle.Addr{Seg: uint16(i >> 4), Off: uint16(i & 15)})
	}
	g.checkpoints = append(g.checkpoints, map[string]any{"step": g.o.Steps(), "regs": g.o.Regs(), "ram_sha256": digest(ram), "indexed_sha256": digest(g.o.Indexed()), "palette": g.o.Palette(), "keys_consumed": g.o.KeysConsumed(), "file_writes": g.o.Wrote()})
}
func (g *liveGame) installLifecycle() {
	o := g.o
	for _, p := range []struct {
		a     oracle.Addr
		bytes string
	}{
		{oracle.Addr{Seg: 0x0ceb, Off: 0x008e}, "558bec83ec085657c45e0626f6471c20"},
		{oracle.Addr{Seg: 0x1bb6, Off: 0x151f}, "558bec83ec0456803ec2da00751833c0"},
		{oracle.Addr{Seg: 0x1bb6, Off: 0x1585}, "cb558bec56803ecfda00750e1eb811a2"},
		{oracle.Addr{Seg: 0x1bb6, Off: 0x17b8}, "cb558bec83ec085657168d46fe50168d"},
	} {
		if got := hex.EncodeToString(o.Bytes(p.a, len(p.bytes)/2)); got != p.bytes {
			panic(fmt.Sprintf("選單生命週期 %04X:%04X bytes 不符：%s", p.a.Seg, p.a.Off, got))
		}
	}
	log := func(kind string) {
		g.boundaries = append(g.boundaries, map[string]any{"step": o.Steps(), "kind": kind, "active": len(g.active), "render_depth": g.renderDepth, "paint_depth": len(g.paints), "transition": g.transition})
	}
	o.OnCall(oracle.Addr{Seg: 0x1bb6, Off: 0x17b8}, func(_ *oracle.Oracle) {
		if !g.lifecycle {
			return
		}
		if o.Regs().AX != 0xffff {
			if (g.interactive || g.camp || g.cold != nil) && len(g.active) == 0 {
				return
			}
			if (g.interactive || g.cold != nil) && o.Regs().AX == 10 {
				g.escapePending = true
				g.escapeStep = o.Steps()
			}
			g.transition = true
			log("selection-return")
		}
	})
	o.OnCall(oracle.Addr{Seg: 0x1bb6, Off: 0x151f}, func(_ *oracle.Oracle) {
		if !g.lifecycle {
			return
		}
		if g.transition {
			g.active = map[[2]int]liveEvent{}
		}
		g.renderDepth++
		if g.transition {
			log("transition-render-entry")
		}
	})
	o.OnCall(oracle.Addr{Seg: 0x1bb6, Off: 0x1585}, func(_ *oracle.Oracle) {
		if !g.lifecycle {
			return
		}
		g.renderDepth--
		if g.renderDepth < 0 {
			panic("繪製邊界不成對")
		}
		if g.transition {
			g.transition = false
			g.escapePending = false
			log("transition-render-return")
		}
	})
	registered := map[oracle.Addr]bool{}
	o.OnCall(oracle.Addr{Seg: 0x0ceb, Off: 0x008e}, func(_ *oracle.Oracle) {
		if !g.lifecycle {
			return
		}
		if o.StackWord(4) != 1 {
			return
		}
		r := o.Regs()
		target := o.Caller()
		g.paints = append(g.paints, paintReturn{target, r.SS, r.SP + 4})
		log("button-paint-entry")
		if registered[target] {
			return
		}
		registered[target] = true
		o.OnCall(target, func(_ *oracle.Oracle) {
			if len(g.paints) == 0 {
				return
			}
			last := g.paints[len(g.paints)-1]
			r := o.Regs()
			if last.Addr != target || last.SS != r.SS || last.SP != r.SP {
				return
			}
			g.paints = g.paints[:len(g.paints)-1]
			log("button-paint-return")
		})
	})
}
func (g *liveGame) Update() error {
	if g.finished {
		return ebiten.Termination
	}
	if g.tickReader() {
		return nil
	}
	if g.interactive {
		if _, err := os.Stat(filepath.Join(g.out, "stop")); err == nil {
			g.capture()
			g.finished = true
			return ebiten.Termination
		}
		for _, ch := range ebiten.AppendInputChars(nil) {
			if ch < 32 || ch > 126 {
				continue
			}
			value := string(ch)
			must(g.o.TypeKeys(value))
			g.inputs = append(g.inputs, map[string]any{"step": g.o.Steps(), "kind": "text", "value": value})
		}
		for key, name := range map[ebiten.Key]string{ebiten.KeyEnter: "Return", ebiten.KeyNumpadEnter: "Return", ebiten.KeyEscape: "Esc", ebiten.KeyBackspace: "Backspace", ebiten.KeyTab: "Tab", ebiten.KeyArrowUp: "Up", ebiten.KeyArrowDown: "Down", ebiten.KeyArrowLeft: "Left", ebiten.KeyArrowRight: "Right"} {
			if inpututil.IsKeyJustPressed(key) {
				must(g.o.SendKeys(name))
				g.inputs = append(g.inputs, map[string]any{"step": g.o.Steps(), "kind": "named", "value": name})
			}
		}
		must(g.o.Run(500000))
		return nil
	}
	if g.cold != nil && !g.cold.ready {
		return g.updateCold()
	}
	if g.o.Steps() >= g.limit() {
		return nil
	}
	if g.list != nil {
		if g.reader != nil {
			g.reader.WaitDraw = true
		}
		return g.updateList()
	}
	if g.camp {
		step := g.o.Steps()
		for i, key := range "spells\n" {
			if step == 330000000+uint64(i)*500000 {
				if key == '\n' {
					must(g.o.SendKeys("Return"))
				} else {
					must(g.o.TypeKeys(string(key)))
				}
			}
		}
		if step >= 375000000 && step < 575000000 && (step-375000000)%25000000 == 0 {
			must(g.o.SendKeys("Return"))
		}
		for _, action := range []struct {
			at  uint64
			key string
		}{{576000000, "l"}, {601000000, "Return"}, {616000000, "i"}, {641000000, "Return"}, {666000000, "s"}, {691000000, "j"}} {
			if step == action.at {
				if action.key == "Return" {
					must(g.o.SendKeys(action.key))
				} else {
					must(g.o.TypeKeys(action.key))
				}
			}
		}
		batch := uint64(500000)
		if g.fine && ((step >= 641000000 && step < 642000000) || (step >= 666000000 && step < 667000000) || (step >= 691000000 && step < 692000000)) {
			batch = 2000
		}
		must(g.o.Run(batch))
		end := g.o.Steps()
		if end == 375000000 || (end > 375000000 && end <= 575000000 && (end-375000000)%25000000 == 0) || end == 600000000 || end == 615000000 || end == 640000000 || end == 665000000 || end == 690000000 || end == 715000000 {
			g.capture()
		}
		return nil
	}
	if g.story {
		step := g.o.Steps()
		if g.storySequence && step >= 375000000 && step < 575000000 && (step-375000000)%25000000 == 0 {
			must(g.o.SendKeys("Return"))
		}
		for i, key := range "spells\n" {
			if step == 330000000+uint64(i)*500000 {
				if key == '\n' {
					must(g.o.SendKeys("Return"))
				} else {
					must(g.o.TypeKeys(string(key)))
				}
			}
		}
		batch := uint64(100000)
		if g.fine && step >= 334000000 && step < 335000000 {
			batch = 2000
		}
		must(g.o.Run(batch))
		if g.o.Steps() == 375000000 || (g.storySequence && g.o.Steps() > 375000000 && (g.o.Steps()-375000000)%25000000 == 0) {
			g.capture()
		}
		return nil
	}
	if g.o.Steps() == 241000000 {
		must(g.o.TypeKeys("p"))
	}
	if g.lifecycle && g.o.Steps() == 260000000 {
		must(g.o.TypeKeys("l"))
	}
	if g.lifecycle && g.o.Steps() == 275000000 {
		must(g.o.TypeKeys("e"))
	}
	batch := uint64(100000)
	step := g.o.Steps()
	if g.fine && ((step >= 241000000 && step < 242000000) || (g.lifecycle && ((step >= 260000000 && step < 261000000) || (step >= 275000000 && step < 276000000)))) {
		batch = 2000
	}
	must(g.o.Run(batch))
	if g.lifecycle && (g.o.Steps() == 246000000 || g.o.Steps() == 275000000 || g.o.Steps() == 290000000) {
		g.capture()
	}
	return nil
}
func (g *liveGame) Layout(_, _ int) (int, int) { return 640, 400 }
func (g *liveGame) Draw(screen *ebiten.Image) {
	w, h, rgb := g.o.ScreenRGB()
	if w != 320 || h != 200 {
		panic("未知畫面尺寸")
	}
	px := make([]byte, 640*400*4)
	for y := 0; y < 400; y++ {
		for x := 0; x < 640; x++ {
			s, d := ((y/2)*320+x/2)*3, (y*640+x)*4
			copy(px[d:d+3], rgb[s:s+3])
			px[d+3] = 255
		}
	}
	if g.translate {
		// 排序固定覆繪順序；來源英文字的遮罩與中文字在同一張貼圖內完成。
		var keys [][2]int
		for k := range g.active {
			keys = append(keys, k)
		}
		sort.Slice(keys, func(i, j int) bool {
			if keys[i][1] != keys[j][1] {
				return keys[i][1] < keys[j][1]
			}
			return keys[i][0] < keys[j][0]
		})
		pal := g.o.Palette()
		for _, k := range keys {
			e := g.active[k]
			x, y, width := e.X*2, e.Y*2, len(e.Source)*16
			if x < 0 || y < 2 || x+width > 640 || y+22 > 400 {
				panic("原型文字框越界")
			}
			bg, fg := pal[(e.Color>>4)&15], pal[e.Color&15]
			for yy := y; yy < y+16; yy++ {
				for xx := x; xx < x+width; xx++ {
					d := (yy*640 + xx) * 4
					copy(px[d:d+3], bg[:])
				}
			}
			if len([]rune(e.Text))*g.glyphs.Size > width {
				panic("譯文超出安全框")
			}
			for i, ch := range []rune(e.Text) {
				alpha, ok := g.glyphs.Glyphs[string(ch)]
				if !ok || len(alpha) != g.glyphs.Size*g.glyphs.Height {
					panic("字型缺字")
				}
				for yy := 0; yy < g.glyphs.Height; yy++ {
					for xx := 0; xx < g.glyphs.Size; xx++ {
						a := uint32(alpha[yy*g.glyphs.Size+xx])
						if a == 0 {
							continue
						}
						textY := y - 2
						if g.camp {
							if yy >= 16 {
								panic("營地中文字墨超出原文字高")
							}
							textY = y
						}
						d := ((textY+yy)*640 + x + i*g.glyphs.Size + xx) * 4
						for c := 0; c < 3; c++ {
							px[d+c] = byte((uint32(fg[c])*a + uint32(px[d+c])*(255-a) + 127) / 255)
						}
					}
				}
			}
		}
		if g.page != nil {
			p := g.page
			pal := g.o.Palette()
			bg, fg := pal[p.Background], pal[p.Foreground]
			var glyphColors []int
			if len(p.ComponentColors) > 0 {
				if len(p.ComponentColors) != len(p.Components) {
					panic("段落來源與字色數量不符")
				}
				for i, key := range p.Components {
					for range []rune(g.catalog[key]) {
						glyphColors = append(glyphColors, p.ComponentColors[i])
					}
				}
				if len(glyphColors) != len([]rune(p.Text)) {
					panic("段落文字與字色長度不符")
				}
			}
			for y := p.Box[1]; y < p.Box[3]; y++ {
				for x := p.Box[0]; x < p.Box[2]; x++ {
					copy(px[(y*640+x)*4:][:3], bg[:])
				}
			}
			glyphIndex := 0
			for row, line := range p.Lines {
				for col, ch := range []rune(line) {
					if len(glyphColors) > 0 {
						fg = pal[glyphColors[glyphIndex]]
					}
					glyphIndex++
					alpha, ok := g.glyphs.Glyphs[string(ch)]
					if !ok || len(alpha) != g.glyphs.Size*g.glyphs.Height {
						panic("劇情字型缺字")
					}
					for yy := 0; yy < g.glyphs.Height; yy++ {
						for xx := 0; xx < g.glyphs.Size; xx++ {
							a := uint32(alpha[yy*g.glyphs.Size+xx])
							d := ((p.Box[1]+row*g.glyphs.Height+yy)*640 + p.Box[0] + col*g.glyphs.Size + xx) * 4
							for c := 0; c < 3; c++ {
								px[d+c] = byte((uint32(fg[c])*a + uint32(px[d+c])*(255-a) + 127) / 255)
							}
						}
					}
				}
			}
		}
	}
	if g.translate && g.list != nil {
		g.composeList(px)
		g.composeReader(px)
	}
	if g.translate && g.cold != nil && !g.cold.ready && g.cold.ui != nil {
		u := g.cold.ui
		g.composeWords(px, u.snapshot(), u.Catalog, u.Glyphs)
	}
	held := g.lifecycle && (g.transition || g.renderDepth > 0 || len(g.paints) > 0)
	if g.cold != nil && !g.cold.ready && g.cold.ui != nil && g.cold.ui.held() {
		held = true
	}
	if g.list != nil {
		held = g.translate && (len(g.list.paints) > 0 || len(g.list.fills) > 0 || len(g.list.scrolls) > 0 || g.list.clearPending || g.list.awaitPageFlip || len(g.list.menus) > 0 || len(g.list.buttons) > 0 || g.list.headerTransition || g.list.footerTransition || g.list.clockReturn != nil || (g.list.feedback != nil && g.list.feedback.Restoring) || (g.list.serviceNotice != nil && g.list.serviceNotice.Restoring))
	}
	if held {
		if len(g.lastPixels) == 0 {
			panic("尚無完整畫格可保留")
		}
		px = g.lastPixels
	} else {
		g.lastPixels = px
	}
	composedHash := digest(px)
	// 保留或空閒畫格不重複上傳。每次 Draw 仍實際讀回並比對呈現內容。
	if composedHash != g.textureHash {
		g.texture.WritePixels(px)
		g.textureHash = composedHash
		g.uploads++
	}
	screen.DrawImage(g.texture, nil)
	// 擷取 GPU 實際讀回的已提交畫格，逐點確認與原子合成的輸入相同。
	readback := make([]byte, len(px))
	screen.ReadPixels(readback)
	if composedHash != digest(readback) {
		panic("前端提交與合成畫格不同")
	}
	name := fmt.Sprintf("frame-%03d-%09d.png", len(g.frames), g.o.Steps())
	if g.interactive || g.camp || g.list != nil || g.cold != nil {
		name = "frame-" + composedHash + ".png"
	}
	if _, err := os.Stat(filepath.Join(g.out, name)); (!g.interactive && !g.camp && g.list == nil && g.cold == nil) || os.IsNotExist(err) {
		f, err := os.Create(filepath.Join(g.out, name))
		must(err)
		im := &image.RGBA{Pix: readback, Stride: 640 * 4, Rect: image.Rect(0, 0, 640, 400)}
		must(png.Encode(f, im))
		must(f.Close())
	}
	g.frames = append(g.frames, liveFrame{Step: g.o.Steps(), Events: len(g.events), File: name, SHA256: digest(readback), Held: held, Active: len(g.active)})
	if g.cold != nil && !g.cold.ready && g.cold.ui != nil {
		u := g.cold.ui
		f := &g.frames[len(g.frames)-1]
		f.ColdUIWords = u.snapshot()
		f.ColdUIEvents = len(u.Events)
		f.ColdUIPending = u.held()
	}
	if g.list != nil {
		g.list.frames = append(g.list.frames, map[string]any{"step": g.o.Steps(), "list_event_count": len(g.list.events), "words": g.list.snapshot(), "palette": g.o.Palette(), "display_start": g.o.VideoLayoutState().DisplayStart, "render_page": g.list.renderPage, "paragraph": g.page})
		if g.reader != nil {
			g.list.frames[len(g.list.frames)-1]["reader"] = g.reader.Page
			g.reader.WaitDraw = false
		}
	}
	if g.camp {
		pal := g.o.Palette()
		colors := [16][3]uint8{}
		copy(colors[:], pal[:16])
		g.frames[len(g.frames)-1].CampPalette = &colors
	}
	if g.interactive || (g.reader != nil && g.reader.Live) {
		state := map[string]any{"step": g.o.Steps(), "active": len(g.active), "held": held, "inputs": len(g.inputs), "keys_consumed": g.o.KeysConsumed(), "file": name}
		if g.reader != nil {
			r := g.reader
			state["reader_mode"], state["reader_stable"], state["reader_seen"] = r.Mode, g.readerStable(), r.seenIDs()
			state["reader_inputs"] = len(r.UIEvents)
			state["reader_entry"], state["reader_page"] = 0, 0
			if r.Page != nil {
				state["reader_entry"], state["reader_page"] = r.Page.Entry, max(1, r.Page.Number)
			}
		}
		status, err := json.Marshal(state)
		must(err)
		tmp := filepath.Join(g.out, "latest.tmp")
		must(os.WriteFile(tmp, status, 0644))
		must(os.Rename(tmp, filepath.Join(g.out, "latest.json")))
		if g.interactive {
			return
		}
	}
	if len(g.frames)%200 == 0 {
		var mem runtime.MemStats
		runtime.ReadMemStats(&mem)
		current, _ := os.ReadFile("/sys/fs/cgroup/memory.current")
		stats, _ := os.ReadFile("/sys/fs/cgroup/memory.stat")
		row, err := json.Marshal(map[string]any{"frames": len(g.frames), "step": g.o.Steps(), "heap_alloc": mem.HeapAlloc, "heap_sys": mem.HeapSys, "sys": mem.Sys, "cgroup_current": string(current), "cgroup_stat": string(stats)})
		must(err)
		log, err := os.OpenFile(filepath.Join(g.out, "memory-samples.jsonl"), os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
		must(err)
		_, err = log.Write(append(row, '\n'))
		must(err)
		must(log.Close())
		if len(g.frames) == 600 {
			profile, err := os.Create(filepath.Join(g.out, "heap-600.pprof"))
			must(err)
			must(pprof.WriteHeapProfile(profile))
			must(profile.Close())
		}
	}
	if g.o.Steps() >= g.limit() {
		g.finished = true
	}
}
func main() {
	state := flag.String("state", "", "正常冷啟動的 #239M 快照")
	out := flag.String("out", "", "隔離研究輸出")
	catalogPath := flag.String("catalog", "", "私有原型 TSV")
	glyphPath := flag.String("glyphs", "", "已核對的 20px 原型字模")
	translate := flag.Bool("translate", true, "啟用呈現層原型")
	fine := flag.Bool("fine", false, "每 2,000 道指令提交一幀，觀察逐字建立期間")
	lifecycle := flag.Bool("lifecycle", false, "DRAFT：一般 p/l/e 選單往返及呈現交易")
	story := flag.Bool("story", false, "DRAFT：正常首段劇情的字級原型")
	storySequence := flag.Bool("story-sequence", false, "DRAFT：接續八次一般 Return，觀測七段已匹配文字")
	interactive := flag.Bool("interactive", false, "DRAFT：冷啟動並接受實際視窗鍵盤事件；只翻譯角色選單")
	coldPath := flag.String("cold-load", "", "DRAFT：已核對 J 槽的冷啟動重播請求")
	coldSave := flag.String("cold-save", "", "唯讀的中文 J 槽來源目錄")
	coldRoles := flag.String("cold-role-inputs", "", "已核對的 20px 角色管理輸入目錄")
	coldFine := flag.String("cold-fine-windows", "", "DRAFT：從獨立原版繪製事件衍生的細驗區間")
	coldUIInputs := flag.String("cold-ui-inputs", "", "DRAFT：冷讀來源、槽位與讀取中提示")
	camp := flag.Bool("camp", false, "DRAFT：正常旅店、營地與存檔 J 的底列短標籤")
	campInputs := flag.String("camp-inputs", "", "營地原型的已觀測來源與座標索引")
	listMode := flag.Bool("list", false, "DRAFT：依原版標題辨識 Shield 列表並處理捲動及退出")
	listInputs := flag.String("list-inputs", "", "列表來源及原版事件索引")
	listRequest := flag.String("list-request", "", "一般按鍵及檢查點請求")
	sourceCatalog := flag.String("source-catalog", "", "劇情原文 TSV，與現行譯文依 key 核對")
	readerCatalog := flag.String("reader-catalog", "", "DRAFT：已校讀的單頁手札 TSV")
	readerIllustrations := flag.String("reader-illustrations", "", "DRAFT：三則重繪圖文清單")
	readerControls := flag.String("reader-controls", "", "DRAFT：獨立前端查閱控制重播")
	readerInteractive := flag.Bool("reader-interactive", false, "DRAFT：接受真正鍵盤的查閱控制")
	readerProbe := flag.Bool("reader-probe", false, "DRAFT：允許明列的手札畫面元件預覽")
	flag.Parse()
	if *coldFine != "" && (*coldPath == "" || !*fine) {
		panic("冷讀細驗區間需要冷讀及 fine 模式")
	}
	if *coldUIInputs != "" && *coldPath == "" {
		panic("冷讀提示需要 MZ 冷讀模式")
	}
	if *readerIllustrations != "" && *readerCatalog == "" {
		panic("圖文清單需要手札 TSV")
	}
	if _, err := os.Stat(*out); !os.IsNotExist(err) {
		panic("輸出必須為全新目錄")
	}
	must(os.MkdirAll(*out, 0755))
	b, err := os.ReadFile("/orig/DQK.EXE")
	must(err)
	if digest(b) != "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58" {
		panic("未知 EXE")
	}
	o, err := oracle.Load("/orig/DQK.EXE", "/orig")
	must(err)
	defer o.Close()
	if *interactive || *coldPath != "" {
		if *state != "" || *story {
			panic("互動原型只支援冷啟動角色選單")
		}
		o.SetCmdLine("SB220 SI7 RB330")
	} else {
		must(o.LoadStateFile(*state))
	}
	o.SetScratch(filepath.Join(*out, "scratch"))
	expectedSteps := uint64(239000000)
	if *interactive || *coldPath != "" {
		expectedSteps = 0
	}
	if *story || *camp {
		expectedSteps = 329000000
	}
	// 列表請求在 installList 核對自己的起始步數，之後另驗快照雜湊。
	if !*listMode && o.Steps() != expectedSteps {
		panic("快照步數不符")
	}
	for i, want := range []byte{0x55, 0x8b, 0xec, 0xff, 0x76, 0x0a, 0x0e, 0xe8, 0x30, 0xff, 0x59} {
		if o.Byte(oracle.Addr{Seg: 0x1212, Off: 0x03a0 + uint16(i)}) != want {
			panic("resident bytes 不符")
		}
	}
	g := &liveGame{o: o, out: *out, translate: *translate, fine: *fine, catalog: map[string]string{}, active: map[[2]int]liveEvent{}}
	g.lifecycle = *lifecycle
	g.interactive = *interactive
	g.camp = *camp
	if *coldPath != "" && (!*listMode || *camp || *story || *interactive || *lifecycle || *coldSave == "" || *coldRoles == "") {
		panic("冷讀原型參數不符")
	}
	if *listMode {
		if *camp || *story || *interactive || *lifecycle {
			panic("列表原型需獨立啟用")
		}
		g.list = &listState{}
	}
	if g.camp && (g.story || *story || g.interactive || !g.lifecycle) {
		panic("營地原型只支援正常快照與生命週期觀測")
	}
	if g.interactive && !g.lifecycle {
		panic("互動原型需要生命週期觀測")
	}
	g.story = *story
	g.storySequence = *storySequence
	if g.storySequence && !g.story {
		panic("連續劇情原型需要 story 模式")
	}
	if g.story && g.lifecycle {
		panic("兩種原型不可同時啟用")
	}
	if g.lifecycle {
		g.installLifecycle()
	}
	b, err = os.ReadFile(*glyphPath)
	must(err)
	must(json.Unmarshal(b, &g.glyphs))
	if ((!g.story && !g.camp && g.list == nil && g.glyphs.Size != 20) || (g.story && g.glyphs.Size != 16 && g.glyphs.Size != 20) || ((g.camp || g.list != nil) && g.glyphs.Size != 16)) || g.glyphs.Height != g.glyphs.Size+4 {
		panic("未批准的字型尺寸")
	}
	g.catalog = readLiveCatalog(*catalogPath)
	if g.storySequence && len(g.catalog) != 7 {
		panic("連續原型需要本輪已匹配的七段子集")
	}
	if !g.story && !g.camp && g.list == nil && len(g.catalog) != 12 {
		panic("角色選單原型需要 12 個標籤")
	}
	if g.camp {
		var input struct {
			Bindings []struct {
				SourceSHA256 string `json:"source_sha256"`
				X, Y         int
			}
		}
		data, err := os.ReadFile(*campInputs)
		must(err)
		must(json.Unmarshal(data, &input))
		g.campPositions = map[[2]int]string{}
		if len(g.catalog) != 10 || len(input.Bindings) != 10 {
			panic("營地原型需要十個已觀測短標籤")
		}
		for _, v := range input.Bindings {
			pos := [2]int{v.X, v.Y}
			if _, ok := g.catalog[v.SourceSHA256]; !ok || v.Y != 189 || g.campPositions[pos] != "" {
				panic("營地來源與座標索引失配")
			}
			g.campPositions[pos] = v.SourceSHA256
		}
	}
	if *coldPath != "" {
		data, err := os.ReadFile(*coldPath)
		must(err)
		c := &coldLoad{catalog: g.catalog, glyphs: g.glyphs, inputs: *listInputs, request: *listRequest, sources: *sourceCatalog, fineWindowsPath: *coldFine, readerCatalog: *readerCatalog, readerImages: *readerIllustrations}
		must(json.Unmarshal(data, c))
		if c.Handoff != 355000000 || c.QuizStep != 355000000 || c.QuizSHA256 != "d7eec5b094e4265a627d2b61333d3bc7d339572431e281ac29b533e10c76ae67" || len(c.Actions) < 12 || len(c.Actions) > 32 || len(c.SaveFiles) != 2 {
			panic("未知冷讀路徑")
		}
		last := uint64(0)
		for _, a := range c.Actions {
			if a.At < last || a.End <= a.At || (a.Kind != "text" && a.Kind != "named") {
				panic("冷讀動作不符")
			}
			last = a.End
		}
		if last != c.Handoff {
			panic("冷讀終點不符")
		}
		for _, name := range []string{"SavGamJ.qsv", "VaultJ.DAT"} {
			spec, ok := c.SaveFiles[name]
			if !ok {
				panic("冷讀存檔缺項")
			}
			raw, err := os.ReadFile(filepath.Join(*coldSave, name))
			must(err)
			info, err := os.Stat(filepath.Join(*coldSave, name))
			must(err)
			if len(raw) != spec.Bytes || digest(raw) != spec.SHA256 {
				panic("中文存檔來源不符")
			}
			dir := filepath.Join(*out, "scratch", "SAVE")
			must(os.MkdirAll(dir, 0755))
			must(os.WriteFile(filepath.Join(dir, name), raw, 0644))
			if info.ModTime().UnixNano() != spec.ModTimeUnixNano {
				panic("中文存檔時間來源不符")
			}
			must(os.Chtimes(filepath.Join(dir, name), info.ModTime(), info.ModTime()))
		}
		g.cold, g.list, g.lifecycle = c, nil, true
		g.catalog = readLiveCatalog(filepath.Join(*coldRoles, "zh-TW.tsv"))
		data, err = os.ReadFile(filepath.Join(*coldRoles, "glyphs-20.json"))
		must(err)
		// Unmarshal 會合併既有 map；先解除與已保存 16px 字模的共享，避免混入 20px 遮罩。
		g.glyphs = glyphSet{}
		must(json.Unmarshal(data, &g.glyphs))
		if len(g.catalog) != 12 || g.glyphs.Size != 20 || g.glyphs.Height != 24 {
			panic("冷讀角色選單需沿用 20px 十二標籤")
		}
		g.installLifecycle()
		g.installShortText()
		if *coldUIInputs != "" {
			g.installColdPrompts(*coldUIInputs)
		}
	} else if g.list != nil {
		g.installList(*listInputs, *listRequest, *sourceCatalog)
		if *readerCatalog != "" {
			g.installReader(*readerCatalog, *readerIllustrations)
		}
		if *readerControls != "" || *readerInteractive || *readerProbe {
			g.installReaderControls(*readerControls, *listRequest, *readerInteractive, *readerProbe)
		}
		stateBytes, err := os.ReadFile(*state)
		must(err)
		if digest(stateBytes) != g.list.request.StateSHA {
			panic("列表快照雜湊不符")
		}
	} else if g.story {
		g.sources = readLiveCatalog(*sourceCatalog)
		anchor := oracle.Addr{Seg: 0x0b72, Off: 0x0311}
		if hex.EncodeToString(o.Bytes(anchor, 8)) != "558bec83ec025657" {
			panic("劇情入口 bytes 不符")
		}
		o.OnCall(anchor, func(_ *oracle.Oracle) {
			ptr := oracle.Addr{Seg: o.StackWord(10), Off: o.StackWord(9)}
			var raw []byte
			terminated := false
			for i := 0; i < 1024; i++ {
				if uint32(ptr.Seg)*16+uint32(ptr.Off)+uint32(i) >= 0xa0000 {
					return
				}
				c := o.Byte(oracle.Addr{Seg: ptr.Seg, Off: ptr.Off + uint16(i)})
				if c == 0 {
					terminated = true
					break
				}
				if c < 32 || c > 126 {
					return
				}
				raw = append(raw, c)
			}
			if !terminated {
				return
			}
			source := string(raw)
			key := "ecl." + digest(raw)[:20]
			text, ok := g.catalog[key]
			if !ok || g.sources[key] != source {
				if g.storySequence {
					panic("連續原型遇到未觀測或來源失配的段落")
				}
				return
			}
			// 限於正常流程已逐字匹配的衍生子集，不把全量候選表當已證實的顯示來源。
			if !g.storySequence && key != "ecl.6eddbe9ac1fb277bfaab" {
				return
			}
			box := [4]int{int(byte(o.StackWord(2))) * 16, int(byte(o.StackWord(3))) * 16, (int(byte(o.StackWord(4))) + 1) * 16, (int(byte(o.StackWord(5))) + 1) * 16}
			clear := byte(o.StackWord(8))
			components := []string{key}
			if box != [4]int{16, 272, 624, 368} || clear > 1 || (!g.storySequence && clear != 1) {
				panic("已觀測的劇情框及清除參數不符")
			}
			if clear == 0 {
				if g.page == nil || g.page.Box != box {
					panic("接續段落沒有可用的前段")
				}
				text = g.page.Text + text
				components = append(append([]string{}, g.page.Components...), key)
			}
			cells := (box[2] - box[0]) / g.glyphs.Size
			var lines []string
			chars := []rune(text)
			for len(chars) > 0 {
				n := cells
				if n > len(chars) {
					n = len(chars)
				}
				if n < len(chars) && strings.ContainsRune("，。！？、；：」』）》】", chars[n]) {
					n--
				}
				if n < len(chars) && strings.ContainsRune("「『（《【", chars[n-1]) {
					n--
				}
				if n <= 0 {
					panic("無可用斷行")
				}
				lines = append(lines, string(chars[:n]))
				chars = chars[n:]
			}
			if len(lines)*g.glyphs.Height > box[3]-box[1] {
				panic("首段中文超出安全框")
			}
			bg := byte(o.StackWord(7))
			if bg == 0 {
				bg = 8
			}
			p := storyPage{Step: o.Steps(), Key: key, Source: source, Text: text, Box: box, Foreground: byte(o.StackWord(6)), Background: bg, Lines: lines, Clear: clear, Components: components}
			g.page = &p
			g.pages = append(g.pages, p)
		})
	} else {
		g.installShortText()
	}
	g.texture = ebiten.NewImage(640, 400)
	ebiten.SetWindowSize(640, 400)
	ebiten.SetWindowTitle("黑暗之后：繪製前文字研究原型")
	ebiten.SetTPS(60)
	if *fine {
		ebiten.SetTPS(ebiten.SyncWithFPS)
	}
	must(ebiten.RunGame(g))
	if g.interactive && len(g.checkpoints) == 0 {
		g.capture()
	}
	ram := make([]byte, 1<<20)
	for i := range ram {
		ram[i] = o.Byte(oracle.Addr{Seg: uint16(i >> 4), Off: uint16(i & 15)})
	}
	result := map[string]any{"prototype": true, "scope": "initial character-menu only; no clear/scroll lifecycle", "translate": *translate,
		"source_commit": "f79eab6db8c64a524a06535e53e5d32b0bbcf7c8", "steps": o.Steps(), "regs": o.Regs(), "ram_sha256": digest(ram),
		"indexed_sha256": digest(o.Indexed()), "palette": o.Palette(), "events": g.events, "frames": g.frames}
	result["texture_uploads"] = g.uploads
	if g.interactive {
		result["scope"] = "DRAFT cold-boot interactive character-menu only; original keyboard; no complete localization claim"
		result["cold_boot"] = true
		result["inputs"] = g.inputs
		result["checkpoints"] = g.checkpoints
		result["unimplemented"] = o.Unimplemented()
	}
	if g.story {
		result["scope"] = "DRAFT first normal story paragraph; font comparison only; no pagination/clear lifecycle"
		if g.storySequence {
			result["scope"] = "DRAFT seven observed normal story fragments through city destination menu; no scrolling/save/complete-game claim"
		}
		result["paragraphs"] = g.pages
		result["font_size"] = g.glyphs.Size
		result["checkpoints"] = g.checkpoints
		result["unimplemented"] = o.Unimplemented()
		data, err := os.ReadFile(*sourceCatalog)
		must(err)
		result["source_catalog_sha256"] = digest(data)
	}
	paths := map[string]string{"catalog_sha256": *catalogPath, "glyphs_sha256": *glyphPath}
	if *state != "" {
		paths["initial_state_sha256"] = *state
	}
	for key, path := range paths {
		data, err := os.ReadFile(path)
		must(err)
		result[key] = digest(data)
	}
	if g.lifecycle {
		if !g.interactive && (g.transition || g.renderDepth != 0 || len(g.paints) != 0) {
			panic("未完成的呈現交易")
		}
		if !g.interactive && !g.camp {
			result["scope"] = "DRAFT normal p/l/e menu roundtrip; twelve labels only; no story/scroll/save"
		}
		result["boundaries"] = g.boundaries
		result["checkpoints"] = g.checkpoints
		result["unimplemented"] = o.Unimplemented()
	}
	if g.camp {
		result["scope"] = "DRAFT normal camp/footer and save J; sixteen-pixel disposable prototype; no production, story, all menus or GUI cold-load claim"
		result["font_size"] = g.glyphs.Size
		data, err := os.ReadFile(*campInputs)
		must(err)
		result["camp_inputs_sha256"] = digest(data)
	}
	if g.list != nil {
		g.listReceipt(result)
		if g.reader != nil {
			result["reader_catalog_sha256"] = g.reader.SHA256
			if g.reader.ImageSHA != "" {
				result["reader_illustrations_sha256"] = g.reader.ImageSHA
			}
			result["reader_events"] = g.reader.Events
			result["final_reader"] = g.reader.Page
			if g.reader.Ready {
				r := g.reader
				result["reader_controls_sha256"], result["reader_ui_events"], result["reader_gallery_frames"] = r.ControlSHA, r.UIEvents, r.GalleryFrames
				result["reader_seen"], result["final_auto_reader"] = r.seenIDs(), r.Auto
				result["reader_complete"] = r.Mode == "" && r.Gallery == nil && r.ControlIndex == len(r.Controls)
				result["reader_probe"], result["reader_interactive"] = r.Probe, r.Live
			}
		}
		for key, path := range map[string]string{"list_inputs_sha256": *listInputs, "list_request_sha256": *listRequest, "source_catalog_sha256": *sourceCatalog} {
			data, err := os.ReadFile(path)
			must(err)
			result[key] = digest(data)
		}
	}
	if g.cold != nil {
		c := g.cold
		if !c.ready {
			panic("冷讀未接回遊戲")
		}
		result["scope"] = "DRAFT continuous MZ cold-load J: approved 20px role labels and existing 16px gameplay prototype; load-source/slot prompts remain original; no complete-game claim"
		result["cold_boot"] = true
		g.coldPromptsReceipt(result)
		result["snapshot_loaded"] = false
		result["bridge_state_sha256"] = c.bridgeSHA
		result["cold_frames"], result["cold_events"], result["cold_checkpoints"], result["cold_boundaries"] = c.frames, c.events, c.checkpoints, c.boundaries
		if c.fineWindowsPath != "" {
			raw, err := os.ReadFile(c.fineWindowsPath)
			must(err)
			result["cold_fine_windows_sha256"] = digest(raw)
		}
		for key, path := range map[string]string{"cold_request_sha256": *coldPath, "cold_role_catalog_sha256": filepath.Join(*coldRoles, "zh-TW.tsv"), "cold_role_glyphs_sha256": filepath.Join(*coldRoles, "glyphs-20.json")} {
			data, err := os.ReadFile(path)
			must(err)
			result[key] = digest(data)
		}
	}
	b, err = json.MarshalIndent(result, "", "  ")
	must(err)
	must(os.WriteFile(filepath.Join(*out, "receipt.json"), append(b, '\n'), 0644))
	must(o.WritePNG(filepath.Join(*out, "guest.png")))
	fmt.Printf("frames=%d events=%d steps=%d RAM=%s\n", len(g.frames), len(g.events), o.Steps(), digest(ram))
}
