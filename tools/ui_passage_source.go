// DRAFT：辨識已校讀的直接相鄰原位元串，不決定執行順序或顯示時機。
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"strings"
)

type passageSourceFragment struct {
	Offset       int    `json:"offset"`
	End          int    `json:"end"`
	PackedLength int    `json:"packed_length"`
	Key          string `json:"key"`
}

// 欄位沿既有 chain-inputs registry，沒有內嵌譯文。
type passageSourceBinding struct {
	Key                 string                  `json:"key"`
	ChunkSHA256         string                  `json:"chunk_sha256"`
	ChunkBytes          int                     `json:"chunk_bytes"`
	ChunkOffset         int                     `json:"chunk_offset"`
	EndChunkOffset      int                     `json:"end_chunk_offset"`
	PacketSHA256        string                  `json:"packet_sha256"`
	Fragments           []passageSourceFragment `json:"fragments"`
	LeadingContinuation bool                    `json:"leading_continuation,omitempty"`
}

type passageSourceObservation struct {
	DS, PointerSeg, PointerOff, CallerSeg, CallerOff uint16
	RawBaseOffset, RawCursorAfter                    uint16
	Kind, Opcode, Clear                              byte
	Script                                           []byte
	Source                                           string
}

type passageSourceCandidate struct {
	Key       string   `json:"key"`
	Part      int      `json:"part"`
	Fragments []string `json:"fragments"`
	Source    string   `json:"source"`
}

func passageSourceHash(raw []byte) string {
	h := sha256.Sum256(raw)
	return hex.EncodeToString(h[:])
}

func passageSourceDecode(raw []byte) string {
	var result []byte
	var bits uint32
	count := uint(0)
	for _, value := range raw {
		bits = bits<<8 | uint32(value)
		count += 8
		for count >= 6 {
			count -= 6
			value := byte((bits >> count) & 63)
			if value == 0 {
				continue
			}
			if value < 32 {
				value += 64
			}
			result = append(result, value)
		}
		bits &= (1 << count) - 1
	}
	return string(result)
}

// part 是目前已觀測的片段；後續片段只可標成候選，不表示原版已執行。
func matchPassageSource(b passageSourceBinding, sources map[string]string, part int, v passageSourceObservation) (passageSourceCandidate, bool) {
	fail := func() (passageSourceCandidate, bool) { return passageSourceCandidate{}, false }
	if len(b.Fragments) < 2 || len(b.Fragments) > 32 || part < 0 || part >= len(b.Fragments) ||
		v.DS != 0x333e || v.PointerSeg != 0x333e || v.PointerOff != 0xb487 || v.CallerSeg != 0x26b4 || v.Kind != 0x80 {
		return fail()
	}
	firstCaller, firstOpcode, firstClear := uint16(0x1d81), byte(0x12), byte(1)
	if b.LeadingContinuation {
		firstCaller, firstOpcode, firstClear = 0x1d53, 0x11, 0
	}
	if (part == 0 && (v.CallerOff != firstCaller || v.Opcode != firstOpcode || v.Clear != firstClear)) ||
		(part != 0 && (v.CallerOff != 0x1d53 || v.Opcode != 0x11 || v.Clear != 0)) {
		return fail()
	}
	if int(uint16(uint32(v.RawBaseOffset)+uint32(v.RawCursorAfter))) != b.Fragments[part].End ||
		b.ChunkBytes <= 0 || b.ChunkBytes > 0x8000 || len(v.Script) < b.ChunkBytes ||
		b.ChunkOffset < 0 || b.EndChunkOffset <= b.ChunkOffset || b.EndChunkOffset > b.ChunkBytes {
		return fail()
	}
	block := v.Script[:b.ChunkBytes]
	if passageSourceHash(block) != b.ChunkSHA256 || passageSourceHash(block[b.ChunkOffset:b.EndChunkOffset]) != b.PacketSHA256 {
		return fail()
	}
	pos := b.ChunkOffset
	fragments := make([]string, 0, len(b.Fragments))
	for i, fragment := range b.Fragments {
		opcode := byte(0x11)
		if i == 0 {
			opcode = firstOpcode
		}
		if fragment.Offset != pos || pos < 0 || pos+3 > b.EndChunkOffset ||
			block[pos] != opcode || block[pos+1] != 0x80 || int(block[pos+2]) != fragment.PackedLength || fragment.PackedLength == 0 {
			return fail()
		}
		end := pos + 3 + fragment.PackedLength
		if end != fragment.End || end > b.EndChunkOffset {
			return fail()
		}
		text := passageSourceDecode(block[pos+3 : end])
		if text == "" || strings.ContainsAny(text, "%\\\r\n\t") || fragment.Key != "ecl."+passageSourceHash([]byte(text))[:20] {
			return fail()
		}
		for _, c := range []byte(text) {
			if c < 32 || c > 126 {
				return fail()
			}
		}
		fragments = append(fragments, text)
		pos = end
	}
	text := strings.Join(fragments, "")
	limit := 96
	if b.LeadingContinuation {
		limit = 128
	}
	if pos != b.EndChunkOffset || len(text) > limit || fragments[part] != v.Source ||
		b.Key != "passage."+passageSourceHash([]byte(text))[:20] || sources[b.Key] != text {
		return fail()
	}
	return passageSourceCandidate{Key: b.Key, Part: part, Fragments: fragments, Source: text}, true
}
