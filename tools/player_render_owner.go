// 玩家視窗只接收完整的前緩衝；原版顯存保留在背景相容路徑。
// 已列 primitive 的來源與界線見規格 005，完整 TLB 命令接管仍另列。
package main

import (
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/wicanr2/dosgolem/oracle"
)

type renderPrimitive struct {
	Name    string `json:"name"`
	Kind    string `json:"kind"`
	Segment uint16 `json:"segment"`
	Offset  uint16 `json:"offset"`
	Prefix  string `json:"prefix"`
}

type renderTransaction struct {
	Return paintReturn
	Origin oracle.Addr
	Step   uint64
}

type playerRenderOwner struct {
	Oracle      *oracle.Oracle
	Pending     []renderTransaction
	ShadowRGB   []byte
	Front, Back *ebiten.Image
	Text        *playerTextOwner
}

func init() { playerRenderLoader = loadPlayerRenderOwner }

func loadPlayerRenderOwner(o *oracle.Oracle, profile string, hd playerHDRenderer) playerFrameRenderer {
	raw, err := os.ReadFile(filepath.Join(profile, "render-hooks.json"))
	must(err)
	var bindings struct {
		Version          int
		ExecutableSHA256 string
		Hooks            []renderPrimitive
		ImageSource      renderPrimitive
		TextGlyph        renderPrimitive
	}
	must(json.Unmarshal(raw, &bindings))
	if bindings.Version != 1 || bindings.ExecutableSHA256 != "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58" || len(bindings.Hooks) != 22 {
		panic("繪圖掛勾資料與原版版本不符")
	}
	owner := &playerRenderOwner{Oracle: o, ShadowRGB: make([]byte, 320*200*3),
		Front: ebiten.NewImage(960, 600), Back: ebiten.NewImage(960, 600)}
	seen := map[oracle.Addr]bool{}
	// 先完整驗證，避免掛上半份邊界後才發現版本失配。
	for _, hook := range bindings.Hooks {
		entry := oracle.Addr{Seg: hook.Segment, Off: hook.Offset}
		want, err := hex.DecodeString(hook.Prefix)
		must(err)
		if hook.Name == "" || hook.Kind == "" || len(want) != 8 || seen[entry] || hex.EncodeToString(o.Bytes(entry, 8)) != hook.Prefix {
			panic(fmt.Sprintf("繪圖入口失配：%s %04X:%04X", hook.Name, entry.Seg, entry.Off))
		}
		seen[entry] = true
	}
	imageSource := oracle.Addr{Seg: bindings.ImageSource.Segment, Off: bindings.ImageSource.Offset}
	if imageSource != (oracle.Addr{Seg: 0x162e, Off: 0x229e}) || len(bindings.ImageSource.Prefix) != 16 ||
		hex.EncodeToString(o.Bytes(imageSource, 8)) != bindings.ImageSource.Prefix {
		panic("影像來源掛勾失配")
	}
	textGlyph := oracle.Addr{Seg: bindings.TextGlyph.Segment, Off: bindings.TextGlyph.Offset}
	if textGlyph != (oracle.Addr{Seg: 0x13c7, Off: 0xcb6}) || len(bindings.TextGlyph.Prefix) != 16 ||
		hex.EncodeToString(o.Bytes(textGlyph, 8)) != bindings.TextGlyph.Prefix {
		panic("字形來源掛勾失配")
	}
	o.OnCall(imageSource, func(_ *oracle.Oracle) {
		if hd == nil {
			return
		}
		r := o.Regs()
		if r.AX|r.DX == 0 {
			return
		}
		var command sourceTileCommand
		copy(command.Header[:], o.Bytes(oracle.Addr{Seg: r.SS, Off: r.BP - 18}, 8))
		command.Source = oracle.Addr{Seg: r.DX, Off: r.AX}
		command.Y = int(int16(o.Word(oracle.Addr{Seg: r.SS, Off: r.BP + 6}))) - int(int16(binary.LittleEndian.Uint16(command.Header[2:4])))
		command.X = int(int16(o.Word(oracle.Addr{Seg: r.SS, Off: r.BP + 8}))) - int(int16(binary.LittleEndian.Uint16(command.Header[4:6])))
		// header 已取得，尚未進入整張影像的分派、裁切或任何前景繪製。
		hd.CaptureTile(o, command)
	})
	returns := map[oracle.Addr]bool{}
	for _, hook := range bindings.Hooks {
		entry := oracle.Addr{Seg: hook.Segment, Off: hook.Offset}
		o.OnCall(entry, func(_ *oracle.Oracle) {
			if len(owner.Pending) >= 256 {
				panic("繪圖交易超過有界容量，停止提交半成品")
			}
			r := o.Regs()
			target := o.Caller()
			owner.Pending = append(owner.Pending, renderTransaction{
				Return: paintReturn{target, r.SS, r.SP + 4}, Origin: entry, Step: o.Steps()})
			if returns[target] {
				return
			}
			returns[target] = true
			o.OnCall(target, func(_ *oracle.Oracle) {
				r := o.Regs()
				for i := len(owner.Pending) - 1; i >= 0; i-- {
					p := owner.Pending[i].Return
					if p.Addr == target && p.SS == r.SS && p.SP == r.SP {
						// 同一返回點可被不同呼叫重用，以實際堆疊身分配對。
						owner.Pending = append(owner.Pending[:i], owner.Pending[i+1:]...)
						return
					}
				}
			})
		})
	}
	owner.Text = loadPlayerTextOwner(o, profile, textGlyph)
	return owner
}

func (p *playerRenderOwner) Busy() bool { return len(p.Pending) != 0 }

func (p *playerRenderOwner) Source() (int, int, []byte) {
	if !p.Busy() {
		w, h, rgb := p.Oracle.ScreenRGB()
		if w != 320 || h != 200 || len(rgb) != len(p.ShadowRGB) {
			panic("繪圖來源尺寸不符")
		}
		copy(p.ShadowRGB, rgb)
	}
	return 320, 200, p.ShadowRGB
}

func (p *playerRenderOwner) ComposeText(px []byte, g *liveGame, rgb []byte) {
	if !p.Busy() {
		p.Text.Compose(px, g, rgb)
	}
}

func (p *playerRenderOwner) Present(screen *ebiten.Image, g *liveGame, rgb []byte, held bool) {
	if !held && !p.Busy() {
		p.Back.Clear()
		op := &ebiten.DrawImageOptions{}
		op.GeoM.Scale(1.5, 1.5)
		p.Back.DrawImage(g.texture, op)
		if g.player.HD != nil {
			// 即使 HD 暫停顯示，也在完整畫格撤除已清掉的來源命令。
			g.player.HD.PrepareFrame(rgb)
		}
		if session := g.player; session.HD != nil && session.HDEnabled && g.translate {
			protected := append(g.playerProtectedRectangles(), p.Text.Rectangles()...)
			session.HD.Draw(p.Back, rgb, protected, false)
		}
		p.Front, p.Back = p.Back, p.Front
	}
	// 視窗永遠只接完整前緩衝，保留期間不重繪原圖或重算 HD。
	screen.DrawImage(p.Front, nil)
}
