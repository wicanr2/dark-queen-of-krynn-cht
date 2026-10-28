package main

// 原版函式窄驗證，需Docker的render-probe覆層及DQK_SOURCE_ROOT。
// 未有合法原版與既有正常快照時略過，不以合成函式冒充原版。
import (
	"bytes"
	"fmt"
	"github.com/wicanr2/dosgolem/oracle"
	"os"
	"path/filepath"
	"testing"
)

func TestColdFillObserverIRQBoundary(t *testing.T) {
	root := os.Getenv("DQK_SOURCE_ROOT")
	if root == "" {
		t.Skip("需要合法原版及固定研究快照")
	}
	original := filepath.Join(root, "workplace/input/dos/drkqueen")
	snapshot := filepath.Join(root, "workplace/probe/battle-continuation-20261025/control-r1/final.state")
	if _, err := os.Stat(snapshot); os.IsNotExist(err) {
		t.Skip("缺少原版快照")
	}
	for _, dosCost := range []bool{false, true} {
		for _, at := range []uint64{999999, 0, 1, 20, 150, 395, 396, 397} {
			t.Run(fmt.Sprintf("dos-%t-irq-%d", dosCost, at), func(t *testing.T) {
				type result struct {
					cpu   oracle.RenderProbeCPU
					ram   []byte
					video [28]byte
					steps uint64
					irq   int
				}
				run := func(observe bool) result {
					o, err := oracle.Load(filepath.Join(original, "DQK.EXE"), original)
					if err != nil {
						t.Fatal(err)
					}
					defer o.Close()
					if err := o.LoadStateFile(snapshot); err != nil {
						t.Fatal(err)
					}
					entry, ret := oracle.Addr{Seg: 0x13c7, Off: 0x78}, oracle.Addr{Seg: 0x7000, Off: 0x100}
					o.RenderProbePrepare(entry, ret, []uint16{0, 0, 8, 8, 2}, dosCost)
					o.WriteBytes(ret, []byte{0x90})
					events := o.RenderProbeIRQAt(at)
					var u *coldPromptUI
					var owner *playerRenderOwner
					var fills []paintReturn
					completed := 0
					if observe {
						g := &liveGame{o: o, cold: &coldLoad{}}
						u = &coldPromptUI{Owner: g, Words: map[[2]int]listWord{{0, 0}: {X: 0, Y: 0, Width: 8, Key: "probe-label"}}}
						u.Config.Bindings = make([]coldPromptBinding, 17)
						g.cold.ui = u
						g.installColdFillObserver(func() bool { return true })
						owner = &playerRenderOwner{Oracle: o, Counters: map[string]uint64{}}
						owner.observeTransaction(entry, "rectangle", map[oracle.Addr]bool{})
						registered := map[oracle.Addr]bool{}
						o.OnCall(entry, func(_ *oracle.Oracle) { beginPaintCall(o, &fills, registered, func() { completed++ }) })
					}
					if err := o.RunUntil(oracle.At(oracle.Addr{Seg: ret.Seg, Off: ret.Off + 1}), oracle.Budget(100000)); err != nil {
						t.Fatal(err)
					}
					if observe {
						if len(owner.Pending) != 0 || len(fills) != 0 || completed != 1 {
							t.Fatalf("繪圖或列表交易沒有單次結束：%d/%d/%d", len(owner.Pending), len(fills), completed)
						}
						if at == 0 && owner.Counters["transaction_entry_revisit"] != 1 {
							t.Fatal("入口IRQ必須真正重訪且只建一筆交易")
						}
						if len(u.Fills) != 0 || len(u.Words) != 0 {
							t.Fatalf("返回後尚有交易或殘字：%d/%d", len(u.Fills), len(u.Words))
						}
						if len(u.Events) != 2 || u.Events[0]["kind"] != "native-clear" || u.Events[1]["kind"] != "native-clear-return" {
							t.Fatalf("單次填色應只配對一次：%v", u.Events)
						}
					}
					return result{o.RenderProbeCPU(), o.RenderProbeRAM(), o.RenderProbeVideoRegisters(), o.Steps(), len(*events)}
				}
				control, observed := run(false), run(true)
				if control.cpu != observed.cpu || control.video != observed.video || control.steps != observed.steps || !bytes.Equal(control.ram, observed.ram) {
					t.Fatal("UI觀察器改變原版機器效果")
				}
				wantIRQ := 1
				if at == 999999 {
					wantIRQ = 0
				}
				if control.irq != wantIRQ || observed.irq != wantIRQ {
					t.Fatalf("固定IRQ未實際發生：%d/%d", control.irq, observed.irq)
				}
			})
		}
	}
}

func TestStartupQuizPresentationGate(t *testing.T) {
	for _, tc := range []struct {
		name                        string
		incomplete, unrelated, want bool
	}{
		{"complete", false, false, true}, {"pending-last-string", true, false, false}, {"unrelated-footer", false, true, false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			dir := t.TempDir()
			path := filepath.Join(dir, "ui.com")
			if err := os.WriteFile(path, []byte{0x90}, 0600); err != nil {
				t.Fatal(err)
			}
			o, err := oracle.LoadProgram(path, dir, "")
			if err != nil {
				t.Fatal(err)
			}
			defer o.Close()
			g := &liveGame{o: o, cold: &coldLoad{}, list: &listState{footerTransition: true, words: map[[2]int]listWord{
				{8, 175}: {Key: "role.c4e0e1d860943362f885", Group: "footer"},
				{8, 80}:  {Key: "body-kept", Group: "body"},
			}}}
			u := &coldPromptUI{Owner: g, Words: map[[2]int]listWord{}, Prints: map[string]*coldPromptPrint{}}
			g.cold.ui = u
			for n, key := range []string{"startup.quiz-page", "startup.quiz-word", "startup.quiz-heading", "startup.quiz-enter"} {
				u.Words[[2]int{24, n * 16}] = listWord{Key: key, Group: "quiz"}
				u.Prints[key] = &coldPromptPrint{Complete: !tc.incomplete || n != 3}
			}
			if tc.unrelated {
				g.list.words[[2]int{8, 189}] = listWord{Key: "unknown-footer", Group: "footer"}
			}
			if got := g.completeStartupQuiz(); got != tc.want {
				t.Fatalf("交接%t，預期%t", got, tc.want)
			}
			_, role := g.list.words[[2]int{8, 175}]
			_, body := g.list.words[[2]int{8, 80}]
			if role == tc.want || !body || g.list.footerTransition == tc.want {
				t.Fatal("交接錯誤撤除詞框或等待")
			}
		})
	}
}
