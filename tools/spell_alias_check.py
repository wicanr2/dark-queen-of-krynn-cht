"""核對明列證據的法術拼字別名，不做相近字串推測或改動遊戲鍵值。"""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def rows(path):
    with path.open() as stream:return list(csv.DictReader(stream,delimiter='\t',quoting=csv.QUOTE_NONE))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(glossary, prior, en, zh, output, batch=None):
    aliases=Path(__file__).with_name('spell-term-aliases.tsv')
    current=rows(glossary);previous=rows(prior);source=rows(en);translated=rows(zh)
    assert len({r['key'] for r in source})==len(source)
    assert len({r['key'] for r in translated})==len(translated)
    target={r['key']:r['text'] for r in translated};seen=set();checked=[]
    if batch:
        candidate=rows(batch)
        assert len({r['key'] for r in candidate})==len(candidate)
        assert all(r['key'] in {item['key'] for item in source} for r in candidate)
        target.update({r['key']:r['text'] for r in candidate})
    for alias in rows(aliases):
        identity=(alias['en'],alias['category']);assert identity not in seen;seen.add(identity)
        assert alias['level'] in ['已證實','強推論'] and alias['evidence']
        now=[r for r in current if (r['en'],r['category'])==identity]
        old=[r for r in previous if r['en']==alias['prior_en'] and r['category']==alias['category']]
        assert len(now)==len(old)==1,identity
        assert now[0]['zh']==old[0]['zh'],('前作別名譯法不一致',identity)
        keys=[]
        for row in source:
            if row['text'].strip().casefold()==alias['en'].casefold() and row['key'] in target:
                assert target[row['key']]==old[0]['zh'],('別名譯文未同步',row['key'])
                keys.append(row['key'])
        checked.append({'en':alias['en'],'prior_en':alias['prior_en'],'category':alias['category'],
                        'level':alias['level'],'evidence':alias['evidence'],'translated_keys':keys})
    assert output.parent.is_dir()
    inputs=[aliases,glossary,prior,en,zh]+([batch] if batch else [])
    report={'aliases':checked,'count':len(checked),'sources':{str(p):sha(p) for p in inputs},'projected_batch':bool(batch),
            'limits':'explicit terminology identity only; no runtime spell identifier or engine behavior changes'}
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('法術拼字別名：',len(checked),'；核對譯文：',sum(len(r['translated_keys']) for r in checked))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for argument in ['glossary','prior','en','zh','output']:parser.add_argument(argument,type=Path)
    parser.add_argument('--batch',type=Path)
    args=parser.parse_args();check(args.glossary,args.prior,args.en,args.zh,args.output,args.batch)
