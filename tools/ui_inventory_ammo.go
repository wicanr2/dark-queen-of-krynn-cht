package main

import (
	"strconv"
	"strings"
)

type ammoRowParts struct {
	Ready                 string
	Quantity              int32
	Bonus                 string
	ReadyStart, NameStart int
}

func inventoryAmmoForm(key string) int {
	switch key {
	case "inventory.05800e70aa10c86f5ab8", "inventory.ea0151c4cf78b351118d":
		return 1
	case "inventory.423c677c12e0b601c34c", "inventory.d3e53a2e348022ba16a6":
		return 2
	}
	return 0
}

func ammoQuantityMatches(key string, quantity int32) bool {
	form := inventoryAmmoForm(key)
	return (form == 1 && quantity == 1) || (form == 2 && quantity > 1)
}

// 只拆已觀測的背包列格式。數量與加值仍由原版輸出，不改寫或重算。
func matchAmmoRow(text, root, yes, no string) (ammoRowParts, bool) {
	fail := func() (ammoRowParts, bool) { return ammoRowParts{}, false }
	if root == "" || yes == "" || no == "" || yes == no || !strings.HasPrefix(text, " ") || !strings.HasSuffix(text, " ") || strings.Count(text, "\t") != 1 {
		return fail()
	}
	tab := strings.IndexByte(text, '\t')
	ready := text[1:tab]
	if (ready != yes && ready != no) || len(ready) > 3 {
		return fail()
	}
	tail := text[tab+1 : len(text)-1]
	padding := strings.Repeat(" ", 3-len(ready))
	if !strings.HasPrefix(tail, padding) {
		return fail()
	}
	tail = tail[len(padding):]
	space := strings.IndexByte(tail, ' ')
	if space <= 0 {
		return fail()
	}
	quantityText := tail[:space]
	quantity, err := strconv.ParseInt(quantityText, 10, 32)
	if err != nil || quantity <= 0 || strconv.FormatInt(quantity, 10) != quantityText {
		return fail()
	}
	name := tail[space+1:]
	bonus := ""
	if name != root {
		if !strings.HasPrefix(name, root+" +") {
			return fail()
		}
		bonus = name[len(root)+1:]
		value, err := strconv.ParseInt(bonus[1:], 10, 32)
		if err != nil || value <= 0 || "+"+strconv.FormatInt(value, 10) != bonus {
			return fail()
		}
	}
	return ammoRowParts{Ready: ready, Quantity: int32(quantity), Bonus: bonus, ReadyStart: 1,
		NameStart: tab + 1 + len(padding) + space + 1}, true
}
