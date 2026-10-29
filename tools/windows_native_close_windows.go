//go:build windows

// 只供Wine封包驗證：送出Windows的正常關窗訊息，不終止程序或改遊戲記憶體。
package main

import (
	"fmt"
	"os"
	"strings"
	"syscall"
	"unsafe"
)

func main() {
	user32 := syscall.NewLazyDLL("user32.dll")
	getText := user32.NewProc("GetWindowTextW")
	post := user32.NewProc("PostMessageW")
	posted := false
	callback := syscall.NewCallback(func(hwnd, unused uintptr) uintptr {
		var title [512]uint16
		getText.Call(hwnd, uintptr(unsafe.Pointer(&title[0])), uintptr(len(title)))
		if !strings.HasPrefix(syscall.UTF16ToString(title[:]), "黑暗之后 · ") {
			return 1
		}
		result, _, _ := post.Call(hwnd, 0x0010, 0, 0) // WM_CLOSE
		posted = result != 0
		fmt.Printf("WM_CLOSE hwnd=%x posted=%t\n", hwnd, posted)
		return 0
	})
	user32.NewProc("EnumWindows").Call(callback, 0)
	if !posted {
		os.Exit(2)
	}
}
