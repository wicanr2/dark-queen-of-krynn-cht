// DRAFT：只匹配已證實的單行武器名稱及原版加值，不改原始字串。
package main

import "strings"

type hudWeaponPart struct {
	Key, Name, Suffix string
}

func hudWeaponVocabulary(keys []string, sources, targets map[string]string) bool {
	seen := map[string]bool{}
	for _, key := range keys {
		name, text := sources[key], targets[key]
		if name == "" || len(name) > 15 || name != strings.TrimSpace(name) || text == "" ||
			len([]rune(text)) > len(name) || seen[name] {
			return false
		}
		for _, ch := range []byte(name) {
			if ch < 32 || ch > 126 || strings.ContainsRune("%\\+", rune(ch)) {
				return false
			}
		}
		seen[name] = true
	}
	return true
}

func hudWeaponName(keys []string, sources map[string]string, source string) (hudWeaponPart, bool) {
	if len(source) < 2 || len(source) > 16 || !strings.HasSuffix(source, " ") {
		return hudWeaponPart{}, false
	}
	for _, key := range keys {
		name := sources[key]
		if name == "" || !strings.HasPrefix(source, name) {
			continue
		}
		suffix := source[len(name):]
		valid := suffix == " "
		if strings.HasPrefix(suffix, " +") && len(suffix) >= 4 {
			digits := suffix[2 : len(suffix)-1]
			valid = digits[0] >= '1' && digits[0] <= '9'
			for _, digit := range []byte(digits) {
				valid = valid && digit >= '0' && digit <= '9'
			}
		}
		if valid {
			return hudWeaponPart{key, name, suffix}, true
		}
	}
	return hudWeaponPart{}, false
}
