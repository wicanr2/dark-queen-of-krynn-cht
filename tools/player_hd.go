// HD 只比對原始可見像素；不讀寫遊戲規則、資源索引或存檔。
// 此檔只加入一般玩家建置，研究工具不需要連入可選 HD 載入器。
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"image"
	"image/draw"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/hajimehoshi/ebiten/v2"
)

type hdAssetRecord struct {
	Key, Original, Image, OriginalSHA256, SHA256 string
}

type hdPixel struct {
	X, Y int
	RGB  uint32
}

type hdAsset struct {
	Key          string
	W, H         int
	Pixels       []hdPixel
	Colors       []uint32
	ColorAnchors map[uint32]hdPixel
	Texture      *ebiten.Image
}

type hdMatch struct {
	Asset *hdAsset
	X, Y  int
}

type hdLayer struct {
	Assets  []*hdAsset
	Hash    string
	Matches []hdMatch
	Visible []hdMatch
}

func init() { playerHDLoader = loadHDLayer }

func hdPath(root, name string) (string, error) {
	clean := filepath.Clean(name)
	if name == "" || filepath.IsAbs(clean) || clean == ".." || strings.HasPrefix(clean, ".."+string(filepath.Separator)) {
		return "", fmt.Errorf("HD 素材路徑越界")
	}
	return filepath.Join(root, clean), nil
}

func hdPNG(root, name, want string) (*image.NRGBA, error) {
	path, err := hdPath(root, name)
	if err != nil {
		return nil, err
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	if len(want) != 64 || digest(raw) != want {
		return nil, fmt.Errorf("HD 素材雜湊失配：%s", name)
	}
	decoded, _, err := image.Decode(bytes.NewReader(raw))
	if err != nil {
		return nil, err
	}
	r := image.NewNRGBA(image.Rect(0, 0, decoded.Bounds().Dx(), decoded.Bounds().Dy()))
	draw.Draw(r, r.Bounds(), decoded, decoded.Bounds().Min, draw.Src)
	return r, nil
}

func loadHDLayer(root string) playerHDRenderer {
	path := filepath.Join(root, "hd.json")
	raw, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return nil
	}
	var manifest struct {
		Version, Scale int
		Ready          bool
		Assets         []hdAssetRecord
	}
	if err == nil {
		err = json.Unmarshal(raw, &manifest)
	}
	if err != nil || manifest.Version != 1 || manifest.Scale != 3 || !manifest.Ready || len(manifest.Assets) == 0 || len(manifest.Assets) > 4096 {
		fmt.Fprintln(os.Stderr, "HD 主題未就緒，維持原版美術")
		return nil
	}
	layer, seen := &hdLayer{}, map[string]bool{}
	fail := func(key string, err error) playerHDRenderer {
		fmt.Fprintf(os.Stderr, "HD 主題 %s 無法完整載入，維持原版美術：%v\n", key, err)
		return nil
	}
	for _, record := range manifest.Assets {
		if record.Key == "" || seen[record.Key] {
			return fail(record.Key, fmt.Errorf("重複或空白 HD 來源"))
		}
		seen[record.Key] = true
		original, err := hdPNG(root, record.Original, record.OriginalSHA256)
		if err != nil {
			return fail(record.Key, err)
		}
		painted, err := hdPNG(root, record.Image, record.SHA256)
		if err != nil {
			return fail(record.Key, err)
		}
		w, h := original.Bounds().Dx(), original.Bounds().Dy()
		if w < 1 || h < 1 || w > 320 || h > 200 || painted.Bounds().Dx() != w*3 || painted.Bounds().Dy() != h*3 {
			return fail(record.Key, fmt.Errorf("HD 尺寸不符"))
		}
		asset := &hdAsset{Key: record.Key, W: w, H: h, ColorAnchors: map[uint32]hdPixel{}}
		for y := 0; y < h; y++ {
			for x := 0; x < w; x++ {
				i := y*original.Stride + x*4
				a := original.Pix[i+3]
				if a != 0 && a != 255 {
					return fail(record.Key, fmt.Errorf("原版 alpha 必須為0或255"))
				}
				for yy := 0; yy < 3; yy++ {
					for xx := 0; xx < 3; xx++ {
						j := (y*3+yy)*painted.Stride + (x*3+xx)*4
						if painted.Pix[j+3] != a {
							return fail(record.Key, fmt.Errorf("HD 遮罩超出原版前景"))
						}
					}
				}
				if a == 0 {
					continue
				}
				pixel := hdPixel{X: x, Y: y, RGB: uint32(original.Pix[i])<<16 | uint32(original.Pix[i+1])<<8 | uint32(original.Pix[i+2])}
				asset.Pixels = append(asset.Pixels, pixel)
				if _, ok := asset.ColorAnchors[pixel.RGB]; !ok {
					asset.Colors = append(asset.Colors, pixel.RGB)
					asset.ColorAnchors[pixel.RGB] = pixel
				}
			}
		}
		// 純色及過短的幾何邊緣保留原版，不將它們當作可辨識圖像。
		if w < 8 || h < 8 || len(asset.Pixels) < 64 || len(asset.Colors) < 4 {
			return fail(record.Key, fmt.Errorf("來源缺乏可辨識的完整圖像資訊"))
		}
		asset.Texture = ebiten.NewImageFromImage(painted)
		layer.Assets = append(layer.Assets, asset)
	}
	// 小型地形先畫，較大的前景／插畫後畫；只在原版像素仍完整吻合時使用。
	sort.SliceStable(layer.Assets, func(i, j int) bool {
		return layer.Assets[i].W*layer.Assets[i].H < layer.Assets[j].W*layer.Assets[j].H
	})
	return layer
}

