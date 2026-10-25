// 紋理與矩形批次。後端不讀取 Oracle 或 DOS RAM。
package main

import (
	"github.com/hajimehoshi/ebiten/v2"
	"image"
)

type sceneBackend struct {
	HD, Native map[*sceneAsset]*ebiten.Image
	Palette    [256][3]byte
}

func clearSceneTextures(textures map[*sceneAsset]*ebiten.Image) {
	for _, t := range textures {
		t.Dispose()
	}
}
func (b *sceneBackend) close() { clearSceneTextures(b.HD); clearSceneTextures(b.Native) }
func (b *sceneBackend) submit(dst *ebiten.Image, rects []sceneRect, pal [256][3]byte) (builds, draws int) {
	if b.HD == nil {
		b.HD = map[*sceneAsset]*ebiten.Image{}
	}
	if b.Native == nil || b.Palette != pal {
		clearSceneTextures(b.Native)
		b.Native = map[*sceneAsset]*ebiten.Image{}
		b.Palette = pal
	}
	if len(b.HD)+len(b.Native) > 2048 {
		b.close()
		b.HD = map[*sceneAsset]*ebiten.Image{}
		b.Native = map[*sceneAsset]*ebiten.Image{}
	}
	for _, r := range rects {
		cache := b.Native
		scale := 1
		if r.HD {
			cache = b.HD
			scale = 3
		}
		texture := cache[r.Asset]
		if texture == nil {
			a := r.Asset
			texture = ebiten.NewImage(a.W*scale, a.H*scale)
			if r.HD {
				texture.WritePixels(a.HD)
			} else {
				rgba := make([]byte, a.W*a.H*4)
				for i, index := range a.Index {
					if len(a.Alpha) > 0 && a.Alpha[i] == 0 {
						continue
					}
					col := pal[index]
					copy(rgba[i*4:i*4+3], col[:])
					rgba[i*4+3] = 255
				}
				texture.WritePixels(rgba)
			}
			cache[a] = texture
			builds++
		}
		source := texture.SubImage(image.Rect(r.SX*scale, r.SY*scale, (r.SX+r.W)*scale, (r.SY+r.H)*scale)).(*ebiten.Image)
		op := &ebiten.DrawImageOptions{}
		op.GeoM.Scale(float64(3/scale), float64(3/scale))
		op.GeoM.Translate(float64(r.X*3), float64(r.Y*3))
		dst.DrawImage(source, op)
		draws++
	}
	return builds, draws
}
