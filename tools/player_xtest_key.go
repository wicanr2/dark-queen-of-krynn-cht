// GUI 抽驗專用。透過既有 XGB/XTEST 套件產生伺服器鍵盤事件，不修改遊戲狀態。
package main

import (
	"fmt"
	"os"
	"strconv"

	"github.com/jezek/xgb"
	"github.com/jezek/xgb/xproto"
	"github.com/jezek/xgb/xtest"
)

func main() {
	if len(os.Args) != 3 || (os.Args[2] != "down" && os.Args[2] != "up" && os.Args[2] != "mouse-down" && os.Args[2] != "mouse-up") {
		panic("用法：xtest-key <X11 keycode或button> down|up|mouse-down|mouse-up")
	}
	code, err := strconv.ParseUint(os.Args[1], 10, 8)
	if err != nil || code == 0 {
		panic("X11 keycode無效")
	}
	conn, err := xgb.NewConn()
	if err != nil {
		panic(err)
	}
	defer conn.Close()
	if err := xtest.Init(conn); err != nil {
		panic(err)
	}
	kind := byte(xproto.KeyRelease)
	if os.Args[2] == "down" {
		kind = xproto.KeyPress
	}
	if os.Args[2] == "mouse-down" {
		kind = xproto.ButtonPress
	}
	if os.Args[2] == "mouse-up" {
		kind = xproto.ButtonRelease
	}
	root := xproto.Setup(conn).Roots[0].Root
	if err := xtest.FakeInputChecked(conn, kind, byte(code), 0, root, 0, 0, 0).Check(); err != nil {
		panic(fmt.Errorf("XTEST鍵盤事件失敗：%w", err))
	}
}
