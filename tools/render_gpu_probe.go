// 真實 HD 素材的 GPU 矩形與獨立 CPU 逐格輸出對照，不執行遊戲。
package main

import (
	"encoding/json"
	"github.com/hajimehoshi/ebiten/v2"
	"image"
	"image/draw"
	"image/png"
	"os"
	"path/filepath"
)

type gpuResult struct {
	Mode                                       string
	Rectangles, Textures, Draws, PixelByteDiff int
}
type gpuCheck struct {
	Page    *scenePage
	Palette [256][3]byte
	Backend sceneBackend
	Frame   int
	Out     string
	Results []gpuResult
}

func gpuMust(err error) {
	if err != nil {
		panic(err)
	}
}
func (g *gpuCheck) Layout(int, int) (int, int) { return 960, 600 }
func (g *gpuCheck) Update() error {
	if g.Frame >= 3 {
		return ebiten.Termination
	}
	return nil
}
func (g *gpuCheck) Draw(screen *ebiten.Image) {
	if g.Frame >= 3 {
		return
	}
	hd := g.Frame != 0
	mode := []string{"native", "hd", "palette"}[g.Frame]
	pal := g.Palette
	if g.Frame == 2 {
		for i := range pal {
			pal[i][0] /= 2
		}
	}
	protected := [][4]int{{14, 35, 23, 40}}
	rects := g.Page.rectangles(hd, pal, protected)
	screen.Clear()
	builds, draws := g.Backend.submit(screen, rects, pal)
	want := g.Page.rgba(hd, pal, protected)
	got := make([]byte, len(want))
	screen.ReadPixels(got)
	diff := 0
	for i := range got {
		if got[i] != want[i] {
			diff++
		}
	}
	f, err := os.Create(filepath.Join(g.Out, mode+".png"))
	gpuMust(err)
	gpuMust(png.Encode(f, &image.RGBA{Pix: got, Stride: 960 * 4, Rect: image.Rect(0, 0, 960, 600)}))
	gpuMust(f.Close())
	g.Results = append(g.Results, gpuResult{mode, len(rects), builds, draws, diff})
	g.Frame++
}
func main() {
	root, out := os.Args[1], os.Args[2]
	hdroot := filepath.Join(root, "workplace/probe/player-current/hd")
	var pack struct {
		Assets []struct{ Key, Original, Image, Indexed string }
	}
	raw, err := os.ReadFile(filepath.Join(hdroot, "hd.json"))
	gpuMust(err)
	gpuMust(json.Unmarshal(raw, &pack))
	load := func(name string) *image.NRGBA {
		f, err := os.Open(filepath.Join(hdroot, name))
		gpuMust(err)
		im, err := png.Decode(f)
		gpuMust(err)
		gpuMust(f.Close())
		out := image.NewNRGBA(image.Rect(0, 0, im.Bounds().Dx(), im.Bounds().Dy()))
		draw.Draw(out, out.Bounds(), im, im.Bounds().Min, draw.Src)
		return out
	}
	g := &gpuCheck{Out: out}
	for _, r := range pack.Assets {
		if r.Key != "CPIC..6" {
			continue
		}
		native, hd := load(r.Original), load(r.Image)
		idx, err := os.ReadFile(filepath.Join(hdroot, r.Indexed))
		gpuMust(err)
		a := &sceneAsset{W: native.Bounds().Dx(), H: native.Bounds().Dy(), Index: idx, Alpha: make([]byte, len(idx)), Reference: make([]byte, len(idx)*3), HD: hd.Pix}
		for i, index := range idx {
			at := i * 4
			copy(a.Reference[i*3:i*3+3], native.Pix[at:at+3])
			a.Alpha[i] = native.Pix[at+3]
			if a.Alpha[i] != 0 {
				copy(g.Palette[index][:], native.Pix[at:at+3])
			}
		}
		s := new(renderScene)
		g.Page = s.page(0, func(int, uint32) byte { return 0 })
		s.record(g.Page, a, 8, 31)
	}
	if g.Page == nil {
		panic("缺少真實 CPIC..6 素材")
	}
	ebiten.SetWindowSize(960, 600)
	ebiten.SetWindowTitle("DQK GPU sample")
	gpuMust(ebiten.RunGame(g))
	g.Backend.close()
	raw, err = json.MarshalIndent(g.Results, "", "  ")
	gpuMust(err)
	gpuMust(os.WriteFile(filepath.Join(out, "gpu-checks.json"), append(raw, '\n'), 0644))
	for _, r := range g.Results {
		if r.PixelByteDiff != 0 {
			panic("GPU 與 CPU 參考輸出不同")
		}
	}
}
