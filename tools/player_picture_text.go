package main

import (
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
)

func init() {
	playerPictureCapture = func(p *playerRenderOwner, c sourceTileCommand, a *sceneAsset) {
		l := p.PictureText
		if l == nil {
			return
		}
		for i := range l.Bindings {
			b := &l.Bindings[i]
			if b.Header != hex.EncodeToString(c.Header[:]) || c.Source.Linear()+uint32(b.SourceBytes-8) > 0xa0000 || uint32(c.Source.Off)+uint32(b.SourceBytes-8) > 65536 {
				continue
			}
			raw := append([]byte(nil), c.Header[:]...)
			raw = append(raw, p.Oracle.Bytes(c.Source, b.SourceBytes-8)...)
			if pictureDigest(raw) == b.SourceSHA256 && l.capture(b, a, p.Scene.page(c.Page, p.Oracle.PresentationPlane), c.X, c.Y, c.Page) {
				p.Counters["picture_text_sources"]++
				return
			}
		}
	}
}
func (p *playerRenderOwner) loadPictureText(profile string) {
	l, err := loadPictureText(filepath.Join(filepath.Dir(profile), "picture-text"))
	if err != nil {
		fmt.Fprintln(os.Stderr, "圖片文字資料失配，維持既有呈現：", err)
		return
	}
	p.PictureText = l
}
func (p *playerRenderOwner) preparePictureText(g *liveGame, page uint32, protected [][4]int) {
	if p.PictureText == nil || !g.translate {
		p.PictureRects = nil
		p.PictureBoxes = nil
		p.PictureKey = ""
		return
	}
	pal := p.Oracle.Palette()
	key := fmt.Sprintf("%d:%x:%t:%x:%v", p.Scene.Revision, page, g.player.HDEnabled, pal, protected)
	if key == p.PictureKey {
		return
	}
	p.PictureRects, p.PictureBoxes = p.PictureText.prepare(p.Scene.page(page, p.Oracle.PresentationPlane), page, pal, g.player.HDEnabled, protected)
	p.PictureKey = key
	if len(p.PictureRects) > 0 {
		p.Counters["picture_text_batches"]++
	}
}
