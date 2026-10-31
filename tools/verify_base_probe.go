// 驗證基準快照：無頭dosgolem從MZ冷啟動，只送一般鍵盤輸入，讀原附A隊伍、開始冒險、
// 回答防拷查驗並進入帕蘭薩斯。答案沿正式玩家的自動填入規則，讀原版出題時寫入的答案緩衝。
// 不寫入原版記憶體、不改EXE或資料。快照含原版整份記憶體，只留本機workplace。
package main

import (
	"bytes"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"image"
	"image/png"
	"io"
	"os"
	"path/filepath"
	"runtime"

	"github.com/wicanr2/dosgolem/oracle"
)

const (
	baseExeSHA256 = "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58"
	basePoolStart = 0x6a996
	basePoolEnd   = 0x6ac44
)

var baseAnswerBuffer = oracle.Addr{Seg: 0x333e, Off: 0xc6f9}

func must(err error) {
	if err != nil {
		panic(err)
	}
}

func digest(b []byte) string { h := sha256.Sum256(b); return hex.EncodeToString(h[:]) }

// 與player_quiz.go相同的解碼規則；本工具獨立建置，不連入玩家程式。
func baseAnswers(exe []byte) (map[string]bool, error) {
	pool := exe[basePoolStart:basePoolEnd]
	if pool[len(pool)-1] != 0 {
		return nil, errors.New("題庫結尾不符")
	}
	parts := bytes.Split(pool[:len(pool)-1], []byte{0})
	if len(parts) != 80 {
		return nil, errors.New("題庫字串數不符")
	}
	answers := map[string]bool{}
	for i, enc := range parts {
		plain := make([]byte, len(enc))
		for j, c := range enc {
			v := c - byte(len(enc))
			if !(v >= 'A' && v <= 'Z' || v == ' ' || v == '0') {
				return nil, errors.New("題庫解碼字元不符")
			}
			plain[len(enc)-1-j] = v
		}
		if i%4 != 0 {
			answers[string(plain)] = true
		}
	}
	if len(answers) != 60 {
		return nil, errors.New("題庫答案數不符")
	}
	return answers, nil
}

func main() {
	if len(os.Args) != 3 {
		panic("用法：verify-base 原版目錄 全新輸出目錄")
	}
	orig, out := os.Args[1], os.Args[2]
	exe, err := os.ReadFile(filepath.Join(orig, "DQK.EXE"))
	must(err)
	if digest(exe) != baseExeSHA256 {
		panic("未知DQK.EXE")
	}
	answers, err := baseAnswers(exe)
	must(err)
	if _, err := os.Stat(out); !os.IsNotExist(err) {
		panic("輸出目錄必須全新")
	}
	must(os.Mkdir(out, 0755))
	o, err := oracle.Load(filepath.Join(orig, "DQK.EXE"), orig)
	must(err)
	defer o.Close()
	o.SetCmdLine("SB220 SI7 RB330")
	o.SetScratch(filepath.Join(out, "scratch"))

	var actions []map[string]any
	screens := map[string]string{}
	shot := func(label string) {
		w, h, rgb := o.ScreenRGB()
		im := image.NewRGBA(image.Rect(0, 0, w, h))
		for i := 0; i < w*h; i++ {
			copy(im.Pix[i*4:], rgb[i*3:i*3+3])
			im.Pix[i*4+3] = 255
		}
		var buf bytes.Buffer
		must(png.Encode(&buf, im))
		must(os.WriteFile(filepath.Join(out, label+".png"), buf.Bytes(), 0644))
		screens[label] = digest(buf.Bytes())
	}
	press := func(kind, key, label string, settle uint64) {
		at := o.Steps()
		if kind == "named" {
			must(o.SendKeys(key))
		} else {
			must(o.TypeKeys(key))
		}
		must(o.Run(settle))
		action := map[string]any{"at": at, "end": o.Steps(), "kind": kind, "label": label}
		if label != "quiz-answer" {
			action["key"] = key
		} else {
			action["length"] = len(key)
		}
		actions = append(actions, action)
		shot(label)
	}

	// 片頭示範以Return跳過；P進角色管理，L為Load Saved Game，T選本作TDQK存檔來源，
	// A讀原附A隊伍，B為Begin Adventuring。
	must(o.Run(150_000_000))
	shot("00-title")
	press("named", "Return", "01-skip-demo", 100_000_000)
	for i, k := range []string{"p", "l", "t", "a", "b"} {
		press("text", k, []string{"02-p", "03-l", "04-t", "05-a", "06-b"}[i], 20_000_000)
	}
	answer := ""
	for i := 0; i < 400 && answer == ""; i++ {
		raw := o.Bytes(baseAnswerBuffer, 16)
		if n := bytes.IndexByte(raw, 0); n > 0 && answers[string(raw[:n])] {
			answer = string(raw[:n])
			break
		}
		must(o.Run(1_000_000))
	}
	if answer == "" {
		panic("400M步內未出現防拷查驗答案")
	}
	quizAt := o.Steps()
	must(o.Run(60_000_000))
	shot("07-quiz")
	must(o.SaveStateFile(filepath.Join(out, "quiz.state")))
	quizSteps := o.Steps()
	press("text", answer, "quiz-answer", 20_000_000)
	press("named", "Return", "08-enter", 600_000_000)
	must(o.SaveStateFile(filepath.Join(out, "palanthas.state")))

	states := map[string]any{}
	for name, steps := range map[string]uint64{"quiz.state": quizSteps, "palanthas.state": o.Steps()} {
		raw, err := os.ReadFile(filepath.Join(out, name))
		must(err)
		zr, err := gzip.NewReader(bytes.NewReader(raw))
		must(err)
		plain, err := io.ReadAll(zr)
		must(err)
		// 還原時會重開快照內的檔案代碼；只允許原版目錄，避免依賴本次scratch。
		if bytes.Contains(plain, []byte(filepath.Join(out, "scratch"))) {
			panic(name + "仍開著scratch檔案，不能作為共用基準")
		}
		probe, err := oracle.Load(filepath.Join(orig, "DQK.EXE"), orig)
		must(err)
		must(probe.LoadStateFile(filepath.Join(out, name)))
		if probe.Steps() != steps {
			panic(name + "還原步數不符")
		}
		probe.Close()
		states[name] = map[string]any{"sha256": digest(raw), "steps": steps}
	}
	receipt := map[string]any{
		"version": 1, "exe_sha256": baseExeSHA256, "cmdline": "SB220 SI7 RB330",
		"sdk_commit": "f79eab6db8c64a524a06535e53e5d32b0bbcf7c8", "go": runtime.Version(),
		"actions": actions, "quiz_answer_step": quizAt, "states": states, "screens": screens,
		"original_memory_written": false, "scope": "正常一般鍵盤輸入的冷啟動基準；答案沿正式自動填入規則讀原版緩衝",
	}
	raw, err := json.MarshalIndent(receipt, "", "  ")
	must(err)
	must(os.WriteFile(filepath.Join(out, "receipt.json"), append(raw, '\n'), 0644))
}
