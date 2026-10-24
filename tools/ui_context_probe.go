// DRAFT：以一般按鍵觀測介面文字；原文及暫存緩衝區在呼叫當下快照。
// 不翻譯、不修改 guest，vararg 只記候選，不視為完整格式解析器。
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"

	"github.com/wicanr2/dosgolem/oracle"
)

func must(err error) {
	if err != nil {
		panic(err)
	}
}
func digest(b []byte) string { h := sha256.Sum256(b); return hex.EncodeToString(h[:]) }
func writeJSON(path string, value any) {
	b, err := json.MarshalIndent(value, "", "  ")
	must(err)
	must(os.WriteFile(path, append(b, '\n'), 0644))
}
func probeRAM(o *oracle.Oracle) []byte {
	ram := make([]byte, 1<<20)
	for i := range ram {
		ram[i] = o.Byte(oracle.Addr{Seg: uint16(i >> 4), Off: uint16(i & 15)})
	}
	return ram
}

type action struct {
	At    uint64 `json:"at"`
	End   uint64 `json:"end"`
	Kind  string `json:"kind"`
	Key   string `json:"key"`
	Label string `json:"label"`
}
type request struct {
	StateSHA string   `json:"state_sha256"`
	Start    uint64   `json:"start_steps"`
	Actions  []action `json:"actions"`
}
type textSnapshot struct {
	Segment uint16 `json:"segment"`
	Offset  uint16 `json:"offset"`
	Hex     string `json:"hex"`
	Text    string `json:"text"`
	NUL     bool   `json:"nul_terminated"`
}
type call struct {
	Step         uint64                  `json:"step"`
	Return       uint64                  `json:"return_step,omitempty"`
	Glyph        uint64                  `json:"first_glyph,omitempty"`
	Caller       oracle.Addr             `json:"caller"`
	SS           uint16                  `json:"ss"`
	SP           uint16                  `json:"sp"`
	Stack        []uint16                `json:"stack"`
	Format       textSnapshot            `json:"format"`
	Candidate1   textSnapshot            `json:"vararg_1_candidate"`
	Candidate2   textSnapshot            `json:"vararg_2_candidate"`
	Wrapper      int                     `json:"wrapper_index"`
	Menu         int                     `json:"menu_index"`
	Paragraph    int                     `json:"paragraph_index"`
	GlyphCalls   []map[string]any        `json:"glyph_calls,omitempty"`
	VideoFirst   *oracle.VideoWriteEvent `json:"video_first,omitempty"`
	VideoLast    *oracle.VideoWriteEvent `json:"video_last,omitempty"`
	VideoPages   map[uint32]int          `json:"video_pages,omitempty"`
	ReturnLayout *oracle.VideoWriteEvent `json:"return_layout,omitempty"`
}
type pendingCall struct {
	index  int
	addr   oracle.Addr
	ss, sp uint16
}

