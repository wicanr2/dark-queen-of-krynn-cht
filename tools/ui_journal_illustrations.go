// DRAFT：只讀重繪 PNG 的手札圖文元件，不載入 PDF 或掃描。
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"image"
	"image/draw"
	"image/png"
	"io"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/hajimehoshi/ebiten/v2/inpututil"
)

type readerImageView struct {
	Zoom int `json:"zoom"`
	X    int `json:"x"`
	Y    int `json:"y"`
}

type readerIllustration struct {
	Entry  int         `json:"entry"`
	File   string      `json:"file"`
	SHA256 string      `json:"sha256"`
	Crop   [4]int      `json:"crop"`
	Pixels *image.RGBA `json:"-"`
	Path   string      `json:"-"`
}

func (g *liveGame) loadReaderIllustrations(r *journalReader, path string) {
	data, err := os.ReadFile(path)
	must(err)
	var manifest struct {
		Draft   bool                 `json:"draft"`
		Entries []readerIllustration `json:"entries"`
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	must(decoder.Decode(&manifest))
	if decoder.Decode(new(any)) != io.EOF {
		panic("圖文清單含額外資料")
	}
	if !manifest.Draft || len(manifest.Entries) != 3 || !r.Ready || r.UI["reader.image_hint"] == "" {
		panic("圖文原型清單或操作提示不符")
	}
	r.Images = map[int]readerIllustration{}
	files := map[string]bool{}
	for _, item := range manifest.Entries {
		if (item.Entry != 12 && item.Entry != 25 && item.Entry != 64) || r.Images[item.Entry].Entry != 0 || files[item.File] ||
			!regexp.MustCompile(`^[a-z0-9][a-z0-9-]*\.png$`).MatchString(item.File) {
			panic("圖文編號或本機檔名不符")
		}
		files[item.File] = true
		encoded, err := os.ReadFile(filepath.Join(filepath.Dir(path), item.File))
		must(err)
		if digest(encoded) != item.SHA256 {
			panic("圖文雜湊不符")
		}
		config, err := png.DecodeConfig(bytes.NewReader(encoded))
		must(err)
		if config.Width < 1 || config.Height < 1 || config.Width > 4096 || config.Height > 4096 {
			panic("圖文尺寸不符")
		}
		decoded, err := png.Decode(bytes.NewReader(encoded))
		must(err)
		crop := image.Rect(item.Crop[0], item.Crop[1], item.Crop[2], item.Crop[3])
		if crop.Empty() || !crop.In(decoded.Bounds()) {
			panic("圖文內容框不符")
		}
		item.Pixels = image.NewRGBA(image.Rect(0, 0, crop.Dx(), crop.Dy()))
		item.Path = filepath.Join(filepath.Dir(path), item.File)
		draw.Draw(item.Pixels, item.Pixels.Bounds(), decoded, crop.Min, draw.Src)
		for i := 3; i < len(item.Pixels.Pix); i += 4 {
			if item.Pixels.Pix[i] != 255 {
				panic("圖文含未定義透明度")
			}
		}
		title := r.UI[fmt.Sprintf("journal.%d.title", item.Entry)]
		if title == "" {
			panic("圖文缺標題")
		}
		heading := fmt.Sprintf(r.UI["reader.heading"], fmt.Sprint(item.Entry), title)
		g.validateReaderText(heading, 37)
		r.Entries[item.Entry] = readerPage{Entry: item.Entry, Heading: heading, Lines: []string{}, Box: [4]int{16, 16, 624, 256}, Image: &readerImageView{}}
		r.Images[item.Entry] = item
	}
	r.ImageSHA = digest(data)
}

func (g *liveGame) validateReaderText(text string, cells int) {
	if len([]rune(text)) > cells {
		panic("手札文字超出安全框")
	}
	for _, ch := range text {
		alpha := g.glyphs.Glyphs[string(ch)]
		if ch < 32 || ch == '\\' || len(alpha) != 320 {
			panic("手札字型或控制字元不符")
		}
		for _, a := range alpha[256:] {
			if a != 0 {
				panic("手札字墨超出列高")
			}
		}
	}
}

func (r *journalReader) pageCount(id int) int {
	if r.Images[id].Entry != 0 {
		return 1
	}
	return (len(r.Entries[id].Lines) + 12) / 13
}

// 固定有理數最近鄰取樣。全圖居中，原尺寸及兩倍模式保持可見來源範圍有界。
func (r *journalReader) imageFor(p *readerPage) readerIllustration {
	if p.Mode == "manual-map" || p.Mode == "guide-map" {
		m := r.Manual
		if p.Mode == "guide-map" {
			m = r.Guide
		}
		if m == nil || !m.Reading {
			panic("說明地圖不在閱讀中")
		}
		doc := m.Books[m.Book].Documents[m.Cursor]
		if doc.Image == nil || p.SourceKey != doc.ID {
			panic("說明地圖來源不符")
		}
		return *doc.Image
	}
	return r.Images[p.Entry]
}

func (r *journalReader) imageGeometry(p *readerPage) (width, height, num, den, x, y int) {
	item := r.imageFor(p)
	width, height = item.Pixels.Bounds().Dx(), item.Pixels.Bounds().Dy()
	num, den = 1, 1
	if p.Image.Zoom == 0 {
		num, den = 608, width
		if 208*den < num*height {
			num, den = 208, height
		}
	} else if p.Image.Zoom == 2 {
		num = 2
	}
	x = max(0, (608-width*num/den)/2)
	y = max(0, (208-height*num/den)/2)
	return
}

func (r *journalReader) clampImage(p *readerPage) {
	w, h, n, d, _, _ := r.imageGeometry(p)
	p.Image.X = max(0, min(p.Image.X, w-(608*d+n-1)/n))
	p.Image.Y = max(0, min(p.Image.Y, h-(208*d+n-1)/n))
}

func (g *liveGame) readerImageKey(key string) {
	r := g.reader
	target := &r.Page
	if r.Mode == "manual" && r.Manual != nil {
		target = &r.Manual.Page
	}
	if r.Mode == "guide" && r.Guide != nil {
		target = &r.Guide.Page
	}
	if *target == nil || (*target).Image == nil {
		panic("圖文控制沒有圖文頁")
	}
	pageCopy, viewCopy := **target, *(*target).Image
	pageCopy.Image = &viewCopy
	*target = &pageCopy // 已提交的畫格與操作紀錄保留當時視圖。
	p := *target
	if key == "Home" {
		*p.Image = readerImageView{}
		return
	}
	if key == "ZoomIn" || key == "ZoomOut" {
		w, h, n, d, _, _ := r.imageGeometry(p)
		cx, cy := p.Image.X+min(w, (608*d+n-1)/n)/2, p.Image.Y+min(h, (208*d+n-1)/n)/2
		if key == "ZoomIn" {
			p.Image.Zoom = min(2, p.Image.Zoom+1)
		} else {
			p.Image.Zoom = max(0, p.Image.Zoom-1)
		}
		_, _, n, d, _, _ = r.imageGeometry(p)
		p.Image.X, p.Image.Y = cx-(608*d+n-1)/n/2, cy-(208*d+n-1)/n/2
	} else if p.Image.Zoom != 0 {
		switch key {
		case "PanLeft":
			p.Image.X -= 64
		case "PanRight":
			p.Image.X += 64
		case "PanUp":
			p.Image.Y -= 64
		case "PanDown":
			p.Image.Y += 64
		default:
			panic("未知圖文控制")
		}
	}
	r.clampImage(p)
}

func (g *liveGame) composeReaderImage(px []byte, p *readerPage) {
	r := g.reader
	w, h, n, d, left, top := r.imageGeometry(p)
	item := r.imageFor(p)
	for y := top; y < min(208, top+h*n/d); y++ {
		for x := left; x < min(608, left+w*n/d); x++ {
			sx, sy := p.Image.X+(x-left)*d/n, p.Image.Y+(y-top)*d/n
			if sx >= w || sy >= h {
				panic("圖文來源越界")
			}
			src, dst := item.Pixels.PixOffset(sx, sy), ((32+y)*640+16+x)*4
			copy(px[dst:dst+3], item.Pixels.Pix[src:src+3])
		}
	}
}

// Ebitengine 每個程序擁有一個視窗。以同一執行檔開啟唯讀地圖程序，
// 主遊戲保持閱讀暫停；子程序沒有 Oracle、遊戲輸入或存檔目錄。
type readerMapProcess struct {
	Command       *exec.Cmd
	Input         io.WriteCloser
	Done          chan error
	Step          uint64
	Exited        bool
	Error         error
	Runnable      bool
	Restoring     bool
	RestoreFrames int
}

type readerMapRequest struct {
	Path, SHA256, Heading, Footer string
	Crop                          [4]int
	Glyphs                        map[string][]byte
}

func readerSeparateMap(p *readerPage) bool {
	return p != nil && p.Image != nil && p.Entry != 12
}

func (g *liveGame) openReaderMapWindow() {
	if g.player == nil || g.mapWindow != nil || g.reader == nil {
		return
	}
	p := g.reader.currentPage()
	if !readerSeparateMap(p) {
		return
	}
	item := g.reader.imageFor(p)
	request := readerMapRequest{Path: item.Path, SHA256: item.SHA256, Crop: item.Crop,
		Heading: p.Heading, Footer: p.Footer, Glyphs: map[string][]byte{}}
	if request.Footer == "" {
		request.Footer = g.reader.UI["reader.image_hint"]
	}
	for _, ch := range request.Heading + request.Footer {
		request.Glyphs[string(ch)] = g.glyphs.Glyphs[string(ch)]
	}
	executable, err := os.Executable()
	if err != nil {
		panic(err)
	}
	command := exec.Command(executable, "--map-viewer")
	command.Stderr = os.Stderr
	input, err := command.StdinPipe()
	if err == nil {
		err = command.Start()
	}
	if err != nil {
		if input != nil {
			input.Close()
		}
		fmt.Fprintln(os.Stderr, "無法開啟地圖視窗：", err)
		g.readerKey("Esc", "map-window-error", 0)
		return
	}
	pending := &readerMapProcess{Command: command, Input: input, Done: make(chan error, 1), Step: g.o.Steps(), Runnable: ebiten.IsRunnableOnUnfocused()}
	g.mapWindow = pending
	// 主視窗即使因另一個全螢幕視窗而失焦／縮小，仍須收取子程序結束。
	// tickReaderMapWindow維持原版暫停，這裡不讓遊戲在背景前進。
	ebiten.SetRunnableOnUnfocused(true)
	go func() {
		if err := json.NewEncoder(input).Encode(request); err != nil {
			input.Close()
		}
	}()
	go func() {
		err := command.Wait()
		input.Close()
		pending.Done <- err
	}()
	g.reader.UIEvents = append(g.reader.UIEvents, map[string]any{"step": pending.Step, "action": "map-window-open", "source": p.SourceKey, "pid": command.Process.Pid, "fullscreen": true})
}

func (g *liveGame) closeReaderMapWindow() {
	if g.mapWindow != nil {
		g.mapWindow.Input.Close() // EOF 使子程序自行關閉，避免殘留視窗。
	}
}

func (g *liveGame) tickReaderMapWindow() bool {
	p := g.mapWindow
	if p == nil {
		return false
	}
	select {
	case err := <-p.Done:
		p.Exited, p.Error = true, err
	default:
	}
	if p.Exited {
		if !p.Restoring {
			if ebiten.IsWindowMinimized() {
				ebiten.RestoreWindow()
			}
			p.Restoring, p.RestoreFrames = true, 2
		}
		if p.RestoreFrames > 0 {
			p.RestoreFrames--
			return true
		}
		// 子視窗關閉後焦點可能在按鍵放開前回到主視窗。先吞掉這個按住的
		// 關閉鍵，避免同一次Esc又離開目錄，甚至送進原版遊戲。
		if ebiten.IsKeyPressed(ebiten.KeyEscape) || ebiten.IsKeyPressed(ebiten.KeyF6) || ebiten.IsKeyPressed(ebiten.KeyF7) {
			return true
		}
		if p.Error != nil {
			fmt.Fprintln(os.Stderr, "地圖視窗結束：", p.Error)
		}
		if g.o.Steps() != p.Step {
			panic("地圖查閱期間原版狀態曾前進")
		}
		g.reader.UIEvents = append(g.reader.UIEvents, map[string]any{"step": g.o.Steps(), "action": "map-window-close"})
		g.mapWindow = nil
		g.readerKey("Esc", "map-window", 0)
		g.reader.WaitDraw = true
		g.mapResumeRunnable = &p.Runnable // 第一張還原畫格提交後才恢復原本的失焦設定。
	}
	return true
}

type readerMapGame struct {
	Request                readerMapRequest
	Image, Heading, Footer *ebiten.Image
	ParentClosed           chan struct{}
	Width, Height          int
	Zoom, PanX, PanY       float64
	MouseX, MouseY         int
	Closing                bool
	CloseKey               ebiten.Key
	CloseDeadline          time.Time
}

func mapWindowText(text string, glyphs map[string][]byte, ink [3]byte) (*ebiten.Image, error) {
	chars := []rune(text)
	px := image.NewRGBA(image.Rect(0, 0, max(1, len(chars)*16), 16))
	for i, ch := range chars {
		alpha := glyphs[string(ch)]
		if len(alpha) < 256 {
			return nil, fmt.Errorf("地圖視窗缺少字型：%c", ch)
		}
		for n, a := range alpha[:256] {
			at := px.PixOffset(i*16+n%16, n/16)
			for c := 0; c < 3; c++ {
				px.Pix[at+c] = byte((uint32(ink[c])*uint32(a) + 127) / 255)
			}
			px.Pix[at+3] = a
		}
	}
	return ebiten.NewImageFromImage(px), nil
}

func runReaderMapWindow() error {
	decoder := json.NewDecoder(io.LimitReader(os.Stdin, 16<<20))
	decoder.DisallowUnknownFields()
	var request readerMapRequest
	if err := decoder.Decode(&request); err != nil {
		return err
	}
	encoded, err := os.ReadFile(request.Path)
	if err != nil {
		return err
	}
	if len(encoded) > 16<<20 || digest(encoded) != request.SHA256 {
		return fmt.Errorf("地圖視窗來源雜湊不符")
	}
	config, err := png.DecodeConfig(bytes.NewReader(encoded))
	if err != nil {
		return err
	}
	if config.Width < 1 || config.Height < 1 || config.Width > 4096 || config.Height > 4096 {
		return fmt.Errorf("地圖視窗尺寸不符")
	}
	decoded, err := png.Decode(bytes.NewReader(encoded))
	if err != nil {
		return err
	}
	crop := image.Rect(request.Crop[0], request.Crop[1], request.Crop[2], request.Crop[3])
	if crop.Empty() || !crop.In(decoded.Bounds()) {
		return fmt.Errorf("地圖視窗內容框越界")
	}
	g := &readerMapGame{Request: request, Zoom: 1, Width: 1280, Height: 800, ParentClosed: make(chan struct{})}
	g.Image = ebiten.NewImageFromImage(decoded.(interface {
		SubImage(image.Rectangle) image.Image
	}).SubImage(crop))
	g.Heading, err = mapWindowText(request.Heading, request.Glyphs, [3]byte{243, 216, 157})
	if err != nil {
		return err
	}
	g.Footer, err = mapWindowText(request.Footer, request.Glyphs, [3]byte{235, 235, 235})
	if err != nil {
		return err
	}
	go func() { var extra any; decoder.Decode(&extra); close(g.ParentClosed) }()
	ebiten.SetWindowTitle("黑暗之后 · " + strings.TrimSpace(request.Heading))
	ebiten.SetWindowSize(1280, 800)
	ebiten.SetWindowResizingMode(ebiten.WindowResizingModeEnabled)
	ebiten.SetWindowClosingHandled(true)
	ebiten.SetRunnableOnUnfocused(true) // 失焦後仍須處理放開關閉鍵及父程序EOF。
	ebiten.SetFullscreen(true)
	return ebiten.RunGame(g)
}

func (g *readerMapGame) geometry() (float64, float64, float64) {
	scale := math.Min(float64(g.Width-32)/float64(g.Image.Bounds().Dx()), float64(g.Height-104)/float64(g.Image.Bounds().Dy())) * g.Zoom
	w, h := float64(g.Image.Bounds().Dx())*scale, float64(g.Image.Bounds().Dy())*scale
	g.PanX = math.Max(-math.Max(0, (w-float64(g.Width-32))/2), math.Min(g.PanX, math.Max(0, (w-float64(g.Width-32))/2)))
	g.PanY = math.Max(-math.Max(0, (h-float64(g.Height-104))/2), math.Min(g.PanY, math.Max(0, (h-float64(g.Height-104))/2)))
	return scale, (float64(g.Width)-w)/2 + g.PanX, 48 + (float64(g.Height-104)-h)/2 + g.PanY
}

func (g *readerMapGame) Update() error {
	select {
	case <-g.ParentClosed:
		return ebiten.Termination
	default:
	}
	if ebiten.IsWindowBeingClosed() {
		return ebiten.Termination
	}
	// 在仍持有焦點的子視窗等關閉鍵放開。父視窗未聚焦時查不到按住的
	// 鍵，不能靠父視窗的IsKeyPressed阻止這次按鍵穿透。
	if g.Closing {
		if !ebiten.IsKeyPressed(g.CloseKey) || time.Now().After(g.CloseDeadline) {
			return ebiten.Termination
		}
		return nil
	}
	for _, key := range []ebiten.Key{ebiten.KeyEscape, ebiten.KeyF6, ebiten.KeyF7} {
		if inpututil.IsKeyJustPressed(key) {
			g.Closing, g.CloseKey = true, key
			g.CloseDeadline = time.Now().Add(750 * time.Millisecond) // Wine失焦時可能漏掉keyup，不能永久卡住。
			return nil
		}
	}
	if inpututil.IsKeyJustPressed(ebiten.KeyF11) {
		ebiten.SetFullscreen(!ebiten.IsFullscreen())
	}
	_, wheel := ebiten.Wheel()
	if inpututil.IsKeyJustPressed(ebiten.KeyEqual) || inpututil.IsKeyJustPressed(ebiten.KeyNumpadAdd) {
		wheel++
	}
	if inpututil.IsKeyJustPressed(ebiten.KeyMinus) || inpututil.IsKeyJustPressed(ebiten.KeyNumpadSubtract) {
		wheel--
	}
	if wheel != 0 {
		factor := math.Pow(1.25, wheel)
		next := math.Max(1, math.Min(16, g.Zoom*factor))
		g.PanX *= next / g.Zoom
		g.PanY *= next / g.Zoom
		g.Zoom = next
	}
	if inpututil.IsKeyJustPressed(ebiten.KeyHome) {
		g.Zoom, g.PanX, g.PanY = 1, 0, 0
	}
	if ebiten.IsKeyPressed(ebiten.KeyA) || ebiten.IsKeyPressed(ebiten.KeyArrowLeft) {
		g.PanX += 12
	}
	if ebiten.IsKeyPressed(ebiten.KeyD) || ebiten.IsKeyPressed(ebiten.KeyArrowRight) {
		g.PanX -= 12
	}
	if ebiten.IsKeyPressed(ebiten.KeyW) || ebiten.IsKeyPressed(ebiten.KeyArrowUp) {
		g.PanY += 12
	}
	if ebiten.IsKeyPressed(ebiten.KeyS) || ebiten.IsKeyPressed(ebiten.KeyArrowDown) {
		g.PanY -= 12
	}
	x, y := ebiten.CursorPosition()
	if ebiten.IsMouseButtonPressed(ebiten.MouseButtonLeft) && !inpututil.IsMouseButtonJustPressed(ebiten.MouseButtonLeft) {
		g.PanX += float64(x - g.MouseX)
		g.PanY += float64(y - g.MouseY)
	}
	g.MouseX, g.MouseY = x, y
	g.geometry()
	return nil
}

func (g *readerMapGame) Layout(w, h int) (int, int) {
	g.Width, g.Height = max(320, w), max(240, h)
	return g.Width, g.Height
}

func (g *readerMapGame) Draw(screen *ebiten.Image) {
	scale, x, y := g.geometry()
	op := &ebiten.DrawImageOptions{Filter: ebiten.FilterLinear}
	op.GeoM.Scale(scale, scale)
	op.GeoM.Translate(x, y)
	// 裁切只作用於地圖區，標題與操作提示固定可見。
	screen.SubImage(image.Rect(0, 48, g.Width, g.Height-56)).(*ebiten.Image).DrawImage(g.Image, op)
	for _, row := range []struct {
		Image *ebiten.Image
		Y     int
	}{{g.Heading, 14}, {g.Footer, g.Height - 36}} {
		factor := math.Min(1.5, float64(g.Width-32)/float64(row.Image.Bounds().Dx()))
		t := &ebiten.DrawImageOptions{Filter: ebiten.FilterLinear}
		t.GeoM.Scale(factor, factor)
		t.GeoM.Translate((float64(g.Width)-float64(row.Image.Bounds().Dx())*factor)/2, float64(row.Y))
		screen.DrawImage(row.Image, t)
	}
}
