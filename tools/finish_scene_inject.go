// 只供使用者授權的場景抽驗及影片素材，不連入正式來源清單。
package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"github.com/wicanr2/dosgolem/oracle"
)

func init() {
	base:=playerRenderLoader
	playerRenderLoader=func(o *oracle.Oracle,profile string,hd playerHDRenderer)playerFrameRenderer {
		path:=os.Getenv("DQK_SAMPLE_STATE")
		raw,err:=os.ReadFile(path);must(err)
		must(o.LoadStateFile(path))
		out:=os.Getenv("DQK_SAMPLE_OUT")
		o.SetScratch(filepath.Join(out,"saves"))
		proof:=map[string]any{"state_injection":true,"snapshot":path,"snapshot_sha256":digest(raw),"steps":o.Steps(),"scope":"既有合法原版快照；之後使用XTEST正常輸入重畫，非冷啟動或通關證據"}
		data,err:=json.MarshalIndent(proof,"","  ");must(err)
		must(os.WriteFile(filepath.Join(out,"injection.json"),append(data,'\n'),0644))
		return base(o,profile,hd)
	}
}
