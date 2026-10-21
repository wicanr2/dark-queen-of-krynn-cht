// DRAFT 研究原型：初始角色選單與一般 p/l/e 往返，不供正式遊玩。
package main

import (
	"crypto/sha256"
	"encoding/csv"
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
type liveGame struct {
	o           *oracle.Oracle
	out         string
	translate   bool
	fine        bool
	catalog     map[string]string
	glyphs      glyphSet
	events      []liveEvent
	active      map[[2]int]liveEvent
	frames      []liveFrame
	texture     *ebiten.Image
	textureHash string
	uploads     int
	finished    bool
	lifecycle   bool
	transition  bool
	renderDepth int
	paints      []paintReturn
	lastPixels  []byte
	boundaries  []map[string]any
	checkpoints []map[string]any
}

func must(err error) {
	if err != nil {
		panic(err)
	}
}
func digest(b []byte) string { h := sha256.Sum256(b); return hex.EncodeToString(h[:]) }
func (g *liveGame) limit() uint64 {
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
	if o.Steps() != 239000000 {
		panic("快照步數不符")
	}
	for i, want := range []byte{0x55, 0x8b, 0xec, 0xff, 0x76, 0x0a, 0x0e, 0xe8, 0x30, 0xff, 0x59} {
		if o.Byte(oracle.Addr{Seg: 0x1212, Off: 0x03a0 + uint16(i)}) != want {
			panic("resident bytes 不符")
		}
	}
	g := &liveGame{o: o, out: *out, translate: *translate, fine: *fine, catalog: map[string]string{}, active: map[[2]int]liveEvent{}}
	g.lifecycle = *lifecycle
	if g.lifecycle {
		g.installLifecycle()
	}
	b, err = os.ReadFile(*glyphPath)
	must(err)
	must(json.Unmarshal(b, &g.glyphs))
	if g.glyphs.Size != 20 || g.glyphs.Height != 24 {
		panic("未批准的字型尺寸")
	}
	f, err := os.Open(*catalogPath)
	must(err)
	reader := csv.NewReader(f)
	reader.Comma = '\t'
	rows, err := reader.ReadAll()
	must(err)
	must(f.Close())
	if len(rows) != 13 || len(rows[0]) != 2 || rows[0][0] != "key" || rows[0][1] != "text" {
		panic("原型 TSV 格式不符")
	}
	for _, row := range rows[1:] {
		if _, ok := g.catalog[row[0]]; ok {
			panic("重複 key")
		}
		g.catalog[row[0]] = row[1]
	}
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
