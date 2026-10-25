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
	Name    string
	Entry   oracle.Addr
	Args    []uint16
	Font    []byte
	Image   *sourceTileCommand
	Data    []byte
	FrameAt uint64
	Reject  bool
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
	state := filepath.Join(root, "workplace/probe/battle-continuation-20261025/control-r1/final.state")
	cases := []probeCase{}
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
	var pack struct {
		Assets []struct {
			Key    string
			File   string `json:"source_file"`
			Offset int    `json:"source_offset"`
			Count  int    `json:"source_block_bytes"`
		}
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
	for _, test := range append([]probeCase(nil), cases...) {
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
			c.Name += "-reject-return"
			c.Reject = true
			cases = append(cases, c)
		}
	}
	results := []probeResult{}
	for _, test := range cases {
		for _, dosCost := range []bool{false, true} {
			pair := make([]*oracle.Oracle, 2)
			var owner *playerRenderOwner
			var before [2][]byte
			res := probeResult{Name: test.Name, DOSCost: dosCost, Checkpoints: map[string][][2]uint64{}}
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
				}
				o.RenderProbePrepare(test.Entry, ret, test.Args, dosCost)
				var frames *[]oracle.RenderProbeFrame
				if test.FrameAt > 0 {
					frames = o.RenderProbeFrameAt(test.FrameAt)
				}
				if test.Font != nil {
					o.WriteBytes(oracle.Addr{Seg: 0x7000, Off: 0x100}, test.Font)
				}
				if test.Image != nil {
					o.WriteBytes(test.Image.Source, test.Data)
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
					tx := renderTransaction{Return: paintReturn{ret, 0x333e, 0xe004}, Origin: test.Entry}
					if test.Image != nil {
						tx.Image = &renderImageSource{Command: *test.Image}
					}
					owner.Pending = append(owner.Pending, tx)
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
					owner.finishDriver(owner.Pending[0].Owned)
					res.Direct = o.RenderProbeCPU()
					res.DirectSteps = o.Steps()
					res.DirectWrites = writes
					res.Counters = owner.Counters
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
			res.VideoEqual = pair[0].PresentationVideoState() == pair[1].PresentationVideoState()
			fa, _ := json.Marshal(res.Frames[0])
			fb, _ := json.Marshal(res.Frames[1])
			res.Passed = res.Native == res.Direct && res.NativeSteps == res.DirectSteps && res.RAMDiff == 0 && res.VGAPlanesDiff == 0 && res.VideoEqual && bytes.Equal(fa, fb)
			if test.FrameAt == 0 && !test.Reject {
				res.Passed = res.Passed && res.DirectWrites == 0 && res.NativeWrites > 0 && res.Counters["virtual_instructions"] > 0
			}
			if test.Reject {
				res.Passed = res.Passed && res.DirectWrites == res.NativeWrites && res.Counters["virtual_instructions"] == 0
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
	raw, err = json.MarshalIndent(evidence, "", "  ")
	must(err)
	must(os.WriteFile(filepath.Join(out, "evidence.json"), append(raw, '\n'), 0644))
	if !passed {
		panic("函式對照未通過，見 abi-initial.json")
	}
}