func main() {
	if (len(os.Args) != 5 && len(os.Args) != 6) || (os.Args[4] != "observe" && os.Args[4] != "control") {
		panic("用法：ui-context-probe 原版快照 request.json 全新輸出目錄 observe|control [唯讀 J 槽目錄]")
	}
	bootPath := os.Getenv("DQK_CONTEXT_BOOT_REQUEST")
	coldBoot := os.Args[1] == "-" || bootPath != ""
	var stateBytes []byte
	var err error
	if !coldBoot {
		stateBytes, err = os.ReadFile(os.Args[1])
		must(err)
	}
	requestBytes, err := os.ReadFile(os.Args[2])
	must(err)
	var req request
	must(json.Unmarshal(requestBytes, &req))
	stateSHA := ""
	if !coldBoot {
		stateSHA = digest(stateBytes)
	}
	if coldBoot && bootPath != "" {
		stateSHA = req.StateSHA // 稍後以真正 MZ 冷啟動重生快照驗證，沒有載入它。
	}
	if stateSHA != req.StateSHA || len(req.Actions) == 0 || (coldBoot && bootPath == "" && req.Start != 0) {
		panic("輸入快照或動作不符")
	}
	last := req.Start
	labels := map[string]bool{}
	for _, a := range req.Actions {
		if a.At < last || a.End <= a.At || a.Label == "" || filepath.Base(a.Label) != a.Label || labels[a.Label] {
			panic("動作必須依步數排序，標籤必須唯一且不是路徑")
		}
		if a.Kind != "text" && a.Kind != "named" && a.Kind != "alt" {
			panic("未知鍵盤輸入種類")
		}
		last = a.End
		labels[a.Label] = true
	}
	footerProbeSteps := map[uint64]bool{}
	for _, field := range strings.Split(os.Getenv("DQK_CONTEXT_FOOTER_STEPS"), ",") {
		if field == "" {
			continue
		}
		step, err := strconv.ParseUint(field, 10, 64)
		must(err)
		if step < req.Start || step > last || len(footerProbeSteps) >= 64 {
			panic("底列來源取樣步數越界或超過 64 點")
		}
		footerProbeSteps[step] = true
	}
	out := os.Args[3]
	if _, err := os.Stat(out); !os.IsNotExist(err) {
		panic("輸出目錄必須全新")
	}
	exe, err := os.ReadFile("/orig/DQK.EXE")
	must(err)
	if digest(exe) != "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58" {
		panic("未知 EXE")
	}
	must(os.Mkdir(out, 0755))
	o, err := oracle.Load("/orig/DQK.EXE", "/orig")
	must(err)
	defer o.Close()
	if coldBoot {
		o.SetCmdLine("SB220 SI7 RB330")
	} else {
		must(o.LoadStateFile(os.Args[1]))
	}
	o.SetScratch(filepath.Join(out, "scratch"))
	var seedFiles []map[string]any
	if len(os.Args) == 6 {
		for _, spec := range []struct {
			name string
			size int
			sha  string
		}{
			{"SavGamJ.qsv", 7965, "72a45079a189126c3a96d4681fac846086a6edaf26748d260d3a73fbc8905488"},
			{"VaultJ.DAT", 866, "2acc13fa21f319fac65ad823d7ca52f1ed02d13ce8708431f7ce5c116d9db7ba"},
		} {
			file := filepath.Join(os.Args[5], spec.name)
			data, e := os.ReadFile(file)
			must(e)
			if len(data) != spec.size || digest(data) != spec.sha {
				panic("觀測用 J 槽來源不符")
			}
			info, e := os.Stat(file)
			must(e)
			dir := filepath.Join(out, "scratch", "SAVE")
			must(os.MkdirAll(dir, 0755))
			target := filepath.Join(dir, spec.name)
			must(os.WriteFile(target, data, 0644))
			must(os.Chtimes(target, info.ModTime(), info.ModTime()))
			seedFiles = append(seedFiles, map[string]any{"name": spec.name, "bytes": len(data), "sha256": spec.sha, "mtime_ns": info.ModTime().UnixNano()})
		}
	}
	var bootSHA string
	var bootCheckpoints []map[string]any
	if bootPath != "" {
		data, e := os.ReadFile(bootPath)
		must(e)
		bootSHA = digest(data)
		var boot struct {
			Actions []struct {
				At, End          uint64
				Kind, Key, Label string
			}
			Handoff, QuizStep uint64
			QuizSHA256        string
		}
		must(json.Unmarshal(data, &boot))
		if o.Steps() != 0 || req.Start != 355000000 || len(boot.Actions) != 12 || boot.Handoff != req.Start || boot.QuizStep != req.Start || len(stateSHA) != 64 {
			panic("未知 MZ 前段請求")
		}
		for _, a := range boot.Actions {
			if a.At < o.Steps() || a.End <= a.At || a.End > req.Start {
				panic("MZ 前段順序不符")
			}
			must(o.Run(a.At - o.Steps()))
			if a.Kind == "text" {
				must(o.TypeKeys(a.Key))
			} else if a.Kind == "named" {
				must(o.SendKeys(a.Key))
			} else {
				panic("未知 MZ 前段按鍵")
			}
			must(o.Run(a.End - o.Steps()))
			// 沿既有冷啟動控制組的觀測順序；讀 VGA 記憶體會更新鎖存器。
			bootCheckpoints = append(bootCheckpoints, map[string]any{"step": o.Steps(), "label": a.Label, "ram_sha256": digest(probeRAM(o))})
		}
		if digest(o.Indexed()) != boot.QuizSHA256 {
			panic("MZ 查驗頁不符")
		}
		file := filepath.Join(out, "cold-handoff.state")
		must(o.SaveStateFile(file))
		raw, e := os.ReadFile(file)
		must(e)
		if digest(raw) != stateSHA {
			panic("MZ 前段快照不符")
		}
	}
	if o.Steps() != req.Start {
		panic("快照步數不符")
	}
	entry := oracle.Addr{Seg: 0x1212, Off: 0x03a0}
	glyph := oracle.Addr{Seg: 0x13c7, Off: 0x0c96}
	if hex.EncodeToString(o.Bytes(entry, 11)) != "558becff760a0ee830ff59" {
		panic("印字入口不符")
	}
	if hex.EncodeToString(o.Bytes(glyph, 3)) != hex.EncodeToString(exe[0x15c06:0x15c09]) {
		panic("字元入口不符")
	}
	read := func(seg, off uint16) textSnapshot {
		s := textSnapshot{Segment: seg, Offset: off}
		var raw []byte
		for i := 0; i < 256; i++ {
			if uint32(off)+uint32(i) > 0xffff || uint32(seg)*16+uint32(off)+uint32(i) >= 0xa0000 {
				break
			}
			v := o.Byte(oracle.Addr{Seg: seg, Off: off + uint16(i)})
			if v == 0 {
				s.NUL = true
				break
			}
			raw = append(raw, v)
		}
		s.Hex = hex.EncodeToString(raw)
		s.Text = string(raw)
		return s
	}
	var calls []call
	var wrappers []map[string]any
	var wrapperPending []pendingCall
	wrapperRegistered := map[oracle.Addr]bool{}
	var menus []menuSourceSnapshot
	var menuRefreshSources []map[string]any
	var paragraphs []map[string]any
	var paragraphPending []pendingCall
	paragraphRegistered := map[oracle.Addr]bool{}
	menuIndices := map[string]int{}
	var listEvents []map[string]any
	var scrollEvents []map[string]any
	var fillEvents []map[string]any
	var fillStack []pendingCall
	var bootMenuEvents []map[string]any
	var bootMenuStack []int
	fillAudit := -1
	var scrollPending []pendingCall
	scrollRegistered := map[oracle.Addr]bool{}
	type listPending struct {
		index   int
		ss, sp  uint16
		pointer oracle.Addr
	}
	var listStack []listPending
	var pending []pendingCall
	registered := map[oracle.Addr]bool{}
	observe := os.Args[4] == "observe"
	var hudPanels func() []map[string]any
	if observe && os.Getenv("DQK_CONTEXT_HUD_PANEL") == "1" {
		hudPanels = observeHUDPanels(o)
	}

	var displayChanges []map[string]any
	videoTrace := observe && os.Getenv("DQK_CONTEXT_VIDEO") == "1"
	if videoTrace {
		o.OnVideoWriteEvent(func(hit oracle.VideoWriteEvent) {
			for _, p := range pending {
				c := &calls[p.index]
				if c.VideoFirst == nil {
					first := hit
					c.VideoFirst = &first
				}
				last := hit
				c.VideoLast = &last
				if c.VideoPages == nil {
					c.VideoPages = map[uint32]int{}
				}
				c.VideoPages[hit.Offset&0xc000]++
			}
			for _, p := range fillStack {
				f := fillEvents[p.index]
				if _, ok := f["video_first"]; !ok {
					f["video_first"] = hit
				}
				f["video_last"] = hit
				pages, ok := f["video_pages"].(map[uint32]int)
				if !ok {
					pages = map[uint32]int{}
					f["video_pages"] = pages
				}
				pages[hit.Offset&0xc000]++
			}
		})
		previous := o.VideoLayoutState()
		layoutRecord := func(layout oracle.VideoWriteEvent) map[string]any {
			record := map[string]any{"step": o.Steps(), "layout": layout}
			if hudPanels != nil {
				menu, valid := readMenuSource(o)
				record["menu_valid"], record["menu_snapshot"] = valid, menu
			}
			return record
		}
		displayChanges = append(displayChanges, layoutRecord(previous))
		o.SetStepGuard(func(_ *oracle.Oracle) error {
			if o.Steps() < 220000000 || o.Steps() > last {
				return nil
			}
			next := o.VideoLayoutState()
			if next.DisplayStart != previous.DisplayStart || next.Mode != previous.Mode || next.Pitch != previous.Pitch || next.Unchained != previous.Unchained {
				displayChanges = append(displayChanges, layoutRecord(next))
				previous = next
			}
			return nil
		})
	}
	wrapperEntry := oracle.Addr{Seg: 0x0b72, Off: 0x0046}
	if hex.EncodeToString(o.Bytes(wrapperEntry, 11)) != "558bec83ec60168d461250" {
		panic("格式化入口不符")
	}
	if observe {
		paragraphEntry := oracle.Addr{Seg: 0x0b72, Off: 0x0311}
		if hex.EncodeToString(o.Bytes(paragraphEntry, 8)) != "558bec83ec025657" {
			panic("段落入口 bytes 不符")
		}
		o.OnCall(paragraphEntry, func(_ *oracle.Oracle) {
			if len(paragraphs) >= 128 {
				panic("段落觀測超出界限")
			}
			r := o.Regs()
			s := make([]uint16, 16)
			for i := range s {
				s[i] = o.StackWord(i)
			}
			target := o.Caller()
			paragraphs = append(paragraphs, map[string]any{"step": o.Steps(), "regs": r, "stack": s, "caller": target,
				"source": read(s[10], s[9]), "native_box": [4]int{int(byte(s[2])) * 8, int(byte(s[3])) * 8, (int(byte(s[4])) + 1) * 8, (int(byte(s[5])) + 1) * 8},
				"foreground": byte(s[6]), "background": byte(s[7]), "clear": byte(s[8])})
			if os.Getenv("DQK_CONTEXT_PARAGRAPH_MENUS") == "1" {
				menu, valid := readMenuSource(o)
				paragraphs[len(paragraphs)-1]["menu_valid"] = valid
				paragraphs[len(paragraphs)-1]["menu_snapshot"] = menu
			}
			paragraphPending = append(paragraphPending, pendingCall{len(paragraphs) - 1, target, r.SS, r.SP + 4})
			if !paragraphRegistered[target] {
				paragraphRegistered[target] = true
				o.OnCall(target, func(_ *oracle.Oracle) {
					if len(paragraphPending) == 0 {
						return
					}
					p, r := paragraphPending[len(paragraphPending)-1], o.Regs()
					if p.addr == target && p.ss == r.SS && p.sp == r.SP {
						paragraphs[p.index]["return_step"] = o.Steps()
						paragraphPending = paragraphPending[:len(paragraphPending)-1]
					}
				})
			}
		})
		refresh := false
		for _, point := range []struct {
			addr  oracle.Addr
			bytes string
		}{
			{oracle.Addr{Seg: 0x1bb6, Off: 0x151f}, "558bec83ec0456803ec2da00751833c0"},
			{oracle.Addr{Seg: 0x1bb6, Off: 0x17b8}, "cb558bec83ec085657168d46fe50168d"},
		} {
			if hex.EncodeToString(o.Bytes(point.addr, len(point.bytes)/2)) != point.bytes {
				panic("選單刷新入口 bytes 不符")
			}
		}
		o.OnCall(oracle.Addr{Seg: 0x1bb6, Off: 0x17b8}, func(_ *oracle.Oracle) {
			if o.Regs().AX != 0xffff {
				refresh = true
			}
		})
		o.OnCall(oracle.Addr{Seg: 0x1bb6, Off: 0x151f}, func(_ *oracle.Oracle) {
			if !refresh && !footerProbeSteps[o.Steps()] {
				return
			}
			refresh = false
			if len(menuRefreshSources) >= 2000 {
				panic("選單刷新來源超出界限")
			}
			menu, ok := readMenuSource(o)
			menuRefreshSources = append(menuRefreshSources, map[string]any{"step": o.Steps(), "regs": o.Regs(), "caller": o.Caller(), "valid": ok, "menu_snapshot": menu})
		})
		fillEntry := oracle.Addr{Seg: 0x13c7, Off: 0x0078}
		fillCoordinates := oracle.Addr{Seg: 0x13c7, Off: 0x00f7}
		fillReturn := oracle.Addr{Seg: 0x13c7, Off: 0x06db}
		if hex.EncodeToString(o.Bytes(fillEntry, 8)) != "558bec83ec2e5657" || hex.EncodeToString(o.Bytes(fillCoordinates, 3)) != "8b4606" || o.Byte(fillReturn) != 0xcb {
			panic("填色邊界不符")
		}
		o.OnCall(fillEntry, func(_ *oracle.Oracle) {
			if len(fillEvents) >= 20000 {
				panic("超出填色觀測上限")
			}
			r := o.Regs()
			s := make([]uint16, 12)
			for i := range s {
				s[i] = o.Word(oracle.Addr{Seg: r.SS, Off: r.SP + uint16(i*2)})
			}
			fillEvents = append(fillEvents, map[string]any{"step": o.Steps(), "stack": s, "within_list": len(listStack) > 0})
			fillStack = append(fillStack, pendingCall{len(fillEvents) - 1, fillReturn, r.SS, r.SP})
		})
		o.OnCall(fillCoordinates, func(_ *oracle.Oracle) {
			if len(fillStack) == 0 {
				panic("未配對的填色座標")
			}
			p := fillStack[len(fillStack)-1]
			fillEvents[p.index]["converted_step"] = o.Steps()
			r := o.Regs()
			if p.ss != r.SS || p.sp != r.BP+2 {
				panic("填色座標堆疊不符")
			}
			v := make([]int, 4)
			for i := range v {
				v[i] = int(int16(o.Word(oracle.Addr{Seg: r.SS, Off: r.BP + 6 + uint16(i*2)})))
			}
			fillEvents[p.index]["native_rect"] = []int{v[1], v[0], v[3] - v[1], v[2] - v[0]}
			if len(listStack) == 0 && v[1] <= 8 && v[0] <= 8 && v[3] >= 312 && v[2] >= 184 {
				fillAudit = p.index
			}
		})
		o.OnCall(fillReturn, func(_ *oracle.Oracle) {
			if len(fillStack) == 0 {
				panic("未配對的填色返回")
			}
			p := fillStack[len(fillStack)-1]
			r := o.Regs()
			if p.ss != r.SS || p.sp != r.SP {
				panic("填色返回堆疊不符")
			}
			e := fillEvents[p.index]
			e["return_instruction_step"] = o.Steps()
			if rect, ok := e["native_rect"].([]int); ok && rect[0] >= 0 && rect[1] >= 0 && rect[0]+rect[2] <= 320 && rect[1]+rect[3] <= 200 && rect[2] >= 200 && rect[3] >= 40 {
				name := fmt.Sprintf("fill-%04d-after.idx", p.index)
				must(os.WriteFile(filepath.Join(out, name), o.Indexed(), 0644))
				e["indexed_after"] = name
			}
			fillStack = fillStack[:len(fillStack)-1]
		})
		scrollEntry := oracle.Addr{Seg: 0x13c7, Off: 0x2f06}
		if hex.EncodeToString(o.Bytes(scrollEntry, 11)) != "558bec83ec0c5657168d46" {
			panic("捲動入口不符")
		}
		o.OnCall(scrollEntry, func(_ *oracle.Oracle) {
			if len(scrollEvents) >= 1000 {
				panic("超出捲動觀測上限")
			}
			r := o.Regs()
			s := make([]uint16, 12)
			for i := range s {
				s[i] = o.Word(oracle.Addr{Seg: r.SS, Off: r.SP + uint16(i*2)})
			}
			i := len(scrollEvents)
			before := fmt.Sprintf("scroll-%03d-before.idx", i)
			must(os.WriteFile(filepath.Join(out, before), o.Indexed(), 0644))
			scrollEvents = append(scrollEvents, map[string]any{"step": o.Steps(), "stack": s, "regs": r, "indexed_before": before})
			target := oracle.Addr{Seg: s[1], Off: s[0]}
			scrollPending = append(scrollPending, pendingCall{i, target, r.SS, r.SP + 4})
			if !scrollRegistered[target] {
				scrollRegistered[target] = true
				o.OnCall(target, func(_ *oracle.Oracle) {
					if len(scrollPending) == 0 {
						return
					}
					p := scrollPending[len(scrollPending)-1]
					r := o.Regs()
					if p.addr == target && p.ss == r.SS && p.sp == r.SP {
						after := fmt.Sprintf("scroll-%03d-after.idx", p.index)
						must(os.WriteFile(filepath.Join(out, after), o.Indexed(), 0644))
						scrollEvents[p.index]["return_step"] = o.Steps()
						scrollEvents[p.index]["indexed_after"] = after
						scrollPending = scrollPending[:len(scrollPending)-1]
					}
				})
			}
		})
		listEntry := oracle.Addr{Seg: 0x0c15, Off: 0x0055}
		listReturn := oracle.Addr{Seg: 0x0c15, Off: 0x0508}
		if hex.EncodeToString(o.Bytes(listEntry, 8)) != "558bec83ec245657" || o.Byte(listReturn) != 0xcb {
			panic("列表繪製邊界不符")
		}
		o.OnCall(listEntry, func(_ *oracle.Oracle) {
			if len(listEvents) >= 2000 {
				panic("超出列表觀測上限")
			}
			r := o.Regs()
			s := make([]uint16, 12)
			for i := range s {
				s[i] = o.Word(oracle.Addr{Seg: r.SS, Off: r.SP + uint16(i*2)})
			}
			ptr := oracle.Addr{Seg: s[6], Off: s[5]}
			if uint32(ptr.Seg)*16+uint32(ptr.Off)+24 >= 0xa0000 || uint32(ptr.Off)+24 > 0x10000 {
				panic("列表結構超出研究範圍")
			}
			data := o.Bytes(ptr, 24)
			cb := oracle.Addr{Off: uint16(data[16]) | uint16(data[17])<<8, Seg: uint16(data[18]) | uint16(data[19])<<8}
			if uint32(cb.Seg)*16+uint32(cb.Off)+64 >= 0xa0000 || uint32(cb.Off)+64 > 0x10000 {
				panic("列表回呼超出研究範圍")
			}
			listEvents = append(listEvents, map[string]any{"step": o.Steps(), "stack": s, "regs": r, "descriptor_pointer": ptr, "descriptor_before_hex": hex.EncodeToString(data), "callback": cb, "callback_bytes_hex": hex.EncodeToString(o.Bytes(cb, 64))})
			if menu, ok := readMenuSource(o); ok {
				listEvents[len(listEvents)-1]["menu_snapshot"] = menu
			}
			listStack = append(listStack, listPending{len(listEvents) - 1, r.SS, r.SP, ptr})
		})
		o.OnCall(listReturn, func(_ *oracle.Oracle) {
			if len(listStack) == 0 {
				panic("未配對的列表返回")
			}
			p := listStack[len(listStack)-1]
			r := o.Regs()
			if p.ss != r.SS || p.sp != r.SP {
				panic("列表返回堆疊不符")
			}
			listEvents[p.index]["return_instruction_step"] = o.Steps()
			listEvents[p.index]["descriptor_after_hex"] = hex.EncodeToString(o.Bytes(p.pointer, 24))
			listStack = listStack[:len(listStack)-1]
		})
		o.OnCall(wrapperEntry, func(_ *oracle.Oracle) {
			if len(wrappers) >= 10000 {
				panic("超出格式化觀測上限")
			}
			r := o.Regs()
			if fillAudit >= 0 {
				name := fmt.Sprintf("fill-%04d-next-wrapper.idx", fillAudit)
				must(os.WriteFile(filepath.Join(out, name), o.Indexed(), 0644))
				fillEvents[fillAudit]["next_wrapper_indexed"] = name
				fillEvents[fillAudit]["next_wrapper_step"] = o.Steps()
				fillEvents[fillAudit]["next_wrapper_index"] = len(wrappers)
				fillAudit = -1
			}
			s := make([]uint16, 32)
			for i := range s {
				s[i] = o.Word(oracle.Addr{Seg: r.SS, Off: r.SP + uint16(i*2)})
			}
			var frames []map[string]any
			bp := r.BP
			for n := 0; n < 6 && uint32(bp)+24 <= 0x10000 && uint32(r.SS)*16+uint32(bp)+24 < 0xa0000; n++ {
				words := make([]uint16, 12)
				for i := range words {
					words[i] = o.Word(oracle.Addr{Seg: r.SS, Off: bp + uint16(i*2)})
				}
				frames = append(frames, map[string]any{"bp": bp, "words": words})
				if words[0] <= bp {
					break
				}
				bp = words[0]
			}
			wrappers = append(wrappers, map[string]any{"step": o.Steps(), "regs": r, "stack": s,
				"format": read(s[7], s[6]), "vararg_1_candidate": read(s[9], s[8]),
				"caller": oracle.Addr{Seg: s[1], Off: s[0]}, "bp_chain_candidates": frames})
			if os.Getenv("DQK_CONTEXT_WRAPPER_MENUS") == "1" {
				menu, valid := readMenuSource(o)
				wrappers[len(wrappers)-1]["menu_valid"] = valid
				wrappers[len(wrappers)-1]["menu_snapshot"] = menu
			}
			target := oracle.Addr{Seg: s[1], Off: s[0]}
			wrapperPending = append(wrapperPending, pendingCall{len(wrappers) - 1, target, r.SS, r.SP + 4})
			if !wrapperRegistered[target] {
				wrapperRegistered[target] = true
				o.OnCall(target, func(_ *oracle.Oracle) {
					if len(wrapperPending) == 0 {
						return
					}
					p, now := wrapperPending[len(wrapperPending)-1], o.Regs()
					if p.addr == target && p.ss == now.SS && p.sp == now.SP {
						wrappers[p.index]["return_step"] = o.Steps()
						wrappers[p.index]["return_ss"], wrappers[p.index]["return_sp"] = now.SS, now.SP
						wrapperPending = wrapperPending[:len(wrapperPending)-1]
					}
				})
			}
		})
		o.OnCall(entry, func(_ *oracle.Oracle) {
			if len(calls) >= 10000 {
				panic("超出文字觀測上限")
			}
			r := o.Regs()
			s := make([]uint16, 16)
			for i := range s {
				s[i] = o.Word(oracle.Addr{Seg: r.SS, Off: r.SP + uint16(i*2)})
			}
			target := oracle.Addr{Seg: s[1], Off: s[0]}
			wrapper := -1
			if target == (oracle.Addr{Seg: 0x0b72, Off: 0x027c}) && len(wrappers) > 0 {
				wrapper = len(wrappers) - 1
			}
			menu := -1
			if target == (oracle.Addr{Seg: 0x0ceb, Off: 0x01be}) || os.Getenv("DQK_CONTEXT_ALL_MENUS") == "1" {
				if snapshot, ok := readMenuSource(o); ok {
					var found bool
					menu, found = menuIndices[snapshot.Signature]
					if !found {
						menu = len(menus)
						menuIndices[snapshot.Signature] = menu
						menus = append(menus, snapshot)
					}
				}
			}
			paragraph := -1
			if len(paragraphPending) > 0 {
				paragraph = paragraphPending[len(paragraphPending)-1].index
			}
			calls = append(calls, call{Step: o.Steps(), Caller: target, SS: r.SS, SP: r.SP, Stack: s, Format: read(s[6], s[5]), Candidate1: read(s[8], s[7]), Candidate2: read(s[10], s[9]), Wrapper: wrapper, Menu: menu, Paragraph: paragraph})
			pending = append(pending, pendingCall{len(calls) - 1, target, r.SS, r.SP + 4})
			if !registered[target] {
				registered[target] = true
				o.OnCall(target, func(_ *oracle.Oracle) {
					if len(pending) == 0 {
						return
					}
					p := pending[len(pending)-1]
					r := o.Regs()
					if p.addr == target && p.ss == r.SS && p.sp == r.SP {
						calls[p.index].Return = o.Steps()
						if videoTrace {
							layout := o.VideoLayoutState()
							calls[p.index].ReturnLayout = &layout
						}
						pending = pending[:len(pending)-1]
					}
				})
			}
		})
		o.OnCall(glyph, func(_ *oracle.Oracle) {
			if len(paragraphPending) > 0 {
				p := paragraphs[paragraphPending[len(paragraphPending)-1].index]
				if _, found := p["first_glyph"]; !found {
					p["first_glyph"] = o.Steps()
				}
			}
			if len(pending) > 0 {
				c := &calls[pending[len(pending)-1].index]
				if c.Glyph == 0 {
					c.Glyph = o.Steps()
				}
				if strings.Contains(strings.ToLower(c.Candidate1.Text), "shield") || (coldBoot && o.Steps() >= 261000000 && o.Steps() < 302000000) {
					if len(c.GlyphCalls) >= 64 {
						panic("超出單列字元觀測上限")
					}
					r := o.Regs()
					s := make([]uint16, 12)
					for i := range s {
						s[i] = o.Word(oracle.Addr{Seg: r.SS, Off: r.SP + uint16(i*2)})
					}
					c.GlyphCalls = append(c.GlyphCalls, map[string]any{"step": o.Steps(), "regs": r, "stack": s,
						"ds_ca12": o.Word(oracle.Addr{Seg: r.DS, Off: 0xca12}), "ds_ca14": o.Word(oracle.Addr{Seg: r.DS, Off: 0xca14}),
						"format_at_glyph": read(c.Format.Segment, c.Format.Offset), "candidate_at_glyph": read(c.Candidate1.Segment, c.Candidate1.Offset)})
				}
			}
		})
	}
	if observe && coldBoot {
		o.OnCall(oracle.Addr{Seg: 0x1bb6, Off: 0x151f}, func(_ *oracle.Oracle) {
			menu, valid := readMenuSource(o)
			bootMenuStack = append(bootMenuStack, len(bootMenuEvents))
			bootMenuEvents = append(bootMenuEvents, map[string]any{"step": o.Steps(), "caller": o.Caller(), "valid": valid, "menu": menu})
		})
		o.OnCall(oracle.Addr{Seg: 0x1bb6, Off: 0x1585}, func(_ *oracle.Oracle) {
			if len(bootMenuStack) == 0 {
				panic("冷啟動選單返回未配對")
			}
			i := bootMenuStack[len(bootMenuStack)-1]
			bootMenuStack = bootMenuStack[:len(bootMenuStack)-1]
			bootMenuEvents[i]["return_step"] = o.Steps()
		})
	}
	ramSnapshot := func() []byte {
		ram := make([]byte, 1<<20)
		for i := range ram {
			ram[i] = o.Byte(oracle.Addr{Seg: uint16(i >> 4), Off: uint16(i & 15)})
		}
		return ram
	}
	var checkpoints []map[string]any
	for _, a := range req.Actions {
		must(o.Run(a.At - o.Steps()))
		if a.Kind == "text" {
			must(o.TypeKeys(a.Key))
		} else if a.Kind == "alt" {
			sender, ok := any(o).(interface{ PressBIOSAltKey(string) error })
			if !ok {
				panic("研究工具未載入 Alt 按鍵 overlay")
			}
			must(sender.PressBIOSAltKey(a.Key))
		} else {
			must(o.SendKeys(a.Key))
		}
		must(o.Run(a.End - o.Steps()))
		must(o.WritePNG(filepath.Join(out, a.Label+".png")))
		must(os.WriteFile(filepath.Join(out, a.Label+".idx"), o.Indexed(), 0644))
		checkpoints = append(checkpoints, map[string]any{"label": a.Label, "step": o.Steps(), "regs": o.Regs(), "ram_sha256": digest(ramSnapshot()), "indexed_sha256": digest(o.Indexed()), "indexed_file": a.Label + ".idx", "palette": o.Palette(), "keys_consumed": o.KeysConsumed(), "file_writes": o.Wrote(), "unimplemented": o.Unimplemented()})
	}
	must(o.SaveStateFile(filepath.Join(out, "final.state")))
	must(os.WriteFile(filepath.Join(out, "ram.bin"), ramSnapshot(), 0644))
	self, err := os.Executable()
	must(err)
	binary, err := os.ReadFile(self)
	must(err)
	var matches []int
	for i, c := range calls {
		if strings.Contains(strings.ToLower(c.Format.Text+" "+c.Candidate1.Text), "shield") {
			matches = append(matches, i)
		}
	}
	result := map[string]any{"draft": true, "observe": observe, "source_commit": "f79eab6db8c64a524a06535e53e5d32b0bbcf7c8", "go_version": runtime.Version(), "exe_sha256": digest(exe), "state_sha256": stateSHA, "request_sha256": digest(requestBytes), "probe_sha256": digest(binary), "request": req, "calls": calls, "wrappers": wrappers, "menus": menus, "menu_refresh_sources": menuRefreshSources, "list_events": listEvents, "pending_lists": len(listStack), "scroll_events": scrollEvents, "pending_scrolls": len(scrollPending), "fill_events": fillEvents, "pending_fills": len(fillStack), "shield_candidate_indices": matches, "pending_calls": len(pending), "checkpoints": checkpoints, "limits": "Original normal key input from a normal-route snapshot; no translation or GUI claim. Varargs and BP chain entries are raw candidates, not a complete formatter or verified frame walker."}
	if coldBoot {
		result["cold_boot"], result["snapshot_loaded"] = true, false
		if bootPath != "" {
			result["boot_request_sha256"] = bootSHA
			result["handoff_sha256"] = stateSHA
			result["cold_checkpoints"] = bootCheckpoints
		}
		result["limits"] = "Original MZ cold boot with normal keys; observation only, no translation or GUI claim. Varargs and BP chain entries remain raw candidates."
	}
	result["paragraphs"], result["pending_paragraphs"] = paragraphs, len(paragraphPending)
	if hudPanels != nil {
		result["hud_panels"] = hudPanels()
	}
	if seedFiles != nil {
		result["seed_save_files"] = seedFiles
	}
	if observe && coldBoot {
		result["boot_menu_events"] = bootMenuEvents
		result["pending_boot_menus"] = len(bootMenuStack)
	}
	result["pending_wrappers"] = len(wrapperPending)
	if videoTrace {
		result["display_changes"] = displayChanges
	}
	writeJSON(filepath.Join(out, "receipt.json"), result)
	fmt.Printf("observe=%t calls=%d shield_candidates=%d checkpoints=%d pending=%d\n", observe, len(calls), len(matches), len(checkpoints), len(pending))
}

