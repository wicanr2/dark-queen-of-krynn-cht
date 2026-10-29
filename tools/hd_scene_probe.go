// 場景素材分層抽驗。使用正式Go畫布與GPU後端，不執行遊戲規則。
package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"image"
	"image/draw"
	"image/png"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/hajimehoshi/ebiten/v2"
)

type sceneProbeRecord struct {
	Key, Original, Image, Indexed, OriginalSHA256, SHA256, IndexedSHA256 string
}
type sceneProbeResult struct {
	Key, Group, Mode                           string
	Rectangles, Textures, Draws, PixelByteDiff int
}
type sceneProbeGame struct {
	Theme, Out string
	Samples    []sceneProbeRecord
	Frame      int
	Scene      renderScene
	Page       *scenePage
	Palette    [256][3]byte
	Backend    sceneBackend
	Results    []sceneProbeResult
}

func sceneProbeMust(err error) {
	if err != nil {
		panic(err)
	}
}
func (g *sceneProbeGame) Layout(int, int) (int, int) { return 960, 600 }
func (g *sceneProbeGame) Update() error {
	if g.Frame >= len(g.Samples)*4 {
		return ebiten.Termination
	}
	return nil
}
func sceneProbeBytes(root, name, want string) []byte {
	clean := filepath.Clean(name)
	if name == "" || filepath.IsAbs(clean) || clean == ".." || strings.HasPrefix(clean, ".."+string(filepath.Separator)) {
		panic("場景素材路徑越界")
	}
	raw, err := os.ReadFile(filepath.Join(root, clean))
	sceneProbeMust(err)
	sum := sha256.Sum256(raw)
	if len(want) != 64 || hex.EncodeToString(sum[:]) != want {
		panic("場景素材雜湊失配：" + name)
	}
	return raw
}
func sceneProbePNG(root, name, want string) *image.NRGBA {
	im, err := png.Decode(bytes.NewReader(sceneProbeBytes(root, name, want)))
	sceneProbeMust(err)
	out := image.NewNRGBA(image.Rect(0, 0, im.Bounds().Dx(), im.Bounds().Dy()))
	draw.Draw(out, out.Bounds(), im, im.Bounds().Min, draw.Src)
	return out
}
func (g *sceneProbeGame) prepare(record sceneProbeRecord) {
	native := sceneProbePNG(g.Theme, record.Original, record.OriginalSHA256)
	hd := sceneProbePNG(g.Theme, record.Image, record.SHA256)
	idx := sceneProbeBytes(g.Theme, record.Indexed, record.IndexedSHA256)
	w, h := native.Bounds().Dx(), native.Bounds().Dy()
	if len(idx) != w*h || hd.Bounds().Dx() != w*3 || hd.Bounds().Dy() != h*3 {
		panic("場景來源尺寸不符")
	}
	asset := &sceneAsset{W: w, H: h, Index: idx, Alpha: make([]byte, len(idx)), Reference: make([]byte, len(idx)*3), HD: hd.Pix}
	g.Palette = [256][3]byte{}
	for i, index := range idx {
		at := i * 4
		asset.Alpha[i] = native.Pix[at+3]
		copy(asset.Reference[i*3:i*3+3], native.Pix[at:at+3])
		if asset.Alpha[i] != 0 {
			copy(g.Palette[index][:], native.Pix[at:at+3])
		}
	}
	g.Scene = renderScene{}
	g.Page = g.Scene.page(0, func(int, uint32) byte { return 0 })
	g.Scene.record(g.Page, asset, (320-w)/2, (200-h)/2)
}
func (g *sceneProbeGame) Draw(screen *ebiten.Image) {
	if g.Frame >= len(g.Samples)*4 {
		return
	}
	record, phase := g.Samples[g.Frame/4], g.Frame%4
	if phase == 0 {
		g.prepare(record)
	}
	mode := []string{"native", "hd", "occlusion", "palette"}[phase]
	pal := g.Palette
	var protected [][4]int
	if phase == 2 {
		protected = [][4]int{{144, 88, 176, 112}}
	}
	if phase == 3 {
		for i := range pal {
			pal[i][0] /= 2
		}
	}
	rects := g.Page.rectangles(phase != 0, pal, protected)
	screen.Clear()
	builds, draws := g.Backend.submit(screen, rects, pal)
	want := g.Page.rgba(phase != 0, pal, protected)
	got := make([]byte, len(want))
	screen.ReadPixels(got)
	diff := 0
	for i := range got {
		if got[i] != want[i] {
			diff++
		}
	}
	name := record.Key + "-" + mode + ".png"
	f, err := os.Create(filepath.Join(g.Out, name))
	sceneProbeMust(err)
	sceneProbeMust(png.Encode(f, &image.RGBA{Pix: got, Stride: 960 * 4, Rect: image.Rect(0, 0, 960, 600)}))
	sceneProbeMust(f.Close())
	g.Results = append(g.Results, sceneProbeResult{record.Key, strings.Split(record.Key, ".")[0], mode, len(rects), builds, draws, diff})
	g.Frame++
}
func main() {
	if len(os.Args) != 3 {
		panic("用法：hd-scene-probe 主題目錄 新輸出目錄")
	}
	theme, out := os.Args[1], os.Args[2]
	var pack struct{ Assets []sceneProbeRecord }
	raw, err := os.ReadFile(filepath.Join(theme, "hd.json"))
	sceneProbeMust(err)
	sceneProbeMust(json.Unmarshal(raw, &pack))
	groups := map[string][]sceneProbeRecord{}
	for _, a := range pack.Assets {
		group := strings.Split(a.Key, ".")[0]
		groups[group] = append(groups[group], a)
	}
	names := make([]string, 0, len(groups))
	for name := range groups {
		names = append(names, name)
	}
	sort.Strings(names)
	g := &sceneProbeGame{Theme: theme, Out: out}
	seen := map[string]bool{}
	add := func(a sceneProbeRecord) {
		if !seen[a.Key] {
			seen[a.Key] = true
			g.Samples = append(g.Samples, a)
		}
	}
	// 固定各家族排序後的首／中／末，另納入七像素完整長邊框。選樣先於測試，不挑通過者。
	for _, name := range names {
		rows := groups[name]
		sort.Slice(rows, func(i, j int) bool { return rows[i].Key < rows[j].Key })
		for _, i := range []int{0, len(rows) / 2, len(rows) - 1} {
			add(rows[i])
		}
	}
	for _, a := range pack.Assets {
		if a.Key == "FRAME..7" {
			add(a)
		}
	}
	raw, err = json.MarshalIndent(g.Samples, "", "  ")
	sceneProbeMust(err)
	sceneProbeMust(os.WriteFile(filepath.Join(out, "selection.json"), append(raw, '\n'), 0644))
	ebiten.SetWindowSize(960, 600)
	ebiten.SetWindowTitle("黑暗之后：場景素材抽驗")
	sceneProbeMust(ebiten.RunGame(g))
	g.Backend.close()
	passed := true
	for _, r := range g.Results {
		passed = passed && r.PixelByteDiff == 0
	}
	result := map[string]any{"passed": passed, "state_injection": false, "layout_only": true, "gameplay_replay": false, "groups": len(groups), "samples": len(g.Samples), "cases": len(g.Results), "selection": "每家族鍵排序首／中／末，另加FRAME..7", "results": g.Results, "scope": "正式Go命令畫布與GPU後端；原版／HD、文字遮擋與色盤變化，非實際房間或結局流程"}
	raw, err = json.MarshalIndent(result, "", "  ")
	sceneProbeMust(err)
	sceneProbeMust(os.WriteFile(filepath.Join(out, "checks.json"), append(raw, '\n'), 0644))
	if !passed {
		panic("GPU與CPU參考輸出不同")
	}
	fmt.Printf("%d個家族、%d個素材、%d項輸出對照通過\n", len(groups), len(g.Samples), len(g.Results))
}
