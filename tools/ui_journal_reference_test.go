package main

import (
	"os"
	"strconv"
	"strings"
	"testing"
)

func TestJournalLiteralOriginalSources(t *testing.T) {
	const path = "/catalogs/en.tsv"
	if _, err := os.Stat(path); err != nil {
		t.Skip("未掛載本機原始目錄，略過真實來源測試")
	}
	sources := readLiveCatalog(path)
	expected := map[string]int{
		"ecl.329431c306e2c18a32f5": 65,
		"ecl.cebe248eb5a12c58345e": 39,
		"ecl.343b2defdb962a661579": 7,
		"ecl.a009fe4812e8bb40e573": 56,
		"ecl.9d85a84571b31de4f0ba": 23,
		"ecl.7889f96fe232e846977a": 2,
		"ecl.c5081d302c08d5b49090": 17,
		"ecl.2d07e522eb8268f57a6c": 49,
		"ecl.bb1f434e4ccb2c00fe38": 5,
		"ecl.644fefe0dbad36054e38": 9,
	}
	for key, want := range expected {
		source, exists := sources[key]
		if !exists {
			t.Fatalf("原始來源缺鍵 %s", key)
		}
		got, ok := journalLiteralNumber(source)
		if !ok || got != want {
			t.Fatalf("%s: got %d/%t, want %d", key, got, ok, want)
		}
		for _, bad := range []string{
			source + "X", strings.TrimSuffix(source, "."),
			strings.TrimSuffix(source, strconv.Itoa(want)+".") + "0" + strconv.Itoa(want) + ".",
			strings.Replace(source, "JOURNAL ENTRY", "JOURNAL ENTRIES", 1),
		} {
			if _, accepted := journalLiteralNumber(bad); accepted {
				t.Fatalf("原始格式變造未拒絕 %s", key)
			}
		}
	}
}

func TestJournalLiteralCanonicalNumbers(t *testing.T) {
	for _, bad := range []string{
		"X AS JOURNAL ENTRY 0.", "X AS JOURNAL ENTRY 100.",
		"X AS JOURNAL ENTRY +5.", "X AS JOURNAL ENTRY -5.",
		"X AS JOURNAL ENTRY 5 .", "X AS JOURNAL ENTRY #5.",
		"X AS JOURNAL ENTRY #  5.", "X AS JOURNAL ENTRY .",
	} {
		if _, ok := journalLiteralNumber(bad); ok {
			t.Fatalf("非原版編號形狀未拒絕 %q", bad)
		}
	}
}
