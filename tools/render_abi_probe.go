// 無視窗函式對照：實際連入玩家的 driver 與場景模型，前端型別僅作無繪圖接頭。
package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"

	"github.com/wicanr2/dosgolem/oracle"
)

type paintReturn struct {
	Addr   oracle.Addr
	SS, SP uint16
}
type renderPrimitive struct {
	Name, Kind      string
	Segment, Offset uint16
	Prefix          string
}
type sourceTileCommand struct {
	Header [8]byte
	Source oracle.Addr
	X, Y   int
	Page   uint32
}
type playerImageAsset struct {
	W, H                        int
	Index, Alpha, HD, Reference []byte
}
type playerHDRenderer interface {
	Lookup(*oracle.Oracle, sourceTileCommand) *playerImageAsset
}
type renderImageSource struct {
	Command sourceTileCommand
	Bound   bool
}
type renderTransaction struct {
	Return paintReturn
	Origin oracle.Addr
	Step   uint64
	Image  *renderImageSource
	Owned  *ownedDriver
	Kind   string
}
type probeText struct{ Words []int }
type probeBackend struct{}

func (probeBackend) close() {}

type playerRenderOwner struct {
	Oracle   *oracle.Oracle
	Scene    renderScene
	Pending  []renderTransaction
	HD       playerHDRenderer
	Counters map[string]uint64
	Assets   map[string]*sceneAsset
	Text     *probeText
	Backend  probeBackend
	LayerKey string
}

func must(err error) {
	if err != nil {
		panic(err)
	}
}
func digest(raw []byte) string { h := sha256.Sum256(raw); return hex.EncodeToString(h[:]) }
func nativePageLayout(o *oracle.Oracle) bool {
	v := o.VideoLayoutState()
	return v.Mode == 0x13 && v.Unchained && v.Pitch == 80 && v.LineCompare >= 400
}
func nativeVisiblePage(o *oracle.Oracle) (uint32, bool) {
	v := o.VideoLayoutState()
	return v.DisplayStart, nativePageLayout(o) && v.DisplayStart <= 0xc000 && v.DisplayStart%0x4000 == 0
}

type probeCase struct {
	Name        string
	Entry       oracle.Addr
	Args        []uint16
	Font        []byte
	Image       *sourceTileCommand
	Data        []byte
	FrameAt     uint64
	IRQAt       uint64
	Reject      bool
	Pattern     bool
	Mask        byte
	MemoryCopy  bool
	Upload      bool
	VideoCopy   bool
	VideoMode   byte
	OwnedSource bool
	AliasReturn bool
	RawTransfer bool
	RawMasked   bool
	MaskData    []byte
	Temporary   bool
	ShiftMasked bool
	Clear       bool
	RawRLE      bool
	StackSS     uint16
	MaskColumn  bool
	SamePage    bool
	MaskedRLE   bool
}
type probeResult struct {
	Name                       string
	DOSCost                    bool
	Native, Direct             oracle.RenderProbeCPU
	NativeSteps, DirectSteps   uint64
	NativeWrites, DirectWrites int
	RAMDiff, VGAPlanesDiff     int
	FirstRAM                   []string
	VideoEqual                 bool
	SourceOwnershipEqual       bool
	Counters                   map[string]uint64
	Checkpoints                map[string][][2]uint64
	Frames                     [2][]oracle.RenderProbeFrame
	Passed                     bool
}

