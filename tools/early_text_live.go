// DRAFT 研究原型：只驗初始角色選單的實際前端提交，不供正式遊玩。
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
}
type glyphSet struct {
	Size, Height int
	Glyphs       map[string][]byte
}
type liveGame struct {
	o         *oracle.Oracle
	out       string
	translate bool
	fine      bool
	catalog   map[string]string
	glyphs    glyphSet
	events    []liveEvent
	active    map[[2]int]liveEvent
	frames    []liveFrame
	texture   *ebiten.Image
	finished  bool
}

func must(err error) {
	if err != nil {
		panic(err)
	}
}
func digest(b []byte) string { h := sha256.Sum256(b); return hex.EncodeToString(h[:]) }
func (g *liveGame) Update() error {
	if g.finished {
		return ebiten.Termination
	}
	if g.o.Steps() >= 246000000 {
		return nil
	}
	if g.o.Steps() == 241000000 {
		must(g.o.TypeKeys("p"))
	}
	batch := uint64(100000)
	if g.fine && g.o.Steps() >= 241000000 && g.o.Steps() < 242000000 {
		batch = 2000
	}
	must(g.o.Run(batch))
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
	g.texture.WritePixels(px)
	screen.DrawImage(g.texture, nil)
	// 擷取 GPU 實際讀回的已提交畫格，逐點確認與原子合成的輸入相同。
	readback := make([]byte, len(px))
	screen.ReadPixels(readback)
	if digest(px) != digest(readback) {
		panic("前端提交與合成畫格不同")
	}
	name := fmt.Sprintf("frame-%03d-%09d.png", len(g.frames), g.o.Steps())
	f, err := os.Create(filepath.Join(g.out, name))
	must(err)
	im := &image.RGBA{Pix: readback, Stride: 640 * 4, Rect: image.Rect(0, 0, 640, 400)}
	must(png.Encode(f, im))
	must(f.Close())
	g.frames = append(g.frames, liveFrame{g.o.Steps(), len(g.events), name, digest(readback)})
	if g.o.Steps() >= 246000000 {
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
	flag.Parse()
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
	b, err = json.MarshalIndent(result, "", "  ")
	must(err)
	must(os.WriteFile(filepath.Join(*out, "receipt.json"), append(b, '\n'), 0644))
	must(o.WritePNG(filepath.Join(*out, "guest.png")))
	fmt.Printf("frames=%d events=%d steps=%d RAM=%s\n", len(g.frames), len(g.events), o.Steps(), digest(ram))
}
