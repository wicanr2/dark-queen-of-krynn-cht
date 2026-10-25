package main

import "testing"

func TestSpellRowSource(t *testing.T) {
	for _, row := range [][2]string{{"\tMagic Missile", "Magic Missile"}, {"\tMagic Missile (5)", "Magic Missile"},
		{"\tFireball (2)", "Fireball"}, {"\tCone of Cold (2)", "Cone of Cold"},
		{"\tProtection From Good 10' Radius (2)", "Protection From Good 10' Radius"}} {
		if !spellRowSource(row[0], row[1]) {
			t.Fatalf("合法顯示結構未匹配: %q", row[0])
		}
	}
	for _, source := range []string{"Magic Missile (5)", "\t\tMagic Missile (5)", "\tMagic Missile (0)", "\tMagic Missile (05)", "\tMagic Missile (-1)", "\tMagic Missile (5) extra", "\tMagic Missile (5", "\tMagic Missile ()", "No 30 Arrows +1"} {
		if spellRowSource(source, "Magic Missile") {
			t.Fatalf("未知格式應保留原版: %q", source)
		}
	}
	if spellRowSource("\tProtection From Good 10' Radius (2)", "Protection From Good") {
		t.Fatal("不得把另一法術的完整名稱當成短名稱加次數")
	}
}
