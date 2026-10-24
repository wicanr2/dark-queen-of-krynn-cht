"""核對列表原型的自動選譯、原版狀態及實際 GPU 提交畫格。"""
import base64
import csv
import hashlib
import json
import re
import struct
import sys
from pathlib import Path
from PIL import Image


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    # 長重播逐幀保存相同色盤。只共用唯讀色盤，完整保留所有畫格與原始 JSON 值。
    palettes = {}
    def intern_palette(record):
        palette = record.get('palette')
        if (isinstance(palette,list) and len(palette)==256 and all(isinstance(c,list) and len(c)==3
            and all(type(v) is int for v in c) for c in palette)):
            key=tuple(tuple(c) for c in palette)
            record['palette']=palettes.setdefault(key,palette)
        return record
    return json.loads(path.read_text(),object_hook=intern_palette)


def check_battle_sources(inputs, config, provenance, en, zh, glyphs, trace):
    from ui_list_inputs import catalog
    proof=provenance["battle_extension"]
    source_path=inputs.parent.parent/proof["source_path"]
    assert source_path.resolve().is_relative_to(inputs.parent.parent.resolve()) and sha(source_path.read_bytes())==proof["source_sha256"]
    source_trace=read(source_path)
    assert source_trace["exe_sha256"]==trace["exe_sha256"]
    trace=source_trace
    base=inputs.parent.parent/proof["base"]
    assert base.resolve().is_relative_to(inputs.parent.parent.resolve())
    assert set(proof["base_files"])=={p.name for p in base.iterdir() if p.is_file()}
    for name,h in proof["base_files"].items():assert sha((base/name).read_bytes())==h
    old=read(base/"inputs.json");parent=read(base/"provenance.json")
    assert {k:v for k,v in provenance.items() if k!="battle_extension"}=={k:v for k,v in parent.items() if not k.endswith("_extension")}
    assert config["Fields"]==old["Fields"]+[r["binding"] for r in proof["fields"]]
    assert config["Paragraphs"]==old["Paragraphs"]+[r["binding"] for r in proof["paragraphs"]]
    for name in set(config)-{"Fields","Paragraphs","Menus","fine_windows"}:assert config[name]==old[name]
    assert set(config)==set(old)
    menus=dict(old["Menus"])
    for m in proof["menus"]:
        assert m in trace["menus"]
        words=[bytes.fromhex(b["SourceHex"]).decode() for b in m["Buttons"]]
        assert words in (["Aim","Use","Cast","Guard","Quick","Delay","View","Speed","End"],["Next","Prev","Manual","Center","Exit"])
        menus[m["Signature"]]="combat" if len(words)==9 else "aiming"
    assert config["Menus"]==menus
    expected_buttons=set()
    for m in trace["menus"]:
        words=[bytes.fromhex(b["SourceHex"]).decode() for b in m["Buttons"]]
        if words in (["Aim","Use","Cast","Guard","Quick","Delay","View","Speed","End"],["Next","Prev","Manual","Center","Exit"]):
            assert m["Signature"] in config["Menus"],"battle menu shape untranslated"
            if m["Signature"] not in old["Menus"]:
                expected_buttons.update((m["Signature"],b["Index"]) for b in m["Buttons"])
    actual_buttons=[(r["menu_signature"],r["button_index"]) for r in proof["fields"] if r["kind"]=="menu"]
    assert len(actual_buttons)==len(set(actual_buttons)) and set(actual_buttons)==expected_buttons,"battle menu buttons incomplete"
    base_en,base_zh=catalog(base/"en.tsv"),catalog(base/"zh-TW.tsv")
    for values,previous in [(en,base_en),(zh,base_zh)]:
        assert all(values[k]==v for k,v in previous.items())
        assert set(values)==set(previous)|set(proof["origins"])
    texts=Path("/catalogs")
    for name,h in proof["formal_files"].items():assert sha((texts/name).read_bytes())==h
    formal_en,formal_zh=catalog(texts/"en.tsv"),catalog(texts/"zh-TW.tsv")
    terms=list(csv.DictReader((texts/"glossary.tsv").open(),delimiter="\t"))
    bank=texts/"battle-ui-review.tsv";assert sha(bank.read_bytes())==proof["review_sha256"]
    review={v["key"]:v for v in csv.DictReader(bank.open(),delimiter="\t")}
    for key,origin in proof["origins"].items():
        if "review" in origin:
            row=review[key];assert row==origin["review"] and (en[key],zh[key])==(row["en"],row["text"])
            assert any(t["en"]==row["glossary_en"] for t in terms)
            if row["formal_key"]:assert formal_en[row["formal_key"]]==row["en"]
        elif "formal_key" in origin:
            k=origin["formal_key"];assert (en[key],zh[key])==(formal_en[k],formal_zh[k])
        else:
            term=origin["glossary"];assert term in terms and term["category"]=="ui"
            assert en[key].casefold()==term["en"].casefold() and zh[key]==term["zh"]
    untouched=set(proof["base_files"])-{"en.tsv","zh-TW.tsv","font-zh-TW.tsv","inputs.json","provenance.json","glyphs-16.json"}
    for name in untouched:assert (inputs/name).read_bytes()==(base/name).read_bytes()
    old_glyphs=read(base/"glyphs-16.json")
    assert all(glyphs[k]==old_glyphs[k] for k in ("size","height","font_sha256"))
    assert all(glyphs["glyphs"][k]==v for k,v in old_glyphs["glyphs"].items())
    old_font=catalog(base/"font-zh-TW.tsv");expected_font=dict(old_font)
    expected_font.update({k:zh[k] for k in proof["origins"]})
    assert catalog(inputs/"font-zh-TW.tsv")==expected_font
    required=set("".join(expected_font.values()))-set("\r\n\t")
    assert set(glyphs["glyphs"])==set(old_glyphs["glyphs"])|required
    path=inputs.parent.parent/proof["source_path"]
    assert path.resolve()==(inputs.parent.parent/"battle-text-20261024/observe-route-r1/receipt.json").resolve()
    assert sha(path.read_bytes())==proof["source_sha256"]
    calls={c["step"]:c for c in trace["calls"]}
    for row in proof["fields"]:
        f=row["binding"]
        assert f["Start"]==0 and f["Length"]==len(en[f["Key"]]),"battle lexical mask mismatch"
        if row["kind"]=="menu":
            m=next(m for m in trace["menus"] if m["Signature"]==row["menu_signature"])
            b=next(b for b in m["Buttons"] if b["Index"]==row["button_index"])
            assert bytes.fromhex(b["SourceHex"]).decode()==en[f["Key"]]
            assert f["SHA256"]==f["FormatSHA256"]==b["SHA256"]
            native=lambda v:v if v<400 else (v-8000)*2
            assert [f["RawX"],f["RawY"]]==[native(b["RawX"]),native(b["RawY"])+1]
            assert f["Pane"]=="menu" and f["Group"]=="footer" and f["Caller"]=={"Seg":0xCEB,"Off":0x1BE}
            assert f["MenuSignature"]==m["Signature"]
        else:
            c=calls[row["call_step"]];w=trace["wrappers"][c["wrapper_index"]];source=c["vararg_1_candidate"]["text"]
            assert f["Pane"]=="callsite" and f["Caller"]==c["caller"]=={"Seg":0xB72,"Off":0x27C}
            assert f["UpperCaller"]==w["caller"] and f["FormatSHA256"]==sha(b"%s") and c["format"]["text"]=="%s"
            assert f["SHA256"]==sha(source.encode()) and source[:f["Length"]]==en[f["Key"]]
            assert source in ("Hitpoints","AC","A battle begins...","Aim: range = 0 ")
            assert w["format"]["text"]==source and [f["RawY"],f["RawX"]]==c["stack"][2:4]
            assert (row["first_glyph"],row["return_step"])==(c["first_glyph"],c["return_step"]) and c["step"]<c["first_glyph"]
            assert f["Group"]==("body" if source in ("Hitpoints","AC") else "footer")
            if source in ("A battle begins...","Aim: range = 0 "):
                assert f["UpperNative"]==[(w["stack"][i]&255)*8 for i in (2,3)],"battle upper coordinate contract mismatch"
                assert f["Color"]==c["stack"][4]==0x8f and "BackgroundOverride" not in f
            else:assert not any(k in f for k in ("UpperNative","Color","BackgroundOverride"))
    native_paragraphs={p["step"]:p for p in trace["paragraphs"] or []}
    for row in proof["paragraphs"]:
        p=native_paragraphs[row["step"]];f=row["binding"];source=p["source"]["text"]
        assert f["Key"]=="ecl."+sha(source.encode())[:20] and en[f["Key"]]==source
        assert f["SHA256"]==sha(source.encode()) and f["Caller"]==p["caller"]
        assert f["NativeBox"]==p["native_box"]==[8,136,312,184]
        assert [f[k] for k in ("Foreground","Background","Clear")]==[p[k] for k in ("foreground","background","clear")]
        assert (row["first_glyph"],row["return_step"])==(p["first_glyph"],p["return_step"])
        if f.get("JournalEntry"):
            match=re.search(r" AS JOURNAL ENTRY ([1-9][0-9]?)\.$",source)
            assert match and f["JournalEntry"]==int(match[1]),"battle journal source number mismatch"
    return source_trace


def check_literal_catalog_sources(inputs,config,provenance,en,zh,glyphs):
    from ui_list_inputs import catalog
    proof=provenance["literal_catalog_extension"]
    base=inputs.parent.parent/proof["base"]
    assert base.resolve().is_relative_to(inputs.parent.parent.resolve())
    assert set(proof["base_files"])=={p.name for p in base.iterdir() if p.is_file()}
    for name,h in proof["base_files"].items():assert sha((base/name).read_bytes())==h
    old,parent=read(base/"inputs.json"),read(base/"provenance.json")
    assert {k:v for k,v in provenance.items() if k!="literal_catalog_extension"}==parent
    assert set(config)==set(old)
    assert all(config[k]==old[k] for k in config if k not in ("Paragraphs","fine_windows")),"literal catalog inherited config mismatch"
    texts=Path("/catalogs")
    for name,h in proof["formal_files"].items():assert sha((texts/name).read_bytes())==h
    assert sha((texts/"passage-candidates.json").read_bytes())==proof["fragments_sha256"]
    source,target=catalog(texts/"en.tsv"),catalog(texts/"zh-TW.tsv")
    fragments=set()
    for group in read(texts/"passage-candidates.json")["groups"]:
        for item in group["sources"]:
            fragments.update(f["key"] for f in item["fragments"])
    wanted=[];excluded=[]
    for key,value in source.items():
        if not key.startswith("ecl.") or key not in target:continue
        assert key=="ecl."+sha(value.encode())[:20]
        why=""
        if len(value)<16:why="name-length"
        elif key in fragments:why="passage-fragment"
        elif any(ord(c)>127 for c in value) or re.search(r"[\x00-\x1f]",value+target[key]) or "\\" in value+target[key] or "%" in value:why="control-or-format"
        elif "JOURNAL ENTRY" in value:why="journal"
        elif len(target[key])>144:why="length"
        if why:excluded.append(dict(key=key,reason=why))
        else:wanted.append(key)
    assert proof["keys"]==sorted(wanted) and proof["excluded"]==excluded,"literal catalog key selection mismatch"
    old_en,old_zh=catalog(base/"en.tsv"),catalog(base/"zh-TW.tsv")
    assert proof["new_keys"]==[k for k in sorted(wanted) if k not in old_en]
    assert en==dict(old_en,**{k:source[k] for k in wanted})
    assert zh==dict(old_zh,**{k:target[k] for k in wanted}),"literal catalog translation mismatch"
    style_values=[]
    for record in proof["styles"]:
        path=inputs.parent.parent/record["source_path"]
        assert path.resolve().is_relative_to(inputs.parent.parent.resolve()) and sha(path.read_bytes())==record["source_sha256"]
        trace=read(path);p=next(p for p in trace["paragraphs"] if p["step"]==record["step"])
        style={"Caller":p["caller"],"NativeBox":p["native_box"],"Foreground":p["foreground"],"Background":p["background"],"Clear":p["clear"]}
        assert record["style"]==style and p["caller"]["Seg"]==0x26B4
        assert p["native_box"]==[8,136,312,184] and p["background"]==0 and p["foreground"] in (3,7)
        assert (p["caller"]["Off"],p["clear"]) in ((0x1D53,0),(0x1D81,1))
        assert {"Key":"ecl."+sha(p["source"]["text"].encode())[:20],"SHA256":sha(p["source"]["text"].encode()),**style} in old["Paragraphs"]
        style_values.append(style)
    assert {(s["Caller"]["Off"],s["Foreground"],s["Clear"]) for s in style_values}=={(0x1D53,3,0),(0x1D53,7,0),(0x1D81,3,1),(0x1D81,7,1)}
    assert len(style_values)==4
    expected=list(old["Paragraphs"]);old_set={json.dumps(p,sort_keys=True) for p in expected}
    for key in sorted(wanted):
        for style in style_values:
            p={"Key":key,"SHA256":sha(source[key].encode()),**style}
            if json.dumps(p,sort_keys=True) not in old_set:expected.append(p)
    assert config["Paragraphs"]==expected and len(expected)-len(old["Paragraphs"])==proof["added_bindings"],"literal catalog binding matrix mismatch"
    font=catalog(base/"font-zh-TW.tsv");font.update({k:target[k] for k in wanted})
    assert catalog(inputs/"font-zh-TW.tsv")==font
    previous=read(base/"glyphs-16.json")
    assert all(glyphs[n]==previous[n] for n in ("size","height","font_sha256"))
    assert all(glyphs["glyphs"][k]==v for k,v in previous["glyphs"].items())
    assert set(glyphs["glyphs"])==set(previous["glyphs"])|(set("".join(font.values()))-set("\r\n\t")),"literal catalog glyph set mismatch"
    outline=inputs.parent.parent/proof["outline_fallback"]["path"]
    assert outline.resolve().is_relative_to(inputs.parent.parent.resolve()) and sha(outline.read_bytes())==proof["outline_fallback"]["sha256"]
    fallback=read(outline)
    assert all(fallback[n]==glyphs[n] for n in ("size","height","font_sha256"))
    assert set(fallback["glyphs"])=={"描","泉"} and not (set(fallback["glyphs"])&set(previous["glyphs"]))
    for char,value in fallback["glyphs"].items():
        assert glyphs["glyphs"][char]==value and len(base64.b64decode(value))==320 and not any(base64.b64decode(value)[256:]),"literal catalog outline mismatch"
    for name in set(proof["base_files"])-{"en.tsv","zh-TW.tsv","font-zh-TW.tsv","inputs.json","provenance.json","glyphs-16.json"}:
        assert (inputs/name).read_bytes()==(base/name).read_bytes()
    return base,old,parent,old_en,old_zh,previous


def check_short_ecl_sources(inputs,config,provenance,en,zh,glyphs):
    from ui_list_inputs import catalog
    proof=provenance["short_ecl_extension"];root=inputs.parent.parent
    base=root/proof["base"]
    assert base.resolve().is_relative_to(root.resolve())
    assert set(proof["base_files"])=={p.name for p in base.iterdir() if p.is_file()}
    for n,h in proof["base_files"].items():assert Path(n).name==n and sha((base/n).read_bytes())==h
    old,parent=read(base/"inputs.json"),read(base/"provenance.json")
    assert {k:v for k,v in provenance.items() if k!="short_ecl_extension"}==parent
    assert {k:v for k,v in config.items() if k!="Paragraphs"}=={k:v for k,v in old.items() if k!="Paragraphs"},"short ECL inherited mismatch"
    texts=Path("/catalogs")
    assert set(proof["formal_files"])=={"en.tsv","zh-TW.tsv","glossary.tsv","catalog.json","glossary-additions.tsv"}
    for n,h in proof["formal_files"].items():assert sha((texts/n).read_bytes())==h
    assert sha((texts/"passage-candidates.json").read_bytes())==proof["fragments_sha256"]
    source,target=catalog(texts/"en.tsv"),catalog(texts/"zh-TW.tsv")
    fragments={f["key"] for g in read(texts/"passage-candidates.json")["groups"] for s in g["sources"] for f in s["fragments"]}
    wanted=[]
    for k,v in source.items():
        if k not in target or not k.startswith("ecl.") or len(v)>15 or k in fragments:continue
        if re.search(r"[^\x20-\x7f]",v) or re.search(r"[\x00-\x1f]",target[k]) or "\\" in v+target[k] or "%" in v or "JOURNAL ENTRY" in v:continue
        assert k=="ecl."+sha(v.encode())[:20];wanted.append(k)
    wanted.sort();old_en,old_zh=catalog(base/"en.tsv"),catalog(base/"zh-TW.tsv")
    assert proof["keys"]==wanted and proof["new_keys"]==[k for k in wanted if k not in old_en]
    assert en==dict(old_en,**{k:source[k] for k in wanted})
    assert zh==dict(old_zh,**{k:target[k] for k in wanted}),"short ECL translation mismatch"
    expected=list(old["Paragraphs"]);seen={json.dumps(p,sort_keys=True) for p in expected}
    for k in wanted:
        for s in parent["literal_catalog_extension"]["styles"]:
            p=dict(Key=k,SHA256=sha(source[k].encode()),**s["style"])
            if json.dumps(p,sort_keys=True) not in seen:expected.append(p)
    assert config["Paragraphs"]==expected and len(expected)-len(old["Paragraphs"])==proof["added_bindings"],"short ECL binding mismatch"
    font=catalog(base/"font-zh-TW.tsv");font.update({k:target[k] for k in wanted})
    assert catalog(inputs/"font-zh-TW.tsv")==font
    previous=read(base/"glyphs-16.json")
    assert all(glyphs[k]==previous[k] for k in ("size","height","font_sha256"))
    assert all(glyphs["glyphs"][k]==v for k,v in previous["glyphs"].items())
    assert set(glyphs["glyphs"])==set(previous["glyphs"])|(set("".join(font.values()))-set("\r\n\t"))
    for name in set(proof["base_files"])-{"inputs.json","provenance.json","en.tsv","zh-TW.tsv","font-zh-TW.tsv","glyphs-16.json"}:
        assert (inputs/name).read_bytes()==(base/name).read_bytes()
    path=root/proof["native_source"]
    assert path.resolve().is_relative_to(root.resolve()) and sha(path.read_bytes())==proof["native_sha256"]
    trace=read(path);control=read(path.parent.parent/"control-bar-r3/receipt.json")
    assert trace["checkpoints"]==control["checkpoints"] and len(trace["checkpoints"])==5
    canonical=root/parent["literal_catalog_extension"]["page_validation"]["source_path"]
    oracle=read(canonical)
    for a,b in zip(trace["checkpoints"],oracle["checkpoints"]):
        assert all(a[k]==b[k] for k in ("step","label","regs","ram_sha256","indexed_sha256","palette"))
        assert not a["writes"] and not a["unimplemented"]
    paragraphs=[e for e in trace["events"] if e["point"]=={"Seg":0xb72,"Off":0x311}]
    assert len(paragraphs)==len(oracle["paragraphs"])==4
    for e,p in zip(paragraphs,oracle["paragraphs"]):
        assert e["step"]==p["step"] and e["buffer"]==p["source"]["text"] and e["caller"]==p["caller"]
        assert e["source_pointer"]=={"Seg":0x333e,"Off":0xb487} and e["raw_b216"]==0x80 and e["raw_b1c7"]==(0x12 if p["clear"] else 0x11)
    return base,old,parent,old_en,old_zh,previous


