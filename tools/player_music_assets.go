package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"github.com/jfreymuth/oggvorbis"
	"io"
	"math"
	"os"
	"path/filepath"
)

type musicAsset struct {
	Key string `json:"key"`
	SHA string `json:"ogg_sha256"`
	PCM struct {
		Frames int `json:"frames"`
	} `json:"pcm"`
}

func decodeMusic(raw []byte, frames int) ([]byte, error) {
	if frames <= 0 || frames > 48000*120 {
		return nil, fmt.Errorf("音樂長度越界")
	}
	reader, err := oggvorbis.NewReader(bytes.NewReader(raw))
	if err != nil {
		return nil, err
	}
	if reader.SampleRate() != 48000 || reader.Channels() != 2 || reader.Length() != int64(frames) {
		return nil, fmt.Errorf("音樂格式或長度失配")
	}
	pcm := make([]byte, 0, frames*4)
	floats := make([]float32, 8192)
	for {
		n, err := reader.Read(floats)
		if len(pcm)+n*2 > frames*4 {
			return nil, fmt.Errorf("解碼音樂長度越界")
		}
		for _, sample := range floats[:n] {
			if math.IsNaN(float64(sample)) || math.IsInf(float64(sample), 0) || sample > 1 || sample < -1 {
				return nil, fmt.Errorf("解碼音樂有無效取樣")
			}
			var pair [2]byte
			binary.LittleEndian.PutUint16(pair[:], uint16(int16(math.Round(float64(sample)*32767))))
			pcm = append(pcm, pair[:]...)
		}
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, err
		}
		if n == 0 {
			return nil, io.ErrNoProgress
		}
	}
	if len(pcm) != frames*4 {
		return nil, fmt.Errorf("解碼音樂長度不足")
	}
	return pcm, nil
}

func loadMusicAssets(directory string) (map[string][]byte, error) {
	raw, err := os.ReadFile(filepath.Join(directory, "manifest.json"))
	if err != nil {
		return nil, err
	}
	var manifest struct {
		Schema     int          `json:"schema"`
		Tracks     []musicAsset `json:"tracks"`
		SampleRate int          `json:"sample_rate"`
		Channels   int          `json:"channels"`
	}
	if err = json.Unmarshal(raw, &manifest); err != nil {
		return nil, err
	}
	if manifest.Schema != 1 || len(manifest.Tracks) != 8 || manifest.SampleRate != 48000 || manifest.Channels != 2 {
		return nil, fmt.Errorf("音樂清單格式不符")
	}
	assets := map[string][]byte{}
	for _, track := range manifest.Tracks {
		var group, seq int
		if _, err := fmt.Sscanf(track.Key, "RODQ%d-%d", &group, &seq); err != nil || musicKey(fmt.Sprintf("RODQ%d.XMI", group), seq) != track.Key || assets[track.Key] != nil {
			return nil, fmt.Errorf("音樂識別失配")
		}
		path := filepath.Join(directory, track.Key+".ogg")
		info, err := os.Stat(path)
		if err != nil {
			return nil, err
		}
		if !info.Mode().IsRegular() || info.Size() > 4<<20 {
			return nil, fmt.Errorf("音樂檔案越界")
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return nil, err
		}
		hash := sha256.Sum256(data)
		if hex.EncodeToString(hash[:]) != track.SHA {
			return nil, fmt.Errorf("音樂雜湊失配：%s", track.Key)
		}
		pcm, err := decodeMusic(data, track.PCM.Frames)
		if err != nil {
			return nil, fmt.Errorf("%s：%w", track.Key, err)
		}
		assets[track.Key] = pcm
	}
	return assets, nil
}
