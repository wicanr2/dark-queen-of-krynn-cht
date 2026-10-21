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
	"github.com/wicanr2/dosgolem/oracle"
)

type liveEvent struct {
	Step              uint64 `json:"step"`
	X, Y              int
	Color             uint16
	Source, Key, Text string
}
type liveFrame struct {
	Step         uint64 `json:"step"`
	Events       int    `json:"events"`
	File, SHA256 string
	Held         bool `json:"held"`
	Active       int  `json:"active"`
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
func (g *liveGame) limit() uint64 {
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
		if o.Regs().AX != 0xffff {
			g.transition = true
			log("selection-return")
		}
	})
	o.OnCall(oracle.Addr{Seg: 0x1bb6, Off: 0x151f}, func(_ *oracle.Oracle) {
		if g.transition {
			g.active = map[[2]int]liveEvent{}
		}
		g.renderDepth++
		if g.transition {
			log("transition-render-entry")
		}
	})
	o.OnCall(oracle.Addr{Seg: 0x1bb6, Off: 0x1585}, func(_ *oracle.Oracle) {
		g.renderDepth--
		if g.renderDepth < 0 {
			panic("繪製邊界不成對")
		}
		if g.transition {
			g.transition = false
			log("transition-render-return")
		}
	})
	registered := map[oracle.Addr]bool{}
	o.OnCall(oracle.Addr{Seg: 0x0ceb, Off: 0x008e}, func(_ *oracle.Oracle) {
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
	if g.o.Steps() >= g.limit() {
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
						d := ((y-2+yy)*640 + x + i*g.glyphs.Size + xx) * 4
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
			for y := p.Box[1]; y < p.Box[3]; y++ {
				for x := p.Box[0]; x < p.Box[2]; x++ {
					copy(px[(y*640+x)*4:][:3], bg[:])
				}
			}
			for row, line := range p.Lines {
				for col, ch := range []rune(line) {
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
	held := g.lifecycle && (g.transition || g.renderDepth > 0 || len(g.paints) > 0)
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
	f, err := os.Create(filepath.Join(g.out, name))
	must(err)
	im := &image.RGBA{Pix: readback, Stride: 640 * 4, Rect: image.Rect(0, 0, 640, 400)}
	must(png.Encode(f, im))
	must(f.Close())
	g.frames = append(g.frames, liveFrame{Step: g.o.Steps(), Events: len(g.events), File: name, SHA256: digest(readback), Held: held, Active: len(g.active)})
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
	sourceCatalog := flag.String("source-catalog", "", "劇情原文 TSV，與現行譯文依 key 核對")
	flag.Parse()
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
	must(o.LoadStateFile(*state))
	o.SetScratch(filepath.Join(*out, "scratch"))
	expectedSteps := uint64(239000000)
	if *story {
		expectedSteps = 329000000
	}
	if o.Steps() != expectedSteps {
		panic("快照步數不符")
	}
	for i, want := range []byte{0x55, 0x8b, 0xec, 0xff, 0x76, 0x0a, 0x0e, 0xe8, 0x30, 0xff, 0x59} {
		if o.Byte(oracle.Addr{Seg: 0x1212, Off: 0x03a0 + uint16(i)}) != want {
			panic("resident bytes 不符")
		}
	}
	g := &liveGame{o: o, out: *out, translate: *translate, fine: *fine, catalog: map[string]string{}, active: map[[2]int]liveEvent{}}
	g.lifecycle = *lifecycle
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
	if ((!g.story && g.glyphs.Size != 20) || (g.story && g.glyphs.Size != 16 && g.glyphs.Size != 20)) || g.glyphs.Height != g.glyphs.Size+4 {
		panic("未批准的字型尺寸")
	}
	g.catalog = readLiveCatalog(*catalogPath)
	if g.storySequence && len(g.catalog) != 7 {
		panic("連續原型需要本輪已匹配的七段子集")
	}
	if !g.story && len(g.catalog) != 12 {
		panic("角色選單原型需要 12 個標籤")
	}
	if g.story {
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
			text, ok := g.catalog[key]
			if !ok {
				return
			}
			e := liveEvent{Step: o.Steps(), X: int(word(6)), Y: int(word(4)), Color: word(8), Source: string(source), Key: key, Text: text}
			g.events = append(g.events, e)
			g.active[[2]int{e.X, e.Y}] = e
		})
	}
	g.texture = ebiten.NewImage(640, 400)
	ebiten.SetWindowSize(640, 400)
	ebiten.SetWindowTitle("黑暗之后：繪製前文字研究原型")
	ebiten.SetTPS(60)
	if *fine {
		ebiten.SetTPS(ebiten.SyncWithFPS)
	}
	must(ebiten.RunGame(g))
	ram := make([]byte, 1<<20)
	for i := range ram {
		ram[i] = o.Byte(oracle.Addr{Seg: uint16(i >> 4), Off: uint16(i & 15)})
	}
	result := map[string]any{"prototype": true, "scope": "initial character-menu only; no clear/scroll lifecycle", "translate": *translate,
		"source_commit": "f79eab6db8c64a524a06535e53e5d32b0bbcf7c8", "steps": o.Steps(), "regs": o.Regs(), "ram_sha256": digest(ram),
		"indexed_sha256": digest(o.Indexed()), "palette": o.Palette(), "events": g.events, "frames": g.frames}
	result["texture_uploads"] = g.uploads
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
	for key, path := range map[string]string{"initial_state_sha256": *state, "catalog_sha256": *catalogPath, "glyphs_sha256": *glyphPath} {
		data, err := os.ReadFile(path)
		must(err)
		result[key] = digest(data)
	}
	if g.lifecycle {
		if g.transition || g.renderDepth != 0 || len(g.paints) != 0 {
			panic("未完成的呈現交易")
		}
		result["scope"] = "DRAFT normal p/l/e menu roundtrip; twelve labels only; no story/scroll/save"
		result["boundaries"] = g.boundaries
		result["checkpoints"] = g.checkpoints
		result["unimplemented"] = o.Unimplemented()
	}
	b, err = json.MarshalIndent(result, "", "  ")
	must(err)
	must(os.WriteFile(filepath.Join(*out, "receipt.json"), append(b, '\n'), 0644))
	must(o.WritePNG(filepath.Join(*out, "guest.png")))
	fmt.Printf("frames=%d events=%d steps=%d RAM=%s\n", len(g.frames), len(g.events), o.Steps(), digest(ram))
}
