package windowbridge

import (
	"strings"
	"syscall"
	"unsafe"
)

var user32 = syscall.NewLazyDLL("user32.dll")
var enumWindows = user32.NewProc("EnumWindows")
var windowPID = user32.NewProc("GetWindowThreadProcessId")
var windowText = user32.NewProc("GetWindowTextW")
var isIconic = user32.NewProc("IsIconic")
var showAsync = user32.NewProc("ShowWindowAsync")
var foreground = user32.NewProc("SetForegroundWindow")

var restoreCallback = syscall.NewCallback(func(hwnd, parentPID uintptr) uintptr {
	var owner uint32
	windowPID.Call(hwnd, uintptr(unsafe.Pointer(&owner)))
	if owner != uint32(parentPID) {
		return 1
	}
	var title [512]uint16
	windowText.Call(hwnd, uintptr(unsafe.Pointer(&title[0])), uintptr(len(title)))
	if !strings.Contains(syscall.UTF16ToString(title[:]), "黑暗之后") {
		return 1
	}
	mode := uintptr(5) // SW_SHOW保留原本大小及最大化狀態。
	if iconic, _, _ := isIconic.Call(hwnd); iconic != 0 {
		mode = 9
	} // SW_RESTORE
	showAsync.Call(hwnd, mode)
	foreground.Call(hwnd)
	return 0
})

// RestoreParent只處理本次啟動者的遊戲視窗，不查找或改動其他程序。
// 從地圖程序呼叫，讓主視窗的訊息迴圈恢復，不依賴被縮小的主視窗先跑Update。
func RestoreParent(pid int) {
	if pid > 0 {
		enumWindows.Call(restoreCallback, uintptr(pid))
	}
}
