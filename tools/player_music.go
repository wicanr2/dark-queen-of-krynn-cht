package main

import (
	"bytes"
	"encoding/json"
	"github.com/ebitengine/oto/v3"
	"github.com/wicanr2/dosgolem/oracle"
	"os"
	"path/filepath"
)

type playerMusic struct {
	context *oto.Context
	player  *oto.Player
	assets  map[string][]byte
	key     string
	volume  int
	enabled bool
	events  []musicCue
	errors  []string
}

func (m *playerMusic) Available() bool {
	return m.context != nil && m.context.Err() == nil && len(m.assets) == 8
}
func (m *playerMusic) applyVolume() {
	if m.player != nil {
		volume := float64(m.volume) / 100
		if !m.enabled {
			volume = 0
		}
		m.player.SetVolume(volume)
	}
}
func (m *playerMusic) SetEnabled(enabled bool) { m.enabled = enabled; m.applyVolume() }
func (m *playerMusic) cue(cue musicCue) {
	if len(m.events) >= 256 {
		m.events = append([]musicCue(nil), m.events[len(m.events)-128:]...)
	}
	m.events = append(m.events, cue)
	if !m.Available() {
		return
	}
	switch cue.Kind {
	case "start":
		if m.player != nil {
			_ = m.player.Close()
		}
		m.key, m.volume = cue.Key, cue.Volume
		m.player = m.context.NewPlayer(bytes.NewReader(m.assets[cue.Key]))
		m.applyVolume()
		m.player.Play()
	case "stop":
		if cue.Key == m.key && m.player != nil {
			_ = m.player.Close()
			m.player = nil
			m.key = ""
		}
	case "volume":
		if cue.Key == m.key {
			m.volume = cue.Volume
			m.applyVolume()
		}
	}
}
func (m *playerMusic) Close(directory string) {
	if m.player != nil {
		_ = m.player.Close()
	}
	if m.context != nil && m.context.Err() != nil {
		m.errors = append(m.errors, m.context.Err().Error())
	}
	raw, err := json.MarshalIndent(map[string]any{"schema": 1, "available": m.Available(), "enabled": m.enabled, "events": m.events, "errors": m.errors, "clock": "standard audio device, hardware-spec approximation"}, "", "  ")
	if err == nil {
		_ = os.WriteFile(filepath.Join(directory, "music-events.json"), append(raw, '\n'), 0644)
	}
}
func newPlayerMusic(o *oracle.Oracle, directory string) *playerMusic {
	m := &playerMusic{enabled: true, volume: 100}
	if err := observeMusic(o, m.cue); err != nil {
		m.errors = append(m.errors, err.Error())
		return m
	}
	assets, err := loadMusicAssets(directory)
	if err != nil {
		m.errors = append(m.errors, err.Error())
		return m
	}
	m.assets = assets
	context, _, err := oto.NewContext(&oto.NewContextOptions{SampleRate: 48000, ChannelCount: 2, Format: oto.FormatSignedInt16LE})
	if err != nil {
		m.errors = append(m.errors, err.Error())
		return m
	}
	m.context = context
	return m
}

func init() {
	playerMusicLoader = func(o *oracle.Oracle, directory string) playerMusicRenderer { return newPlayerMusic(o, directory) }
}
