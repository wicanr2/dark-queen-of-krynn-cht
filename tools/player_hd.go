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

	"github.com/hajimehoshi/ebiten/v2"
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
	Texture      *ebiten.Image
	SourceSHA256 string
	SourceBytes  int
}

type hdMatch struct {
	Asset *hdAsset
	X, Y  int
	Page  uint32
}

type hdLayer struct {
	Assets         []*hdAsset
	Hash           string
	Matches        []hdMatch
	Visible        []hdMatch
	Commands       []hdMatch
	BySourceHeader map[string][]*hdAsset
	Oracle         *oracle.Oracle
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
		asset := &hdAsset{Key: record.Key, W: w, H: h, SourceSHA256: record.SourceSHA256, SourceBytes: record.SourceBytes}
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
			}
		}
		// 純色及過短的幾何邊緣保留原版，不將它們當作可辨識圖像。
		if w < 8 || h < 8 || len(asset.Pixels) < 64 || len(colors) < 4 {
			return fail(record.Key, fmt.Errorf("來源缺乏可辨識的完整圖像資訊"))
		}
		asset.Texture = ebiten.NewImageFromImage(painted)
		layer.Assets = append(layer.Assets, asset)
		layer.BySourceHeader[record.SourceHeader] = append(layer.BySourceHeader[record.SourceHeader], asset)
	}
	return layer
}

func (h *hdLayer) Available() bool { return len(h.Assets) > 0 }
func (h *hdLayer) Invalidate() {
	h.Hash, h.Matches, h.Visible = "", nil, nil
}

// 在原版第一個影像像素之前，以原始 header＋payload 辨識來源及目的地。
// 不在完成的畫面中搜尋角色位置，未匹配的來源保持原版。
func (h *hdLayer) CaptureTile(o *oracle.Oracle, command sourceTileCommand) {
	h.Oracle = o
	group := h.BySourceHeader[hex.EncodeToString(command.Header[:])]
	if len(group) == 0 {
		return
	}
	hashes := map[int]string{}
	for _, asset := range group {
		if command.X < 0 || command.Y < 0 || command.X+asset.W > 320 || command.Y+asset.H > 200 ||
			command.Source.Linear()+uint32(asset.SourceBytes-8) > 0xa0000 {
			continue
		}
		sha, ok := hashes[asset.SourceBytes]
		if !ok {
			raw := append([]byte(nil), command.Header[:]...)
			raw = append(raw, o.Bytes(command.Source, asset.SourceBytes-8)...)
			sha = digest(raw)
			hashes[asset.SourceBytes] = sha
		}
		if sha != asset.SourceSHA256 {
			continue
		}
		match := hdMatch{asset, command.X, command.Y, command.Page}
		for i, previous := range h.Commands {
			if previous == match {
				// 同一圖格重畫時移到最新順序；前後遮擋沿原始命令。
				h.Commands = append(h.Commands[:i], h.Commands[i+1:]...)
				h.Commands = append(h.Commands, match)
				h.Hash = ""
				return
			}
		}
		if len(h.Commands) >= 4096 {
			panic("HD 來源命令超過有界容量")
		}
		h.Commands = append(h.Commands, match)
		h.Hash = ""
		return
	}
}

func (h *hdLayer) PrepareFrame(rgb []byte) {
	if h.Oracle == nil {
		return
	}
	page, known := nativeVisiblePage(h.Oracle)
	if !known {
		h.Hash, h.Matches = "", nil
		return
	}
	_, _, indices := h.Oracle.Screen()
	palette := h.Oracle.Palette()
	sha := fmt.Sprintf("%x:%s:%s", page, digest(indices), digest(rgb))
	if sha == h.Hash {
		return
	}
	h.Hash, h.Matches = sha, nil
	kept := h.Commands[:0]
	for _, command := range h.Commands {
		if command.Page != page {
			kept = append(kept, command)
			continue
		}
		matches := true
		paletteMatches := true
		// 這裡只核已攔截命令的遮擋／清除；位置與資產身分不從畫面推測。
		for _, p := range command.Asset.Pixels {
			i := (command.Y+p.Y)*320 + command.X + p.X
			if indices[i] != p.Index {
				matches = false
				break
			}
			color := palette[p.Index]
			if uint32(color[0])<<16|uint32(color[1])<<8|uint32(color[2]) != p.RGB {
				paletteMatches = false
			}
		}
		if matches {
			kept = append(kept, command)
			if paletteMatches {
				h.Matches = append(h.Matches, command)
			}
		}
	}
	h.Commands = kept
}

func (h *hdLayer) Draw(screen *ebiten.Image, rgb []byte, protected [][4]int, held bool) {
	if !held {
		h.PrepareFrame(rgb)
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
