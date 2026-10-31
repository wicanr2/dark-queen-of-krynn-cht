// 防拷查驗自動填入。使用者2026-10-31選定：出題後把正確答案當一般鍵盤輸入送進原版輸入框，
// 由玩家自行按Enter。原版出題、亂數、答案比較與存檔都不改，也不寫入原版記憶體。
//
// 證據（DQK.EXE 1.1，SHA-256 3b41fb06…）：
//   - 題庫在檔案偏移0x6A996起，80個以NUL分隔的字串，四個一組為標題與三個答案。
//     每個byte減去該字串長度後整串反轉即為明文，共20個標題、60個答案。
//   - 出題時0x132D4的字串複製把解碼後的答案寫到DS:C6F9（呼叫者2808:0084，來源為堆疊區域變數）。
//   - 研究探針把該緩衝改成其他字後輸入同一字可通過；答錯後換題，緩衝隨之更新；比對不分大小寫。
//   - 出題後尚未畫完提示就送入答案仍可通過，原版不清鍵盤緩衝。
package main

import (
	"bytes"
	"errors"

	"github.com/wicanr2/dosgolem/oracle"
)

const (
	dqkQuizPoolOffset = 0x6a996
	dqkQuizPoolEnd    = 0x6ac44
	dqkQuizStrings    = 80
)

var dqkQuizAnswerBuffer = oracle.Addr{Seg: 0x333e, Off: 0xc6f9}

func init() { playerQuizLoader = loadPlayerQuiz }

// decodeQuizPool 回傳題庫的60個答案（不含標題）。
func decodeQuizPool(exe []byte) (map[string]bool, error) {
	if len(exe) < dqkQuizPoolEnd {
		return nil, errors.New("DQK.EXE長度不足，找不到防拷題庫")
	}
	return decodeQuizStrings(exe[dqkQuizPoolOffset:dqkQuizPoolEnd])
}

// decodeQuizStrings 解一段以NUL結尾的題庫。
func decodeQuizStrings(pool []byte) (map[string]bool, error) {
	if len(pool) == 0 || pool[len(pool)-1] != 0 {
		return nil, errors.New("防拷題庫結尾不符")
	}
	parts := bytes.Split(pool[:len(pool)-1], []byte{0})
	if len(parts) != dqkQuizStrings {
		return nil, errors.New("防拷題庫字串數不符")
	}
	answers := map[string]bool{}
	for i, enc := range parts {
		if len(enc) < 2 {
			return nil, errors.New("防拷題庫字串過短")
		}
		plain := make([]byte, len(enc))
		for j, c := range enc {
			v := c - byte(len(enc))
			if !(v >= 'A' && v <= 'Z' || v == ' ' || v == '0') {
				return nil, errors.New("防拷題庫解碼後含非預期字元")
			}
			plain[len(enc)-1-j] = v
		}
		if i%4 != 0 {
			answers[string(plain)] = true
		}
	}
	if len(answers) != 60 {
		return nil, errors.New("防拷題庫答案數不符")
	}
	return answers, nil
}

func loadPlayerQuiz(exe []byte) func(*liveGame) {
	answers, err := decodeQuizPool(exe)
	must(err)
	filled := ""
	return func(g *liveGame) {
		if !g.startupQuizShown() {
			filled = ""
			return
		}
		raw := g.o.Bytes(dqkQuizAnswerBuffer, 16)
		answer := string(raw[:max(0, bytes.IndexByte(raw, 0))])
		if !answers[answer] || answer == filled {
			return
		}
		must(g.o.TypeKeys(answer))
		filled = answer
		p := g.player
		p.Controls = append(p.Controls, map[string]any{"action": "quiz_autofill", "step": g.o.Steps(), "length": len(answer)})
	}
}

// startupQuizShown 只讀冷啟動提示層已核對的四個查驗文字，不改其狀態。
func (g *liveGame) startupQuizShown() bool {
	u := g.cold.ui
	if u == nil {
		return false
	}
	for _, key := range []string{"startup.quiz-page", "startup.quiz-word", "startup.quiz-heading", "startup.quiz-enter"} {
		if p := u.Prints[key]; p == nil || !p.Complete {
			return false
		}
		found := false
		for _, word := range u.Words {
			found = found || word.Key == key && word.Group == "quiz"
		}
		if !found {
			return false
		}
	}
	return true
}
