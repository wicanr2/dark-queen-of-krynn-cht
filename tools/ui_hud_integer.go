package main

import (
	"strconv"
	"strings"
)

// 只辨識顯示字串的一個十進位參數，不讀取或改寫原版傷害資料。
func hudIntegerTemplate(pattern string) bool {
	if strings.Count(pattern, "%d") != 1 || strings.Contains(strings.Replace(pattern, "%d", "", 1), "%") {
		return false
	}
	left, right, _ := strings.Cut(pattern, "%d")
	return left != "" && right != ""
}

func hudInteger(source, pattern string) (int32, bool) {
	if !hudIntegerTemplate(pattern) {
		return 0, false
	}
	left, right, _ := strings.Cut(pattern, "%d")
	if len(source) <= len(left)+len(right) || !strings.HasPrefix(source, left) || !strings.HasSuffix(source, right) {
		return 0, false
	}
	raw := source[len(left) : len(source)-len(right)]
	value, err := strconv.ParseInt(raw, 10, 32)
	if err != nil || strconv.FormatInt(value, 10) != raw {
		return 0, false
	}
	return int32(value), true
}

func hudIntegerText(pattern string, value int32) (string, bool) {
	if !hudIntegerTemplate(pattern) {
		return "", false
	}
	return strings.Replace(pattern, "%d", strconv.FormatInt(int64(value), 10), 1), true
}
