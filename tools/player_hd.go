// HD 由繪製前的原始來源及目的頁命令辨識；像素只核遮擋，不搜尋角色位置。
// 此檔只加入一般玩家建置，研究工具不需要連入可選 HD 載入器。
package main

import (
	"bytes"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"image"
	"image/draw"
	"os"
	"path/filepath"
	"strings"

	"github.com/wicanr2/dosgolem/oracle"
)

type hdAssetRecord struct {
	Key, Original, Image, OriginalSHA256, SHA256 string
	Indexed, IndexedSHA256                       string
	SourceSHA256                                 string `json:"source_block_sha256"`
	SourceBytes                                  int    `json:"source_block_bytes"`
	SourceHeader                                 string `json:"source_header_hex"`
}

type hdPixel struct {
	X, Y  int
	RGB   uint32
	Index byte
}

type hdAsset struct {
	Key          string
	W, H         int
	Pixels       []hdPixel
	Image        *playerImageAsset
	SourceSHA256 string
	SourceBytes  int
	Colors       map[byte]uint32
}

type hdLayer struct {
	Assets         []*hdAsset
	BySourceHeader map[string][]*hdAsset
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
	layer, seen := &hdLayer{BySourceHeader: map[string][]*hdAsset{}}, map[string]bool{}
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
		header, err := hex.DecodeString(record.SourceHeader)
		if err != nil || len(header) != 8 || record.SourceBytes < 8 || record.SourceBytes > 1<<20 || len(record.SourceSHA256) != 64 ||
			int(binary.LittleEndian.Uint16(header[:2])) != h || int(header[6])*4 != w {
			return fail(record.Key, fmt.Errorf("缺少完整的原版影像來源"))
		}
		asset := &hdAsset{Key: record.Key, W: w, H: h, SourceSHA256: record.SourceSHA256, SourceBytes: record.SourceBytes, Colors: map[byte]uint32{}}
		indexedPath, err := hdPath(root, record.Indexed)
		if err != nil {
			return fail(record.Key, err)
		}
		indexed, err := os.ReadFile(indexedPath)
		if err != nil || len(indexed) != w*h || len(record.IndexedSHA256) != 64 || digest(indexed) != record.IndexedSHA256 {
			return fail(record.Key, fmt.Errorf("原版色號來源失配"))
		}
		colors := map[uint32]bool{}
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
				pixel := hdPixel{X: x, Y: y, Index: indexed[y*w+x], RGB: uint32(original.Pix[i])<<16 | uint32(original.Pix[i+1])<<8 | uint32(original.Pix[i+2])}
				asset.Pixels = append(asset.Pixels, pixel)
				colors[pixel.RGB] = true
				if rgb, exists := asset.Colors[pixel.Index]; exists && rgb != pixel.RGB {
					return fail(record.Key, fmt.Errorf("原版色號對應不一致"))
				}
				asset.Colors[pixel.Index] = pixel.RGB
			}
		}
		// 純色及過短的幾何邊緣保留原版，不將它們當作可辨識圖像。
		if w < 8 || h < 8 || len(asset.Pixels) < 64 || len(colors) < 2 {
			return fail(record.Key, fmt.Errorf("來源缺乏可辨識的完整圖像資訊"))
		}
		asset.Image = &playerImageAsset{W: w, H: h, Index: indexed, Alpha: make([]byte, w*h), HD: painted.Pix, Reference: make([]byte, w*h*3)}
		for y := 0; y < h; y++ {
			for x := 0; x < w; x++ {
				i := y*w + x
				j := y*original.Stride + x*4
				asset.Image.Alpha[i] = original.Pix[j+3]
				copy(asset.Image.Reference[i*3:i*3+3], original.Pix[j:j+3])
			}
		}
		layer.Assets = append(layer.Assets, asset)
		layer.BySourceHeader[record.SourceHeader] = append(layer.BySourceHeader[record.SourceHeader], asset)
	}
	return layer
}

func (h *hdLayer) Available() bool { return len(h.Assets) > 0 }
func (h *hdLayer) Invalidate()     {} // 視窗及偏好不撤除來源命令。

func (h *hdLayer) Lookup(o *oracle.Oracle, command sourceTileCommand) *playerImageAsset {
	group := h.BySourceHeader[hex.EncodeToString(command.Header[:])]
	hashes := map[int]string{}
	pal := o.Palette()
	var fallback *playerImageAsset
	for _, asset := range group {
		if command.X < 0 || command.Y < 0 || command.X+asset.W > 320 || command.Y+asset.H > 200 || command.Source.Linear()+uint32(asset.SourceBytes-8) > 0xa0000 || uint32(command.Source.Off)+uint32(asset.SourceBytes-8) > 65536 {
			continue
		}
		sha, ok := hashes[asset.SourceBytes]
		if !ok {
			raw := append([]byte(nil), command.Header[:]...)
			raw = append(raw, o.Bytes(command.Source, asset.SourceBytes-8)...)
			sha = digest(raw)
			hashes[asset.SourceBytes] = sha
		}
		if sha == asset.SourceSHA256 {
			if fallback == nil {
				fallback = asset.Image
			}
			matched := true
			for index, rgb := range asset.Colors {
				c := pal[index]
				if rgb != uint32(c[0])<<16|uint32(c[1])<<8|uint32(c[2]) {
					matched = false
					break
				}
			}
			if matched {
				return asset.Image
			}
		}
	}
	// 未匹配色盤時保留已核對來源；場景既有Reference檢查只繪原版色號。
	return fallback
}