// 一次性觀測原始 sub_1803F；原名與 IDA／執行期位址的對照見規格 001。
func observeHUDPanels(o *oracle.Oracle) func() []map[string]any {
	entry := oracle.Addr{Seg: 0x088e, Off: 0x085f}
	finish := oracle.Addr{Seg: 0x088e, Off: 0x0a18}
	if hex.EncodeToString(o.Bytes(entry, 11)) != "558bec83ec02803eb7c600" || o.Byte(finish) != 0xcb {
		panic("右側更新函式 bytes 不符")
	}
	var events []map[string]any
	var pending []pendingCall
	registered := map[oracle.Addr]bool{}
	o.OnCall(entry, func(_ *oracle.Oracle) {
		r := o.Regs()
		target := o.Caller()
		stack := make([]uint16, 8)
		for i := range stack {
			stack[i] = o.StackWord(i)
		}
		e := map[string]any{"step": o.Steps(), "regs": r, "stack": stack, "caller": target, "raw_c6b7": o.Byte(oracle.Addr{Seg: r.DS, Off: 0xc6b7}), "entry_bytes": "558bec83ec02803eb7c600"}
		if menu, ok := readMenuSource(o); ok {
			e["menu_snapshot"] = menu
		}
		events = append(events, e)
		pending = append(pending, pendingCall{len(events) - 1, target, r.SS, r.SP})
		if !registered[target] {
			registered[target] = true
			o.OnCall(target, func(_ *oracle.Oracle) {
				if len(pending) == 0 {
					return
				}
				p := pending[len(pending)-1]
				now := o.Regs()
				if p.addr != target || p.ss != now.SS || p.sp+4 != now.SP {
					return
				}
				if _, ok := events[p.index]["return_instruction_step"]; !ok {
					panic("右側函式沒有 retf 證據")
				}
				events[p.index]["return_step"] = o.Steps()
				pending = pending[:len(pending)-1]
			})
		}
	})
	o.OnCall(finish, func(_ *oracle.Oracle) {
		if len(pending) == 0 {
			panic("右側函式 retf 未配對")
		}
		p := pending[len(pending)-1]
		r := o.Regs()
		if p.ss != r.SS || p.sp != r.SP {
			panic("右側函式 retf 堆疊不符")
		}
		events[p.index]["return_instruction_step"] = o.Steps()
	})
	return func() []map[string]any {
		if len(pending) != 0 {
			panic("右側函式觀測未結束")
		}
		return events
	}
}
