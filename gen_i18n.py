#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性生成多语言静态字典 i18n_all.json（供 build_appjs.py 内嵌进 app.js）。

  python3 gen_i18n.py

流程：
  1. 从 build_appjs.py 抽取已手写的 STR_EN / STR_ZH（用 node 把 JS 字面量转成 JSON）。
  2. 用线上 /api/translate 引擎把 EN 翻成其余 10 种语言（分批 + 行数校验 + 逐条重试）。
  3. 写出 i18n_all.json = { en, zh, ja, ko, fr, de, es, it, ru, ar, pt, hi }。

英文/中文是手写精翻；其余为引擎翻译（机器水平，已与用户确认），但已在构建期预生成→运行期即时。
仅在改动了界面文案时需要重跑本脚本；平时构建只读 i18n_all.json。
"""
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(ROOT, "build_appjs.py")
OUT = os.path.join(ROOT, "i18n_all.json")
API = os.environ.get("TRANSMED_API", "https://transmed.onrender.com")
TARGET_LANGS = ["ja", "ko", "fr", "de", "es", "it", "ru", "ar", "pt", "hi"]


def extract_en_zh():
    """从 build_appjs.py 抽取 STR_EN / STR_ZH 两个 JS 对象字面量，用 node 转 JSON。"""
    src = open(BUILD, encoding="utf-8").read()

    def grab(name):
        # 匹配 var NAME = { ... };  （非贪婪到第一个 "};\n" 之前的平衡靠 node 解析兜底）
        m = re.search(r"var\s+" + name + r"\s*=\s*\{", src)
        if not m:
            raise SystemExit("could not find " + name)
        i = src.index("{", m.start())
        depth, j = 0, i
        while j < len(src):
            c = src[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        return src[i:j + 1]

    en_lit, zh_lit = grab("STR_EN"), grab("STR_ZH")
    node = "var STR_EN=%s;var STR_ZH=%s;process.stdout.write(JSON.stringify({en:STR_EN,zh:STR_ZH}));" % (en_lit, zh_lit)
    tmp = os.path.join(ROOT, "_i18n_extract.js")
    open(tmp, "w", encoding="utf-8").write(node)
    try:
        out = subprocess.check_output(["node", tmp], text=True)
    finally:
        os.remove(tmp)
    return json.loads(out)


def translate_batch(texts, lang):
    """整批 \\n 拼接翻译，行数对得上才采用；否则返回 None 触发逐条。"""
    try:
        r = requests.post(API + "/api/translate", json={"text": "\n".join(texts), "source": "en", "target": lang}, timeout=40)
        out = (r.json().get("translated") or "").split("\n")
    except Exception:
        return None
    return out if len(out) == len(texts) else None


def translate_one(text, lang):
    try:
        r = requests.post(API + "/api/translate", json={"text": text, "source": "en", "target": lang}, timeout=40)
        return (r.json().get("translated") or "").split("\n")[0].strip() or text
    except Exception:
        return text


PH = re.compile(r"\{\w+\}")


def gen_lang(en, lang):
    keys = list(en.keys())
    result = {}
    # pass 1: batches of 20
    CH = 20
    for i in range(0, len(keys), CH):
        ks = keys[i:i + CH]
        texts = [en[k] for k in ks]
        out = translate_batch(texts, lang)
        if out:
            for k, src, o in zip(ks, texts, out):
                ph = PH.findall(src)
                if ph and any(p not in o for p in ph):
                    continue  # 占位符丢失→保留英文，留待逐条
                result[k] = o.strip()
    # pass 2: per-string retry for missing keys
    missing = [k for k in keys if k not in result]
    for k in missing:
        o = translate_one(en[k], lang)
        ph = PH.findall(en[k])
        if ph and any(p not in o for p in ph):
            o = en[k]
        result[k] = o
    print("  %s: %d/%d keys" % (lang, len(result), len(keys)))
    return lang, result


def main():
    base = extract_en_zh()
    en = base["en"]
    print("extracted EN=%d ZH=%d keys" % (len(en), len(base["zh"])))
    all_dict = {"en": en, "zh": base["zh"]}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=4) as ex:
        for lang, d in ex.map(lambda L: gen_lang(en, L), TARGET_LANGS):
            all_dict[lang] = d
    json.dump(all_dict, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote %s (%d langs) in %.1fs" % (os.path.relpath(OUT, ROOT), len(all_dict), time.time() - t0))


if __name__ == "__main__":
    main()