func main() {
	root, out := os.Args[1], os.Args[2]
	must(os.MkdirAll(out, 0755))
	var hooks struct{ NativeSteps []renderPrimitive }
	raw, err := os.ReadFile(filepath.Join(root, "docs/spec/005-render-hooks.json"))
	must(err)
	must(json.Unmarshal(raw, &hooks))
	base := filepath.Join(root, "workplace/input/dos/drkqueen")
	gate, err := oracle.Load(filepath.Join(base, "DQK.EXE"), base)
	must(err)
	boundaryChecks := 0
	for _, check := range []struct {
		Args []uint16
		Want bool
	}{
		{[]uint16{0x100, 0x7000, 0x200, 0x7100, 65}, false},
		{[]uint16{0, 0xa000, 0x200, 0x7100, 1}, true},
		{[]uint16{0x100, 0x7000, 0, 0xb800, 1}, true},
		{[]uint16{0, 0xa000, 0, 0xb800, 0}, false},
		{[]uint16{0xfff0, 0x9000, 0x200, 0x7100, 32}, true},
		{[]uint16{0x100, 0x7000, 0xfff0, 0xbfff, 32}, true},
	} {
		gate.RenderProbePrepare(oracle.Addr{Seg: 0x1e7, Off: 0x8c2}, oracle.Addr{}, check.Args, false)
		if renderTransactionTouchesVideo(gate, 0x11632) != check.Want {
			panic("RAM／顯存跨度的交易邊界失配")
		}
		boundaryChecks++
	}
	gate.Close()
	state := filepath.Join(root, "workplace/probe/battle-continuation-20261025/control-r1/final.state")
	cases := []probeCase{}
	for _, height := range []uint16{1, 3} {
		for _, width := range []uint16{2, 5, 10} {
			for _, plane := range []byte{1, 15} {
				data, colors := []byte{}, []byte{}
				for y := 0; y < int(height); y++ {
					data = append(data, 0xc3, 0x43, 0xf0, 0x0f, 0xaa, 0x82, 0x02, 0)
					for x := 0; x < 7; x++ {
						colors = append(colors, byte(x*31+y*7))
					}
				}
				c := probeCase{Name: fmt.Sprintf("masked-rle-%d-%d-%02x", height, width, plane), Entry: oracle.Addr{Seg: 0x1e7, Off: 0x57e}, Args: []uint16{0, height, 0, width, 0x100, 0x7000, 0x300}, Data: data, MaskData: colors, Mask: plane, MaskedRLE: true}
				cases = append(cases, c)
				c.Name += "-frame"
				c.FrameAt = 60
				cases = append(cases, c)
				c.Name += "-IRQ"
				c.IRQAt = 60
				c.FrameAt = 0
				cases = append(cases, c)
			}
		}
	}
	for _, entry := range []uint16{0x8c2, 0x918} {
		for _, mode := range []byte{0x40, 0x41} {
			for _, from := range []uint16{0, 7} {
				for _, mask := range []byte{5, 15} {
					to := uint16(7)
					if from != 0 {
						to = 0
					}
					c := probeCase{Name: fmt.Sprintf("overlap-%04x-%02x-%d-%02x", entry, mode, from, mask), Entry: oracle.Addr{Seg: 0x1e7, Off: entry}, Args: []uint16{from, 0xa000, to, 0xa000, 161}, VideoCopy: true, VideoMode: mode, Mask: mask, SamePage: true}
					cases = append(cases, c)
					c.Name += "-frame"
					c.FrameAt = 300
					cases = append(cases, c)
				}
			}
		}
	}
	for _, height := range []uint16{1, 3, 17} {
		for _, mask := range []uint16{0, 0xf0f0, 0xffff} {
			for _, plane := range []byte{1, 15} {
				c := probeCase{Name: fmt.Sprintf("mask-fill-%d-%04x-%02x", height, mask, plane), Entry: oracle.Addr{Seg: 0x1e7, Off: 0x3b0}, Args: []uint16{0x3509, mask, height, 12}, Mask: plane}
				cases = append(cases, c)
				c.Name += "-frame"
				c.FrameAt = 40
				cases = append(cases, c)
				data := make([]byte, 32)
				for i := range data {
					data[i] = byte(i * 37)
				}
				c = probeCase{Name: fmt.Sprintf("mask-column-%d-%04x-%02x", height, mask, plane), Entry: oracle.Addr{Seg: 0x1e7, Off: 0xd31}, Args: []uint16{height, mask, 0x100, 0x7000, 3}, Mask: plane, Data: data, MaskColumn: true}
				cases = append(cases, c)
				c.Name += "-frame"
				c.FrameAt = 40
				cases = append(cases, c)
			}
		}
	}
	for _, width := range []int{1, 17, 64} {
		for _, height := range []uint16{1, 3} {
			data := []byte{}
			for y := 0; y < int(height); y++ {
				data = append(data, byte(width))
				for x := 0; x < width; x++ {
					data = append(data, byte(x*11+y*31))
				}
				data = append(data, 0)
			}
			c := probeCase{Name: fmt.Sprintf("raw-rle-%d-%d", width, height), Entry: oracle.Addr{Seg: 0x1e7, Off: 0xdb6}, Args: []uint16{0, 0, height, 0, 0, 0x100, 0x7000}, RawRLE: true, Data: data, Mask: 5}
			cases = append(cases, c)
			c.Name += "-frame"
			c.FrameAt = 31
			cases = append(cases, c)
		}
	}
	for _, page := range []uint16{0xa000, 0xa400, 0xac00} {
		for _, count := range []uint16{0, 2, 18, 16000} {
			for _, mode := range []byte{0, 0x40} {
				for _, color := range []uint16{0, 0x3709} {
					c := probeCase{Name: fmt.Sprintf("clear-%04x-%d-%02x-%04x", page, count, mode, color), Entry: oracle.Addr{Seg: 0x1e7, Off: 0x8a2}, Args: []uint16{0, page, count, color}, Clear: true, VideoMode: mode, Mask: 5}
					cases = append(cases, c)
					if count == 18 && mode == 0 {
						c.Name += "-frame"
						c.FrameAt = 12
						cases = append(cases, c)
					}
				}
			}
		}
	}
	for _, font := range [][]byte{{0, 0, 0, 0, 0, 0, 0, 0}, {255, 255, 255, 255, 255, 255, 255, 255}, {0x81, 0x42, 0x24, 0x18, 0x18, 0x24, 0x42, 0x81}} {
		cases = append(cases, probeCase{Name: fmt.Sprintf("glyph-%x", font), Entry: oracle.Addr{Seg: 0x1e7, Off: 0x2171}, Args: []uint16{15, 0, 0x100, 0x7000}, Font: font})
	}
	for _, h := range []uint16{1, 2, 8, 48} {
		for _, word := range []bool{false, true} {
			entry := uint16(0x348)
			color := uint16(7)
			if word {
				entry = 0x37b
				color = 0x0707
			}
			cases = append(cases, probeCase{Name: fmt.Sprintf("fill-%t-%d", word, h), Entry: oracle.Addr{Seg: 0x1e7, Off: entry}, Args: []uint16{h, 12, color}})
		}
	}
	for _, h := range []uint16{1, 17} {
		for _, mask := range []byte{15, 5} {
			cases = append(cases, probeCase{Name: fmt.Sprintf("fill-word-alternating-%d-%02x", h, mask),
				Entry: oracle.Addr{Seg: 0x1e7, Off: 0x37b}, Args: []uint16{h, 12, 0x0e03}, Mask: mask})
		}
	}
	for _, entry := range []uint16{0x8c2, 0x918} {
		for _, count := range []uint16{64, 65, 161, 16000} {
			for _, mask := range []byte{1, 5, 15} {
				for _, page := range []uint16{0xa000, 0xac00} {
					data := make([]byte, int(count))
					for i := range data {
						data[i] = byte(i*37 + i/11)
					}
					c := probeCase{Name: fmt.Sprintf("upload-%04x-%d-%02x-%04x", entry, count, mask, page),
						Entry: oracle.Addr{Seg: 0x1e7, Off: entry}, Args: []uint16{0x100, 0x7000, 0, page, count},
						Upload: true, Mask: mask, Data: data}
					cases = append(cases, c)
					if count == 161 && mask == 15 {
						c.Name += "-frame"
						c.FrameAt = 30
						cases = append(cases, c)
					}
				}
			}
		}
		for _, args := range [][]uint16{
			{0x100, 0x7000, 15999, 0xa000, 64},
			{0xfff0, 0x7000, 0, 0xa000, 64},
		} {
			cases = append(cases, probeCase{Name: fmt.Sprintf("upload-%04x-reject-%04x-%04x-%04x", entry, args[0], args[1], args[2]),
				Entry: oracle.Addr{Seg: 0x1e7, Off: entry}, Args: args, Upload: true, Reject: true})
		}
	}
	for _, entry := range []uint16{0x8c2, 0x918} {
		for _, pages := range [][2]uint16{{0xa000, 0xac00}, {0xac00, 0xa000}} {
			for _, mode := range []byte{0x40, 0x41} {
				for _, mask := range []byte{1, 5, 15} {
					for _, count := range []uint16{64, 65, 16000} {
						c := probeCase{Name: fmt.Sprintf("pagecopy-%04x-%04x-%04x-%02x-%02x-%d", entry, pages[0], pages[1], mode, mask, count),
							Entry: oracle.Addr{Seg: 0x1e7, Off: entry}, Args: []uint16{0, pages[0], 0, pages[1], count},
							VideoCopy: true, VideoMode: mode, Mask: mask, OwnedSource: count != 64}
						cases = append(cases, c)
						if count == 64 && mask == 15 {
							// r1實際原版返回步數減去原尾端指令，定位REP前後的事件。
							step := uint64(303)
							if entry == 0x918 {
								step = 299
								if pages[0] > pages[1] {
									step = 296
								}
							} else if pages[0] > pages[1] {
								step = 298
							}
							for _, delta := range []uint64{1, 2} {
								c.Name = fmt.Sprintf("pagecopy-event-%04x-%04x-%02x-%d", entry, pages[0], mode, delta)
								c.FrameAt = step + delta
								c.Reject = false
								cases = append(cases, c)
							}
						}
					}
				}
			}
		}
		for _, args := range [][]uint16{
			{15999, 0xa000, 0, 0xac00, 64},
			{0, 0xa000, 15999, 0xac00, 64},
		} {
			cases = append(cases, probeCase{Name: fmt.Sprintf("pagecopy-reject-%04x-%04x-%04x-%04x", entry, args[0], args[2], args[3]),
				Entry: oracle.Addr{Seg: 0x1e7, Off: entry}, Args: args, VideoCopy: true, VideoMode: 0x40, Mask: 15, Reject: true})
		}
	}
	for _, h := range []uint16{1, 2, 17} {
		for _, mask := range []byte{15, 5} {
			for variant := 0; variant < 3; variant++ {
				data := make([]byte, 32)
				for i := range data {
					if variant == 1 {
						data[i] = byte(2 + i%2*5)
					} else if variant == 2 {
						data[i] = byte(3 + i*7)
					}
				}
				c := probeCase{Name: fmt.Sprintf("pattern-%d-%02x-%d", h, mask, variant),
					Entry: oracle.Addr{Seg: 0x1e7, Off: 0x3ee}, Args: []uint16{h, 12, 0x100, 0x7000, 3},
					Data: data, Pattern: true, Mask: mask}
				if h == 17 && variant == 2 {
					c.FrameAt = 100
				}
				cases = append(cases, c)
			}
		}
	}
	var pack struct {
		Assets []struct {
			Key    string
			File   string `json:"source_file"`
			Offset int    `json:"source_offset"`
			Count  int    `json:"source_block_bytes"`
		}
	}
	for _, height := range []uint16{1, 3} {
		for _, width := range []uint16{1, 2, 8} {
			for _, shift := range []uint16{0, 3, 7} {
				for _, planeMask := range []byte{1, 15} {
					for edge := 0; edge < 2; edge++ {
						data, mask := make([]byte, int(height)*int(width)), make([]byte, int(height)*int(width))
						for i := range data {
							data[i], mask[i] = byte(i*29+3), byte(i*51)
						}
						left, right := uint16(255), uint16(255)
						if edge == 1 {
							left, right = 0xf0, 0x0f
						}
						c := probeCase{Name: fmt.Sprintf("shifted-mask-%d-%d-%d-%02x-%d", height, width, shift, planeMask, edge),
							Entry: oracle.Addr{Seg: 0x1e7, Off: 0xbbc}, Args: []uint16{0x100, 0x7000, 0x300, 0, height, width, 0, left, right, shift},
							Data: data, MaskData: mask, Mask: planeMask, ShiftMasked: true}
						cases = append(cases, c)
						if height == 3 && width == 8 && shift == 7 && planeMask == 15 && edge == 1 {
							c.Name += "-frame"
							c.FrameAt = 333
							cases = append(cases, c)
						}
						if height == 3 && width == 8 && shift == 3 && planeMask == 15 && edge == 0 {
							c.Name += "-temporary"
							c.Temporary = true
							cases = append(cases, c)
						}
					}
				}
			}
		}
	}
	for _, height := range []uint16{1, 7} {
		for _, width := range []uint16{2, 14} {
			for _, planeMask := range []byte{1, 5, 15} {
				for variant := 0; variant < 3; variant++ {
					data, mask := make([]byte, int(height)*int(width)), make([]byte, int(height)*int(width))
					for i := range data {
						data[i] = byte(i * 37)
						mask[i] = byte(variant * 0x7f)
						if variant == 2 && i%3 == 0 {
							mask[i], data[i] = 255, 0
						}
					}
					c := probeCase{Name: fmt.Sprintf("masked-blit-%d-%d-%02x-%d", height, width, planeMask, variant),
						Entry: oracle.Addr{Seg: 0x1e7, Off: 0x2ba}, Args: []uint16{0x100, 0x7000, 0x300, 0, height, width, 0},
						Data: data, MaskData: mask, Mask: planeMask, RawMasked: true}
					cases = append(cases, c)
					if height == 7 && variant == 2 {
						c.Name += "-frame"
						c.FrameAt = 333
						cases = append(cases, c)
					}
				}
			}
		}
	}
	cases = append(cases, probeCase{Name: "masked-blit-BX-overflow", Entry: oracle.Addr{Seg: 0x1e7, Off: 0x2ba},
		Args: []uint16{0x7ff0, 0x7000, 0x300, 0, 1, 16, 0}, Data: make([]byte, 16), MaskData: make([]byte, 16), RawMasked: true, Mask: 15})
	for _, entry := range []uint16{0x241, 0x286, 0x212e, 0xc46} {
		for _, height := range []uint16{1, 7} {
			for _, width := range []uint16{8, 12} {
				for _, mask := range []byte{1, 5, 15} {
					data := make([]byte, int(height)*int(width))
					for i := range data {
						data[i] = byte(i * 37)
						if i%3 == 2 {
							data[i] = 255
						}
					}
					args := []uint16{0x100, 0x7000, height, width, 0}
					if entry == 0x212e {
						args = append(args, 255)
					}
					cases = append(cases, probeCase{Name: fmt.Sprintf("source-blit-%04x-%d-%d-%02x", entry, height, width, mask),
						Entry: oracle.Addr{Seg: 0x1e7, Off: entry}, Args: args, Data: data, Mask: mask, RawTransfer: true})
				}
			}
		}
	}
	for _, entry := range []uint16{0x8c2, 0x918, 0x956} {
		args := []uint16{0x100, 0x7000, 0x200, 0x7100, 65}
		if entry == 0x956 {
			args = []uint16{0x7000, 0x7100}
		}
		cases = append(cases, probeCase{Name: fmt.Sprintf("RAM-copy-%04x", entry), Entry: oracle.Addr{Seg: 0x1e7, Off: entry}, Args: args, MemoryCopy: true})
	}
	raw, err = os.ReadFile(filepath.Join(root, "workplace/probe/player-current/hd/hd.json"))
	must(err)
	must(json.Unmarshal(raw, &pack))
	for _, asset := range pack.Assets {
		if asset.Key != "CPIC..6" && asset.Key != "PICA.7.1" {
			continue
		}
		raw, err := os.ReadFile(filepath.Join(base, asset.File))
		must(err)
		block := raw[asset.Offset : asset.Offset+asset.Count]
		var header [8]byte
		copy(header[:], block[:8])
		data := append([]byte(nil), block[8:]...)
		for _, method := range []byte{header[7], 16} {
			if method == 16 && header[7] != 21 {
				continue
			}
			hh := header
			hh[7] = method
			h, w := binary.LittleEndian.Uint16(hh[:2]), uint16(hh[6])*4
			c := sourceTileCommand{Header: hh, Source: oracle.Addr{Seg: 0x7000, Off: 0x100}, X: 8, Y: 31}
			entry := oracle.Addr{Seg: 0x162e, Off: 0x19d4}
			args := []uint16{0x100, 0x7000, 31, 8, w * h / 4, h, w / 4, 4, 0, uint16(method & 15)}
			if method == 18 {
				entry.Off = 0x1bd9
				args = []uint16{31, 8, h, w / 4, 4, 0, 0, 0, 0x100, 0x7000, 0}
			}
			cases = append(cases, probeCase{Name: fmt.Sprintf("image-%s-%02x", asset.Key, method), Entry: entry, Args: args, Image: &c, Data: data})
		}
	}

	// 新格式按來源檔抽樣；全部素材另由離線解碼比對覆蓋。
	var inventory struct {
		Records []struct {
			Key, Source                          string
			Offset, Bytes, Method, Width, Height int
		}
	}
	raw, err = os.ReadFile(filepath.Join(root, "workplace/probe/hd-assets-20261026-r1/inventory.json"))
	must(err)
	must(json.Unmarshal(raw, &inventory))
	seenFormats := map[string]bool{}
	for _, asset := range inventory.Records {
		if asset.Method != 17 && asset.Method != 23 || asset.Width < 1 || asset.Width > 320 || asset.Height < 1 || asset.Height > 200 {
			continue
		}
		family := fmt.Sprintf("%s-%d", asset.Source, asset.Method)
		if seenFormats[family] {
			continue
		}
		seenFormats[family] = true
		path, err := filepath.Glob(filepath.Join(base, "*", asset.Source+".TLB"))
		must(err)
		if len(path) != 1 {
			panic("來源檔歧義")
		}
		blob, err := os.ReadFile(path[0])
		must(err)
		block := blob[asset.Offset : asset.Offset+asset.Bytes]
		var hh [8]byte
		copy(hh[:], block[:8])
		h, w := uint16(asset.Height), uint16(asset.Width)
		y := uint16(31)
		if int(y)+asset.Height > 200 {
			y = 0
		}
		x := uint16(8)
		if int(x)+asset.Width > 320 {
			x = 0
		}
		c := sourceTileCommand{Header: hh, Source: oracle.Addr{Seg: 0x7000, Off: 0x100}, X: int(x), Y: int(y)}
		entry := oracle.Addr{Seg: 0x162e, Off: 0x19d4}
		args := []uint16{0x100, 0x7000, y, x, w * h / 4, h, w / 4, 4, 0, uint16(hh[7] & 15)}
		if asset.Method == 23 {
			entry.Off = 0x1b8a
			args = []uint16{y, x, h, w / 4, 4, 0, 0, 0, 0, 0x100, 0x7000}
		}
		cases = append(cases, probeCase{Name: fmt.Sprintf("image-%s-%02x", asset.Key, hh[7]), Entry: entry, Args: args, Image: &c, Data: append([]byte(nil), block[8:]...)})
	}
	for _, test := range append([]probeCase(nil), cases...) {
		if test.RawTransfer && test.Args[2] == 7 && test.Args[3] == 12 && test.Mask == 15 ||
			test.RawMasked && test.Args[4] == 7 && test.Args[5] == 14 && test.Mask == 15 && test.FrameAt == 0 && test.Name == "masked-blit-7-14-0f-2" ||
			test.Name == "glyph-8142241818244281" {
			c := test
			c.Name += "-temporary"
			c.Temporary = true
			cases = append(cases, c)
		}
		if test.Font != nil || test.Image != nil || test.Args[0] == 48 {
			c := test
			c.Name += "-frame"
			c.FrameAt = 400
			if c.Image != nil {
				c.FrameAt = 1000
			}
			cases = append(cases, c)
		}
		if test.Image != nil {
			c := test
			c.Name += "-alias-byte-high"
			c.AliasReturn = true
			c.Args = append([]uint16(nil), test.Args...)
			if c.Image.Header[7] != 23 {
				c.Args[len(c.Args)-1] |= 0x6800
			}
			cases = append(cases, c)
			c = test
			c.Name += "-reject-return"
			c.Reject = true
			cases = append(cases, c)
		}
	}
	for _, test := range append([]probeCase(nil), cases...) {
		if test.RawMasked {
			test.Name += "-byte"
			test.Entry = oracle.Addr{Seg: 0x1e7, Off: 0x30a}
			cases = append(cases, test)
		}
	}
	for _, test := range append([]probeCase(nil), cases...) {
		if test.FrameAt > 0 && (test.Clear || test.RawRLE || test.Font != nil || test.ShiftMasked) {
			test.Name += "-IRQ"
			test.IRQAt = test.FrameAt
			test.FrameAt = 0
			cases = append(cases, test)
		}
	}
	for _, test := range append([]probeCase(nil), cases...) {
		if test.ShiftMasked || test.RawTransfer && test.Entry.Off == 0xc46 {
			test.Name += "-mouse-stack"
			test.StackSS = 0x11c
			cases = append(cases, test)
		}
	}
	results := []probeResult{}
	for _, test := range cases {
		for _, dosCost := range []bool{false, true} {
			pair := make([]*oracle.Oracle, 2)
			var owner *playerRenderOwner
			var before [2][]byte
			res := probeResult{Name: test.Name, DOSCost: dosCost, Checkpoints: map[string][][2]uint64{}, SourceOwnershipEqual: true}
			for side := 0; side < 2; side++ {
				o, err := oracle.Load(filepath.Join(base, "DQK.EXE"), base)
				must(err)
				pair[side] = o
				must(o.LoadStateFile(state))
				ret := oracle.Addr{Seg: 0x1e7, Off: 0x20}
				if test.Image != nil && !test.Reject {
					ret = oracle.Addr{Seg: 0x162e, Off: 0x2263}
					if test.Image.Header[7] == 18 {
						ret.Off = 0x21f3
					}
					if test.Image.Header[7] == 23 {
						ret.Off = 0x221f
					}
					if test.AliasReturn {
						ret = oracle.Addr{Seg: 0x17ab, Off: uint16(ret.Linear() - 0x17ab0)}
					}
				}
				o.RenderProbePrepare(test.Entry, ret, test.Args, dosCost)
				if test.StackSS != 0 {
					o.RenderProbeStackSS(test.StackSS)
				}
				if test.Clear {
					o.RenderProbeVideoMode(test.VideoMode, 2)
				}
				if test.Mask != 0 {
					o.RenderProbePlaneMask(test.Mask)
				}
				if test.RawMasked || test.ShiftMasked {
					o.RenderProbeVideoMode(0x40, 2)
					o.WriteBytes(oracle.Addr{Seg: test.Args[1], Off: test.Args[0]}, test.Data)
					o.WriteBytes(oracle.Addr{Seg: test.Args[1], Off: test.Args[2]}, test.MaskData)
				}
				if test.MaskedRLE {
					o.RenderProbeVideoMode(0x40, 2)
					o.WriteBytes(oracle.Addr{Seg: 0x7000, Off: 0x100}, test.Data)
					o.WriteBytes(oracle.Addr{Seg: 0x7000, Off: 0x300}, test.MaskData)
				}
				var sourceAsset *sceneAsset
				if test.VideoCopy {
					o.RenderProbeVideoMode(test.VideoMode, 2)
					sourceAsset = &sceneAsset{W: 320, H: 200, Index: make([]byte, 64000)}
					page := uint32(test.Args[1]-0xa000) * 16
					for off := 0; off < 16000; off++ {
						for plane := 0; plane < 4; plane++ {
							value := byte(off*37 + off/11 + plane*53)
							o.SetPresentationPlane(plane, page+uint32(off), value)
							sourceAsset.Index[off*4+plane] = value
						}
					}
				}
				var frames *[]oracle.RenderProbeFrame
				if test.FrameAt > 0 {
					frames = o.RenderProbeFrameAt(test.FrameAt)
				}
				if test.IRQAt > 0 {
					frames = o.RenderProbeIRQAt(test.IRQAt)
				}
				if test.Font != nil {
					o.WriteBytes(oracle.Addr{Seg: 0x7000, Off: 0x100}, test.Font)
				}
				if test.Image != nil {
					o.WriteBytes(test.Image.Source, test.Data)
				}
				if test.Pattern || test.MaskColumn || test.RawTransfer || test.RawRLE || test.Upload && test.Data != nil {
					o.WriteBytes(oracle.Addr{Seg: 0x7000, Off: 0x100}, test.Data)
				}
				before[side] = o.RenderProbeRAM()
				writes := 0
				o.OnVideoWriteEvent(func(v oracle.VideoWriteEvent) {
					if !v.Presentation {
						writes++
					}
				})
				if side == 1 {
					owner = &playerRenderOwner{Oracle: o, Counters: map[string]uint64{}, Assets: map[string]*sceneAsset{}}
					if test.Temporary {
						sourceAsset = &sceneAsset{W: 320, H: 200, Index: make([]byte, 64000)}
						for off := 0; off < 16000; off++ {
							for plane := 0; plane < 4; plane++ {
								sourceAsset.Index[off*4+plane] = o.PresentationPlane(plane, uint32(off))
							}
						}
						owner.Scene.record(owner.Scene.page(0, o.PresentationPlane), sourceAsset, 0, 0)
					}
					if test.OwnedSource {
						page := uint32(test.Args[1]-0xa000) * 16
						owner.Scene.record(owner.Scene.page(page, o.PresentationPlane), sourceAsset, 0, 0)
					}
					tx := renderTransaction{Return: paintReturn{ret, 0x333e, 0xe004}, Origin: test.Entry}
					if test.StackSS != 0 {
						tx.Return.SS = test.StackSS
					}
					if test.Image != nil {
						tx.Image = &renderImageSource{Command: *test.Image}
					}
					if renderTransactionTouchesVideo(o, test.Entry.Linear()+0xef00) {
						owner.Pending = append(owner.Pending, tx)
					}
					if test.Temporary {
						owner.Pending = append(owner.Pending, renderTransaction{Kind: "readback-scope"})
					}
					owner.installOwnedDrivers(hooks.NativeSteps)
				} else {
					for _, ea := range []uint32{0x12ef8, 0x12f95, 0x110d2, 0x110d8, 0x11107, 0x1110d, 0x12ebf, 0x12ec7, 0x10fd6, 0x10fd8, 0x11017, 0x11019} {
						entry := oracle.Addr{Seg: 0x1e7, Off: uint16(ea - 0x10d70)}
						key := fmt.Sprintf("%x", ea)
						o.OnCall(entry, func(*oracle.Oracle) {
							r := o.RenderProbeCPU()
							if len(res.Checkpoints[key]) < 3000 {
								res.Checkpoints[key] = append(res.Checkpoints[key], [2]uint64{o.Steps(), r.Cycles})
							}
						})
					}
				}
				must(o.RunUntil(oracle.At(ret), oracle.Budget(2_000_000)))
				if frames != nil {
					res.Frames[side] = append([]oracle.RenderProbeFrame(nil), (*frames)...)
				}
				if side == 0 {
					res.Native = o.RenderProbeCPU()
					res.NativeSteps = o.Steps()
					res.NativeWrites = writes
				} else {
					if len(owner.Pending) > 0 {
						owner.finishDriver(owner.Pending[0].Owned)
					}
					res.Direct = o.RenderProbeCPU()
					res.DirectSteps = o.Steps()
					res.DirectWrites = writes
					res.Counters = owner.Counters
					if test.Image != nil && !test.Reject {
						d := owner.Pending[0].Owned
						if d == nil || d.Kind != "image" || d.Asset == nil {
							res.SourceOwnershipEqual = false
						} else if d.Fallback {
							// 已有事件邊界契約允許整圖身分撤回；像素與機器效果仍須一致。
							res.SourceOwnershipEqual = test.FrameAt > 0 || test.IRQAt > 0
						} else {
							model := owner.Scene.page(d.Page, o.PresentationPlane)
							for i := range d.Asset.Index {
								if len(d.Asset.Alpha) != 0 && d.Asset.Alpha[i] == 0 { continue }
								cell := model.Cells[(d.Y+i/d.W)*320+d.X+i%d.W]
								res.SourceOwnershipEqual = res.SourceOwnershipEqual && cell.Asset == d.Asset && cell.Source == i && cell.Visible
							}
						}
					}
					if test.Temporary {
						for i, cell := range owner.Scene.page(0, o.PresentationPlane).Cells {
							res.SourceOwnershipEqual = res.SourceOwnershipEqual && cell.Asset == sourceAsset && cell.Source == i
						}
					}
					if test.OwnedSource {
						count, unit := int(test.Args[4]), 1
						if test.Entry.Off == 0x8c2 {
							unit = 2
						}
						start := 0
						if test.Args[1] > test.Args[3] {
							start = count % unit
						}
						model := owner.Scene.page(uint32(test.Args[3]-0xa000)*16, o.PresentationPlane)
						for i := 0; i < count/unit*unit; i++ {
							sourceOff := start + i
							if test.VideoMode == 0x41 && unit == 2 {
								sourceOff = start + i/2*2 + 1
							}
							for plane := 0; plane < 4; plane++ {
								if test.Mask&(1<<uint(plane)) == 0 {
									continue
								}
								readPlane := plane
								if test.VideoMode == 0x40 {
									readPlane = 2
								}
								cell := model.Cells[(start+i)*4+plane]
								res.SourceOwnershipEqual = res.SourceOwnershipEqual && cell.Asset == sourceAsset && cell.Source == sourceOff*4+readPlane && cell.Visible
							}
						}
					}
					owner.releaseScene()
				}
			}
			if !bytes.Equal(before[0], before[1]) {
				panic("對照初始 RAM 不同")
			}
			a, b := pair[0].RenderProbeRAM(), pair[1].RenderProbeRAM()
			for i := range a {
				if a[i] != b[i] {
					res.RAMDiff++
					if len(res.FirstRAM) < 24 {
						res.FirstRAM = append(res.FirstRAM, fmt.Sprintf("%05x:%02x/%02x", i, a[i], b[i]))
					}
				}
			}
			for plane := 0; plane < 4; plane++ {
				a, b = pair[0].EGAPlane(plane), pair[1].EGAPlane(plane)
				for i := range a {
					if a[i] != b[i] {
						res.VGAPlanesDiff++
					}
				}
			}
			res.VideoEqual = pair[0].RenderProbeVideoRegisters() == pair[1].RenderProbeVideoRegisters()
			fa, _ := json.Marshal(res.Frames[0])
			fb, _ := json.Marshal(res.Frames[1])
			res.Passed = res.Native == res.Direct && res.NativeSteps == res.DirectSteps && res.RAMDiff == 0 && res.VGAPlanesDiff == 0 && res.VideoEqual && res.SourceOwnershipEqual && bytes.Equal(fa, fb)
			if test.MemoryCopy {
				res.Passed = res.Passed && res.DirectWrites == 0 && res.NativeWrites == 0 && len(owner.Pending) == 0 && res.Counters["virtual_instructions"] == 0
			} else if (test.Upload || test.VideoCopy) && test.FrameAt == 0 && !test.Reject {
				prefix := 0
				if test.Entry.Off == 0x8c2 {
					prefix = int(test.Args[4] % 2)
				}
				res.Passed = res.Passed && res.DirectWrites == 0 && int(res.Counters["owned_copy_prefix"]) == prefix && res.NativeWrites > res.DirectWrites && res.Counters["owned_ram_upload_rep"]+res.Counters["owned_video_copy_rep"] == 1
			} else if test.Clear && test.Args[2] == 0 {
				res.Passed = res.Passed && res.DirectWrites == 0 && res.NativeWrites == 0
			} else if test.Image != nil && res.NativeWrites == 0 {
				// 原始空封包沒有像素，仍核對返回、時間與全部狀態。
				res.Passed = res.Passed && res.DirectWrites == 0 && res.Counters["virtual_instructions"] == 0
			} else if test.FrameAt == 0 && test.IRQAt == 0 && !test.Reject {
				res.Passed = res.Passed && res.DirectWrites == 0 && res.NativeWrites > 0 && res.Counters["virtual_instructions"] > 0
			}
			if test.Reject {
				if test.Image != nil {
					res.Passed = res.Passed && res.DirectWrites == 0 && res.Counters["owned_image_transfers"] == 0 && (res.NativeWrites == 0 || res.Counters["owned_source_blit_bytes"]+res.Counters["owned_masked_blit"] > 0)
				} else {
					res.Passed = res.Passed && res.DirectWrites == res.NativeWrites && res.Counters["virtual_instructions"] == 0
				}
			}
			results = append(results, res)
			for _, o := range pair {
				delete(renderOwners, o)
				o.OnVideoWriteEvent(nil)
				o.SetPresentationVideo(nil, nil, nil)
				o.Close()
			}
			fmt.Printf("%s dos=%t RAM=%d VGA=%d steps=%d/%d cycles=%d/%d regs=%t owned=%v\n", res.Name, dosCost, res.RAMDiff, res.VGAPlanesDiff, res.NativeSteps, res.DirectSteps, res.Native.Cycles, res.Direct.Cycles, res.Native.Regs == res.Direct.Regs, res.Counters)
		}
	}
	raw, err = json.MarshalIndent(results, "", "  ")
	must(err)
	must(os.WriteFile(filepath.Join(out, "abi-initial.json"), append(raw, '\n'), 0644))
	passed := true
	for _, r := range results {
		passed = passed && r.Passed
	}
	sources := map[string]string{}
	for _, name := range []string{"player_owned_drivers.go", "render_scene_state.go", "player_video_overlay.py", "machine_presentation_video.go", "oracle_presentation_video.go", "oracle_video_observer.go", "render_abi_probe.go", "oracle_render_probe.go", "machine_render_probe.go", "render-abi.sh"} {
		raw, err := os.ReadFile(filepath.Join(root, "tools", name))
		must(err)
		sources[name] = digest(raw)
	}
	inputs := map[string]string{}
	for key, path := range map[string]string{"original_exe": filepath.Join(base, "DQK.EXE"), "normal_source_snapshot": state, "bindings": filepath.Join(root, "docs/spec/005-render-hooks.json")} {
		raw, err := os.ReadFile(path)
		must(err)
		inputs[key] = digest(raw)
	}
	evidence := map[string]any{"version": 1, "mode": "isolated-original-function", "passed": passed, "cases": len(results), "sources": sources, "inputs": inputs, "go": runtime.Version(), "sdk_commit": "f79eab6db8c64a524a06535e53e5d32b0bbcf7c8", "machine_effects_verified": passed, "virtual_time_verified": passed, "normal_player_path_verified": false, "receipt_sha256": digest(append(append([]byte(nil), raw...), '\n'))}
	evidence["routing_boundary_checks"] = boundaryChecks
	raw, err = json.MarshalIndent(evidence, "", "  ")
	must(err)
	must(os.WriteFile(filepath.Join(out, "evidence.json"), append(raw, '\n'), 0644))
	if !passed {
		panic("函式對照未通過，見 abi-initial.json")
	}
}