func (h *hdLayer) Available() bool { return len(h.Assets) > 0 }
func (h *hdLayer) Invalidate() {
	h.Hash, h.Matches, h.Visible = "", nil, nil
}

func (h *hdLayer) find(rgb []byte) {
	sha := digest(rgb)
	if sha == h.Hash {
		return
	}
	h.Hash, h.Matches = sha, nil
	positions := map[uint32][]int{}
	for i := 0; i < 320*200; i++ {
		c := uint32(rgb[i*3])<<16 | uint32(rgb[i*3+1])<<8 | uint32(rgb[i*3+2])
		positions[c] = append(positions[c], i)
	}
	for _, asset := range h.Assets {
		var anchor hdPixel
		fewest, possible := 320*200+1, true
		for _, c := range asset.Colors {
			count := len(positions[c])
			if count == 0 {
				possible = false
				break
			}
			if count < fewest {
				fewest, anchor = count, asset.ColorAnchors[c]
			}
		}
		if !possible {
			continue
		}
		for _, position := range positions[anchor.RGB] {
			x, y := position%320-anchor.X, position/320-anchor.Y
			if x < 0 || y < 0 || x+asset.W > 320 || y+asset.H > 200 {
				continue
			}
			matches := true
			// 先檢查分散位置，避免重複色地形每次走完全文。
			for j := 0; j < 8; j++ {
				p := asset.Pixels[j*(len(asset.Pixels)-1)/7]
				i := ((y+p.Y)*320 + x + p.X) * 3
				if uint32(rgb[i])<<16|uint32(rgb[i+1])<<8|uint32(rgb[i+2]) != p.RGB {
					matches = false
					break
				}
			}
			if !matches {
				continue
			}
			for _, p := range asset.Pixels {
				i := ((y+p.Y)*320 + x + p.X) * 3
				if uint32(rgb[i])<<16|uint32(rgb[i+1])<<8|uint32(rgb[i+2]) != p.RGB {
					matches = false
					break
				}
			}
			if matches {
				h.Matches = append(h.Matches, hdMatch{asset, x, y})
			}
		}
	}
}

func (h *hdLayer) Draw(screen *ebiten.Image, rgb []byte, protected [][4]int, held bool) {
	if !held {
		h.find(rgb)
		h.Visible = nil
		for _, match := range h.Matches {
			covered := false
			for _, r := range protected {
				if match.X < r[2] && match.X+match.Asset.W > r[0] && match.Y < r[3] && match.Y+match.Asset.H > r[1] {
					covered = true
					break
				}
			}
			if !covered {
				h.Visible = append(h.Visible, match)
			}
		}
	}
	for _, match := range h.Visible {
		op := &ebiten.DrawImageOptions{}
		op.GeoM.Translate(float64(match.X*3), float64(match.Y*3))
		screen.DrawImage(match.Asset.Texture, op)
	}
}
