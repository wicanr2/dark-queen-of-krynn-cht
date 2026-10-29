package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestOriginalMusicAliases(t *testing.T) {
	for _, prefix := range []string{"AD", "RO", "TY", "PC"} {
		for _, key := range []struct {
			file string
			seq  int
			want string
		}{{"DQ1.XMI", 0, "RODQ1-0"}, {"DQ2.XMI", 0, "RODQ2-0"}, {"DQ2.XMI", 1, "RODQ2-1"}, {"DQ2.XMI", 2, "RODQ2-2"}, {"DQ2.XMI", 3, "RODQ2-3"}, {"DQ2.XMI", 4, "RODQ2-4"}, {"DQ2.XMI", 5, "RODQ2-5"}, {"DQ3.XMI", 0, "RODQ3-0"}} {
			if got := musicKey(prefix+key.file, key.seq); got != key.want {
				t.Fatalf("%s:%d=%s", prefix+key.file, key.seq, got)
			}
		}
	}
	for _, key := range []struct {
		file string
		seq  int
	}{{"PCDQ1.XMI", 1}, {"PCDQ2.XMI", 6}, {"PCDQ3.XMI", -1}, {"RODQ4.XMI", 0}, {"PCDQ1.XMI.extra", 0}, {"../PCDQ1.XMI", 0}, {"SFXDQ.VOC", 0}} {
		if musicKey(key.file, key.seq) != "" {
			t.Fatal(key)
		}
	}
}

func TestDecodeOriginalScoreMusic(t *testing.T) {
	directory := os.Getenv("DQK_MUSIC_ASSETS")
	if directory == "" {
		t.Skip("需要本機原譜衍生音樂")
	}
	assets, err := loadMusicAssets(directory)
	if err != nil {
		t.Fatal(err)
	}
	if len(assets) != 8 {
		t.Fatal(len(assets))
	}
	for key, data := range assets {
		if len(data) < 48000*4 {
			t.Fatal(key)
		}
		t.Logf("%s: %d PCM bytes", key, len(data))
	}
	if _, err = decodeMusic([]byte("damaged ogg"), 48000); err == nil {
		t.Fatal("接受損壞音樂")
	}
	if _, err = decodeMusic(nil, 48000*121); err == nil {
		t.Fatal("接受超長音樂")
	}
	if _, err = loadMusicAssets(filepath.Join(directory, "missing")); err == nil {
		t.Fatal("接受不存在清單")
	}
}