def check(en_run, zh_run, inputs, control, observed, output):
    assert not output.exists()
    a, b, oracle, trace = [read(p / "receipt.json") for p in (en_run, zh_run, control, observed)]
    # 未進列表的正常路徑，Go 的空 slice 會輸出 null。
    for field in ("list_events", "scroll_events", "wrappers", "fill_events", "menu_refresh_sources", "paragraphs", "menus"):
        if trace[field] is None:
            trace[field] = []
        assert isinstance(trace[field], list)
    assert not a["translate"] and b["translate"]
    assert a["prototype"] and b["prototype"]
    glyphs = read(inputs / "glyphs-16.json")
    assert glyphs["size"] == 16 and glyphs["height"] == 20
    alpha = {key: base64.b64decode(value) for key, value in glyphs["glyphs"].items()}
    assert all(len(v) == 320 and not any(v[256:]) for v in alpha.values())
    from ui_list_inputs import catalog
    zh = catalog(inputs / "zh-TW.tsv")
    en = catalog(inputs / "en.tsv")
    config = read(inputs / "inputs.json")
    provenance = read(inputs / "provenance.json")
    fire=provenance.get('fire_extension')
    fire_path=None
    if fire:
        selected=[p for p in fire['data']['paths'].values() if (inputs.parent.parent/p['source_path']).resolve()==(observed/'receipt.json').resolve()]
        assert len(selected)==1,'unknown fire path'
        fire_path=selected[0]
    magic_toggle=provenance.get('magic_toggle_extension')
    magic_path=None
    if magic_toggle:
        if (inputs.parent.parent/magic_toggle['source_path']).resolve()==(observed/'receipt.json').resolve():magic_path=magic_toggle
        else:assert fire_path,'unknown magic toggle path'
    spell_route=provenance.get('spell_route_extension')
    spell_path=None
    if spell_route:
        if (inputs.parent.parent/spell_route['source_path']).resolve()==(observed/'receipt.json').resolve():spell_path=spell_route
        else:assert magic_path or fire_path,'unknown spell route path'
    scoped_path=fire_path or magic_path or spell_path
    scoped_data=fire if fire_path else magic_toggle if magic_path else spell_route
    journal_refs=provenance.get('journal_reference_extension')
    journal_path=None
    if journal_refs:
        selected=[p for p in journal_refs['paths'].values() if (inputs.parent.parent/p['source_path']).resolve()==(observed/'receipt.json').resolve()]
        assert len(selected)<=1,'ambiguous journal reference path'
        journal_path=selected[0] if selected else None
    rounds=provenance.get("round_extension")
    round_path=None
    if rounds:
        selected=[p for p in rounds['data']['paths'].values() if (inputs.parent.parent/p['source_path']).resolve()==(observed/'receipt.json').resolve()]
        assert len(selected)==1 or (not selected and (journal_path or scoped_path)),'unknown combat round path'
        round_path=selected[0] if selected else None
    boundary=provenance.get("ammo_boundary_extension")
    boundary_path=None
    if boundary:
        from ammo_boundary_inputs import row_model as ammo_row_model
        matches=[p for p in boundary['data']['paths'].values() if (inputs.parent.parent/p['source_path']).resolve()==(observed/'receipt.json').resolve()]
        assert len(matches)==1 or (not matches and (round_path or journal_path or scoped_path)),'unknown ammo boundary path'
        boundary_path=matches[0] if matches else None
    else:
        from ammo_ui_inputs import row_model as ammo_row_model
    if journal_refs:
        assert journal_path or round_path or boundary_path or scoped_path,'unknown journal reference path'
    ammo=provenance.get("ammo_extension")
    movement=provenance.get("movement_extension")
    movement_path=None
    if movement and not ammo:
        selected=[p for p in movement["data"]["paths"].values()
                  if (inputs.parent.parent/p["source_path"]).resolve()==(observed/"receipt.json").resolve()]
        assert len(selected)==1,"unknown movement path"
        movement_path=selected[0]
    finish=provenance.get("finish_extension")
    effects=provenance.get("effects_extension")
    hud=provenance.get("hud_extension")
    party_cast=provenance.get("party_cast_extension")
    cast=provenance.get("cast_extension")
    bar=provenance.get("bar_extension")
    hud_field_bindings=[row["binding"] for extension in (hud,effects,finish,rounds,fire) if extension
                        for row in extension["data"].get("fields",[])]
    source_args=(inputs,config,provenance,en,zh,glyphs)
    if fire:
        from combat_fire_inputs import check_sources as check_fire_sources
        source_args=check_fire_sources(*source_args)
    if magic_toggle:
        from magic_toggle_inputs import check_sources as check_magic_toggle_sources
        source_args=check_magic_toggle_sources(*source_args)
    if spell_route:
        from spell_route_inputs import check_sources as check_spell_route_sources
        source_args=check_spell_route_sources(*source_args)
    if journal_refs:
        from journal_reference_inputs import check_sources as check_journal_reference_sources
        source_args=check_journal_reference_sources(*source_args)
    if rounds:
        from combat_rounds_inputs import check_sources as check_round_sources
        source_args=check_round_sources(*source_args)
    if boundary:
        from ammo_boundary_inputs import check_sources as check_ammo_boundary_sources
        source_args=check_ammo_boundary_sources(*source_args)
    if ammo:
        from ammo_ui_inputs import check_sources as check_ammo_sources
        source_args=check_ammo_sources(*source_args)
    if movement:
        from movement_ui_inputs import check_sources as check_movement_sources
        source_args=check_movement_sources(*source_args)
    if finish:
        from combat_finish_inputs import check_sources as check_finish_sources
        source_args=check_finish_sources(*source_args)
    if effects:
        from combat_effects_inputs import check_sources as check_effects_sources
        source_args=check_effects_sources(*source_args)
        from combat_effects_inputs import copy_witness
        effects_copy_witness=copy_witness(inputs.parent.parent)
    if hud:
        from combat_hud_inputs import check_sources as check_hud_sources
        source_args=check_hud_sources(*source_args)
    if party_cast:
        from party_cast_inputs import check_sources as check_party_cast_sources
        source_args=check_party_cast_sources(*source_args)
    if cast:
        from cast_ui_inputs import check_sources as check_cast_sources
        source_args=check_cast_sources(*source_args)
    if bar:
        from bar_ui_inputs import check_sources
        source_args=check_sources(*source_args)
    # 父批資料仍逐層核對；本條正常路徑沒有瞄準或魔法傷害的生命週期。
    if finish:
        effects=None
    if movement:
        finish=None
    if ammo:
        movement=finish=effects=hud=None
    if rounds:
        hud=rounds
    if journal_path or scoped_path:
        # 父批資料已逐層核對；本次原版路徑另由完整來源指定。
        rounds=boundary=ammo=movement=finish=effects=hud=party_cast=cast=bar=None
        if scoped_path:
            hud=scoped_data
        else:
            hud_field_bindings=[]
    short_ecl=provenance.get("short_ecl_extension")
    literal_batch=provenance.get("literal_catalog_extension")
    battle=provenance.get("battle_extension")
    if literal_batch:
        literal_args=check_short_ecl_sources(*source_args) if short_ecl else source_args
        parent_args=check_literal_catalog_sources(*literal_args)
        battle_source=check_battle_sources(*parent_args,trace)
    else:battle_source=check_battle_sources(inputs,config,provenance,en,zh,glyphs,trace) if battle else None
    ancestor_journal_sets={}
    if journal_path or scoped_path:
        # 完整驗過父批資料後，改按本次原版實際輸出檢查，不要求重演酒館新增項。
        if literal_batch:ancestor_journal_sets['literal']=set(literal_batch['new_keys'])
        if short_ecl:ancestor_journal_sets['short']=set(short_ecl['keys'])
        literal_batch=short_ecl=None
    inherited_creation_fields=read(inputs.parent.parent/battle["base"]/"inputs.json")["Fields"] if battle else []
    creation_tracking=any(f["Pane"]=="menu-text" and f["Caller"]=={"Seg":0x1BB6,"Off":0x1BE} for f in inherited_creation_fields)
    item_context=provenance.get("item_context_extension")
    context_fields=[r["binding"] for r in item_context["fields"]] if item_context else []
    equipment=provenance.get("equipment_extension")
    equipment_fields=[r["binding"] for r in equipment["fields"]] if equipment else []
    equipment_rows=[r["binding"] for r in equipment["rows"]] if equipment else []
    creation=provenance.get("creation_extension")
    creation_added=[r["binding"] for r in creation["added"]] if creation else []
    removed_age=creation.get("removed_age_fields",[]) if creation else []
    retain_creation=lambda fields:[f for f in fields if f not in removed_age]
    page_proof=(finish or {}).get("page_validation") or (effects or {}).get("page_validation") or (hud or {}).get("page_validation") or (party_cast or {}).get("page_validation") or (cast or {}).get("page_validation") or (bar or {}).get("page_validation") or (literal_batch or {}).get("page_validation") or (battle or {}).get("page_validation") or (item_context or {}).get("page_validation") or (equipment or {}).get("page_validation") or (creation or {}).get("page_validation")
    if movement:
        page_proof=movement_path["page_validation"]
    if ammo:
        page_proof=ammo["page_validation"]
    if boundary_path:
        page_proof=boundary_path['page_validation']
    if rounds:
        page_proof=round_path['page_validation']
    if journal_path:
        page_proof=journal_path['page_validation']
    if scoped_path:
        page_proof=scoped_path['page_validation']
    movement_reference=None
    if movement:
        witness=movement["data"]["quick_witness"]
        original=(inputs.parent.parent/witness["indexed_path"]).read_bytes()
        x,y,w,h=witness["native_rect"]
        movement_reference=b"".join(original[row*320+x:row*320+x+w] for row in range(y,y+h))
        assert sha(movement_reference)==witness["reference_sha256"]
    if item_context:
        base=inputs.parent.parent/item_context["base"]
        for name,h in item_context["base_files"].items():assert Path(name).name==name and sha((base/name).read_bytes())==h
        base_config=read(base/"inputs.json")
        assert config["Fields"]==base_config["Fields"]+context_fields
        for name in ("Rows","Headers","Menus","Paragraphs","PaneLists","RowCallers","Background"):
            assert config[name]==base_config[name]
        old_en,old_zh=catalog(base/"en.tsv"),catalog(base/"zh-TW.tsv")
        key=item_context["prefix_key"]
        assert set(en)==set(old_en)|{key} and set(zh)==set(old_zh)|{key}
        assert all(en[k]==v for k,v in old_en.items()) and all(zh[k]==v for k,v in old_zh.items())
        formal_en,formal_zh=catalog(Path("/catalogs/en.tsv")),catalog(Path("/catalogs/zh-TW.tsv"))
        root=item_context["formal_key"]
        assert formal_en[root]==en[key]+"%s" and formal_zh[root]==zh[key]+"%s"
        for name in ("glyphs-16.json","glyphs-20.json","role.zh-TW.tsv","reader.zh-TW.tsv"):
            assert (inputs/name).read_bytes()==(base/name).read_bytes()
        for row in item_context["fields"]:
            path=inputs.parent.parent/row["source_path"]
            assert path.resolve().is_relative_to(inputs.parent.parent.resolve()) and sha(path.read_bytes())==row["source_sha256"]
            native_source=read(path)
            assert native_source["exe_sha256"]==oracle["exe_sha256"]
            c=next(c for c in native_source["calls"] if c["step"]==row["call_step"])
            f=row["binding"];source=c["vararg_1_candidate"]["text"]
            assert c["caller"]==f["Caller"]=={"Seg":0xB72,"Off":0x27C} and c["format"]["text"]=="%s"
            assert f["FormatSHA256"]==sha(b"%s") and f["SHA256"]==sha(source.encode())
            assert [f["RawY"],f["RawX"]]==c["stack"][2:4]
            assert (row["first_glyph"],row["return_step"])==(c["first_glyph"],c["return_step"]) and c["step"]<c["first_glyph"]
            assert source[f["Start"]:f["Start"]+f["Length"]]==en[f["Key"]]
            if f["Pane"] in ("suffix","inventory"):
                assert f["Group"]=="header" and f["Start"]==0 and f["Length"]==len(source)
                assert source==("'s" if f["Pane"]=="suffix" else "Items") and f["RawY"]==8004
            else:
                wrapper=native_source["wrappers"][c["wrapper_index"]]
                assert f["Pane"]=="callsite" and f["Group"]=="footer" and f["UpperCaller"]==wrapper["caller"]=={"Seg":0x88E,"Off":0x1560}
                assert wrapper["format"]["text"]=="%s" and f["UpperFormatSHA256"]==sha(b"%s") and f["UpperNative"]==[0,192]
                assert f["Color"]==0x8f and c["stack"][2:5]==[189,8004,0x8f] and "BackgroundOverride" not in f
                if f["Key"]==key:assert f["Start"]==0 and f["Length"]==len(en[key])
                else:assert f["Start"]==len(en[key]) and f["Length"]==len(en[f["Key"]]) and f["Key"].startswith("inventory.")
        # 獨立來源集合不從新增 binding 反推，刪去整個 metadata 列仍須報錯。
        names_proof=read(inputs.parent/"names-check.json")
        assert [v["length"] for v in names_proof["cases"]]==list(range(1,16))
        for case in names_proof["cases"]:
            path=inputs.parent/"names"/f'length-{case["length"]:02}'/"observe/receipt.json"
            assert sha(path.read_bytes())==case["receipt_sha256"]
            source_trace=read(path)
            assert source_trace["exe_sha256"]==oracle["exe_sha256"]
            for source,pane,step in (("'s","suffix",case["suffix_call"]),("Items","inventory",case["items_call"])):
                c=next(c for c in source_trace["calls"] if c["step"]==step)
                assert c["format"]["text"]=="%s" and c["vararg_1_candidate"]["text"]==source
                assert any(f["Pane"]==pane and f["Group"]=="header" and en[f["Key"]]==source
                           and [f["RawY"],f["RawX"]]==c["stack"][2:4] and f["Caller"]==c["caller"]
                           and f["SHA256"]==sha(source.encode()) for f in config["Fields"]),"item context name title remains untranslated"
    if equipment:
        base=inputs.parent.parent/equipment["base"]
        for name,h in equipment["base_files"].items():
            assert Path(name).name==name and sha((base/name).read_bytes())==h
        base_config=read(base/"inputs.json")
        assert config["Fields"]==base_config["Fields"]+equipment_fields+context_fields
        assert config["Rows"]==base_config["Rows"]+equipment_rows
        menus=dict(base_config["Menus"])
        menus.update({m["Signature"]:"inventory" for m in equipment["menus"]})
        assert config["Menus"]==menus
        assert all(m["Signature"] in menus for m in trace["menus"]),"equipment route contains untranslated menu shape"
        inventory_header=next(h for h in config["Headers"] if h["Pane"]=="inventory")
        for c in trace["calls"]:
            if c["wrapper_index"]<0:continue
            w=trace["wrappers"][c["wrapper_index"]]
            if w["format"]["segment"]==inventory_header["Segment"] and w["format"]["offset"]==inventory_header["Offset"] and w["stack"][3]&255==1:
                assert any(f["Pane"]=="inventory" and f["Group"]=="header" and f["SHA256"]==sha(c["vararg_1_candidate"]["text"].encode())
                           and [f["RawY"],f["RawX"]]==c["stack"][2:4] and f["Caller"]==c["caller"] for f in config["Fields"]),"equipment title remains untranslated"
        for name in (("glyphs-16.json","glyphs-20.json","reader.zh-TW.tsv") if item_context else ("en.tsv","zh-TW.tsv","glyphs-16.json","glyphs-20.json","reader.zh-TW.tsv")):
            assert (inputs/name).read_bytes()==(base/name).read_bytes()
        source=inputs.parent.parent/equipment["source_path"]
        assert source.resolve().is_relative_to(inputs.parent.parent.resolve()) and sha(source.read_bytes())==equipment["source_sha256"]
        original=read(source)
        for row in equipment["fields"]:
            f=row["binding"]
            assert f["Start"]==0 and f["Length"]==len(en[f["Key"]]),"equipment lexical mask mismatch"
            if f["Pane"]=="callsite":
                c=next(c for c in original["calls"] if c["step"]==row["call_step"])
                text=c["vararg_1_candidate"]["text"]
                assert f["Group"]=="body" and original["wrappers"][c["wrapper_index"]]["caller"]==f["UpperCaller"]=={"Seg":0x88E,"Off":0x71D}
                assert c["caller"]==f["Caller"]=={"Seg":0xB72,"Off":0x27C}
                assert f["SHA256"]==sha(text.encode()) and f["FormatSHA256"]==sha(b"%s")
                assert text.startswith(en[f["Key"]]) and re.fullmatch(r"(?: \+[0-9]+)? *",text[f["Length"]:])
                assert c["stack"][4]==0x87
                assert [f["RawY"],f["RawX"]]==c["stack"][2:4]
                assert (row["first_glyph"],row["return_step"])==(c["first_glyph"],c["return_step"])
            elif f["Pane"] in ("suffix","inventory"):
                c=next(c for c in original["calls"] if c["step"]==row["call_step"])
                assert f["Group"]=="header" and c["caller"]==f["Caller"]=={"Seg":0xB72,"Off":0x27C}
                assert c["vararg_1_candidate"]["text"]==en[f["Key"]]==("'s" if f["Pane"]=="suffix" else "Items") and c["format"]["text"]=="%s"
                assert f["SHA256"]==sha(en[f["Key"]].encode()) and f["FormatSHA256"]==sha(b"%s")
                assert [f["RawY"],f["RawX"]]==c["stack"][2:4] and f["RawY"]==8004
                assert (row["first_glyph"],row["return_step"])==(c["first_glyph"],c["return_step"])
            else:
                assert f["Pane"]=="menu" and f["Group"]=="footer" and f["Caller"]=={"Seg":0xCEB,"Off":0x1BE}
                menu=original["menus"][row["menu_index"]]
                button=next(b for b in menu["Buttons"] if b["Index"]==row["button_index"])
                assert bytes.fromhex(button["SourceHex"]).decode()==en[f["Key"]]
                assert f["SHA256"]==f["FormatSHA256"]==button["SHA256"]
                native_coord=lambda v:v if v<400 else (v-8000)*2
                assert [f["RawX"],f["RawY"]]==[native_coord(button["RawX"]),native_coord(button["RawY"])+1]
                assert menu in equipment["menus"] and menu["Signature"]==f["MenuSignature"]
                assert menu["Count"] in (7,9) and len(menu["Buttons"])==6
        for row in equipment["rows"]:
            f=row["binding"];w=next(w for w in original["wrappers"] if w["step"]==row["wrapper_step"])
            text=w["vararg_1_candidate"]["text"]
            assert w["format"]["text"]=="%s" and text==row["source"] and f["SHA256"]==sha(text.encode())
            assert any(p["step"]<=w["step"]<=p["return_instruction_step"] for p in original["list_events"])
            assert f["Pane"]=="inventory" and f["Foregrounds"]==[7,11] and len(f["Spans"])==2
            for span in f["Spans"]:
                assert text[span["Start"]:span["Start"]+span["Length"]]==en[span["Key"]]
            assert f["Spans"][0]["Start"]==1 and en[f["Spans"][0]["Key"]] in ("Yes","No")
    if page_proof:
        proof=page_proof
        path=inputs.parent.parent/proof["source_path"]
        expected_sha=proof["source_sha256"] if (cast or bar or scoped_path) else proof["sha256"]
        assert path.resolve().is_relative_to(inputs.parent.parent.resolve()) and sha(path.read_bytes())==expected_sha
        assert path.resolve()==(observed/"receipt.json").resolve() and trace["display_changes"]
    if creation:
        base=inputs.parent.parent/creation["base"]
        source=inputs.parent.parent/creation["source_path"]
        assert source.resolve().is_relative_to(inputs.parent.parent.resolve()) and sha(source.read_bytes())==creation["source_sha256"]
        creation_source=read(source)
        base_en,base_zh=catalog(base/"en.tsv"),catalog(base/"zh-TW.tsv")
        assert all(en[k]==v for k,v in base_en.items()) and all(zh[k]==v for k,v in base_zh.items())
        for f in removed_age:
            assert f in read(base/"inputs.json")["Fields"] and f["Pane"]=="callsite" and base_en[f["Key"]]=="years"
            assert f["UpperCaller"]=={"Seg":0x2C4A,"Off":0xD3} and (f["RawX"],f["RawY"],f["Length"])==(8032,8012,5)
        assert config["Fields"]==retain_creation(read(base/"inputs.json")["Fields"])+creation_added+equipment_fields+context_fields
        bank=Path("/catalogs/creation-ui-review.tsv")
        assert sha(bank.read_bytes())==creation["review_sha256"]
        review={r["key"]:r for r in csv.DictReader(bank.open(),delimiter="\t")}
        formal_en,formal_zh=catalog(Path("/catalogs/en.tsv")),catalog(Path("/catalogs/zh-TW.tsv"))
        for key,origin in creation["origins"].items():
            if "review" in origin:
                assert origin["review"]==review[key] and (en[key],zh[key])==(review[key]["en"],review[key]["zh-TW"])
            elif "base_key" in origin:assert (en[key],zh[key])==(base_en[origin["base_key"]],base_zh[origin["base_key"]])
            else:assert (en[key],zh[key])==(formal_en[origin["formal_key"]],formal_zh[origin["formal_key"]])
        for row in creation["added"]:
            original=creation_source
            if row.get("source_path"):
                path=inputs.parent.parent/row["source_path"]
                assert path.resolve().is_relative_to(inputs.parent.parent.resolve()) and sha(path.read_bytes())==row["source_sha256"]
                original=read(path)
            binding=row["binding"];call=next(c for c in original["calls"] if c["step"]==row["call_step"])
            text=call["vararg_1_candidate"]["text"] if call["format"]["text"]=="%s" else call["format"]["text"]
            assert (row["first_glyph"],row["return_step"])==(call["first_glyph"],call["return_step"])
            assert call["step"]<call["first_glyph"]<call["return_step"]
            assert binding["Caller"]==call["caller"] and (binding["RawY"],binding["RawX"])==tuple(call["stack"][2:4])
            assert en[binding["Key"]]==("Save" if binding.get("SourcePattern")=="created-name" else "years" if binding.get("SourcePattern")=="age-unit" else text)
            if binding["Pane"] in ("menu","menu-text"):
                assert binding["MenuSignature"]==original["menus"][call["menu_index"]]["Signature"]
            if binding["Pane"]=="menu-text":assert binding["Caller"]!={"Seg":0xCEB,"Off":0x1BE} and not binding.get("FontSize")
    startup = provenance.get("startup_extension")
    session = provenance.get("session_load_extension")
    role_alpha = None
    if session:
        base = inputs.parent.parent / session["base"]
        for name,value in session["base_files"].items():
            assert Path(name).name==name and sha((base/name).read_bytes())==value
        source_path=inputs.parent.parent/session["observed_path"]
        assert source_path.resolve().is_relative_to(inputs.parent.parent.resolve())
        assert session["observed_sha256"]==sha(source_path.read_bytes())
        source_trace=read(source_path)
        source_calls={c["step"]:c for c in source_trace["calls"]}
        formal=Path("/catalogs")
        for name,value in session["formal_files"].items():assert sha((formal/name).read_bytes())==value
        formal_en,formal_zh=catalog(formal/"en.tsv"),catalog(formal/"zh-TW.tsv")
        short_en,short_zh=catalog(inputs.parent/"ui-inputs/en.tsv"),catalog(inputs.parent/"ui-inputs/zh-TW.tsv")
        roles=inputs.parent.parent/"interactive-menu-inputs-20261022"
        for name,value in session["role_files"].items():assert sha((roles/name).read_bytes())==value
        assert (inputs/"role.zh-TW.tsv").read_bytes()==(roles/"zh-TW.tsv").read_bytes()
        assert (inputs/"glyphs-20.json").read_bytes()==(roles/"glyphs-20.json").read_bytes()
        role_zh=catalog(inputs/"role.zh-TW.tsv")
        bank=read(inputs/"glyphs-20.json")
        assert bank["size"]==20 and bank["height"]==24
        role_alpha={key:base64.b64decode(value) for key,value in bank["glyphs"].items()}
        assert all(len(value)==480 for value in role_alpha.values())
        for run in (a,b):
            for name in ["glyphs-20.json","role.zh-TW.tsv"]:assert run["list_role_"+name+"_sha256"]==sha((inputs/name).read_bytes())
        added=[row["binding"] for row in session["added"]]
        assert len(added)==21 and sum(f.get("FontSize")==20 for f in added)==12
        assert config["Fields"]==retain_creation(read(base/"inputs.json")["Fields"]+added+([row["binding"] for row in startup["added"]] if startup else []))+creation_added+equipment_fields+context_fields
        for row in session["added"]:
            binding,origin=row["binding"],row["origin"]
            key=binding["Key"]
            call=source_calls[row["call_step"]]
            text=call["vararg_1_candidate"]["text"] if call["format"]["text"]=="%s" else call["format"]["text"]
            assert text==origin["source"] and binding["SHA256"]==sha(text.encode())
            assert binding["Caller"]==call["caller"] and [binding["RawY"],binding["RawX"]]==call["stack"][2:4]
            assert binding["FormatSHA256"]==sha(call["format"]["text"].encode())
            if binding["Pane"]=="menu":
                assert binding["MenuSignature"]==source_trace["menus"][call["menu_index"]]["Signature"]
            else:
                upper=source_trace["wrappers"][call["wrapper_index"]]
                assert binding["UpperCaller"]==upper["caller"]
                assert binding["UpperNative"]==[(upper["stack"][i]&255)*8 for i in (2,3)]
                assert binding["Color"]==call["stack"][4]
                assert binding.get("BackgroundOverride",8)==(call["stack"][4]>>4)&15
            if "role_key" in origin:
                assert binding["FontSize"]==20 and origin["role_key"]==sha(origin["source"].encode())
                assert zh[key]==role_zh[origin["role_key"]]
            elif "short_key" in origin:
                assert (origin["source"],zh[key])==(short_en[origin["short_key"]],short_zh[origin["short_key"]])
            else:
                assert origin["source"].rstrip(" ")==formal_en[origin["formal_key"]].rstrip(" ")
                assert zh[key]==formal_zh[origin["formal_key"]]
            assert en[key]==origin["source"].rstrip(" ") and origin["translation"]==zh[key]
    if startup:
        base=inputs.parent.parent/startup["base"]
        for name,digest in startup["base_files"].items():assert sha((base/name).read_bytes())==digest
        base_config=read(base/"inputs.json");added=startup["added"]
        assert len(added)==2 and config["Fields"]==retain_creation(base_config["Fields"]+[row["binding"] for row in added])+creation_added+equipment_fields+context_fields
        assert config["Rows"]==base_config["Rows"]+equipment_rows
        for name in ["Headers","Paragraphs","PaneLists","RowCallers","Background"]:assert config[name]==base_config[name]
        path=inputs.parent.parent/startup["observed_path"]
        assert path.resolve().is_relative_to(inputs.parent.parent.resolve()) and sha(path.read_bytes())==startup["observed_sha256"]
        original=read(path);calls={c["step"]:c for c in original["calls"]}
        formal_en,formal_zh=catalog(Path("/catalogs/en.tsv")),catalog(Path("/catalogs/zh-TW.tsv"))
        for row in added:
            binding=row["binding"];call=calls[row["call_step"]];key=binding["Key"]
            source=call["vararg_1_candidate"]["text"] if call["format"]["text"]=="%s" else call["format"]["text"]
            assert source==formal_en[row["formal_key"]] and zh[key]==formal_zh[row["formal_key"]]
            assert binding["BackgroundOverride"]==23
            assert en[key]==source and binding["SHA256"]==sha(source.encode())
            assert binding["Caller"]==call["caller"] and [binding["RawY"],binding["RawX"]]==call["stack"][2:4]
            if binding["Pane"]=="menu":
                table=original["menus"][call["menu_index"]]
                assert table["Count"]==1 and len(table["Buttons"])==1 and binding["MenuSignature"]==table["Signature"]
            else:
                assert source=="Name" and binding["UpperCaller"]==original["wrappers"][call["wrapper_index"]]["caller"]
        old=read(base/"glyphs-16.json")
        assert all(glyphs["glyphs"][key]==value for key,value in old["glyphs"].items())
    trade = provenance.get("trade_extension")
    trade_bindings = []
    if trade:
        base = inputs.parent.parent / trade["base"]
        assert base.resolve().is_relative_to(inputs.parent.parent.resolve())
        for name, value in trade["base_files"].items():
            assert Path(name).name == name and sha((base/name).read_bytes()) == value
        base_en, base_zh = catalog(base/"en.tsv"), catalog(base/"zh-TW.tsv")
        base_config = read(base/"inputs.json")
        item_keys = {s["Key"] for row in base_config["Rows"] if row["Pane"] in ("inventory","shop-stock") for s in row["Spans"]}
        for key, template in trade["formal_templates"].items():
            assert key == "ui."+sha(template["en"].encode())[:20]
        for origin in trade["added"]["words"]:
            key, origin = origin["key"], origin["origin"]
            if "formal_key" in origin:
                template = trade["formal_templates"][origin["formal_key"]]
                expected_source = template["en"].rstrip() if origin.get("lexical_slice") else template["en"]
                assert (en[key],zh[key]) == (expected_source,template["zh"])
            else:
                prefix = trade["formal_templates"][origin["prefix_key"]]
                suffix = trade["formal_templates"][origin["suffix_key"]]
                expected_source = suffix["en"] % prefix["en"]
                if origin.get("lexical_slice"): expected_source = expected_source.rstrip()
                assert (en[key],zh[key]) == (expected_source,suffix["zh"] % prefix["zh"])
        boundary = trade["feedback_boundaries"]
        boundary_path = inputs.parent / boundary["receipt"]
        assert boundary_path.resolve().is_relative_to(inputs.parent.resolve()) and sha(boundary_path.read_bytes()) == boundary["sha256"]
        native_boundaries = read(boundary_path)
        owners = {0xEEE:"ui.a5f32753448bc7d88ee9",0xFD0:"ui.b7bfe11c801993157e68",0xC7F:"ui.7dcd9be2f67dc050f7b6"}
        for message in trade["messages"]:
            binding = message["binding"]
            assert binding["Caller"]["Seg"] == 0x291A and owners[binding["Caller"]["Off"]] == message["template_key"]
            template = trade["formal_templates"][message["template_key"]]
            original_args, translated_args = [], []
            for arg in message["args"]:
                if arg["kind"] == "integer":
                    assert type(arg["value"]) is int and arg["value"] >= 0
                    original_args.append(arg["value"]);translated_args.append(arg["value"])
                else:
                    assert arg["kind"] == "term" and arg["key"] in item_keys
                    assert (en[arg["key"]],zh[arg["key"]]) == (base_en[arg["key"]],base_zh[arg["key"]])
                    original_args.append(base_en[arg["key"]]);translated_args.append(base_zh[arg["key"]])
            source = template["en"] % tuple(original_args)+" "
            translated = template["zh"] % tuple(translated_args)
            assert binding["Key"] == "service-message."+sha(source.encode())[:20] and binding["SHA256"] == sha(source.encode())
            assert (en[binding["Key"]],zh[binding["Key"]]) == (source,translated)
            assert binding["NativeBox"] == [8,168,312,184] and [binding[k] for k in ("Foreground","Background","Clear")] == [11,0,1]
            cp = next(c for c in native_boundaries["checkpoints"] if c["step"] == message["native_painted_step"])
            raw = (boundary_path.parent / cp["indexed_file"]).read_bytes()
            assert sha(raw) == cp["indexed_sha256"]
            crop = b"".join(raw[y*320+8:y*320+312] for y in range(168,184))
            assert set(crop) == {11,23} and sha(crop) == message["native_pixels_sha256"]
            trade_bindings.append(binding)
    messages = [f for f in config.get("Paragraphs",[]) if f["Key"].startswith("message.")]
    if messages:
        provenance = read(inputs / "provenance.json")
        for f in messages:
            assert f["Key"] == "message."+sha(en[f["Key"]].encode())[:20]
            assert f["Caller"] == {"Seg":0x26B4,"Off":0x3320} and f["Foreground"] == 7 and f["Clear"] == 1
            origins = [item for item in provenance["paragraph_bindings"] if item["binding"] == f]
            if not origins and journal_refs:
                # 模板展開資料另查正式來源，不偽造尚未走過的原版引用觀測。
                assert f in journal_refs['added'] and f['JournalEntry'] in journal_refs['ids']
                alias=journal_refs['aliases'][f['Key']]
                assert alias['template_key']=='ui.aa93370ee0689e9a462e' and alias['entry']==f['JournalEntry']
                argument=str(f['JournalEntry']);template=provenance['formatted_paragraph_templates'][alias['template_key']]
                assert en[f['Key']]==template['en'].replace('%s',argument)
                assert zh[f['Key']]==template['zh'].replace('%s',argument)
                continue
            assert origins
            for item in origins:
                assert item["kind"] == "formatted-journal-reference"
                template_key, argument = item["formal_template_key"], item["argument"]
                assert template_key == "ui.aa93370ee0689e9a462e" and re.fullmatch(r"[1-9][0-9]?",argument)
                template = provenance["formatted_paragraph_templates"][template_key]
                assert template_key == "ui."+sha(template["en"].encode())[:20]
                assert template["en"].count("%s") == template["zh"].count("%s") == 1
                assert en[f["Key"]] == template["en"].replace("%s",argument)
                assert zh[f["Key"]] == template["zh"].replace("%s",argument)
                if f.get("JournalEntry") or (inputs / "reader.zh-TW.tsv").exists():
                    assert f["JournalEntry"] == int(argument)
                    assert en[template_key] == template["en"] and zh[template_key] == template["zh"]
    typed_buttons = bool(b.get("button_ownership"))
    assert bool(a.get("button_ownership")) == typed_buttons
    if config.get("Paragraphs"):
        assert typed_buttons
    native_paragraphs = trace.get("paragraphs") or []
    paragraph_by_step = {p["step"]:p for p in native_paragraphs}
    def paragraph_bindings(p):
        source = p["source"]["text"]
        return [f for f in config.get("Paragraphs",[]) if f["SHA256"] == sha(source.encode()) and en[f["Key"]] == source
                and f["Caller"] == p["caller"] and f["NativeBox"] == p["native_box"]
                and [f[k] for k in ("Foreground","Background","Clear")] == [p[k] for k in ("foreground","background","clear")]]
    hud_entries=[e for e in b["list_events"] if e["Kind"]=="hud-before-glyph"]
    hud_returns=[e for e in b["list_events"] if e["Kind"]=="hud-return"]
    hud_words={}
    hud_records=[]
    if hud:
        if scoped_path:
            from combat_rounds_inputs import hud_records as derive_hud_records
            hud_records=derive_hud_records(trace,config['HUDParagraphs'],en)
            assert hud_records==(fire_path['records'] if fire_path else scoped_data['data']['records'])
        elif rounds or effects or finish or movement:
            if rounds:
                from combat_rounds_inputs import hud_records as derive_hud_records
            else:
                from combat_effects_inputs import hud_records as derive_hud_records
            hud_records=derive_hud_records(trace,config["HUDParagraphs"],en)
            assert hud_records==(round_path['records'] if rounds else movement_path["records"] if movement else (finish or effects)["data"]["records"])
        else:hud_records=hud["data"]["records"]
        assert {e["Step"] for e in hud_entries}=={r["step"] for r in hud_records}
    else:assert not hud_entries and not hud_returns
    assert len(hud_entries)==len(hud_returns)
    for e,returned in zip(hud_entries,hud_returns):
        p=paragraph_by_step[e["Step"]]
        record=next(r for r in hud_records if r["step"]==e["Step"])
        binding=record["binding"]
        assert binding in config["HUDParagraphs"] and binding["Caller"]==p["caller"] and binding["NativeBox"]==p["native_box"]
        assert p["source"]["nul_terminated"] and bytes.fromhex(p["source"]["hex"]).decode("ascii")==p["source"]["text"]
        assert e["Step"]<e["first_glyph"]==p["first_glyph"]<returned["Step"]==p["return_step"]
        assert e["detail"]==dict(caller=p["caller"],native_box=p["native_box"],source_sha256=sha(p["source"]["text"].encode()),
            source_pointer={"Seg":p["source"]["segment"],"Off":p["source"]["offset"]},spans=binding["Spans"],words=e["detail"]["words"])
        words_here=[]
        for span in binding["Spans"]:
            if binding.get("IntegerTemplateKey"):
                from combat_effects_inputs import integer
                number=integer(p["source"]["text"],en[span["Key"]])
                assert number is not None and number==record["number"]
                assert en[span["Key"]].replace("%d",str(number))==p["source"]["text"]
            else:assert p["source"]["text"][span["Start"]:span["Start"]+span["Length"]]==en[span["Key"]]
            x,y,width,height=span["Rect"]
            w=dict(X=x,Y=y,Width=width,Key=span["Key"],Group="body",Foreground=p["foreground"],Background=config["Background"])
            if height!=8:w["Height"]=height
            if binding.get("IntegerTemplateKey"):w["Number"]=number
            words_here.append(w)
        assert e["detail"]["words"]==words_here
        assert returned["detail"]==dict(entry_step=e["Step"],caller=p["caller"],ss=p["regs"]["SS"],sp=(p["regs"]["SP"]+4)&65535,
            words=words_here,footer_hidden=binding.get("HideFooter",False))
        hud_words[e["Step"]]=words_here
    hud_source_clears=[]
    rounds_copy_images=[]
    fire_copy_witness=None
    if rounds or scoped_path:
        if fire_path:
            from combat_fire_inputs import copy_witnesses
            copies=copy_witnesses(inputs.parent.parent.parent.parent,observed.parent)
            assert copies==read(observed.parent/'copy-witnesses.json')
            copy_key,=[k for k,p in fire['data']['paths'].items() if p['source_path']==fire_path['source_path']]
            fire_copy_witness=copies[copy_key]
            rounds_copy_images=[(v['step'],inputs.parent.parent/v['path']) for v in fire_copy_witness['images']]
        if observed.name=='observe-r14':
            from combat_rounds_inputs import copy_witness
            witness=copy_witness(observed.parent)
            rounds_copy_images=[(witness['step'],observed.parent/witness['path'])]
        for record in hud_records:
            x,y,right,bottom=record['binding']['NativeBox']
            fills=[f for f in trace['fill_events'] if record['step']<f['converted_step']<record['first_glyph'] and f['native_rect']==[x,y,right-x,bottom-y]]
            assert len(fills)==1,('missing original HUD clear',record['step'])
            hud_source_clears.append(fills[0]['converted_step'])
    hud_update_entries=[e for e in b["list_events"] if e["Kind"]=="hud-update-entry"]
    hud_update_returns=[e for e in b["list_events"] if e["Kind"]=="hud-update-return"]
    assert len(hud_update_entries)==len(hud_update_returns)
    hud_updates=[]
    if effects:
        for panel in trace["hud_panels"]:
            if not panel["raw_c6b7"] or panel["menu_snapshot"]["Signature"]!=effects["data"]["bindings"][0]["KeepFooterSignature"]:continue
            signature=panel["menu_snapshot"]["Signature"]
            buttons=[c for c in trace["calls"] if c["step"]<panel["step"] and c["caller"]=={"Seg":0xceb,"Off":0x1be} and c.get("menu_index",-1)>=0 and trace["menus"][c["menu_index"]]["Signature"]==signature]
            # 六個原版按鈕都已返回，才有可保留的目標選單。
            if len(buttons)<6 or max(c["return_step"] for c in buttons[-6:])>=panel["step"]:continue
            hud_updates.append(panel)
        assert len(hud_updates)==len(hud_update_entries)
    else:assert not hud_update_entries
    for entry,returned,panel in zip(hud_update_entries,hud_update_returns,hud_updates):
        signature=panel["menu_snapshot"]["Signature"]
        assert entry["Step"]==panel["step"] and returned["Step"]==panel["return_step"]
        assert entry["detail"]==dict(caller=panel["caller"],ss=panel["regs"]["SS"],sp=panel["regs"]["SP"],menu_signature=signature,raw_c6b7=panel["raw_c6b7"])
        assert returned["detail"]==dict(entry_step=entry["Step"],caller=panel["caller"],ss=panel["regs"]["SS"],sp=(panel["regs"]["SP"]+4)&65535,menu_signature=signature)
    hud_restores=[e for e in b["list_events"] if e["Kind"]=="hud-footer-restored"]
    if effects:
        next_panel=next(p for p in hud_updates if p["caller"]=={"Seg":0x22f4,"Off":0x2d1c})
        restore=next(c for c in trace["calls"] if c["step"]>next_panel["return_step"] and c["caller"]=={"Seg":0xceb,"Off":0x1be} and c["format"]["text"]=="Next" and (c["stack"][4]&15)==7)
        assert len(hud_restores)==1 and hud_restores[0]["Step"]==restore["return_step"]
        assert hud_restores[0]["detail"]==dict(caller=restore["caller"],ss=restore["ss"],sp=(restore["sp"]+4)&65535)
    else:assert not hud_restores
    hud_retired=[e for e in b["list_events"] if e["Kind"]=="hud-damage-retired"]
    if effects:
        retire_fills=[]
        for record in hud_records:
            if record.get("number") is None:continue
            fill=next(f for f in trace["fill_events"] if f["step"]>record["return_step"] and f["native_rect"]==[184,80,128,96])
            assert fill["stack"][:2]==[0x1b,0xb72] and not fill["within_list"]
            retire_fills.append(fill)
        assert [e["Step"] for e in hud_retired]==[f["converted_step"] for f in retire_fills]
        last_retire=retire_fills[-1]["converted_step"]
        new_buttons=[c for c in trace["calls"] if c["step"]>last_retire and c["caller"]=={"Seg":0xceb,"Off":0x1be}]
        new_signature=trace["menus"][new_buttons[0]["menu_index"]]["Signature"]
        footer_restored=max(c["return_step"] for c in new_buttons if trace["menus"][c["menu_index"]]["Signature"]==new_signature)
    elif rounds or fire_path:
        # 自動施法沿用原版傷害框清除；來源限定為具原生選單見證的魔法傷害模板。
        retire_fills=[]
        aim_keys={p['IntegerTemplateKey'] for p in config['HUDParagraphs'] if p.get('KeepFooterSignature')}
        for record in hud_records:
            if record['binding'].get('IntegerTemplateKey') not in aim_keys:continue
            fill=next(f for f in trace['fill_events'] if f['step']>record['return_step'] and f['native_rect']==[184,80,128,96])
            assert fill['stack'][:2]==[0x1b,0xb72] and not fill['within_list']
            retire_fills.append(fill)
        assert [e['Step'] for e in hud_retired]==[f['converted_step'] for f in retire_fills]
        for event in hud_retired:
            assert event['detail']==dict(caller=dict(Seg=0xb72,Off=0x1b),native_rect=[184,80,128,96])
    else:assert not hud_retired
    paragraph_entries = [e for e in b["list_events"] if e["Kind"] == "paragraph-before-glyph"]
    paragraph_fallbacks = [e for e in b["list_events"] if e["Kind"] == "unknown-paragraph-original"]
    if config.get("Paragraphs"):
        assert {e["Step"] for e in paragraph_entries+paragraph_fallbacks+hud_entries} == set(paragraph_by_step)
        assert len(paragraph_entries)+len(paragraph_fallbacks)+len(hud_entries) == len(native_paragraphs)
    else:
        assert not paragraph_entries and not paragraph_fallbacks
    for e in paragraph_entries:
        p = paragraph_by_step[e["Step"]]
        assert len(paragraph_bindings(p)) == 1
        assert p["source"]["nul_terminated"] and bytes.fromhex(p["source"]["hex"]).decode("ascii") == p["source"]["text"]
        assert (p["source"]["segment"],p["source"]["offset"]) == (p["stack"][10],p["stack"][9])
        assert e["Step"] < e["first_glyph"] == p["first_glyph"] < p["return_step"]
        assert e["detail"]["caller"] == p["caller"]
        assert e["detail"]["source_pointer"] == {"Seg":p["source"]["segment"],"Off":p["source"]["offset"]}
    paragraph_returns = [e for e in b["list_events"] if e["Kind"] == "paragraph-return"]
    assert len(paragraph_returns) == len(paragraph_entries)
    for entry, returned in zip(paragraph_entries,paragraph_returns):
        p = paragraph_by_step[entry["Step"]]
        assert returned["Step"] == p["return_step"]
        assert returned["detail"] == {"caller":p["caller"],"ss":p["regs"]["SS"],"sp":(p["regs"]["SP"]+4)&65535}
    from ui_journal_reader_check import reader_model, paint_reader
    from ui_journal_illustrations_check import illustrations
    reader_images = illustrations(inputs)
    reader = reader_model(inputs,config,native_paragraphs,paragraph_entries,(a,b))
    def field_start(field, text):
        if not field.get("SourcePattern"):
            return field["Start"] if sha(text.encode()) == field["SHA256"] else None
        if field["SourcePattern"]=="movement-left":
            movement_source=provenance.get('movement_extension')
            assert movement_source and field in [row["binding"] for row in movement_source["data"]["fields"][:2]]
            from movement_ui_inputs import counter
            return 0 if counter(text,en[field["Key"]]) is not None else None
        if field["SourcePattern"]=="created-name":
            assert (creation or field in inherited_creation_fields) and field["Pane"]=="callsite" and field["Group"]=="footer"
            assert en[field["Key"]]=="Save" and field["SHA256"]==sha(b"Save")
            assert field["UpperCaller"]=={"Seg":0xCEB,"Off":0x995} and field["Caller"]=={"Seg":0xB72,"Off":0x27C}
            assert (field["RawX"],field["RawY"],field["Start"],field["Length"])==(8004,189,0,4)
            return 0 if re.fullmatch(r"Save [ -~]{1,15}\? ",text) else None
        if field["SourcePattern"]=="age-unit":
            assert (creation or field in inherited_creation_fields) and field["Pane"]=="callsite" and field["Group"]=="body" and en[field["Key"]]=="years"
            assert field["UpperCaller"]=={"Seg":0x2C4A,"Off":0xD3} and (field["RawX"],field["RawY"],field["Length"])==(8032,8012,5)
            return len(text)-5 if re.fullmatch(r"[0-9]+ years",text) else None
        assert field["SourcePattern"] == "clock-period"
        assert field["Pane"] == "callsite" and field["Group"] == "body"
        assert field["UpperCaller"] == {"Seg": 0x205E, "Off": 0x53C}
        assert (field["RawX"], field["RawY"], field["Start"], field["Length"]) == (8104, 8060, 0, 2)
        if re.fullmatch(r"[0-9]{1,2}:[0-9]{2} (AM|PM)", text) and text[-2:] == en[field["Key"]] and sha(text[-2:].encode()) == field["SHA256"]:
            return len(text)-2
        return None
    # 從原版整表 bytes 獨立重建按鈕順序、文字指標、座標及指紋。
    native = lambda value: value if value < 400 else (value - 8000) * 2
    refresh_sources = {e["step"]: e for e in trace.get("menu_refresh_sources") or []}
    for menu in [*trace["menus"], *(e["menu_snapshot"] for e in trace["list_events"] if "menu_snapshot" in e),
                 *(e["menu_snapshot"] for e in refresh_sources.values() if e["valid"])]:
        raw = bytes.fromhex(menu["RawHex"])
        assert len(raw) == menu["Count"] * 32
        indices = [i for i in range(menu["Count"]) if struct.unpack_from("<HH", raw, i*32) == (0x8E, 0xCEB)]
        assert indices == [b["Index"] for b in menu["Buttons"]]
        signature = []
        for button in menu["Buttons"]:
            record = raw[button["Index"]*32:][:32]
            off, seg, y, x = struct.unpack_from("<HHHH", record, 12)
            assert button["SourcePointer"] == {"Seg": seg, "Off": off}
            assert (button["RawX"], button["RawY"]) == (x, y)
            assert sha(bytes.fromhex(button["SourceHex"])) == button["SHA256"]
            signature.append([button["Index"], button["SHA256"], x, y])
        assert sha(json.dumps([menu["Count"], signature], separators=(",", ":")).encode()) == menu["Signature"]
        if menu["Signature"] in config["Menus"]:
            for button in menu["Buttons"]:
                text = bytes.fromhex(button["SourceHex"]).decode("ascii")
                matches = [f for f in config["Fields"] if f["Pane"] == "menu" and f["MenuSignature"] == menu["Signature"]
                           and f["RawX"] == native(button["RawX"]) and f["RawY"] == native(button["RawY"])+1
                           and f["SHA256"] == button["SHA256"] and f["FormatSHA256"] == button["SHA256"]
                           and f["Caller"] == {"Seg": 0xCEB, "Off": 0x1BE}]
                assert len(matches) == 1
                field = matches[0]
                assert field["Group"] == "footer" and field["Start"] == 0 and field["Length"] == len(text)
                assert en[field["Key"]] == text
    def menu_signature(call):
        index = call.get("menu_index", -1)
        return trace["menus"][index]["Signature"] if index >= 0 else ""
    for c in trace["calls"]:
        if c["caller"] != {"Seg": 0xCEB, "Off": 0x1BE}:
            continue
        assert c["menu_index"] >= 0
        menu = trace["menus"][c["menu_index"]]
        buttons = [b for b in menu["Buttons"] if b["SourceHex"] == c["format"]["hex"]
                   and native(b["RawX"]) == native(c["stack"][3]) and native(b["RawY"])+1 == native(c["stack"][2])]
        assert len(buttons) == 1
    for actual in (a, b):
        if actual.get("cold_boot"):
            assert "initial_state_sha256" not in actual
            assert actual["bridge_state_sha256"] == oracle["state_sha256"]
            assert sha((en_run if actual is a else zh_run).joinpath("cold-handoff.state").read_bytes()) == oracle["state_sha256"]
            if oracle.get("cold_boot"):
                assert not oracle["snapshot_loaded"] and actual["cold_request_sha256"]==oracle["boot_request_sha256"]
        else:
            assert actual["initial_state_sha256"] == oracle["state_sha256"]
        assert actual["list_request_sha256"] == oracle["request_sha256"]
        assert actual["list_inputs_sha256"] == sha((inputs / "inputs.json").read_bytes())
        assert actual["catalog_sha256"] == sha((inputs / "zh-TW.tsv").read_bytes())
        assert actual["source_catalog_sha256"] == sha((inputs / "en.tsv").read_bytes())
        assert actual["glyphs_sha256"] == sha((inputs / "glyphs-16.json").read_bytes())
        assert not actual["unimplemented"]
        assert len(actual["checkpoints"]) == len(oracle["checkpoints"])
        for x, y in zip(actual["checkpoints"], oracle["checkpoints"]):
            for field in ("label", "step", "regs", "ram_sha256", "indexed_sha256", "palette", "keys_consumed", "file_writes"):
                offset = actual["cold_checkpoints"][-1]["keys_consumed"] if field == "keys_consumed" and actual.get("cold_boot") and not oracle.get("cold_boot") else 0
                expected = y[field]+offset if offset else y[field]
                assert x[field] == expected, (field, x["step"])
        for field in ("regs", "ram_sha256", "indexed_sha256", "palette"):
            assert actual[field] == oracle["checkpoints"][-1][field]
    assert a["list_events"] == b["list_events"]
    if creation:
        name_calls=[c for c in trace["calls"] if c["caller"]=={"Seg":0x266D,"Off":0x11F} and c["vararg_1_candidate"]["text"]=="Character name:"]
        entries=[e for e in b["list_events"] if e["Kind"]=="creation-name-entry"]
        ready=[e for e in b["list_events"] if e["Kind"]=="creation-name-ready"]
        assert len(entries)==len(ready)==len(name_calls)
        for call,entry,done in zip(name_calls,entries,ready):
            assert entry["Step"]==call["step"] and done["Step"]==call["return_step"]
            assert done["detail"]==dict(caller=call["caller"],ss=call["ss"],sp=(call["sp"]+4)&65535)
        if name_calls:
            stable={f["step"]:f for f in b["frames"]}
            assert not stable[320000000]["held"] and not stable[322000000]["held"]
            assert stable[320000000]["SHA256"]!=stable[322000000]["SHA256"],"命名輸入必須在 Return 前可見"
    accepted = [e for e in b["list_events"] if e["Kind"] == "row-before-glyph"]
    bindings = {(row["Pane"], row["SHA256"]): row for row in config["Rows"]}
    configured_bindings=set(bindings)
    wrappers, pane = {}, ""
    timeline = []
    raw_timeline = []
    for fill in trace["fill_events"]:
        x, y, w, h = fill["native_rect"]
        if not fill["within_list"] and x <= 8 and y <= 8 and x+w >= 312 and y+h >= 184:
            raw_timeline.append((fill["step"], "clear", ""))
    for wrapper in trace["wrappers"]:
        if wrapper["stack"][3] & 255 == 1:
            found = [h["Pane"] for h in config["Headers"] if wrapper["format"]["segment"] == h["Segment"]
                     and wrapper["format"]["offset"] == h["Offset"] and sha(wrapper["format"]["text"].encode()) == h["SHA256"]]
            kind = "row-at-title" if wrapper["caller"] in config["RowCallers"] else "header"
            raw_timeline.append((wrapper["step"], kind, found[0] if found else ""))
    contexts = []
    for original in trace["list_events"]:
        matched = []
        for source in config["PaneLists"]:
            if source["DescriptorSHA256"] == sha(bytes.fromhex(original["descriptor_before_hex"])) \
                    and source["Caller"] == {"Seg": original["stack"][1], "Off": original["stack"][0]} \
                    and source["MenuSignature"] == original.get("menu_snapshot", {}).get("Signature"):
                contexts.append((original["step"], source))
                matched.append(source["Pane"])
        assert len(matched) <= 1
        raw_timeline.append((original["step"], "descriptor", matched[0] if matched else ""))
    active_pane, descriptor_context = "", False
    for step, kind, value in sorted(raw_timeline, key=lambda event: event[0]):
        if kind == "descriptor":
            if descriptor_context:
                active_pane = ""
            descriptor_context = bool(value)
            if value:
                active_pane = value
        elif kind != "row-at-title" or not descriptor_context:
            active_pane, descriptor_context = value, False
        timeline.append((step, active_pane))
    hits = [e for e in b["list_events"] if e["Kind"] == "list-context"]
    assert len(hits) == len(contexts)
    for event, (step, source) in zip(hits, contexts):
        assert event["Step"] == step and event["Pane"] == source["Pane"]
        assert event["detail"] == {"descriptor_sha256": source["DescriptorSHA256"], "menu_signature": source["MenuSignature"], "caller": source["Caller"]}
    baselines = [e for e in b["list_events"] if e["Kind"] == "list-page-baseline"]
    pages = [e for e in b["list_events"] if e["Kind"] == "list-render-page"]
    expected_baselines = []
    for step, source in contexts:
        listing = next(e for e in trace["list_events"] if e["step"] == step)
        fills = [f for f in trace["fill_events"] if step <= f["step"] <= listing["return_instruction_step"] and f["native_rect"][2] > 0 and f["native_rect"][3] > 0]
        if source["RowFillPage"] and fills:
            expected_baselines.append(fills[0])
    assert len(baselines) == len(pages) == len(expected_baselines)
    for baseline, page in zip(baselines, pages):
        fill = next(f for f in trace["fill_events"] if f["step"] <= baseline["Step"] <= f["return_instruction_step"]
                    and f["native_rect"] == baseline["detail"] and f["within_list"])
        assert baseline["Step"] < page["Step"] <= fill["return_instruction_step"]
        x, y, width, height = fill["native_rect"]
        assert width > 0 and height > 0 and x % 4 == 0
        assert page["detail"]["origin"] == [x, y]
        assert page["detail"]["target_page"] == (page["detail"]["first_write_offset"] - y*80-x//4) & 65535
        assert page["detail"]["target_page"] in (0, 16384)
        assert page["detail"].get("pre_origin_writes", 0) >= 0
    timeline.sort()
    actor_headers = []
    for step, source in contexts:
        if source["Pane"] != "effects":
            continue
        listing = next(e for e in trace["list_events"] if e["step"] == step)
        end = next(f["step"] for f in trace["fill_events"] if f["step"] > listing["return_instruction_step"]
                   and f["native_rect"] == [8, 8, 304, 176])
        for wrapper in trace["wrappers"]:
            if listing["step"] <= wrapper["step"] <= listing["return_instruction_step"] and wrapper["stack"][4] & 255 == 12:
                text = wrapper["vararg_1_candidate"]["text"]
                actor_headers.append((step, end, ((wrapper["stack"][2]&255)*8, (wrapper["stack"][3]&255)*8, len(text)*8, 8)))
    cursor = 0
    for i, wrapper in enumerate(trace["wrappers"]):
        while cursor < len(timeline) and timeline[cursor][0] <= wrapper["step"]:
            pane = timeline[cursor][1]
            cursor += 1
        if wrapper["format"]["text"] != "%s":
            continue
        source = wrapper["vararg_1_candidate"]["text"]
        row = bindings.get((pane, sha(source.encode())))
        if row is None and pane=="inventory" and any(r["Pane"]=="inventory" and any(s["Key"]=="inventory.423c677c12e0b601c34c" for s in r["Spans"]) for r in config["Rows"]):
            row=ammo_row_model(source,en)
            if row is not None:
                bindings[(pane,row["SHA256"])]=row
        within_list = any(p["step"] <= wrapper["step"] <= p["return_instruction_step"] for p in trace["list_events"])
        if wrapper["format"]["text"] == "%s" and within_list and "\t" in source:
            assert row is not None, (pane, source)
        if pane in ("shop-stock", "temple-spells") and wrapper["caller"] in config["RowCallers"] and wrapper["stack"][4] & 255 in (7, 11):
            assert row is not None, ("untranslated observed service row", pane, source)
        if row and wrapper["stack"][4] & 255 in row["Foregrounds"]:
            assert wrapper["caller"] in config["RowCallers"], ("unregistered known-row caller", wrapper["caller"], source)
            wrappers[i] = row
    expected = [c for c in trace["calls"] if c["wrapper_index"] in wrappers]
    assert len(accepted) == len(expected)
    assert accepted or paragraph_entries or ((creation or battle) and any(e["Kind"]=="field-before-glyph" for e in b["list_events"])), "沒有列表列、段落或已驗來源欄位接入"
    for event, original in zip(accepted, expected):
        wrapper = trace["wrappers"][original["wrapper_index"]]
        assert event["Step"] == wrapper["step"] < event["first_glyph"] == original["first_glyph"]
        assert event["detail"]["source_sha256"] == sha(original["vararg_1_candidate"]["text"].encode())
        binding = wrappers[original["wrapper_index"]]
        assert event["Pane"] == binding["Pane"]
        assert event["detail"]["spans"] == binding["Spans"]
        assert event["detail"]["caller"] == wrapper["caller"]
        assert event["detail"]["foreground"] == wrapper["stack"][4] & 255
        assert event["detail"]["within_list"] == any(p["step"] <= wrapper["step"] <= p["return_instruction_step"] for p in trace["list_events"])
        for span in binding["Spans"]:
            wanted = {"X": ((wrapper["stack"][2] & 255) + span["Start"]) * 8,
                      "Y": (wrapper["stack"][3] & 255) * 8, "Width": span["Length"] * 8,
                      "Key": span["Key"], "Group": "body", "Foreground": wrapper["stack"][4] & 255,
                      "Background": config["Background"]}
            assert wanted in event["Words"]
    assert {e["detail"]["source_sha256"] for e in accepted} == {row["SHA256"] for row in wrappers.values()}
    # 由原版下層印字事件核對欄位，不以原型自行宣稱的文字框作為來源。
    fields = [e for e in b["list_events"] if e["Kind"] == "field-before-glyph"]
    calls_by_step = {c["step"]: c for c in trace["calls"]}
    field_by_id = {}
    verified_field_widths = set()
    verified_field_backgrounds = set()
    verified_field_widths.update((w["Key"],w["Width"]) for words_here in hud_words.values() for w in words_here)
    for e in fields:
        c = calls_by_step[e["Step"]]
        source = c["vararg_1_candidate"] if c["format"]["text"] == "%s" else c["format"]
        matches = [f for f in config["Fields"] if f["Key"] == e["detail"]["key"] and f["RawX"] == c["stack"][3] and f["RawY"] == c["stack"][2]
                   and f["Caller"] == c["caller"] and field_start(f, source["text"]) is not None
                   and ("Color" not in f or f["Color"] == (c["stack"][4]&255))
                   and f["FormatSHA256"] == sha(c["format"]["text"].encode())
                   and (f["Pane"] == e["Pane"] or f["Pane"] in ("suffix", "callsite", "menu", "menu-text"))
                   and (f["Pane"] not in ("menu","menu-text") or f["MenuSignature"] == menu_signature(c))
                   and (f["Pane"] != "callsite" or c["wrapper_index"] >= 0
                        and trace["wrappers"][c["wrapper_index"]]["caller"] == f["UpperCaller"]
                        and (not f.get("UpperFormatSHA256") or sha(trace["wrappers"][c["wrapper_index"]]["format"]["text"].encode()) == f["UpperFormatSHA256"]))]
        assert len(matches) == 1
        f = matches[0]
        movement_field=bool(movement and f.get("SourcePattern")=="movement-left"
                            and f in [row["binding"] for row in movement["data"]["fields"][:2]])
        assert e["detail"]["menu_signature"] == f.get("MenuSignature", "")
        assert e["Step"] < e["first_glyph"] == c["first_glyph"]
        start = field_start(f, source["text"])
        assert e["detail"]["source_sha256"] == sha(source["text"].encode())
        assert e["detail"].get("source_start", None if f.get("SourcePattern") else f["Start"]) == start
        assert e["detail"]["deferred"] == (f["Pane"] == "suffix")
        assert source["text"][start:start+f["Length"]] == en[f["Key"]]
        if f["Pane"] == "callsite":
            wrapper = trace["wrappers"][c["wrapper_index"]]
            assert wrapper["step"] < c["step"]
            if f.get("UpperFormatSHA256"):
                assert sha(wrapper["format"]["text"].encode()) == f["UpperFormatSHA256"]
                assert wrapper["format"]["text"] in ("%s", "%s%s")
            else:
                assert wrapper["format"]["text"] == source["text"]
            expected_upper = f.get("UpperNative",[native(c["stack"][3]),native(c["stack"][2])])
            assert [(wrapper["stack"][n]&255)*8 for n in (2,3)] == expected_upper
            if movement_field:
                assert f["UpperNative"]==[0,192] and c["stack"][2:5]==[189,8004,f["Color"]]
            elif hud and f.get("UpperNative") in ([184,8],[184,80],[184,96]) and f in hud_field_bindings:
                assert f["UpperCaller"]=={"Seg":0x088e,"Off":0x16fb} and f["UpperNative"]==[184,native(f["RawY"])]
                assert c["stack"][2:5]==[f["RawY"],8092,0x82] and f["Color"]==0x82
            elif f.get("UpperFormatSHA256") and "UpperNative" in f:
                assert f["UpperNative"] == [0,192] and c["stack"][2:4] == [189,8004]
                if f["UpperCaller"] == {"Seg":0x088e,"Off":0x1560}:
                    assert c["stack"][4] == f["Color"] == 0x8f and "BackgroundOverride" not in f
                else:
                    assert f["UpperCaller"] == {"Seg":0xCEB,"Off":0x995}
                    assert c["stack"][4] == f["Color"] == 0x70 and f["BackgroundOverride"] == 7
                    assert (source["text"] == "items :" and (start,f["Length"]) == (0,5)) or (
                        source["text"] in ("Is It a Deal? ","Will you sell it? ","Game not saved. Load anyway? ","load from where? ","load which game:") and start == 0 and f["Length"] == len(source["text"].rstrip())) or (creation and (
                        (source["text"] in ("add from where? ","add a character:") and start==0 and f["Length"]==16) or
                        (f.get("SourcePattern")=="created-name" and start==0 and f["Length"]==4 and re.fullmatch(r"Save [ -~]{1,15}\? ",source["text"]))))
            if f.get("UpperCaller")=={"Seg":0x2287,"Off":0x316A}:
                assert source["text"]=="Loading...Please Wait" and f["UpperNative"]==[0,192]
                assert c["stack"][2:5]==[189,8004,0x8f] and f["Color"]==0x8f and "BackgroundOverride" not in f
        background = f.get("BackgroundOverride",config["Background"])
        if "BackgroundOverride" in f and background==23:
            if hud and f.get("UpperNative") in ([184,8],[184,80],[184,96]) and f in hud_field_bindings:
                assert f["Pane"]=="callsite" and f["Group"]=="body" and f["UpperNative"]==[184,native(f["RawY"])]
            elif creation and source["text"]=="Character name:":
                assert f["Pane"]=="menu-text" and f["Group"]=="footer" and f["Caller"]=={"Seg":0x266D,"Off":0x11F}
                assert c["stack"][2:5]==[189,8004,0x80] and f["Color"]==0x80 and (start,f["Length"])==(0,15)
            elif source["text"]=="Name":
                assert f["UpperCaller"]=={"Seg":0x205E,"Off":0x2A0}
                assert f["Pane"]=="callsite" and f["Group"]=="body" and (start,f["Length"])==(0,4)
                assert c["stack"][2:5]==[8008,8004,0x8c] and f["Color"]==0x8c
            else:
                assert source["text"]=="Return" and f["Pane"]=="menu" and f["Group"]=="footer"
                assert (start,f["Length"])==(0,6) and c["stack"][2:4]==[189,112]
                assert f["MenuSignature"]=="8f950eaf29b783d0b7fe41ad37f46380472d6c96b5cdc43d415f4384519f189f"
            word=e["detail"]["word"]
            gpu_frames={v["step"]:v for v in b["frames"]}
            visible=any(not gpu_frames[v["step"]]["held"] and word in (v["words"] or []) for v in b["list_frames"])
            if visible and (f["Key"],background) not in verified_field_backgrounds:
                checkpoint=next(cp for cp in trace["checkpoints"] if cp["step"]>=c["return_step"])
                original=Image.open(observed/(checkpoint["label"]+".png")).convert("RGB")
                x,y=native(c["stack"][3]),native(c["stack"][2])
                colors=set(original.crop((x,y,x+f["Length"]*8,y+8)).getdata())
                rect=(x,y,f["Length"]*8,8)
                overlap=lambda box: box[0]<x+rect[2] and box[0]+box[2]>x and box[1]<y+8 and box[1]+box[3]>y
                changes=[v["step"] for v in trace["fill_events"] if c["return_step"]<v["step"]<=checkpoint["step"] and overlap(v["native_rect"])]
                changes += [v["step"] for v in trace["calls"] if c["return_step"]<v["step"]<=checkpoint["step"]
                            and v["format"]["text"]!="%c" and overlap((native(v["stack"][3]),native(v["stack"][2]),8*len(v["vararg_1_candidate"]["text"] if v["format"]["text"]=="%s" else v["format"]["text"]),8))]
                if changes:
                    # 終點已換頁時，取覆寫前的獨立原版色號快照。
                    samples=[v for v in trace["fill_events"] if c["return_step"]<v["return_instruction_step"]<min(changes) and v.get("indexed_after")]
                    if samples:
                        data=(observed/samples[0]["indexed_after"]).read_bytes()
                        indices={data[yy*320+xx] for yy in range(y,y+8) for xx in range(x,x+rect[2])}
                        colors={tuple(checkpoint["palette"][v]) for v in indices}
                    else:
                        assert rounds or fire_path, '缺少欄位背景的原版色號快照'
                        original_frame=next(v for v in a['frames'] if c['return_step']<v['step']<min(changes) and not v['held'])
                        # 英文側不畫翻譯；取文字已返回且尚未被覆寫的實際 GPU 像素。
                        image=Image.open(en_run/original_frame['File']).convert('RGB')
                        assert image.size==(640,400)
                        colors=set(image.crop((x*2,y*2,(x+rect[2])*2,(y+8)*2)).getdata())
                bg=tuple(checkpoint["palette"][23]);fg=tuple(checkpoint["palette"][c["stack"][4]&15])
                assert bg in colors and colors<={bg,fg,tuple(checkpoint["palette"][0]),tuple(checkpoint["palette"][15])}, ("background sample",source["text"],c["step"],checkpoint["label"],colors,bg,fg)
                verified_field_backgrounds.add((f["Key"],background))
        elif "BackgroundOverride" in f:
            if f["UpperCaller"] == {"Seg":0xCEB,"Off":0x4BD}:
                assert f["UpperNative"] == [56,192] and c["stack"][2:5] == [189,8032,0x70]
                assert source["text"] == "Press        to continue." and (start,f["Length"]) in ((0,5),(13,12))
            else:
                assert f["UpperCaller"] == {"Seg":0xCEB,"Off":0x995} and f["UpperNative"] == [0,192]
                assert c["stack"][2:5] == [189,8004,0x70]
                assert (movement_field and start==0 and f["Length"]==len(en[f["Key"]])) or (source["text"] == "items :" and (start,f["Length"]) == (0,5)) or (
                    source["text"] in ("Is It a Deal? ","Will you sell it? ","Game not saved. Load anyway? ","load from where? ","load which game:") and start == 0 and f["Length"] == len(source["text"].rstrip())) or (creation and (
                    (source["text"] in ("add from where? ","add a character:") and start==0 and f["Length"]==16) or
                    (f.get("SourcePattern")=="created-name" and start==0 and f["Length"]==4 and re.fullmatch(r"Save [ -~]{1,15}\? ",source["text"]))))
            assert f["Color"] == 0x70 and background == 7
            checkpoint=next(cp for cp in trace["checkpoints"] if cp["step"]>=c["return_step"])
            original=Image.open(observed/(checkpoint["label"]+".png")).convert("RGB")
            foreground=tuple(checkpoint["palette"][0]);bg=tuple(checkpoint["palette"][7])
            left=native(c["stack"][3])+start*8
            assert set(original.crop((left,189,left+f.get("Width",f["Length"]*8),197)).getdata())=={foreground,bg}
            verified_field_backgrounds.add((f["Key"],background))
        width = f.get("Width", f["Length"]*8)
        if "Width" in f and source["text"]=="load which game:":
            assert (f["Width"],f["Length"],start)==(124,16,0)
            assert f["UpperCaller"]=={"Seg":0xCEB,"Off":0x995} and c["stack"][2:5]==[189,8004,0x70]
            checkpoint=next(cp for cp in trace["checkpoints"] if cp["step"]>=c["return_step"])
            original=Image.open(observed/(checkpoint["label"]+".png")).convert("RGB")
            assert set(original.crop((132,189,136,197)).getdata()).isdisjoint({tuple(checkpoint["palette"][0]),tuple(checkpoint["palette"][7])})
        elif creation and f.get("Width")==124 and source["text"] in ("add from where? ","add a character:"):
            assert f["Pane"]=="callsite" and f["Group"]=="footer" and f["UpperCaller"]=={"Seg":0xCEB,"Off":0x995}
            assert (start,f["Length"])==(0,16) and c["stack"][2:5]==[189,8004,0x70]
            checkpoint=next(cp for cp in trace["checkpoints"] if cp["step"]>=c["return_step"])
            original=Image.open(observed/(checkpoint["label"]+".png")).convert("RGB")
            assert set(original.crop((132,189,136,197)).getdata()).isdisjoint({tuple(checkpoint["palette"][0]),tuple(checkpoint["palette"][7])})
        elif "Width" in f:
            # 唯一已量測擴框是 AC／HP 的欄間及面板留白，不准任意擴框。
            assert f["UpperCaller"] == {"Seg": 0x205E, "Off": 0x2B9}
            assert source["text"] == "AC\tHP" and (f["Start"], f["Length"], width) in ((0, 2, 24), (3, 2, 24))
            assert (native(c["stack"][3]), native(c["stack"][2])) == (264, 16)
            checkpoint = next(cp for cp in trace["checkpoints"] if cp["step"] >= c["return_step"])
            original = Image.open(observed / (checkpoint["label"] + ".png")).convert("RGB")
            foreground = tuple(checkpoint["palette"][c["stack"][4] & 15])
            assert original.size == (320, 200)
            background_rgb = tuple(checkpoint["palette"][config["Background"]])
            assert set(original.crop((264, 16, 312, 24)).getdata()) == {foreground, background_rgb}
            ink = {x for x in range(264, 312) if any(original.getpixel((x, y)) == foreground for y in range(16, 24))}
            assert ink and ink <= set(range(264, 280)) | set(range(288, 304))
            assert ink & set(range(264, 280)) and ink & set(range(288, 304))
        word = {"X": native(c["stack"][3])+start*8, "Y": native(c["stack"][2]), "Width": width,
                "Key": f["Key"], "Group": f["Group"], "Foreground": c["stack"][4] & 15,
                "Background": background}
        if typed_buttons and f["Pane"] == "menu":
            word["Button"] = True
        if f.get("FontSize"):
            assert f["FontSize"]==20 and f["MenuSignature"]=="191c0ba49dc03bfaceb8be1ab19c0d92efb10341e05b2c851e46682a74451ed1"
            assert role_alpha is not None
            word["FontSize"]=20
        assert e["detail"]["word"] == word
        verified_field_widths.add((f["Key"], width))
        identity = e["Step"], f["Key"]
        assert identity not in field_by_id
        field_by_id[identity] = e
    # 所有已辨識列表內的靜態標題、提示及按鈕均須接入。所有格候選另驗 attach。
    title_wrappers = [w for w in trace["wrappers"] if any(
        w["format"]["segment"] == h["Segment"] and w["format"]["offset"] == h["Offset"]
        and w["stack"][3] & 255 == 1 for h in config["Headers"])]
    full_fills = [f["step"] for f in trace["fill_events"] if not f["within_list"]
                  and f["native_rect"][0] <= 8 and f["native_rect"][1] <= 8
                  and f["native_rect"][0] + f["native_rect"][2] >= 312
                  and f["native_rect"][1] + f["native_rect"][3] >= 184]
    intervals = [(w["step"], next((s for s in full_fills if s > w["step"]),oracle["request"]["actions"][-1]["end"]+1)) for w in title_wrappers]
    for c in trace["calls"]:
        source = c["vararg_1_candidate"] if c["format"]["text"] == "%s" else c["format"]
        in_list = any(start <= c["step"] < end for start, end in intervals)
        expected_keys = {f["Key"] for f in config["Fields"] if f["Pane"] != "suffix" and f["RawX"] == c["stack"][3] and f["RawY"] == c["stack"][2]
               and f["Caller"] == c["caller"] and field_start(f, source["text"]) is not None
               and ("Color" not in f or f["Color"] == (c["stack"][4]&255))
               and f["FormatSHA256"] == sha(c["format"]["text"].encode())
               and ((f["Pane"] == "callsite" and c["wrapper_index"] >= 0
                     and trace["wrappers"][c["wrapper_index"]]["caller"] == f["UpperCaller"]
                     and (not f.get("UpperFormatSHA256") or sha(trace["wrappers"][c["wrapper_index"]]["format"]["text"].encode()) == f["UpperFormatSHA256"]))
                    or (f["Pane"] in ("menu","menu-text") and f["MenuSignature"] == menu_signature(c))
                    or (f["Pane"] not in ("callsite", "menu","menu-text") and in_list))}
        actual_keys = {key for (step, key), event in field_by_id.items() if step == c["step"] and not event["detail"]["deferred"]}
        assert actual_keys == expected_keys, (c["step"], expected_keys, actual_keys)
    assert len([e for e in b["list_events"] if e["Kind"] == "title-suffix-attached"]) == len(title_wrappers)
    clock_keys = {f["Key"] for f in config["Fields"] if f.get("SourcePattern") == "clock-period"}
    clock_wrappers = [w for w in trace["wrappers"] if clock_keys and w["caller"] == {"Seg": 0x205E, "Off": 0x53C}
                      and ((w["stack"][2]&255)*8, (w["stack"][3]&255)*8) == (208, 120)]
    resets = [e for e in b["list_events"] if e["Kind"] == "clock-source-reset"]
    returns = [e for e in b["list_events"] if e["Kind"] == "clock-render-return"]
    assert len(resets) == len(returns) == len(clock_wrappers)
    clock_intervals = []
    for wrapper, reset, returned in zip(clock_wrappers, resets, returns):
        assert reset["Step"] == wrapper["step"]
        assert reset["detail"] == {"caller": wrapper["caller"], "native_xy": [208, 120]}
        assert returned["detail"] == {"caller": wrapper["caller"], "ss": wrapper["regs"]["SS"], "sp": (wrapper["regs"]["SP"]+4)&65535}
        lower = [c for c in trace["calls"] if c["wrapper_index"] >= 0 and trace["wrappers"][c["wrapper_index"]]["step"] == wrapper["step"]]
        assert len(lower) == 1 and lower[0]["return_step"] < returned["Step"]
        assert returned["Step"] < next((w["step"] for w in clock_wrappers if w["step"] > wrapper["step"]), oracle["request"]["actions"][-1]["end"])
        clock_intervals.append((reset["Step"], returned["Step"]))

    # 從有原版來源的事件重建每幀詞框位置，避免遺漏捲動頂列仍通過像素合成檢查。
    words, pending_suffix, model, row_positions = {}, None, [], set()
    feedback, feedback_intervals, service_scroll_checks = None, [], []
    battle_warning,battle_warning_intervals=None,[]
    battle_status,battle_status_intervals=None,[]
    status_witnesses={w['entry']:w for w in magic_toggle['data']['notices']} if magic_path else {}
    fire_captions={w['entry']:w for w in fire_path['captions']} if fire_path else {}
    fire_movement_witnesses={}
    active_fire_caption=None
    status_pixels={}
    for entry,witness in status_witnesses.items():
        x,y,w,h=witness['rect']
        values={}
        for name in ('before','ready','restored'):
            raw=(inputs.parent.parent/witness[name+'_index']).read_bytes()
            values[name]=b''.join(raw[row*320+x:row*320+x+w] for row in range(y,y+h))
        assert sha(values['before'])==witness['before_sha256'] and sha(values['ready'])==witness['ready_sha256']
        assert values['before']==values['restored']
        status_pixels[entry]=values
    warning_witness=rounds['data']['notice_witness'] if rounds else None
    warning_pixels={}
    if warning_witness:
        x,y,w,h=warning_witness['rect']
        for name in ('before','ready'):
            raw=(inputs.parent.parent/warning_witness[name+'_index']).read_bytes()
            warning_pixels[name]=b''.join(raw[row*320+x:row*320+x+w] for row in range(y,y+h))
            assert sha(warning_pixels[name])==warning_witness[name+'_sha256']
    notice, notice_intervals = None, []
    expected_notices = {p["step"] for p in native_paragraphs if p["caller"] == {"Seg":0x291A,"Off":0xFD0}
                        and any(f in trade_bindings for f in paragraph_bindings(p))}
    assert {e["Step"] for e in b["list_events"] if e["Kind"] == "service-notice-entry"} == expected_notices
    feedback_proof = None
    feedback_candidates = {w["step"]:w for w in trace["wrappers"] if w["caller"] == {"Seg":0x088E,"Off":0x1560}
                         and w["format"]["text"] == "%s" and any(
                             f["Pane"] == "callsite" and f["UpperCaller"] == w["caller"]
                             and f.get("UpperFormatSHA256") == sha(b"%s") and f["SHA256"] == sha(w["vararg_1_candidate"]["text"].encode())
                             for f in config["Fields"])}
    def feedback_pane(step):
        return next((pane for when,pane in reversed(timeline) if when <= step),"")
    expected_feedback = {step for step in feedback_candidates if feedback_pane(step) in ("shop-stock","inventory")}
    expected_battle_warning={warning_witness['entry']} & set(feedback_candidates) if warning_witness else set()
    expected_battle_status=set(status_witnesses)&set(feedback_candidates)
    assert expected_battle_status==set(status_witnesses)
    assert {e['Step'] for e in b['list_events'] if e['Kind']=='battle-status-entry'}==expected_battle_status
    assert {e["Step"] for e in b["list_events"] if e["Kind"] == "unknown-feedback-original"} == set(feedback_candidates)-expected_feedback-expected_battle_warning-expected_battle_status
    assert {e['Step'] for e in b['list_events'] if e['Kind']=='battle-warning-entry'}==expected_battle_warning
    assert {e["Step"] for e in b["list_events"] if e["Kind"] == "footer-feedback-capture"} == expected_feedback
    if any(e["Kind"] == "footer-feedback-capture" for e in b["list_events"]):
        service = item_context or trade or provenance["service_extension"]
        proof = service["feedback_proof"]
        proof_path = inputs.parent / proof["receipt"]
        assert proof_path.resolve().is_relative_to(inputs.parent.resolve())
        assert sha(proof_path.read_bytes()) == proof["sha256"]
        feedback_proof = read(proof_path)
        boundary = service["feedback_boundaries"]
        boundary_path = inputs.parent / boundary["receipt"]
        assert boundary_path.resolve().is_relative_to(inputs.parent.resolve())
        assert sha(boundary_path.read_bytes()) == boundary["sha256"]
        feedback_boundaries = read(boundary_path)
    page, page_history = None, []
    battle_erased_fields=[]
    active_movement_caption=None
    clear_baselines = []
    pending_clear_index = None
    wrappers_by_step = {w["step"]: w for w in trace["wrappers"]}
    def intersects(w, rect):
        x, y, width, height = rect
        return w["X"] < x + width and w["X"] + w["Width"] > x and w["Y"] < y + height and w["Y"] + w.get("Height",8) > y
    def erase(rect):
        for pos, w in list(words.items()):
            if intersects(w, rect):
                x,y,width,height=rect
                hud=any(w['Key']==s['Key'] and (w['X'],w['Y'],w['Width'])==tuple(s['Rect'][:3]) and w.get('Height',8)<=s['Rect'][3]
                    for p in config.get('HUDParagraphs',[]) for s in p['Spans'])
                if (hud and x<=w['X'] and x+width>=w['X']+w['Width'] and
                    w['Y']+8<=y<w['Y']+w.get('Height',8)<=y+height):
                    w=dict(w,Height=y-w['Y'])
                    if w['Height']==8:w.pop('Height')
                    words[pos]=w
                    continue
                del words[pos]
                row_positions.discard(pos)
    for e in b["list_events"]:
        kind = e["Kind"]
        if kind=='battle-status-entry':
            assert magic_path and battle_status is None and not e['Pane']
            witness=status_witnesses[e['Step']]
            assert e['detail']==dict(source_sha256=sha(witness['source'].encode()),native_rect=witness['rect'],before_sha256=witness['before_sha256'])
            for position,word in list(words.items()):
                if word['Group']=='footer':
                    del words[position]
                    row_positions.discard(position)
            battle_status=dict(entry=e['Step'],entry_index=b['list_events'].index(e),phase='painting',restoring_index=None)
        elif kind=='battle-status-ready':
            assert battle_status and battle_status['phase']=='painting'
            witness=status_witnesses[battle_status['entry']]
            wrapper=wrappers_by_step[battle_status['entry']]
            call=calls_by_step[witness['field_entry']]
            pages={int(k) for k in call['video_pages']}
            assert len(pages)==1 and e['Step']==wrapper['return_step']==witness['returned']
            assert e['detail']==dict(entry_step=wrapper['step'],caller=wrapper['caller'],ss=wrapper['return_ss'],sp=wrapper['return_sp'],
                native_rect=witness['rect'],reference_sha256=witness['ready_sha256'],paint_page=next(iter(pages)))
            battle_status.update(phase='ready',ready=e['Step'],ready_index=b['list_events'].index(e))
        elif kind=='battle-status-restore-begin':
            assert battle_status and battle_status['phase']=='ready'
            witness=status_witnesses[battle_status['entry']]
            assert witness['returned']<e['Step']<=witness['restored_by']
            assert e['detail']['entry_step']==battle_status['entry'] and e['detail']['native_rect']==witness['rect']
            assert e['detail']['actual_sha256'] not in (witness['before_sha256'],witness['ready_sha256'])
            battle_status.update(phase='restoring',restoring=e['Step'],restoring_index=b['list_events'].index(e))
        elif kind=='battle-status-closed':
            assert battle_status and battle_status['phase'] in ('ready','restoring')
            witness=status_witnesses[battle_status['entry']]
            assert witness['returned']<e['Step']<=witness['restored_by']
            assert e['detail']==dict(entry_step=battle_status['entry'],native_rect=witness['rect'],before_sha256=witness['before_sha256'],actual_sha256=witness['before_sha256'])
            erase(witness['rect'])
            battle_status_intervals.append(dict(battle_status,closed=e['Step'],closed_index=b['list_events'].index(e)))
            battle_status=None
        elif kind=='battle-warning-entry':
            assert warning_witness and battle_warning is None and not e['Pane']
            assert e['Step']==warning_witness['entry'] and not any(w['Group']=='footer' for w in words.values())
            wrapper=wrappers_by_step[e['Step']]
            assert wrapper['caller']=={'Seg':0x88e,'Off':0x1560} and wrapper['format']['text']=='%s'
            assert e['detail']==dict(source_sha256=sha(wrapper['vararg_1_candidate']['text'].encode()),native_rect=warning_witness['rect'],before_sha256=warning_witness['before_sha256'])
            battle_warning=dict(entry=e['Step'],entry_index=b['list_events'].index(e),phase='painting',restoring_index=None)
        elif kind=='battle-warning-ready':
            assert battle_warning and battle_warning['phase']=='painting'
            wrapper=wrappers_by_step[battle_warning['entry']];call=calls_by_step[warning_witness['field_entry']]
            pages={int(k) for k in call['video_pages']};assert len(pages)==1 and sum(call['video_pages'].values())==176*8
            assert e['Step']==wrapper['return_step']==warning_witness['returned']
            assert e['detail']==dict(entry_step=wrapper['step'],caller=wrapper['caller'],ss=wrapper['return_ss'],sp=wrapper['return_sp'],
                native_rect=warning_witness['rect'],reference_sha256=warning_witness['ready_sha256'],paint_page=next(iter(pages)))
            battle_warning.update(phase='ready',ready=e['Step'],ready_index=b['list_events'].index(e))
        elif kind=='battle-warning-restore-begin':
            assert battle_warning and battle_warning['phase']=='ready' and e['Step']>=warning_witness['return_key_at']
            assert e['detail']['entry_step']==battle_warning['entry'] and e['detail']['native_rect']==warning_witness['rect']
            assert e['detail']['actual_sha256'] not in (warning_witness['before_sha256'],warning_witness['ready_sha256'])
            battle_warning.update(phase='restoring',restoring=e['Step'],restoring_index=b['list_events'].index(e))
        elif kind=='battle-warning-closed':
            assert battle_warning and battle_warning['phase'] in ('ready','restoring')
            assert warning_witness['return_key_at']<=e['Step']<=warning_witness['restored_by']
            assert e['detail']==dict(entry_step=battle_warning['entry'],native_rect=warning_witness['rect'],before_sha256=warning_witness['before_sha256'],actual_sha256=warning_witness['before_sha256'])
            erase(warning_witness['rect'])
            battle_warning_intervals.append(dict(battle_warning,closed=e['Step'],closed_index=b['list_events'].index(e)))
            battle_warning=None
        elif kind=="hud-before-glyph":
            p=paragraph_by_step[e["Step"]]
            x,y,right,bottom=p["native_box"]
            erase((x,y,right-x,bottom-y))
            page=None
        elif kind=='spell-caption-ready':
            assert rounds or fire_path
            call=calls_by_step[e['detail']['entry_step']]
            wrapper=trace['wrappers'][call['wrapper_index']]
            assert call['format']['text']=='%s'
            if fire_path:
                witness=fire_captions[call['step']]
                checkpoint=next(c for c in trace['checkpoints'] if c['step']==wrapper['return_step'])
                rect=witness['rect']
                active_fire_caption=witness
                assert call['vararg_1_candidate']['text']==en[witness['key']]
            else:
                assert call['vararg_1_candidate']['text']=='Spell:Magic Missile'
                checkpoint=next(c for c in trace['checkpoints'] if c['step']>wrapper['return_step'])
                rect=[8,178,152,8]
            raw=(observed/(checkpoint['label']+'.idx')).read_bytes()
            x,y,width,height=rect
            reference=b''.join(raw[row*320+x:row*320+x+width] for row in range(y,y+height))
            assert sha(raw)==checkpoint['indexed_sha256']
            if fire_path:assert sha(reference)==witness['reference_sha256']
            assert e['Step']==wrapper['return_step']
            assert e['detail']==dict(entry_step=call['step'],caller=wrapper['caller'],ss=wrapper['return_ss'],sp=wrapper['return_sp'],
                native_rect=rect,reference_sha256=sha(reference))
        elif kind=='spell-caption-retired':
            if fire_path:
                assert active_fire_caption and active_fire_caption['entry']==e['detail']['entry_step']
                rect=active_fire_caption['rect']
                assert any(w['Key']==active_fire_caption['key'] for w in words.values())
                active_fire_caption=None
            else:
                assert rounds and any(w['Key']=='round.1a0e55074a01fc9262bb' for w in words.values())
                rect=[8,178,152,8]
            ready=next(v for v in b['list_events'] if v['Kind']=='spell-caption-ready' and v['detail']['entry_step']==e['detail']['entry_step'])
            assert ready['Step']<e['Step'] and e['detail']['native_rect']==rect
            assert e['detail']['reference_sha256']==ready['detail']['reference_sha256']!=e['detail']['actual_sha256']
            erase(rect)
        elif kind=="movement-caption-ready":
            if fire_path:
                call=calls_by_step[e['detail']['entry_step']]
                wrapper=trace['wrappers'][call['wrapper_index']]
                field,=[f for f in config['Fields'] if f.get('SourcePattern')=='movement-left' and f.get('Color')==0x8f and f['UpperCaller']==wrapper['caller']]
                assert call['format']['text']=='%s' and call['vararg_1_candidate']['text'].startswith(en[field['Key']])
                checkpoint=next(c for c in trace['checkpoints'] if c['step']>wrapper['return_step'])
                raw=(observed/checkpoint['indexed_file']).read_bytes()
                assert sha(raw)==checkpoint['indexed_sha256']
                rect=[8,189,field['Length']*8,8]
                reference=b''.join(raw[y*320+8:y*320+8+rect[2]] for y in range(189,197))
                witness=dict(step=wrapper['return_step'],native_rect=rect,reference_sha256=sha(reference))
                counter_record=dict(step=call['step'])
                counter_key=field['Key']
                fire_movement_witnesses[call['step']]=witness
            else:
                assert movement and movement_path["source_path"]==movement["data"]["quick_source"]
                counter_record=movement_path["counters"][0]
                call=calls_by_step[counter_record["step"]]
                wrapper=trace["wrappers"][call["wrapper_index"]]
                witness=movement["data"]["quick_witness"]
                counter_key=movement['data']['fields'][0]['binding']['Key']
            removed=sorted((w for w in words.values() if w["Group"]=="footer" and w.get("Button")),key=lambda w:(w["Y"],w["X"]))
            assert e["Step"]==wrapper["return_step"]==witness["step"]
            assert e["detail"]==dict(entry_step=counter_record["step"],caller=wrapper["caller"],ss=wrapper["return_ss"],sp=wrapper["return_sp"],
                native_rect=witness["native_rect"],reference_sha256=witness["reference_sha256"],removed_buttons=(removed or None) if fire_path else removed)
            for w in removed:del words[(w["X"],w["Y"])]
            active_movement_caption=dict(key=counter_key,entry=counter_record["step"],rect=witness["native_rect"],reference=witness["reference_sha256"])
        elif kind=="movement-caption-retired":
            assert active_movement_caption and (movement or fire_path)
            c=active_movement_caption;detail=e["detail"]
            assert detail["entry_step"]==c["entry"] and detail["native_rect"]==c["rect"] and detail["reference_sha256"]==c["reference"]
            assert len(detail["actual_sha256"])==64 and detail["actual_sha256"]!=c["reference"]
            erase(c["rect"])
            active_movement_caption=None
        elif kind=="hud-return":
            for w in hud_words[e["detail"]["entry_step"]]:
                erase((w["X"],w["Y"],w["Width"],w.get("Height",8)))
                words[(w["X"],w["Y"])]=w
            if e["detail"]["footer_hidden"]:
                for pos,w in list(words.items()):
                    if w["Group"]=="footer":
                        if active_fire_caption and w['Key']==active_fire_caption['key']:
                            continue
                        if rounds and w['Key']=='round.1a0e55074a01fc9262bb' and (w['X'],w['Y'],w['Width'])==(8,178,152):
                            continue
                        if active_movement_caption and w["Key"]==active_movement_caption["key"]:
                            continue
                        del words[pos]
                        row_positions.discard(pos)
        elif kind=="hud-damage-retired":
            original=next(f for f in trace["fill_events"] if f["converted_step"]==e["Step"])
            assert original["native_rect"]==[184,80,128,96] and any(w.get("Number") is not None for w in words.values())
            assert e["detail"]==dict(caller={"Seg":0xb72,"Off":0x1b},native_rect=original["native_rect"])
        elif kind in ("hud-update-entry","hud-update-return","hud-footer-restored"):
            assert effects
        elif kind=="hud-panel-redraw":
            assert hud
            original=next(f for f in trace["fill_events"] if f["converted_step"]==e["Step"])
            assert not original["within_list"] and original["native_rect"]==[184,8,128,168] and original["stack"][:2]==[0x1b,0xb72]
            assert e["detail"]==dict(caller={"Seg":0xb72,"Off":0x1b},native_rect=original["native_rect"])
        elif kind == "memory-list-closed":
            assert (cast or spell_path) and config["Headers"][-1]["SHA256"]=="41b8dd827bde29bd2677001414cc57fb5111abb92366cc5e7179c24c8304d341"
            original=next(f for f in trace["fill_events"] if f["converted_step"]==e["Step"])
            assert not original["within_list"] and original["native_rect"]==[184,8,128,168]
            assert original["stack"][:2]==[0x1b,0xb72]
            assert e["detail"]==dict(caller={"Seg":0xb72,"Off":0x1b},native_rect=original["native_rect"])
            for position,word in list(words.items()):
                if word["Group"]!="footer":
                    del words[position]
                    row_positions.discard(position)
            page=None
        elif kind == "paragraph-before-glyph":
            p = paragraph_by_step[e["Step"]]
            binding = paragraph_bindings(p)[0]
            components = [binding["Key"]]
            component_colors = [p["foreground"]]
            box = [v*2 for v in p["native_box"]]
            if binding["Key"].startswith("service-message."):
                assert binding in trade_bindings
                bg = 23
            else:
                bg = p["background"] or 8
            if not p["clear"]:
                assert page is not None and page["Box"] == box and page["Background"] == bg
                component_colors = page.get("ComponentColors",[page["Foreground"]]*len(page["Components"]))+component_colors
                components = page["Components"]+components
            text = "".join(zh[key] for key in components)
            # 由正式全文、框與禁則獨立驗每個分界，不呼叫 runtime 的斷行實作。
            lines = e["detail"]["page"]["Lines"]
            cells = (box[2]-box[0])//glyphs["size"]
            assert lines and all(lines) and "".join(lines) == text
            assert len(lines)*glyphs["height"] <= box[3]-box[1]
            assert all(len(line) <= cells for line in lines)
            offset = 0
            for line in lines[:-1]:
                offset += len(line)
                legal = lambda end: text[end] not in "，。！？、；：」』）》】" and text[end-1] not in "「『（《【"
                assert legal(offset)
                assert not any(legal(end) for end in range(offset+1,min(offset-len(line)+cells,len(text)-1)+1))
            expected_page = {"step":p["step"],"Key":binding["Key"],"Source":p["source"]["text"],"Text":text,"Box":box,
                             "Foreground":p["foreground"],"Background":bg,"Lines":lines,"Clear":p["clear"],"Components":components}
            if len(set(component_colors)) > 1:
                expected_page["ComponentColors"] = component_colors
            assert e["detail"]["page"] == expected_page
            page = expected_page
            page_history.append(page)
            x,y,right,bottom = p["native_box"]
            erase((x,y,right-x,bottom-y))
        elif kind == "unknown-paragraph-original":
            p = paragraph_by_step[e["Step"]]
            assert e["detail"]["caller"] == p["caller"]
            bindings_here = paragraph_bindings(p)
            if bindings_here:
                assert not p["clear"] and page is None
                assert e["detail"]["reason"] == "missing compatible predecessor"
            else:
                assert e["detail"]["reason"] == "source or context mismatch"
            page = None
        elif kind == "paragraph-invalidated":
            assert page is not None
            rect = e["detail"]["native_rect"]
            x,y,width,height = rect
            left,top,right,bottom = [v//2 for v in page["Box"]]
            assert x<right and x+width>left and y<bottom and y+height>top
            assert not any(p["step"]<=e["Step"]<=p["return_step"] for p in native_paragraphs)
            if e["detail"]["reason"] == "native fill":
                assert any(f["step"]<=e["Step"]<=f["return_instruction_step"] and f["native_rect"]==rect for f in trace["fill_events"])
            else:
                assert e["detail"]["reason"] == "field overwrite"
                assert any(step==e["Step"] and [event["detail"]["word"][k] for k in ("X","Y","Width")]+[8]==rect for (step,key),event in field_by_id.items())
            page = None
        elif kind == "clear-write-restarted":
            assert pending_clear_index is not None
            previous=clear_baselines[pending_clear_index][1]
            added=sorted((w for w in words.values() if w["Group"]!="footer"),key=lambda w:(w["Y"],w["X"]))
            assert e["detail"]["previous_targets"]==previous and (e["detail"]["added_targets"] or [])==added
            merged={}
            for word in previous+added:merged.setdefault((word["X"],word["Y"],word["Width"]),word)
            targets=sorted(merged.values(),key=lambda w:(w["Y"],w["X"],w["Width"]))
            assert e["detail"]["targets"]==targets
            assert any(f["step"]<=e["Step"]<=f["return_instruction_step"] and f["native_rect"]==e["detail"]["native_rect"] and not f["within_list"] for f in trace["fill_events"])
            clear_baselines[pending_clear_index]=(e["Step"],targets)
            words={pos:w for pos,w in words.items() if w["Group"]=="footer"}
        elif kind == "pane-cleared":
            assert pending_clear_index is not None
            assert e["detail"]["targets"]==clear_baselines[pending_clear_index][1]
            pending_clear_index=None
        elif kind in ("pane-invalidate", "clear-write-baseline"):
            targets = sorted((w for w in words.values() if w["Group"] != "footer"), key=lambda w:(w["Y"],w["X"]))
            if kind == "clear-write-baseline":
                assert pending_clear_index is None,("dropped pending clear",e["Step"])
                assert targets and e["detail"]["targets"] == targets
                assert any(f["step"] <= e["Step"] <= f["return_instruction_step"] and not f["within_list"]
                           and f["native_rect"][0] <= 8 and f["native_rect"][1] <= 8
                           and f["native_rect"][0]+f["native_rect"][2] >= 312 and f["native_rect"][1]+f["native_rect"][3] >= 184 for f in trace["fill_events"])
                clear_baselines.append((e["Step"], targets))
                pending_clear_index=len(clear_baselines)-1
            else:
                assert not targets, ("missing clear baseline", e["Step"])
            words = {pos: w for pos, w in words.items() if w["Group"] == "footer"}
            pending_suffix = None
        elif kind == "service-notice-entry":
            assert notice is None
            p = paragraph_by_step[e["Step"]]
            binding = paragraph_bindings(p)[0]
            assert binding in trade_bindings and p["caller"] == {"Seg":0x291A,"Off":0xFD0}
            assert e["detail"] == {"key":binding["Key"],"caller":p["caller"]}
            notice = {"entry":p["step"],"phase":"painted"}
        elif kind == "service-notice-ready":
            assert notice is not None and notice["phase"] == "painted"
            p = paragraph_by_step[notice["entry"]]
            assert e["Step"] == p["return_step"]
            button = next(c for c in reversed(trace["calls"]) if c["step"] < e["Step"] and c["caller"] == {"Seg":0xCEB,"Off":0x1BE})
            signature = menu_signature(button)
            assert config["Menus"][signature] == "confirm"
            assert e["detail"] == {"entry_step":notice["entry"],"caller":p["caller"],"ss":p["regs"]["SS"],
                                    "sp":(p["regs"]["SP"]+4)&65535,"menu_signature":signature}
            notice.update(phase="ready",ready=e["Step"])
        elif kind == "service-notice-restore-begin":
            assert notice is not None and notice["phase"] == "ready"
            rect = e["detail"]["native_rect"]
            assert e["detail"]["entry_step"] == notice["entry"]
            assert any(f["step"] <= e["Step"] <= f["return_instruction_step"] and f["native_rect"] == rect for f in trace["fill_events"])
            p = paragraph_by_step[notice["entry"]];left,top,right,bottom = p["native_box"];x,y,width,height = rect
            assert x<right and x+width>left and y<bottom and y+height>top
            notice.update(phase="restoring",restoring=e["Step"])
        elif kind == "service-notice-closed":
            assert notice is not None and notice["phase"] == "restoring"
            refresh = refresh_sources[e["Step"]]
            signature = refresh["menu_snapshot"]["Signature"]
            assert refresh["valid"] and refresh["caller"] == {"Seg":0xCEB,"Off":0xE18} and config["Menus"][signature] == "inventory"
            assert e["detail"] == {"entry_step":notice["entry"],"caller":refresh["caller"],"menu_signature":signature}
            erase((8,189,304,8))
            notice_intervals.append({**notice,"closed":e["Step"]});notice = None
        elif kind == "clock-source-reset":
            words = {pos: w for pos, w in words.items() if w["Key"] not in clock_keys}
        elif kind == "unknown-feedback-original":
            w = feedback_candidates[e["Step"]]
            assert feedback_pane(e["Step"]) not in ("shop-stock","inventory") and e["Pane"] == feedback_pane(e["Step"])
            assert e["detail"] == {"caller":w["caller"],"source_sha256":sha(w["vararg_1_candidate"]["text"].encode()),"native_rect":[8,189,304,8],"reason":"unrecognized return context"}
            erase((8,189,304,8))
        elif kind == "footer-feedback-capture":
            assert feedback is None and feedback_proof is not None
            w = wrappers_by_step[e["Step"]]
            assert w["caller"] == {"Seg": 0x088E, "Off": 0x1560} and w["format"]["text"] == "%s"
            source = w["vararg_1_candidate"]["text"]
            return_pane = e["detail"].get("return_pane","shop-stock")
            assert return_pane == e["Pane"] and return_pane in ("shop-stock","inventory")
            rect = [8, 189, 304 if return_pane == "inventory" else len(source)*8, 8]
            checkpoint = next(c for c in feedback_boundaries["checkpoints"] if c["step"] == e["Step"])
            raw = (boundary_path.parent / checkpoint["indexed_file"]).read_bytes()
            assert sha(raw) == checkpoint["indexed_sha256"]
            before = b"".join(raw[y*320+rect[0]:y*320+rect[0]+rect[2]] for y in range(rect[1], rect[1]+rect[3]))
            saved = sorted((w for w in words.values() if intersects(w, rect)), key=lambda w:(w["Y"],w["X"]))
            expected = {"caller":w["caller"], "source_sha256":sha(source.encode()), "native_rect":rect,
                        "before_sha256":sha(before), "saved_words":saved or None}
            if "return_pane" in e["detail"]: expected["return_pane"] = return_pane
            assert e["detail"] == expected
            feedback = {"entry":e["Step"], "rect":rect, "source_sha":sha(source.encode()), "before_sha":sha(before), "return_pane":return_pane, "phase":"captured"}
        elif kind == "footer-feedback-entry":
            assert feedback is not None and feedback["phase"] == "captured"
            c = calls_by_step[e["Step"]]
            assert trace["wrappers"][c["wrapper_index"]]["step"] == feedback["entry"]
            assert e["detail"] == {"entry_step":feedback["entry"], "native_rect":feedback["rect"], "source_sha256":feedback["source_sha"]}
            erase(feedback["rect"])
            feedback["phase"] = "painted"
        elif kind == "footer-feedback-ready":
            assert feedback is not None and feedback["phase"] == "painted"
            w = next(w for w in feedback_proof["wrappers"] if w["step"] == feedback["entry"])
            assert e["Step"] == w["return_step"]
            assert e["detail"] == {"entry_step":feedback["entry"], "caller":w["caller"], "ss":w["return_ss"], "sp":w["return_sp"]}
            feedback.update(phase="ready", ready=e["Step"])
        elif kind == "footer-feedback-restore-begin":
            assert feedback is not None and feedback["phase"] == "ready"
            assert e["detail"]["entry_step"] == feedback["entry"] and e["detail"]["native_rect"] == feedback["rect"]
            assert e["detail"]["map_mask"] in range(1,16)
            feedback.update(phase="restoring", restoring=e["Step"])
        elif kind == "footer-feedback-closed":
            assert feedback is not None and feedback["phase"] == "restoring"
            refresh = refresh_sources[e["Step"]]
            assert refresh["valid"] and refresh["caller"] == {"Seg":0x0CEB,"Off":0x0E18}
            signature = refresh["menu_snapshot"]["Signature"]
            assert config["Menus"][signature] == feedback["return_pane"]
            assert e["detail"]["entry_step"] == feedback["entry"] and e["detail"]["native_rect"] == feedback["rect"]
            assert e["detail"]["caller"] == refresh["caller"] and e["detail"]["menu_signature"] == signature
            assert e["detail"]["native_sha256"] == feedback["before_sha"]
            erase(feedback["rect"])
            feedback_intervals.append({**feedback,"closed":e["Step"]})
            feedback = None
        elif kind == "load-caption-ready":
            loading_wrappers=[w for w in trace["wrappers"] if w["return_step"]==e["Step"] and w["caller"]=={"Seg":0x2287,"Off":0x316A}]
            assert len(loading_wrappers)==1
            w=loading_wrappers[0]
            assert w["format"]["text"]=="Loading...Please Wait"
            assert e["detail"]=={"caller":w["caller"],"ss":w["return_ss"],"sp":w["return_sp"],"source_sha256":sha(w["format"]["text"].encode())}
        elif kind == "footer-render-entry":
            preserved = False
            retire_return_prompt=False
            def return_prompt(w):
                return retire_return_prompt and w["Foreground"]==0 and w["Background"]==7 and en[w["Key"]] in ("Press","to continue.")
            if e.get("detail") is not None:
                native_refresh = refresh_sources[e["Step"]]
                signature = native_refresh["menu_snapshot"]["Signature"] if native_refresh["valid"] else ""
                menu=native_refresh["menu_snapshot"]
                retire_return_prompt=native_refresh["valid"] and not (menu["Count"]==1 and len(menu["Buttons"])==1 and menu["Buttons"][0]["SourceHex"]==b"Return".hex())
                expected = {(f["RawX"]+f["Start"]*8, f["RawY"], f.get("Width", f["Length"]*8), f["Key"])
                            for f in config["Fields"] if f["Pane"] == "menu" and f["MenuSignature"] == signature}
                before = {(w["X"], w["Y"], w["Width"], w["Key"]) for w in words.values() if w["Group"] == "footer" and (not typed_buttons or w.get("Button"))}
                preserved = bool(expected) and signature in config["Menus"] and before == expected
                assert e["detail"] == {"menu_signature": signature, "preserved": preserved}
            if not preserved:
                words = {pos: w for pos, w in words.items() if w["Group"] != "footer" or (typed_buttons and not w.get("Button") and not return_prompt(w))}
        elif kind == "native-fill":
            assert any(f["step"] <= e["Step"] <= f["return_instruction_step"]
                       and f["native_rect"] == e["detail"] for f in trace["fill_events"])
            if battle:
                targets=[dict(w) for w in words.values() if w["Group"]=="body" and intersects(w,e["detail"])]
                if targets:battle_erased_fields.append({"step":e["Step"],"rect":e["detail"],"targets":targets})
            erase(e["detail"])
        elif kind == "creation-pane-redraw":
            assert (creation or creation_tracking) and e["detail"]==[8,8,304,104]
            assert any(f["step"]<=e["Step"]<=f["return_instruction_step"] and f["native_rect"]==e["detail"] for f in trace["fill_events"])
        elif kind == "creation-name-leave":
            assert creation or creation_tracking
            assert any(f["step"]<=e["Step"]<=f["return_instruction_step"] and f["native_rect"]==e["detail"] for f in trace["fill_events"])
            prompt=next(w for w in words.values() if w["X"]==8 and w["Y"]==189 and en[w["Key"]]=="Character name:")
            assert prompt["Group"]=="footer"
        elif kind == "creation-footer-entry":
            assert creation or creation_tracking
            c=calls_by_step[e["Step"]]
            assert e["detail"]["call_step"]==c["step"]
            assert any(f["Key"]==e["detail"]["key"] and f["Caller"]==c["caller"] and (f["RawY"],f["RawX"])==tuple(c["stack"][2:4]) for f in config["Fields"])
        elif kind == "creation-footer-page":
            assert creation or creation_tracking
            c=next(c for c in trace["calls"] if c.get("first_glyph",e["Step"]+1)<=e["Step"]<c["return_step"])
            if c.get("video_first"):
                assert c["video_first"]["Step"]==e["Step"]
                assert e["detail"]=={"target_page":int(next(iter(c["video_pages"]))),"first_write_offset":c["video_first"]["Offset"]}
            else:
                assert e["detail"]["target_page"]==e["detail"]["first_write_offset"]&0x4000
                assert 0<=e["detail"]["first_write_offset"]<0x8000
        elif kind == "creation-footer-visible":
            assert creation or creation_tracking
            if trace.get("display_changes"):
                layout=next(v["layout"] for v in reversed(trace["display_changes"]) if v["step"]<=e["Step"])
                assert e["detail"]=={"target_page":layout["DisplayStart"]}
            else:assert e["detail"]["target_page"] in (0,0x4000)
        elif kind in ("row-before-glyph", "unknown-row-original"):
            w = wrappers_by_step[e["Step"]]
            source = w["vararg_1_candidate"]["text"]
            x, y = (w["stack"][2] & 255)*8, (w["stack"][3] & 255)*8
            erase((x, y, len(source)*8, 8))
            if kind == "row-before-glyph":
                for span in bindings[(e["Pane"], sha(source.encode()))]["Spans"]:
                    word = {"X": x + span["Start"]*8, "Y": y, "Width": span["Length"]*8,
                            "Key": span["Key"], "Group": "body", "Foreground": w["stack"][4]&255,
                            "Background": config["Background"]}
                    words[(word["X"], word["Y"])] = word
                    row_positions.add((word["X"], word["Y"]))
        elif kind=="ammo-row-render-return":
            w=wrappers_by_step[e["detail"]["entry_step"]]
            assert ammo_row_model(w["vararg_1_candidate"]["text"],en) is not None
            assert e["Step"]==w["return_step"]
            assert e["detail"]==dict(entry_step=w["step"],source_sha256=sha(w["vararg_1_candidate"]["text"].encode()),caller=w["caller"],ss=w["return_ss"],sp=w["return_sp"])
        elif kind == "field-before-glyph":
            w = field_by_id[e["Step"], e["detail"]["key"]]["detail"]["word"]
            if e["detail"]["deferred"]:
                pending_suffix = w
            else:
                erase((w["X"], w["Y"], w["Width"], 8))
                words[(w["X"], w["Y"])] = w
        elif kind == "title-suffix-attached":
            assert pending_suffix and pending_suffix["Key"] == e["detail"]["key"]
            words[(pending_suffix["X"], pending_suffix["Y"])] = pending_suffix
            pending_suffix = None
        elif kind == "native-scroll":
            original = next(s for s in trace["scroll_events"] if s["step"] == e["Step"])
            s = [(v - 8000)*2 for v in original["stack"][2:8]]
            x, y, width, height = s[1], s[0], s[3]-s[1], s[2]-s[0]
            dx, dy = -s[5], -s[4]
            assert e["detail"] == {"delta": [dx, dy], "rect": [x, y, width, height]}
            # 原始參數給裁切區；實際來源是裁切區與反向平移區的交集。
            sx, sy = max(x, x-dx), max(y, y-dy)
            sw, sh = min(x+width, x+width-dx)-sx, min(y+height, y+height-dy)-sy
            source, destination = (sx,sy,sw,sh), (sx+dx,sy+dy,sw,sh)
            before = (observed / original["indexed_before"]).read_bytes()
            after = (observed / original["indexed_after"]).read_bytes()
            source_pixels = b"".join(before[(sy+row)*320+sx:(sy+row)*320+sx+sw] for row in range(sh))
            destination_pixels = b"".join(after[(sy+dy+row)*320+sx+dx:(sy+dy+row)*320+sx+dx+sw] for row in range(sh))
            if e["Pane"] in ("shop-stock", "temple-spells"):
                service_scroll_checks.append({"step":e["Step"],"source_sha256":sha(source_pixels),"destination_sha256":sha(destination_pixels),
                                              "changed_pixels":sum(a!=b for a,b in zip(source_pixels,destination_pixels))})
            else:
                assert source_pixels == destination_pixels
            moved, moved_rows = [], set()
            for w in words.values():
                if intersects(w, source):
                    assert sx <= w["X"] and w["X"]+w["Width"] <= sx+sw and sy <= w["Y"] and w["Y"]+w.get("Height",8) <= sy+sh
                    moved.append({**w, "X": w["X"]+dx, "Y": w["Y"]+dy})
                    if (w["X"], w["Y"]) in row_positions:
                        moved_rows.add((w["X"]+dx, w["Y"]+dy))
            erase((x,y,width,height))
            for w in moved:
                words[(w["X"], w["Y"])] = w
            row_positions.update(moved_rows)
        row_positions.intersection_update(words)
        expected_words = sorted(words.values(), key=lambda w: (w["Y"], w["X"]))
        assert (e["Words"] or []) == expected_words, (kind, e["Step"])
        model.append((e["Step"], expected_words, sorted(row_positions), page))
    assert feedback is None and notice is None and battle_warning is None and battle_status is None and pending_clear_index is None
    for actual in (a,b):
        assert (actual.get("paragraphs") or []) == page_history
        assert actual.get("final_paragraph") == (model[-1][3] if model else None)
    def footer_hidden_at(step):
        hidden=[e for e in hud_returns if e["Step"]<step and e["detail"]["footer_hidden"]]
        if rounds and hidden and any(hidden[-1]['Step']<e['Step']<step and e['detail']['word']['Group']=='footer' for e in fields):
            return False
        return bool(hidden) and not any(c["caller"]=={"Seg":0xCEB,"Off":0x1BE}
            and hidden[-1]["Step"]<c["step"]<step for c in trace["calls"])
    # 原版可能已隱去底列而仍保留舊表指標，終點與中途截點使用同一生命週期。
    final_button = next((c for c in reversed(trace["calls"]) if c["caller"] == {"Seg": 0xCEB, "Off": 0x1BE}),None)
    if final_button:
        final_signature = menu_signature(final_button)
        final_keys = {f["Key"] for f in config["Fields"] if f["Pane"] == "menu" and f["MenuSignature"] == final_signature}
    else:
        assert (rounds or journal_path or scoped_path) and not trace['menus'] and typed_buttons
        final_signature=""
        final_keys=set()
    if footer_hidden_at(trace["checkpoints"][-1]["step"]):
        final_keys=set()
    for actual in (a, b):
        assert (actual["final_words"] or []) == model[-1][1]
        assert {w["Key"] for w in actual["final_words"] or [] if w["Group"] == "footer" and (not typed_buttons or w.get("Button"))} == final_keys
        # 每個動作終點都應保留完整已知按鈕；同區提示另外由生命週期模型驗證。
        layouts = {frame["step"]: frame for frame in actual["list_frames"]}
        menu_field_keys = {f["Key"] for f in config["Fields"] if f["Pane"] == "menu"}
        for checkpoint in actual["checkpoints"]:
            if magic_path:
                count=layouts[checkpoint['step']]['list_event_count']
                active=any(v['entry_index']<count<=v['closed_index'] for v in battle_status_intervals)
                before_buttons=any(checkpoint['step']==w['restored_by'] for w in status_witnesses.values())
                if active or before_buttons:
                    assert not any(w.get('Button') for w in layouts[checkpoint['step']]['words'] or []),'buttons visible during original status'
                    continue
            if movement:
                captions=[r for r in movement_path["counters"] if r["returned"]<checkpoint["step"]]
                retired=False
                if movement_path["source_path"]==movement["data"]["quick_source"]:
                    idx=(observed/(checkpoint["label"]+".idx")).read_bytes()
                    x,y,w,h=movement["data"]["quick_witness"]["native_rect"]
                    retired=b"".join(idx[row*320+x:row*320+x+w] for row in range(y,y+h))!=movement_reference
                if captions and not retired and not any(c["caller"]=={"Seg":0xCEB,"Off":0x1BE}
                    and captions[-1]["step"]<c["step"]<checkpoint["step"] for c in trace["calls"]):
                    key=movement["data"]["fields"][0]["binding"]["Key"]
                    assert {w["Key"] for w in layouts[checkpoint["step"]]["words"] or [] if w["Group"]=="footer"}=={key}
                    continue
            if finish and next(f for f in b["frames"] if f["step"]==checkpoint["step"])["held"]:
                # 原版右框已清除，尚待已證實的狀態回報完成；內部詞框此時不是可見畫面。
                step=checkpoint["step"]
                returned=[r["return_step"] for r in hud_records if r["binding"].get("HideFooter") and r["return_step"]<step]
                previous=max(returned,default=trace["request"]["start_steps"])
                following=next(r["return_step"] for r in hud_records if r["binding"].get("HideFooter") and r["return_step"]>step)
                assert any(previous<f["step"]<step<following and f["native_rect"]==[184,8,128,168] for f in trace["fill_events"])
                continue
            if footer_hidden_at(checkpoint["step"]):
                footers=[w for w in layouts[checkpoint['step']]['words'] or [] if w['Group']=='footer']
                if fire_path:
                    assert all(any(w['Key']==c['key'] and (w['X'],w['Y'],w['Width'])==tuple(c['rect'][:3]) for c in fire_captions.values()) or
                        any(f.get('SourcePattern')=='movement-left' and w['Key']==f['Key'] and (w['X'],w['Y'],w['Width'])==(8,189,f['Length']*8) for f in config['Fields']) for w in footers)
                elif rounds:
                    assert all(w['Key']=='round.1a0e55074a01fc9262bb' and (w['X'],w['Y'],w['Width'])==(8,178,152) for w in footers)
                else:assert not footers
                continue
            buttons = [c for c in trace["calls"] if c["step"] < checkpoint["step"] and c["caller"] == {"Seg": 0xCEB, "Off": 0x1BE}]
            if not buttons:
                if rounds or journal_path or scoped_path:
                    assert typed_buttons and not any(w.get('Button') for w in layouts[checkpoint['step']]['words'] or [])
                    continue
                if battle_source:
                    previous_buttons=[c for c in battle_source["calls"] if c["step"]<checkpoint["step"] and c["caller"]=={"Seg":0xCEB,"Off":0x1BE}]
                    assert previous_buttons and previous_buttons[-1]["return_step"]<trace["request"]["start_steps"]
                    signature=battle_source["menus"][previous_buttons[-1]["menu_index"]]["Signature"]
                    assert signature not in config["Menus"],"known initial menu missing translation"
                    assert not any(w["Group"]=="footer" for w in layouts[checkpoint["step"]]["words"] or [])
                    continue
                # 第六個字母的終點在 359M；同一步的 Return 尚未送入。
                assert actual.get("cold_boot") and checkpoint["step"] <= 359000000
                assert not layouts[checkpoint["step"]]["words"]
                continue
            button = buttons[-1]
            signature = menu_signature(button)
            if signature not in config["Menus"]:
                continue
            expected_keys = {f["Key"] for f in config["Fields"] if f["Pane"] == "menu" and f["MenuSignature"] == signature}
            # 命名使用原版輸入框，先完整清掉上一個擲值選單；表指標暫未換掉。
            prompts = [c for c in trace["calls"] if button["step"] < c["step"] < checkpoint["step"]
                       and c["caller"] == {"Seg":0x266D,"Off":0x11F}
                       and c["format"]["text"] == "%s" and c["vararg_1_candidate"]["text"] == "Character name:"]
            if creation and prompts:
                prompt = prompts[-1]
                assert any(button["return_step"] < fill["step"] < prompt["step"]
                           and fill["native_rect"] == [8,189,304,8] for fill in trace["fill_events"])
                expected_keys = set()
            # 原版回報暫時撤掉底列，但尚未替換按鈕表指標。
            if any(interval["ready"]<=checkpoint["step"]<interval["closed"] for interval in feedback_intervals):
                expected_keys=set()
            actual_keys = {w["Key"] for w in layouts[checkpoint["step"]]["words"] or [] if w["Group"] == "footer" and (w.get("Button") if typed_buttons else w["Key"] in menu_field_keys)}
            assert actual_keys == expected_keys, ("checkpoint footer incomplete", checkpoint["label"], expected_keys-actual_keys, actual_keys-expected_keys)
        # 原版仍保留的提示必須留在穩定畫面，不能因模型也把它清掉而通過。
        for checkpoint in actual["checkpoints"]:
            for f in config["Fields"]:
                if "UpperNative" not in f or f["UpperCaller"] == {"Seg":0x088E,"Off":0x1560}:
                    continue
                candidates=[event for (step,key),event in field_by_id.items() if step<checkpoint["step"] and key==f["Key"]]
                if not candidates:
                    continue
                event=candidates[-1]; word=event["detail"]["word"]
                x,y,width,height=word["X"],word["Y"],word["Width"],8
                start=calls_by_step[event["Step"]]["return_step"]
                changed=any(start<fill["step"]<checkpoint["step"] and intersects(word,fill["native_rect"]) for fill in trace["fill_events"])
                if magic_path:
                    changed=changed or any(w['field_entry']==event['Step'] and checkpoint['step']>=w['restored_by'] for w in status_witnesses.values())
                for call in trace["calls"]:
                    if not start<call["step"]<checkpoint["step"]:
                        continue
                    text=call["vararg_1_candidate"]["text"] if call["format"]["text"]=="%s" else call["format"]["text"]
                    changed=changed or intersects(word,(native(call["stack"][3]),native(call["stack"][2]),max(1,len(text))*8,8))
                if (movement and f.get("SourcePattern")=="movement-left"
                    and movement_path["source_path"]==movement["data"]["quick_source"]):
                    # 原版翻頁／整區複製也會撤除提示；以獨立原版色號檢查，
                    # 不拿覆層自己的退休事件代替原版清除證據。
                    idx=(observed/(checkpoint["label"]+".idx")).read_bytes()
                    x,y,w,h=movement["data"]["quick_witness"]["native_rect"]
                    changed=changed or b"".join(idx[row*320+x:row*320+x+w] for row in range(y,y+h))!=movement_reference
                if rounds and f['Key']=='round.1a0e55074a01fc9262bb':
                    ready=next(v for v in b['list_events'] if v['Kind']=='spell-caption-ready' and v['detail']['entry_step']==event['Step'])
                    idx=(observed/(checkpoint['label']+'.idx')).read_bytes()
                    changed=changed or sha(b''.join(idx[row*320+8:row*320+160] for row in range(178,186)))!=ready['detail']['reference_sha256']
                if fire_path and event['Step'] in fire_captions:
                    witness=fire_captions[event['Step']]
                    idx=(observed/(checkpoint['label']+'.idx')).read_bytes()
                    x,y,width,height=witness['rect']
                    changed=changed or sha(b''.join(idx[row*320+x:row*320+x+width] for row in range(y,y+height)))!=witness['reference_sha256']
                if fire_path and event['Step'] in fire_movement_witnesses:
                    witness=fire_movement_witnesses[event['Step']]
                    idx=(observed/checkpoint['label']).with_suffix('.idx').read_bytes()
                    x,y,width,height=witness['native_rect']
                    changed=changed or sha(b''.join(idx[row*320+x:row*320+x+width] for row in range(y,y+height)))!=witness['reference_sha256']
                if not changed:
                    assert word in (layouts[checkpoint["step"]]["words"] or []), ("missing retained prompt",checkpoint["label"],f["Key"])
    cleared = [e for e in b["list_events"] if e["Kind"] == "pane-cleared"]
    assert len(cleared) == len(clear_baselines)
    battle_field_cycles=[dict(item,reprinted=[f["Step"] for f in fields if f["Step"]>item["step"] and any(
        all(f["detail"]["word"][k]==w[k] for k in ("X","Y","Width","Key","Group")) for w in item["targets"])]) for item in battle_erased_fields]
    battle_field_cycles=[item for item in battle_field_cycles if item["reprinted"]]
    movement_reprints=False
    if movement:
        key=movement["data"]["fields"][0]["binding"]["Key"]
        captions=[e for e in fields if e["detail"]["key"]==key]
        assert [e["Step"] for e in captions]==[r["step"] for r in movement_path["counters"]]
        movement_reprints=len(captions)>1 and len({r["value"] for r in movement_path["counters"]})>1
    assert cleared or any(p["Clear"] for p in page_history) or feedback_intervals or battle_field_cycles or movement_reprints or hud_source_clears, "沒有列表清除、段落替換、回報復原或已驗證欄位重印"
    for event, (start, targets) in zip(cleared, clear_baselines):
        assert start < event["Step"] and event["detail"]["targets"] == targets
    assert all(e["detail"]["pixels"] == len({y*320+x for w in e["detail"]["targets"] for y in range(w["Y"],w["Y"]+w.get("Height",8)) for x in range(w["X"],w["X"]+w["Width"])}) for e in cleared)
    assert all(e["detail"]["target_page"] == e["detail"]["visible_page"] for e in cleared)
    originals = {}
    native_layouts = {s["step"]: s for s in a["list_frames"]}
    for frame in a["frames"]:
        assert not frame["held"]
        originals[frame["step"]] = frame
    verified_pngs, cache = set(), {}

    def pixels(folder, frame):
        name = frame["File"]
        assert Path(name).name == name
        with Image.open(folder / name) as im:
            assert im.size == (640, 400)
            data = im.convert("RGBA").tobytes()
        assert sha(data) == frame["SHA256"]
        verified_pngs.add((str(folder), name))
        return data

    def compose(source, words, palette, page, reader_page, cold_words=()):
        px = bytearray(source)
        rectangles = []
        if page is not None:
            x,y,right,bottom = page["Box"]
            if page["Key"].startswith("service-message."):
                assert [x,y,right,bottom] == [16,336,624,368] and page["Background"] == 23 and page["Foreground"] == 11
            else:
                assert [x,y,right,bottom] == [16,272,624,368]
            width,height = right-x,bottom-y
            rectangles.append((x,y,width,height))
            fg,bg = palette[page["Foreground"]],palette[page["Background"]]
            row = bytes([*bg,255])*width
            for yy in range(y,bottom):
                at=(yy*640+x)*4;px[at:at+width*4]=row
            assert len(page["Lines"])*glyphs["height"] <= height
            colors = [color for key,color in zip(page["Components"],page.get("ComponentColors",[page["Foreground"]]*len(page["Components"]))) for ch in zh[key]]
            assert len(colors) == len(page["Text"])
            glyph_index = 0
            for line,text in enumerate(page["Lines"]):
                assert len(text)*glyphs["size"] <= width
                for col,ch in enumerate(text):
                    fg = palette[colors[glyph_index]]
                    glyph_index += 1
                    for off,value in enumerate(alpha[ch]):
                        if value:
                            yy,xx=divmod(off,glyphs["size"])
                            at=((y+line*glyphs["height"]+yy)*640+x+col*glyphs["size"]+xx)*4
                            for channel in range(3):px[at+channel]=(fg[channel]*value+px[at+channel]*(255-value)+127)//255
        for w in words or []:
            x, y = w["X"] * 2, w["Y"] * 2
            width = w["Width"] * 2
            height = w.get("Height",8)*2
            assert (w["Width"] == len(en[w["Key"]])*8 or (w["Key"], w["Width"]) in verified_field_widths)
            assert w["Background"] == config["Background"] or (w["Key"],w["Background"]) in verified_field_backgrounds
            assert 0 <= x < x + width <= 640 and 0 <= y < y + height <= 400
            size=w.get("FontSize",16)
            assert size in (16,20) and (size==16 or role_alpha is not None)
            text=zh[w["Key"]]
            if "Number" in w:
                assert text.count("%d")==1 and text.count("%")==1
                text=text.replace("%d",str(w["Number"]))
            assert len(text) * size <= width
            assert all(x + width <= xx or xx + ww <= x or y + height <= yy or yy + hh <= y for xx, yy, ww, hh in rectangles)
            rectangles.append((x, y, width, height))
            fg, bg = palette[w["Foreground"]], palette[w["Background"]]
            if startup and w["Background"]==23 and (w["Key"]=="field.6b0143d03864993fdf69" or (w["Key"]=="field.dcd1d5223f73b3a965c0" and w["X"]==8 and w["Y"]==16)):
                original_colors={tuple(source[(yy*640+xx)*4:(yy*640+xx)*4+3]) for yy in range(y,y+16) for xx in range(x,x+width)}
                allowed={tuple(bg),tuple(fg),tuple(palette[0]),tuple(palette[15])}
                assert tuple(bg) in original_colors and original_colors<=allowed,("native field background",frame["step"],w,original_colors-allowed)
            row = bytes([*bg, 255]) * width
            for yy in range(y, y + height):
                at = (yy * 640 + x) * 4
                px[at:at + width * 4] = row
            text_y=y-2 if size==20 else y
            assert 0<=text_y and text_y+(24 if size==20 else 16)<=400
            selected_alpha=role_alpha if size==20 else alpha
            for col, ch in enumerate(text):
                for off, value in enumerate(selected_alpha[ch] if size==20 else selected_alpha[ch][:256]):
                    if value:
                        yy, xx = divmod(off, size)
                        at = ((text_y + yy) * 640 + x + col * size + xx) * 4
                        for channel in range(3):
                            px[at + channel] = (fg[channel] * value + px[at + channel] * (255 - value) + 127) // 255
        paint_reader(px,reader_page,palette,alpha,reader_images)
        if cold_ui is not None:
            cold_paint(px,cold_words,palette,cold_ui)
        return sha(px)

    cold_ui=None;cold_index=0;cold_words=[];cold_pending=False;cold_count=0;cold_retained=0
    if startup and a.get("cold_ui"):
        from load_prompt_check import model as cold_model,paint as cold_paint,pending_at as cold_pending_at
        cold_ui=cold_model(inputs.parent.parent,a,b)
    previous, held, translated_frames, model_index = None, 0, 0, -1
    last_row_frame, copied_row_page, copied_row_pages = None, None, []
    service_row_keys = {span["Key"] for row in config["Rows"] if row["Pane"] in ("shop-stock","temple-spells") for span in row["Spans"]}
    inventory_row_keys = {span["Key"] for row in config["Rows"] if row["Pane"] == "inventory" for span in row["Spans"]}
    assert len(b["frames"]) == len(b["list_frames"])
    for frame, state in zip(b["frames"], b["list_frames"]):
        assert frame["step"] == state["step"] and frame["step"] in originals
        for interval in battle_status_intervals:
            count=state['list_event_count']
            witness=status_witnesses[interval['entry']]
            if interval['entry_index']<count<=interval['ready_index'] or (interval['restoring_index'] is not None and interval['restoring_index']<count<=interval['closed_index']):
                assert frame['held'],('battle status transition exposed',frame['step'])
            if interval['ready_index']<count<=interval['closed_index'] and not frame['held']:
                assert any(w['Key']==witness['key'] for w in state['words'] or [])
            if frame['step']==interval['closed']:
                x,y,w,h=witness['rect']
                image=Image.frombytes('P',(w,h),status_pixels[interval['entry']]['before'])
                image.putpalette([component for color in state['palette'] for component in color])
                expected=image.convert('RGBA').resize((w*2,h*2),Image.Resampling.NEAREST).tobytes()
                raw=pixels(en_run,originals[frame['step']])
                actual=b''.join(raw[(row*640+x*2)*4:(row*640+(x+w)*2)*4] for row in range(y*2,(y+h)*2))
                assert actual==expected,'battle status original restoration pixels'
        for interval in battle_warning_intervals:
            count=state['list_event_count']
            if interval['entry_index']<count<=interval['ready_index'] or (interval['restoring_index'] is not None and interval['restoring_index']<count<=interval['closed_index']):
                assert frame['held'],('battle warning transition exposed',frame['step'])
            if interval['ready_index']<count<=interval['closed_index'] and not frame['held']:
                assert any(w['Key']=='round.50e28de96686ceec7dc0' for w in state['words'] or [])
            if frame['step']==interval['closed']:
                x,y,w,h=warning_witness['rect'];image=Image.frombytes('P',(w,h),warning_pixels['before'])
                image.putpalette([component for color in state['palette'] for component in color])
                expected=image.convert('RGBA').resize((w*2,h*2),Image.Resampling.NEAREST).tobytes()
                raw=pixels(en_run,originals[frame['step']]);actual=b''.join(raw[(row*640+x*2)*4:(row*640+(x+w)*2)*4] for row in range(y*2,(y+h)*2))
                assert actual==expected,'battle warning original restoration pixels'
        if movement and movement_path["source_path"]==movement["data"]["quick_source"] and frame["step"]>=movement["data"]["quick_witness"]["step"] and not frame["held"]:
            x,y,w,h=movement["data"]["quick_witness"]["native_rect"]
            image=Image.frombytes("P",(w,h),movement_reference)
            image.putpalette([component for color in state["palette"] for component in color])
            expected=image.convert("RGBA").resize((w*2,h*2),Image.Resampling.NEAREST).tobytes()
            raw=pixels(en_run,originals[frame["step"]])
            actual=b"".join(raw[(row*640+x*2)*4:(row*640+(x+w)*2)*4] for row in range(y*2,(y+h)*2))
            key=movement["data"]["fields"][0]["binding"]["Key"]
            assert any(word["Key"]==key for word in state["words"] or [])==(actual==expected),("movement caption lifetime",frame["step"])
        if cold_ui is not None:
            count=frame.get("cold_ui_events",0)
            assert cold_index<=count<=len(cold_ui["timeline"])
            assert count==0 or cold_ui["timeline"][count-1][0]<=frame["step"]
            assert count==len(cold_ui["timeline"]) or cold_ui["timeline"][count][0]>=frame["step"]
            if count:_,cold_words,cold_pending,cold_count=cold_ui["timeline"][count-1]
            cold_index=count
            for actual in (frame,originals[frame["step"]]):
                assert (actual.get("cold_ui_words") or [])==cold_words and actual.get("cold_ui_events",0)==cold_count
                expected_pending=cold_pending_at(cold_ui,actual,count,cold_words,cold_pending)
                assert actual.get("cold_ui_pending",False)==expected_pending,("cold page pending",frame["step"])
            if expected_pending:assert frame["held"]
            if cold_words and not frame["held"]:cold_retained+=1
        if "list_event_count" in state:
            count = state["list_event_count"]
            assert model_index+1 <= count <= len(model)
            assert count == 0 or model[count-1][0] <= frame["step"]
            assert count == len(model) or model[count][0] >= frame["step"]
            model_index = count-1
        else:
            while model_index + 1 < len(model) and model[model_index + 1][0] <= frame["step"]:
                model_index += 1
        assert (state["words"] or []) == (model[model_index][1] if model_index >= 0 else []), frame["step"]
        expected_page = model[model_index][3] if model_index >= 0 else None
        assert state.get("paragraph") == expected_page, ("paragraph frame lifetime",frame["step"])
        original = originals[frame["step"]]
        if hud and any(r["step"]<=frame["step"]<r["return_step"] for r in hud_records):
            assert frame["held"],("HUD transaction exposed",frame["step"])
        if any(r["step"]<=frame["step"]<r["return_step"] for r in hud_updates):
            assert frame["held"],("HUD panel transaction exposed",frame["step"])
        if effects and next_panel["step"]<=frame["step"]<restore["return_step"]:
            assert frame["held"],("HUD footer restoration exposed",frame["step"])
        if effects and last_retire<=frame["step"]<footer_restored:
            assert frame["held"],("HUD damage retirement exposed",frame["step"])
        if any(start <= frame["step"] < end for start, end in clock_intervals):
            assert frame["held"], ("clock transaction exposed", frame["step"])
        native_state = native_layouts[frame["step"]]
        if page_proof:
            layout=next(v["layout"] for v in reversed(trace["display_changes"]) if v["step"]<=frame["step"])
            assert native_state["display_start"]==layout["DisplayStart"]
            if not frame["held"]:
                for word in state["words"] or []:
                    origins=[(e,w) for e in hud_entries if e['Step']<=frame['step'] for w in hud_words[e['Step']]
                        if {k:v for k,v in w.items() if k!='Height'}=={k:v for k,v in word.items() if k!='Height'} and
                        word.get('Height',8)<=w.get('Height',8)]
                    if origins:
                        e,w=origins[-1];record=next(r for r in hud_records if r["step"]==e["Step"])
                        if record["paint_page"]!=native_state["display_start"]:
                            candidates=[(cp["step"],observed/(cp["label"]+".png")) for cp in trace["checkpoints"] if cp["step"]>=record["return_step"]]
                            candidates += [(step,path) for step,path in rounds_copy_images if step>=record['return_step']]
                            if effects:
                                candidates += [(cp["step"],inputs.parent.parent/cp["path"]) for cp in effects_copy_witness["images"] if cp["step"]>=record["return_step"]]
                            _,native_image=min(candidates,key=lambda item:item[0])
                            x,y,width,height=word["X"]*2,word["Y"]*2,word["Width"]*2,word.get("Height",8)*2
                            expected=Image.open(native_image).convert("RGBA").resize((640,400),Image.Resampling.NEAREST).crop((x,y,x+width,y+height)).tobytes()
                            raw=pixels(en_run,originals[frame["step"]])
                            actual=b"".join(raw[(yy*640+x)*4:(yy*640+x+width)*4] for yy in range(y,y+height))
                            assert actual==expected,("HUD page or unproved copy",frame["step"],word["Key"])
                        continue
                    events=[e for e in fields if e["Step"]<=frame["step"] and e["detail"]["word"]==word]
                    if not events:
                        assert model_index>=0 and (word["X"],word["Y"]) in model[model_index][2],("unproved word origin",frame["step"],word)
                        continue
                    call=calls_by_step[events[-1]["Step"]]
                    pages=call.get("video_pages")
                    assert pages and len(pages)==1
                    if int(next(iter(pages)))!=native_state["display_start"]:
                        # 原版也會將已畫好的頁複製到另一頁，逐詞框核對真正原版像素。
                        checkpoint=next(cp for cp in trace["checkpoints"] if cp["step"]>=call["return_step"])
                        x,y,width=word["X"]*2,word["Y"]*2,word["Width"]*2
                        expected=Image.open(observed/(checkpoint["label"]+".png")).convert("RGBA").resize((640,400),Image.Resampling.NEAREST).crop((x,y,x+width,y+16)).tobytes()
                        source=pixels(en_run,originals[frame["step"]])
                        actual=b"".join(source[(yy*640+x)*4:(yy*640+x+width)*4] for yy in range(y,y+16))
                        assert actual==expected,("field before native page or unproved copy",frame["step"],word["Key"])
        if "list_event_count" in state:
            assert state["list_event_count"] == native_state["list_event_count"]
        assert native_state.get("paragraph") == state.get("paragraph")
        for field in ("display_start", "render_page", "palette"):
            assert state[field] == native_state[field]
        if frame["held"]:
            assert previous is not None
            expected_hash = previous
            held += 1
        else:
            # 此契約來自上層列表列；下層靜態標題／提示不共用列表的填色頁生命週期。
            if model_index >= 0 and model[model_index][2]:
                row_words = [w for w in state["words"] if (w["X"],w["Y"]) in model[model_index][2]]
                if state["display_start"] == state["render_page"]:
                    last_row_frame, copied_row_page = (original,state,row_words), None
                elif copied_row_page != (state["render_page"],state["display_start"]):
                    # 服務返回可先複製整頁，重用列表不再填色。逐詞框驗原版畫格，不能只略過頁面條件。
                    allowed = service_row_keys | inventory_row_keys if (trade or ammo) else service_row_keys
                    assert row_words and all(w["Key"] in allowed for w in row_words), ("unproved row page",frame["step"])
                    assert last_row_frame is not None
                    prior_frame, prior_state, prior_words = last_row_frame
                    assert prior_words == row_words and prior_state["display_start"] == state["render_page"]
                    prior_pixels, current_pixels = pixels(en_run,prior_frame), pixels(en_run,original)
                    checks = []
                    for w in row_words:
                        x,y,width = w["X"]*2,w["Y"]*2,w["Width"]*2
                        crop = lambda data: b"".join(data[(yy*640+x)*4:(yy*640+x+width)*4] for yy in range(y,y+16))
                        before,after = crop(prior_pixels),crop(current_pixels)
                        assert before == after, ("service row page copy",frame["step"],w["Key"])
                        checks.append({"key":w["Key"],"rect":[x,y,width,16],"pixels_sha256":sha(after)})
                    copied_row_page = state["render_page"],state["display_start"]
                    copied_row_pages.append({"step":frame["step"],"source_step":prior_frame["step"],"pages":list(copied_row_page),"rows":checks})
            else:
                last_row_frame, copied_row_page = None, None
            for start, end, (x, y, width, height) in actor_headers:
                if start <= frame["step"] < end:
                    assert all(w["X"]+w["Width"] <= x or x+width <= w["X"] or w["Y"]+w.get("Height",8) <= y or y+height <= w["Y"] for w in state["words"] or [])
            key = (original["SHA256"], json.dumps(state["words"], sort_keys=True), json.dumps(state["palette"]),json.dumps(state.get("paragraph"),sort_keys=True),json.dumps(state.get("reader"),sort_keys=True),json.dumps(cold_words,sort_keys=True))
            if key not in cache:
                cache[key] = compose(pixels(en_run, original), state["words"], state["palette"],state.get("paragraph"),state.get("reader"),cold_words)
            expected_hash = cache[key]
            if state["words"]:
                translated_frames += 1
        assert frame["SHA256"] == expected_hash, (frame["step"], frame["held"])
        if (str(zh_run), frame["File"]) not in verified_pngs:
            pixels(zh_run, frame)
        previous = expected_hash
    translated_content_frames=sum(not frame["held"] and bool(state["words"] or state.get("paragraph") or state.get("reader"))
                                  for frame,state in zip(b["frames"],b["list_frames"]))
    assert translated_content_frames > 0
    for interval in feedback_intervals:
        visible = [f for f in b["frames"] if interval["ready"] <= f["step"] < interval["restoring"] and not f["held"]]
        assert visible, "購買回報被過渡畫面遮住"
        interval["visible_gpu_frames"] = len(visible)
    for interval in notice_intervals:
        visible = [f for f in b["frames"] if interval["ready"] <= f["step"] < interval["restoring"] and not f["held"]]
        assert visible, "鑑定回報被過渡畫面遮住"
        interval["visible_gpu_frames"] = len(visible)
    start = oracle["request"]["start_steps"]
    end = oracle["request"]["actions"][-1]["end"]
    for receipt in (a,b):
        for lo,hi in config["fine_windows"]:
            if start<=lo<hi<=end:
                gaps=[right["step"]-left["step"] for left,right in zip(receipt["frames"],receipt["frames"][1:]) if right["step"]>lo and left["step"]<hi]
                assert gaps and max(gaps)<=2000,("paint observation gap",lo,hi,max(gaps) if gaps else None)
    result = {"draft": True, "real_gpu_readback_frames": len(b["frames"]), "held_frames": held,
              "translated_frames": translated_frames, "original_checkpoints_equal": len(b["checkpoints"]),
              "observed_unique_rows": len({e["detail"]["source_sha256"] for e in accepted}),
              "row_events": len(accepted), "clear_transactions": len(cleared),
              "single_row_events": sum(not e["detail"]["within_list"] for e in accepted),
              "list_context_events": len(contexts),
              "list_page_rebases": len(pages),
              "purchase_feedback": feedback_intervals,
              "service_notices": notice_intervals,
              "service_scroll_copy_reports": service_scroll_checks,
              "service_row_page_copy_checks": copied_row_pages,
              "preserved_actor_headers": len(actor_headers),
              "field_events": len(fields), "field_keys": sorted({e["detail"]["key"] for e in fields}),
              "clock_transactions": len(clock_intervals),
              "typed_button_ownership":typed_buttons,
              "paragraph_events":len(paragraph_entries),"paragraph_original_fallbacks":len(paragraph_fallbacks),
              "formatted_paragraph_events":sum(e["detail"]["page"]["Key"].startswith("message.") for e in paragraph_entries),
              "paragraph_joins":sum(not p["Clear"] for p in page_history),
              "paragraph_replacements":sum(bool(p["Clear"]) for p in page_history),
              "paragraph_invalidations":sum(e["Kind"]=="paragraph-invalidated" for e in b["list_events"]),
              "compatible_footer_refreshes": sum(e["Kind"] == "footer-render-entry" and bool((e.get("detail") or {}).get("preserved")) for e in b["list_events"]),
              "fine_window_count": len(config["fine_windows"]),
              "callsite_field_events": sum(1 for e in fields if any(f["Pane"] == "callsite" and f["Key"] == e["detail"]["key"] for f in config["Fields"])),
              "menu_field_events": sum(bool(e["detail"]["menu_signature"]) for e in fields),
              "menu_kinds": sorted({config["Menus"][e["detail"]["menu_signature"]] for e in fields if e["detail"]["menu_signature"]}),
              "final_menu_kind": config["Menus"].get(final_signature, "original"),
              "final_footer_words": sum(w["Group"] == "footer" for w in b["final_words"] or []),
              "final_body_words": sum(w["Group"] != "footer" for w in b["final_words"] or []),
              "native_button_calls": sum(c["caller"] == {"Seg": 0xCEB, "Off": 0x1BE} for c in trace["calls"]),
              "known_menu_shapes": sorted({menu["Signature"] for menu in trace["menus"] if menu["Signature"] in config["Menus"]}),
              "field_lifetime_model_equal": True,
              "fine_windows_verified": True,
              "all_submitted_pixels_equal_expected": True,
              "en_receipt_sha256": sha((en_run / "receipt.json").read_bytes()),
              "zh_receipt_sha256": sha((zh_run / "receipt.json").read_bytes()),
              "checker_sha256": sha(Path(__file__).read_bytes()),
              "limits": "固定正常旅店快照與一般按鍵；已觀測列表、角色欄位及已知整表選單。數字與加值維持原版。不是全部介面、冷啟動、X11、裝備操作、施法、存讀檔、正式字級或正式中文化驗收。"}
    if reader is not None:
        from ui_journal_reader_check import check_reader_x11
        windows=[check_reader_x11(folder,run) for folder,run in ((en_run,a),(zh_run,b))]
        if any(windows):
            reader["x11_windows"] = windows
        result["reader"] = reader
        result["reader_model_sha256"] = sha((Path(__file__).parent / "ui_journal_reader_check.py").read_bytes())
    if cold_ui is not None:
        assert cold_retained>0 and not cold_words and not cold_pending
        result["cold_caption_carry_frames"]=cold_retained
        result["cold_caption_model_sha256"]=sha(Path(__file__).with_name("load_prompt_check.py").read_bytes())
    if creation:
        result["creation_name_input_visible"]=bool(name_calls)
        result["creation_added_fields"]=len(creation_added)
        result["creation_replaced_age_fields"]=len(removed_age)
        if name_calls:result["limits"]="正常 MZ 角色管理狀態後的人類戰士建角、命名、造型、實際保存、加入及檢視；未驗其他職業、重擲、修改、正式入口或全遊戲中文化。"
    if equipment:
        result["equipment_added_fields"]=len(equipment_fields)
        result["equipment_added_rows"]=len(equipment_rows)
        result["limits"]="正常建角後狀態及一般背包按鍵，或原建角路徑回歸；只驗已觀測裝備名稱與裝卸，不含任意物品、所有拒絕回報、正式入口或全遊戲中文化。"
    if item_context:
        result["item_context_added_fields"]=len(context_fields)
        result["limits"]="已觀測裝備拒絕及姓名長度的 DRAFT；GUI 以各自正常請求列明，不宣稱所有姓名字元、所有裝備回報或正式入口完成。"
    if battle:
        result["battle_added_fields"]=len(battle["fields"])
        result["battle_added_paragraphs"]=len(battle["paragraphs"])
        result["battle_field_cycles"]=battle_field_cycles
        result["limits"]="正常宮殿告別狀態後連續離城、凱爾高斯手札 65 與首次戰鬥、瞄準退出及首次攻擊。右側武器、攻擊及傷害回報仍原文，未宣稱整場戰鬥、正式入口或全遊戲中文化完成。"
    if literal_batch:
        result["translated_content_frames"]=translated_content_frames
        added=set(literal_batch["new_keys"])
        seen={e["detail"]["page"]["Key"] for e in paragraph_entries}&added
        visible={k for f,s in zip(b["frames"],b["list_frames"]) if not f["held"] and s.get("paragraph") for k in s["paragraph"]["Components"]}&added
        assert visible==seen and (seen or cast),"new catalog text not visible"
        result["literal_catalog"]={"eligible_keys":len(literal_batch["keys"]),"new_keys":len(added),
            "added_bindings":literal_batch["added_bindings"],"observed_new_keys":sorted(seen),"visible_new_keys":sorted(visible)}
        result["limits"]="既有正式 ECL 譯文沿四種已證實顯示情境批次接入；本次 GUI 只驗普通宮殿狀態後進酒館與交談，不能將目錄數換算成已走過的玩家路徑。短句、相鄰片段及新手札引用保留缺口；正式入口與全遊戲中文化未完成。"
    short_events=[e for e in paragraph_entries if len(e["detail"]["page"]["Source"])<=15 and e["detail"]["page"]["Key"].startswith("ecl.")]
    for e in short_events:
        proof=e["detail"].get("short_ecl_source")
        if short_ecl or proof:
            assert proof==dict(raw_b216=0x80,raw_b1c7=0x12 if e["detail"]["page"]["Clear"] else 0x11,
                handler_sha256="c61ccaba966f4c04eea49304ea633c61c02566cd8ca8e93105412d50e7f239c9",
                operand_sha256="c6f1c1c8cb204e32aa000a8ca180da3a23431f5d2a0e799cf4e65792269ef6ff")
            assert e["detail"]["source_pointer"]=={"Seg":0x333e,"Off":0xb487}
    if short_ecl:
        seen={e["detail"]["page"]["Key"] for e in short_events}
        visible={k for f,s in zip(b["frames"],b["list_frames"]) if not f["held"] and s.get("paragraph") for k in s["paragraph"]["Components"]}&set(short_ecl["keys"])
        assert visible==seen and (cast or (seen and seen&set(short_ecl["new_keys"])))
        result["short_ecl"]=dict(eligible=len(short_ecl["keys"]),new_keys=len(short_ecl["new_keys"]),added_bindings=short_ecl["added_bindings"],observed_keys=sorted(seen),visible_keys=sorted(visible))
        result["limits"]="80h 字面短敘事的 DRAFT 接入；本輪正常 GUI 只驗酒館標題一個新增短鍵及既有長台詞、離開後城市恢復。資料接入數不作玩家路徑覆蓋率，間接型別回退另作受控測試。相鄰片段、新引用、其他介面及正式入口仍待完成。"
    if cast:
        cast_base=inputs.parent.parent/cast["base"]
        result["cast"]={"source_rows":len(cast["data"]["rows"]),"source_aliases":len(cast["data"]["aliases"]),
            "new_keys":len(set(en).difference(catalog(cast_base/"en.tsv"))),
            "closed_events":sum(e["Kind"]=="memory-list-closed" for e in b["list_events"])}
        result["limits"]="正常首戰角色的兩頁記憶法術、選取與取消返回；沒有本輪新 ECL 敘事、完整施法、戰鬥勝利、其他角色、正式入口或全遊戲中文化聲明。"
    if party_cast:
        result["cast"]["scope"]="inherited catalog"
        party_base=inputs.parent.parent/party_cast["base"]
        result["cast"]["new_keys"]=len(set(catalog(party_base/"en.tsv")).difference(catalog(cast_base/"en.tsv")))
        result["party_cast"]={"source_rows":len(party_cast["data"]["rows"]),"new_rows":len(party_cast["data"]["added_rows"]),
            "new_keys":len(set(en).difference(catalog(party_base/"en.tsv")))}
        result["limits"]="Joris 正常記憶清單的兩頁、選取與取消；原版判定維持不變，不外推其他角色、完整施法、戰鬥或正式入口。"
    if hud and not scoped_path:
        hud_base=inputs.parent.parent/hud["base"]
        result["party_cast"]["scope"]="inherited catalog"
        result["party_cast"]["new_keys"]=len(set(catalog(hud_base/"en.tsv")).difference(catalog(party_base/"en.tsv")))
        result["hud"]={"bindings":len(config["HUDParagraphs"]),"entries":len(hud_entries),"returns":len(hud_returns),"aliases":len(hud["data"]["aliases"]),"added_fields":len(hud["data"]["fields"]),"added_menus":len(hud["data"]["menus"])}
        result["limits"]="正常兩位角色清單、右側兩種武器、施法起始、一次攻擊與未命中；不外推傷害、完整施法、勝利或正式入口。"
    if effects:
        result["effects"]=dict(bindings=len(effects["data"]["bindings"]),aliases=len(effects["data"]["aliases"]),fields=len(effects["data"]["fields"]),menus=len(effects["data"]["menus"]),numeric_reports=sum(r.get("number") is not None for r in hud_records),panel_updates=len(hud_updates))
        result["effects"]["copy_witness"]=effects_copy_witness
        result["limits"]="正常冰風暴目標選取、七次魔法傷害文字與返回戰鬥選單；只保留原版輸出數值，不推導傷害公式，不宣稱勝利或正式入口完成。"
    if finish:
        result["finish"]=dict(bindings=len(finish["data"]["bindings"]), numeric_reports=sum(r.get("number") is not None for r in hud_records), aliases=len(finish["data"]["aliases"]))
        result["limits"]="正常首戰的命中、一般傷害、閃電吐息與死亡回報；保留原版數值及勝負，沒有宣稱勝利、整場戰鬥或正式入口完成。"
    if movement:
        result["movement"]=dict(counter_values=[r["value"] for r in movement_path["counters"]],fields=len(movement["data"]["fields"]),menus=len(movement["data"]["menus"]))
    if ammo and not rounds:
        result["ammo"]=dict(dynamic_row_forms=len(set(bindings)-configured_bindings),
            source_path=(boundary_path or ammo)["source_path"],scope="正常備妥、分半、集合與反白；不宣稱本作已取得 +1 箭。")
    if boundary and not rounds:
        result['ammo_boundary']=dict(aliases=len(boundary['data']['aliases']),added_rows=len(boundary['data']['rows']),source_rows=len(boundary_path['records']))
        result["limits"]="正常單支／複數箭與弩箭的背包顯示；購買另有原版無頭收據，不稱為連續 GUI、正式入口或全遊戲完成。"
    if rounds:
        result['rounds']=dict(source_path=round_path['source_path'],records=len(round_path['records']),aliases=len(rounds['data']['aliases']),paragraphs=len(rounds['data']['paragraphs']))
        result['rounds']['original_clear_transactions']=len(hud_source_clears)
        result['rounds']['battle_warning_intervals']=battle_warning_intervals
        result['limits']='首戰正常續行至敗北的分段重播；原版傷害、包紮及勝負不變，未驗勝利或正式入口。'
    if journal_path or scoped_path:
        inherited={}
        for name,keys in ancestor_journal_sets.items():
            expected=set()
            for p in native_paragraphs:
                key='ecl.'+sha(p['source']['text'].encode())[:20]
                if key in keys and any(f['Key']==key and f['Caller']==p['caller'] and f['NativeBox']==p['native_box']
                    and all(f[k]==p[v] for k,v in (('Foreground','foreground'),('Background','background'),('Clear','clear')))
                    for f in config['Paragraphs']):expected.add(key)
            observed_keys={e['detail']['page']['Key'] for e in paragraph_entries}&keys
            visible_keys={k for f,s in zip(b['frames'],b['list_frames']) if not f['held'] and s.get('paragraph') for k in s['paragraph']['Components']}&keys
            assert observed_keys==visible_keys==expected,('journal ancestor text',name,expected,observed_keys,visible_keys)
            inherited[name]=dict(expected=sorted(expected),observed=sorted(observed_keys),visible=sorted(visible_keys))
        if journal_path:
            result['journal_references']=dict(formatted_ids=len(journal_refs['ids']),literal_sources=len(journal_refs['sources']),
                added_bindings=len(journal_refs['added']),new_aliases=len(journal_refs['aliases']),source_path=journal_path['source_path'],ancestor_sampling=inherited)
            result['limits']='DRAFT 全冊引用資料；正常 GUI 只回驗第 54／65 則，不將其餘資料當作正常引用證據。'
        if spell_path:
            records=spell_route['data']['rows']
            expected={r['row']['SHA256'] for r in records}
            accepted_hashes={e['detail']['source_sha256'] for e in accepted}
            expected_keys={span['Key'] for r in records for span in r['row']['Spans']}
            assert len(expected_keys)==len(records),'ambiguous spell source names'
            visible_keys={w['Key'] for f,s in zip(b['frames'],b['list_frames']) if not f['held'] for w in s.get('words') or []}
            # 原版會把首列重印為既有 field 綁定；兩份 catalog 都相同才接受別名。
            visible_aliases={key:sorted(k for k in visible_keys if (en[k],zh[k])==(en[key],zh[key])) for key in expected_keys}
            missing={key for key,aliases in visible_aliases.items() if not aliases}
            assert expected<=accepted_hashes and not missing,('spell route rows',expected-accepted_hashes,missing)
            result['spell_route']=dict(rows=len(records),added_rows=len(spell_route['data']['added_rows']),
                source_path=spell_path['source_path'],ancestor_sampling=inherited,visible_aliases=visible_aliases)
            result['limits']='DRAFT 正常首戰三頁記憶法術清單及退出；未驗本條路徑施法成功或戰鬥勝利。'
        if magic_path:
            assert len(battle_status_intervals)==len(status_witnesses)==3
            visible={w['Key'] for f,s in zip(b['frames'],b['list_frames']) if not f['held'] for w in s.get('words') or []}
            assert {w['key'] for w in status_witnesses.values()}<=visible
            result['magic_toggle']=dict(fields=len(magic_toggle['data']['fields']),intervals=battle_status_intervals,source_path=magic_path['source_path'],ancestor_sampling=inherited)
            result['limits']='DRAFT 正常 Alt-M 三次切換與原版按鈕恢復；未驗勝利或完整中文入口。'
        if fire_path:
            result['fire']=dict(source_path=fire_path['source_path'],records=len(hud_records),captions=len(fire_captions),ancestor_sampling=inherited,
                original_copy_witness=fire_copy_witness)
            result['limits']='DRAFT 原版自動施法支線的分段繁中顯示；火焰、保護及武器名稱不改數值，未驗勝利或完整中文入口。'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("real_gpu_readback_frames", "held_frames", "original_checkpoints_equal", "clear_transactions")}, ensure_ascii=False))


if __name__ == "__main__":
    check(*map(Path, sys.argv[1:7]))
