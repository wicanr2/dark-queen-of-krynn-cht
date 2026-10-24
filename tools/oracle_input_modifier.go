// DRAFT 編譯 overlay：以既有 DOS 入口送 Alt 字母，不改遊戲記憶體。
// 掛到 /src/oracle/dqk_input_modifier.go；只供本專案隔離研究工具使用。
package oracle

import (
	"fmt"

	"github.com/wicanr2/dosgolem/internal/dos"
)

func (o *Oracle) PressBIOSAltKey(letter string) error {
	if len(letter) != 1 {
		return fmt.Errorf("Alt 按鍵須為單一 ASCII 字母")
	}
	key, ok := dos.KeyAlt(letter[0])
	if !ok {
		return fmt.Errorf("不支援的 Alt 字母 %q", letter)
	}
	o.d.PushKey(key)
	return nil
}
