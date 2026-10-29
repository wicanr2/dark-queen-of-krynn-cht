// 高清字形直接進Go文字畫布；原版320x200座標與16／20邏輯字級保持。
package main

import (
	"compress/gzip"
	"encoding/json"
	"fmt"
	"image"
	"image/color"
	"io"
	"os"
	"path/filepath"
	"sort"

	"github.com/hajimehoshi/ebiten/v2"
)

type sharpFace struct {
	LogicalSize, Size, Height int
	Glyphs                    map[string][]byte
	atlas                     *ebiten.Image
	boxes                     map[rune]image.Rectangle
}
type sharpCommand struct {
	Rect  image.Rectangle
	Face  int
	Char  rune
	Color [3]byte
}
type sharpText struct {
	Faces        map[int]*sharpFace
	Commands     []sharpCommand
	Layer, Pixel *ebiten.Image
	Draws        uint64
	GlyphDraws   map[int]uint64
}

func init() { playerSharpTextLoader = loadSharpText }

func loadSharpText(profile string) playerSharpText {
	f, err := os.Open(filepath.Join(profile, "sharp-text.json.gz"))
	if os.IsNotExist(err) {
		return nil
	}
	must(err)
	defer f.Close()
	z, err := gzip.NewReader(f)
	must(err)
	defer z.Close()
	var m struct {
		Version, Scale int
		FontSHA256     string
		Faces          []*sharpFace
	}
	raw, err := io.ReadAll(io.LimitReader(z, 48<<20))
	must(err)
	must(json.Unmarshal(raw, &m))
	if m.Version != 1 || m.Scale != 3 || m.FontSHA256 != "9d5bf4932d31fe94c18cd8cfddc98bc1b14ce10f4e354c682179db290a99c825" || len(m.Faces) != 2 {
		panic("高清字模來源不符")
	}
	h := &sharpText{Faces: map[int]*sharpFace{}}
	for _, face := range m.Faces {
		if (face.LogicalSize != 16 && face.LogicalSize != 20) || face.Size != face.LogicalSize*3 || face.Height != (face.LogicalSize+4)*3 || len(face.Glyphs) == 0 || len(face.Glyphs) > 8192 || h.Faces[face.LogicalSize] != nil {
			panic("高清字模尺寸不符")
		}
		for key, alpha := range face.Glyphs {
			if len([]rune(key)) != 1 || len(alpha) != face.Size*face.Height {
				panic("高清字模資料不符")
			}
			if face.LogicalSize == 16 {
				for _, a := range alpha[face.Size*face.Size:] {
					if a != 0 {
						panic("高清字墨超出列高")
					}
				}
			}
		}
		h.Faces[face.LogicalSize] = face
	}
	return h
}
func (h *sharpText) Reset()                  { h.Commands = h.Commands[:0] }
func (h *sharpText) Clear(r image.Rectangle) { h.Commands = append(h.Commands, sharpCommand{Rect: r}) }
func (h *sharpText) Glyph(x, y, size int, ch rune, ink [3]byte) {
	face := h.Faces[size]
	if face == nil || face.Glyphs[string(ch)] == nil {
		panic(fmt.Sprintf("高清字模缺字：%U", ch))
	}
	if len(h.Commands) >= 8192 {
		panic("高清文字命令超過容量")
	}
	h.Commands = append(h.Commands, sharpCommand{Rect: image.Rect(x, y, x+size, y+size+4), Face: size, Char: ch, Color: ink})
}
func (h *sharpText) Alpha(ch rune) ([]byte, int, int) {
	f := h.Faces[16]
	return f.Glyphs[string(ch)], f.Size, f.Height
}
func (f *sharpFace) texture() {
	if f.atlas != nil {
		return
	}
	chars := make([]rune, 0, len(f.Glyphs))
	for ch := range f.Glyphs {
		chars = append(chars, []rune(ch)[0])
	}
	sort.Slice(chars, func(i, j int) bool { return chars[i] < chars[j] })
	const columns = 32
	px := image.NewRGBA(image.Rect(0, 0, columns*f.Size, ((len(chars)+columns-1)/columns)*f.Height))
	f.boxes = map[rune]image.Rectangle{}
	for n, ch := range chars {
		left, top := (n%columns)*f.Size, (n/columns)*f.Height
		f.boxes[ch] = image.Rect(left, top, left+f.Size, top+f.Height)
		for i, a := range f.Glyphs[string(ch)] {
			at := px.PixOffset(left+i%f.Size, top+i/f.Size)
			px.Pix[at], px.Pix[at+1], px.Pix[at+2], px.Pix[at+3] = a, a, a, a
		}
	}
	f.atlas = ebiten.NewImageFromImage(px)
}
func (h *sharpText) Draw(dst *ebiten.Image) {
	if len(h.Commands) == 0 {
		return
	}
	h.Draws++
	if h.GlyphDraws == nil {
		h.GlyphDraws = map[int]uint64{}
	}
	if h.Layer == nil {
		h.Layer = ebiten.NewImage(1920, 1200)
		h.Pixel = ebiten.NewImage(1, 1)
		h.Pixel.Fill(color.White)
	}
	h.Layer.Clear()
	for _, c := range h.Commands {
		op := &ebiten.DrawImageOptions{}
		if c.Face == 0 {
			op.GeoM.Scale(float64(c.Rect.Dx()*3), float64(c.Rect.Dy()*3))
			op.GeoM.Translate(float64(c.Rect.Min.X*3), float64(c.Rect.Min.Y*3))
			op.Blend = ebiten.BlendClear
			h.Layer.DrawImage(h.Pixel, op)
		} else {
			h.GlyphDraws[c.Face]++
			face := h.Faces[c.Face]
			face.texture()
			op.GeoM.Translate(float64(c.Rect.Min.X*3), float64(c.Rect.Min.Y*3))
			op.ColorScale.Scale(float32(c.Color[0])/255, float32(c.Color[1])/255, float32(c.Color[2])/255, 1)
			h.Layer.DrawImage(face.atlas.SubImage(face.boxes[c.Char]).(*ebiten.Image), op)
		}
	}
	dst.DrawImage(h.Layer, nil)
}

func (h *sharpText) Diagnostics() any {
	return map[string]any{"canvas": []int{1920, 1200}, "logical_canvas": []int{640, 400}, "raster_sizes": []int{48, 60}, "draws": h.Draws, "glyph_draws": h.GlyphDraws, "source": "TrueType outlines; no enlarged legacy glyphs"}
}
