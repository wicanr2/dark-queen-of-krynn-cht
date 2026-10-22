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
	"os"
	"path/filepath"
	"regexp"
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
func (r *journalReader) imageGeometry(p *readerPage) (width, height, num, den, x, y int) {
	item := r.Images[p.Entry]
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
	if r.Page == nil || r.Page.Image == nil {
		panic("圖文控制沒有圖文頁")
	}
	pageCopy, viewCopy := *r.Page, *r.Page.Image
	pageCopy.Image = &viewCopy
	r.Page = &pageCopy // 已提交的畫格與操作紀錄保留當時視圖。
	p := r.Page
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
	item := r.Images[p.Entry]
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
