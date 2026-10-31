package main

import (
	"os"
	"testing"
)

// 合成題庫只驗解碼規則；正式答案以下一個測試讀原版檔案核對。
func TestQuizPoolDecodeRule(t *testing.T) {
	encode := func(s string) []byte {
		out := make([]byte, len(s))
		for i := range s {
			out[i] = s[len(s)-1-i] + byte(len(s))
		}
		return out
	}
	var pool []byte
	for i := 0; i < dqkQuizStrings; i++ {
		word := "HEADING ONE"
		if i%4 != 0 {
			word = string(rune('A'+i/26%26)) + string(rune('A'+i%26)) + "X"
		}
		pool = append(append(pool, encode(word)...), 0)
	}
	answers, err := decodeQuizStrings(pool)
	if err != nil || len(answers) != 60 || !answers["ABX"] || answers["HEADING ONE"] {
		t.Fatalf("解碼失敗：%v %d", err, len(answers))
	}
	if _, err := decodeQuizStrings(pool[:len(pool)-1]); err == nil {
		t.Fatal("缺結尾NUL時應拒絕")
	}
}

func TestQuizPoolMatchesOriginalAnswers(t *testing.T) {
	exe, err := os.ReadFile("/orig/DQK.EXE")
	if err != nil {
		t.Skip("缺原版DQK.EXE，略過")
	}
	answers, err := decodeQuizPool(exe)
	if err != nil {
		t.Fatal(err)
	}
	// CREATION、MAY、ABOUT為實際出題時DS:C6F9的內容。
	for _, word := range []string{"CREATION", "MAY", "ABOUT", "SUCH", "DRUIDIC"} {
		if !answers[word] {
			t.Fatalf("題庫缺少%s", word)
		}
	}
	// THAC0是含數字的標題，能解出代表數字規則正確。
	for _, heading := range []string{"THE MOONS OF KRYNN", "RUNNING AWAY", "MAGICAL TREASURES", "THAC0"} {
		if answers[heading] {
			t.Fatalf("標題%s不應列為答案", heading)
		}
	}
	broken := append([]byte(nil), exe...)
	broken[dqkQuizPoolOffset] ^= 0x40
	if _, err := decodeQuizPool(broken); err == nil {
		t.Fatal("題庫位元組失配時應拒絕")
	}
}
