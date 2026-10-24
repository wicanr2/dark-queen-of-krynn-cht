package main

import (
	"encoding/json"
	"os"
	"testing"
)

func TestObservedParagraphPredecessor(t *testing.T) {
	raw, err := os.ReadFile("/out/inputs-r1/inputs.json")
	if err != nil {
		t.Fatal(err)
	}
	var config struct{ Paragraphs []listParagraph }
	if err := json.Unmarshal(raw, &config); err != nil {
		t.Fatal(err)
	}
	var binding *listParagraph
	for i := range config.Paragraphs {
		if config.Paragraphs[i].Key == "ecl.265fda17a34611b1533d" {
			binding = &config.Paragraphs[i]
		}
	}
	if binding == nil || binding.PredecessorKey != "ecl.437aee976a56a4f37a63" {
		t.Fatal("缺少原版 Explain 的開引號來源")
	}
	previous := binding.PredecessorKey
	for _, test := range []struct {
		name string
		page *storyPage
		want bool
	}{
		{"normal-introduction", &storyPage{Key: previous, Components: []string{previous}}, true},
		{"missing-page", nil, false},
		{"empty-components", &storyPage{Key: previous}, false},
		{"opening-already-appended", &storyPage{Key: binding.Key, Components: []string{previous, binding.Key}}, false},
		{"closing-context", &storyPage{Key: "ecl.93facbfe1b03675657da", Components: []string{previous, binding.Key, "ecl.93facbfe1b03675657da"}}, false},
		{"wrong-latest-component", &storyPage{Key: previous, Components: []string{previous, binding.Key}}, false},
	} {
		t.Run(test.name, func(t *testing.T) {
			if got := paragraphPredecessor(binding, test.page); got != test.want {
				t.Fatalf("接受=%v，預期=%v", got, test.want)
			}
		})
	}
	if !paragraphPredecessor(&listParagraph{}, nil) {
		t.Fatal("一般段落不能新增前文限制")
	}
}
