"""核心翻译引擎：
1) 默认在线：Groq API（基于 llama-3.3-70b-versatile 模型，超快推理）
2) RAG 语料库：
   - corpus_medical.py 中的 2000+ 专业医学术语（疾病/症状/解剖/检验/药品/科室/影像/缩写）
   - data.py 中的药品/分诊规则/医院信息
   - data/thuocl_medical.txt（清华医学词汇，若存在则加载）
3) 离线兜底：术语规则替换
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import threading
import time
from collections import Counter, OrderedDict
from typing import List, Tuple, Dict, Optional

from .config import settings
from .data import MEDICAL_TERMS, MEDICATIONS, TRIAGE_RULES, HOSPITALS
from .corpus_medical import MEDICAL_CORPUS, MEDICAL_CORPUS_DOCS, build_professional_rag_docs

logger = logging.getLogger(__name__)

# THUOCL 清华医学词汇路径
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_THUOCL_PATH = os.path.join(_BASE_DIR, "data", "thuocl_medical.txt")

# -------------------- 语言代码规范化 --------------------
_LANG_MAP: Dict[str, str] = {
    "zh": "zh", "zh-cn": "zh", "zh-CN": "zh", "zh-Hans": "zh", "chinese": "zh", "cn": "zh",
    "zh-tw": "zh-TW", "zh-TW": "zh-TW", "zh-Hant": "zh-TW",
    "en": "en", "en-US": "en", "en-GB": "en", "english": "en",
    "ja": "ja", "ko": "ko", "fr": "fr", "de": "de",
    "es": "es", "it": "it", "ru": "ru", "ar": "ar",
    "hi": "hi", "pt": "pt", "nl": "nl", "tr": "tr",
    "vi": "vi", "th": "th", "auto": "auto",
}

_LANG_NAME = {
    "zh": "中文", "en": "英文", "ja": "日文", "ko": "韩文", "fr": "法文", "de": "德文",
    "es": "西班牙文", "it": "意大利文", "ru": "俄文", "ar": "阿拉伯文",
    "hi": "印地文", "pt": "葡萄牙文", "nl": "荷兰文", "tr": "土耳其文",
    "vi": "越南文", "th": "泰文", "zh-TW": "繁体中文",
}

def _norm_lang(l: str) -> str:
    return _LANG_MAP.get((l or "").lower().strip(), "auto")

def _lang_display(code: str) -> str:
    c = _norm_lang(code)
    return _LANG_NAME.get(c, c)


# -------------------- RAG 语料库构建 --------------------
# 文档结构：每个 doc = {"content": str, "meta": str, "keywords": List[str]}
_RAG_DOCS: List[Dict] = []

# 已构建好的 en->zh 查找表（包含 2000+ 专业术语）
_PROFESSIONAL_EN2ZH: Dict[str, str] = {}


def _load_thuocl() -> List[Dict]:
    """加载 THUOCL 清华医学词汇。
    文件格式大致：每行一个词（部分文件为 "词\t频次"）。
    """
    docs: List[Dict] = []
    if not os.path.exists(_THUOCL_PATH):
        logger.info("THUOCL file not found at %s (skipping)", _THUOCL_PATH)
        return docs
    try:
        with open(_THUOCL_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = re.split(r"[\t,， ]+", line, maxsplit=1)
                word = parts[0].strip()
                if not word:
                    continue
                docs.append({
                    "content": f"THUOCL 医学词汇：{word}",
                    "meta": "THUOCL/zh-medical-vocab",
                    "keywords": [word],
                    "priority": 1,
                })
        logger.info("Loaded %d THUOCL terms", len(docs))
    except Exception as e:
        logger.warning("Failed to load THUOCL: %s", e)
    return docs


def _build_rag_docs():
    """从 corpus_medical.py 专业语料 + data.py 扩展信息 + THUOCL 构建 RAG 语料库。"""
    # 1. 专业医学语料（约 2000 条，优先）
    for doc in MEDICAL_CORPUS_DOCS:
        _RAG_DOCS.append(dict(doc))
        en = doc["keywords"][0] if doc["keywords"] else ""
        zh = doc["keywords"][1] if len(doc["keywords"]) > 1 else ""
        if en and zh:
            _PROFESSIONAL_EN2ZH[en.lower()] = zh

    # 2. 药品信息（MEDICATIONS）
    for key, info in MEDICATIONS.items():
        name = info.get("name", "")
        name_zh = info.get("name_zh", "")
        cat = info.get("category", "")
        cat_zh = info.get("category_zh", "")
        dosage = info.get("dosage", "")
        dosage_zh = info.get("dosage_zh", "")
        warnings_en = "; ".join(info.get("warnings", []))
        warnings_zh = "; ".join(info.get("warnings_zh", []))
        side_en = "; ".join(info.get("side_effects", []))
        rx = "处方" if info.get("rx_required") else "非处方"
        price = info.get("price_cny", "")

        content_en = f"Drug: {name} ({cat}). Dosage: {dosage}. Warnings: {warnings_en}. Side effects: {side_en}. {rx}, ¥{price}."
        content_zh = f"药品：{name_zh}（{cat_zh}）。剂量：{dosage_zh}。注意：{warnings_zh}。{rx}，¥{price}。"
        content = f"{content_en}\n{content_zh}"

        kws = [key, name, name_zh, cat, cat_zh]
        _RAG_DOCS.append({"content": content, "meta": "药品信息", "keywords": kws, "priority": 3})

    # 3. 分诊规则（TRIAGE_RULES）
    for symptom, (dep_en, dep_zh, rec_en, rec_zh, is_urgent) in TRIAGE_RULES.items():
        urgent_tag = "紧急" if is_urgent else "普通"
        content = (f"症状：{symptom} → 科室：{dep_en}/{dep_zh}（{urgent_tag}）\n"
                   f"建议（EN）：{rec_en}\n建议（ZH）：{rec_zh}")
        kws = [symptom, dep_en, dep_zh]
        _RAG_DOCS.append({"content": content, "meta": "分诊规则", "keywords": kws, "priority": 3})

    # 4. 医院信息（HOSPITALS）
    for h in HOSPITALS:
        content = (f"Hospital: {h.get('name', '')} / {h.get('name_zh', '')}\n"
                   f"Address: {h.get('address', '')} / {h.get('address_zh', '')}\n"
                   f"Phone: {h.get('phone', '')}\n"
                   f"Specialties: {', '.join(h.get('specialties', []))}\n"
                   f"Departments: {', '.join([d[0] + '/' + d[1] for d in h.get('departments', [])])}\n"
                   f"Languages: {', '.join(h.get('languages', []))}\n"
                   f"Insurance: {', '.join(h.get('insurance', []))}\n"
                   f"Rating: {h.get('rating', '')}")
        kws = [h.get("name", ""), h.get("name_zh", ""), h.get("id", "")] + h.get("specialties", [])
        _RAG_DOCS.append({"content": content, "meta": "医院信息", "keywords": kws, "priority": 1})

    # 5. THUOCL 中文医学词汇（若文件存在）
    for doc in _load_thuocl():
        _RAG_DOCS.append(doc)

    logger.info("RAG corpus built: %d documents (pro medical + data + THUOCL)",
                len(_RAG_DOCS))


_build_rag_docs()


# -------------------- 简易关键词检索 --------------------
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z\-']+|[\u4e00-\u9fff]{2,}")


def _tokenize(text: str) -> List[str]:
    """简易分词：提取英文词（≥2字母）和中文词（≥2字）。"""
    if not text:
        return []
    tokens = _TOKEN_RE.findall(text.lower())
    return tokens


# 构建全局词频（用于 IDF）+ 预计算每篇文档的 tf/dl（避免每次检索重复分词，约 2000+ 篇）
_DOC_FREQ: Counter = Counter()
for doc in _RAG_DOCS:
    toks = _tokenize(doc["content"])
    tf = Counter(toks)
    for kw in (k.lower() for k in doc["keywords"] if k):
        tf[kw] += 3
    doc["_tf"] = tf
    doc["_dl"] = max(len(toks), 1)
    uniq = set(toks)
    for kw in (k.lower() for k in doc["keywords"] if k):
        uniq.add(kw)
    for t in uniq:
        _DOC_FREQ[t] += 1

_TOTAL_DOCS = max(len(_RAG_DOCS), 1)


def _bm25(query_tokens: List[str], doc: Dict, k1: float = 1.5, b: float = 0.75) -> float:
    """简化版 BM25 打分（使用预计算的 tf/dl，O(查询词) 而非每次重新分词整篇）。"""
    tf = doc.get("_tf")
    if not tf:
        return 0.0
    avg_len = 40  # 经验平均长度
    dl = doc.get("_dl", 1)
    score = 0.0
    for qt in query_tokens:
        f = tf.get(qt, 0)
        if f == 0:
            continue
        df = _DOC_FREQ.get(qt, 0)
        idf = math.log((_TOTAL_DOCS - df + 0.5) / (df + 0.5) + 1.0)
        numerator = f * (k1 + 1)
        denominator = f + k1 * (1 - b + b * dl / avg_len)
        score += idf * numerator / denominator
    return score * doc.get("priority", 1)


def retrieve(query: str, top_k: int = 5) -> List[Tuple[str, float]]:
    """从 RAG 语料库中检索与查询最相关的文档。"""
    tokens = _tokenize(query)
    if not tokens:
        return []
    scored = [(doc, _bm25(tokens, doc)) for doc in _RAG_DOCS]
    scored.sort(key=lambda x: x[1], reverse=True)
    results: List[Tuple[str, float]] = []
    seen = set()
    for doc, s in scored:
        if s <= 0:
            continue
        key = doc["content"][:80]
        if key in seen:
            continue
        seen.add(key)
        results.append((f"[{doc['meta']}] {doc['content']}", round(s, 2)))
        if len(results) >= top_k:
            break
    return results


# -------------------- 翻译结果缓存（进程内 TTL + 有界 LRU）--------------------
# 相同 (text, source, target) 的重复翻译直接命中，省掉一次 Groq/MyMemory 外部调用
# （Groq 往返通常占整次请求的绝大部分时间）。仅缓存成功的在线翻译结果，
# 不改变任何输出 schema / 翻译质量。
_TRANS_CACHE_TTL = 900.0   # 秒（15 分钟）
_TRANS_CACHE_MAX = 512     # 有界，防止长跑进程内存无限增长
_trans_cache: "OrderedDict[Tuple[str, str, str], Tuple[float, Tuple]]" = OrderedDict()
_trans_cache_lock = threading.Lock()


def _trans_cache_get(key: Tuple[str, str, str]) -> Optional[Tuple]:
    """命中且未过期返回缓存的 translate() 结果元组；顺带刷新 LRU 顺序。"""
    now = time.time()
    with _trans_cache_lock:
        item = _trans_cache.get(key)
        if item is None:
            return None
        expires, value = item
        if expires < now:
            _trans_cache.pop(key, None)
            return None
        _trans_cache.move_to_end(key)  # 标记为最近使用
        return value


def _trans_cache_put(key: Tuple[str, str, str], value: Tuple) -> None:
    """写入缓存并按 LRU 淘汰最旧条目。"""
    with _trans_cache_lock:
        _trans_cache[key] = (time.time() + _TRANS_CACHE_TTL, value)
        _trans_cache.move_to_end(key)
        while len(_trans_cache) > _TRANS_CACHE_MAX:
            _trans_cache.popitem(last=False)  # 丢弃最久未使用


# -------------------- Groq API 调用（OpenAI 兼容格式，超快响应）--------------------
_GROQ_TIMEOUT = 30.0  # 秒


def _call_groq(text: str, source: str, target: str) -> Optional[str]:
    """调用 Groq Chat Completions API 做翻译（llama-3.3-70b-versatile 等模型）。
    关键：**不要**把 RAG 长文档塞进翻译 prompt，否则模型会复述参考文本而不是翻译。
    术语对齐改用 `_match_terms` 关键词匹配 + 本地 `MEDICAL_TERMS` 词典完成。
    """
    try:
        import requests
    except ImportError:
        logger.error("requests library not installed")
        return None

    api_key = settings.GROQ_API_KEY
    if not api_key:
        logger.warning("Groq API key not configured")
        return None

    src_name = _lang_display(source)
    tgt_name = _lang_display(target)

    system_prompt = (
        f"You are a professional medical translator. Translate from {src_name} to {tgt_name}. "
        f"Rules:\n"
        f"- Output ONLY the translation. No intro, no explanation, no notes, no references, no lists, no bullet points.\n"
        f"- Preserve medical meaning: symptoms, disease names, drug names, dosages, warnings.\n"
        f"- Use standard medical terminology appropriate for the target language.\n"
        f"- Keep original structure (if the input is one sentence, output one sentence).\n"
        f"- Keep numbers, dates, measurements exactly as they appear.\n"
        f"- If source == target, return the original text unchanged.\n"
    )

    user_msg = (
        f"Translate from {src_name} to {tgt_name}. Output ONLY the translation — nothing else.\n\n"
        f"TEXT: {text}"
    )

    payload = {
        "model": settings.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.2,
        # 翻译输出长度受输入长度约束；512 token 对任何现实临床句子/段落都绰绰有余，
        # 同时收紧最坏情况下的生成上限以缩短 Groq 往返时间（纯加速，不影响质量）。
        "max_tokens": 512,
    }

    url = settings.GROQ_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    t0 = time.time()
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=_GROQ_TIMEOUT)
    except Exception as e:
        logger.error("Groq request failed: %s", e)
        return None

    elapsed = time.time() - t0
    if resp.status_code != 200:
        if resp.status_code == 403:
            logger.error("Groq API 403 Forbidden — the API key is invalid, revoked, or your account is inactive. "
                         "Please get a new key from https://console.groq.com/keys")
        else:
            logger.error("Groq API HTTP %s: %s (%.2fs)", resp.status_code, resp.text[:500], elapsed)
        return None

    try:
        data = resp.json()
    except Exception:
        logger.error("Groq returned invalid JSON")
        return None

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        logger.error("Groq unexpected response: %s", json.dumps(data)[:500])
        return None

    logger.info("Groq translate OK (%.2fs, model=%s)", elapsed, settings.GROQ_MODEL)
    return content.strip() if content else None


# -------------------- MyMemory 免费翻译（全球可用，无需 key）--------------------
# 作为 Groq 不可用时的备选方案；提供邮箱可提升额度
def _call_mymemory(text: str, source: str, target: str) -> Optional[str]:
    """MyMemory Translation API — https://mymemory.translated.net/doc/spec.php
    免费额度：5000 字符/天；带邮箱时更多。"""
    try:
        import requests
    except ImportError:
        return None

    # MyMemory 使用 2-letter code，如 "en" "zh-CN"
    src = source.lower()
    tgt = target.lower()
    if tgt.startswith("zh"):
        tgt = "zh-CN"
    if src.startswith("zh"):
        src = "zh-CN"

    url = "https://api.mymemory.translated.net/get"
    params = {"q": text, "langpair": f"{src}|{tgt}", "de": "admin@transmed.io"}
    try:
        resp = requests.get(url, params=params, timeout=15)
    except Exception as e:
        logger.warning("MyMemory request failed: %s", e)
        return None
    if resp.status_code != 200:
        logger.warning("MyMemory HTTP %s: %s", resp.status_code, resp.text[:200])
        return None
    try:
        data = resp.json()
    except Exception:
        logger.warning("MyMemory bad JSON")
        return None
    translated = None
    # 常见返回格式：{'responseData': {'translatedText': '...'}} 或列表
    rd = data.get("responseData")
    if isinstance(rd, dict):
        translated = rd.get("translatedText")
    elif isinstance(rd, list) and rd:
        translated = rd[0].get("translatedText") if isinstance(rd[0], dict) else None
    if not translated:
        matches = data.get("matches") or []
        if isinstance(matches, list) and matches:
            # matches 可能是 [{translation: ...}, ...]
            for m in matches[:3]:
                if isinstance(m, dict):
                    t = m.get("translation")
                    if isinstance(t, str):
                        translated = t
                        break
    if isinstance(translated, str) and translated:
        # 去除 HTML 实体（MyMemory 有时返回 &quot; 等）
        import html as _html
        translated = _html.unescape(translated).strip()
        logger.info("MyMemory translate OK (%.2fs)", resp.elapsed.total_seconds() if hasattr(resp, 'elapsed') else 0)
        return translated
    return None


# -------------------- 预计算术语映射 / 合并正则（仅构建一次，加速每次请求） --------------------
def _build_term_indexes():
    en2zh: Dict[str, str] = {}
    zh2en: Dict[str, str] = {}
    for en, v in MEDICAL_TERMS.items():
        zh = v[0] if v else ""
        if en and zh:
            en2zh.setdefault(en, zh)
            zh2en.setdefault(zh, en)
    for info in MEDICAL_CORPUS.values():
        en = info.get("en", "")
        zh = info.get("zh", "")
        if en and zh:
            en2zh.setdefault(en, zh)
            zh2en.setdefault(zh, en)
    return en2zh, zh2en


_EN2ZH, _ZH2EN = _build_term_indexes()
_EN_KEYS_SORTED = sorted((t for t in _EN2ZH if len(t) >= 3), key=len, reverse=True)
_ZH_KEYS_SORTED = sorted((t for t in _ZH2EN if len(t) >= 2), key=len, reverse=True)
# 单遍匹配用的合并正则（一次编译，findall 一遍扫描，取代每请求数千次单独 search）
_EN_TERM_RE = re.compile(r"\b(" + "|".join(re.escape(t) for t in _EN_KEYS_SORTED) + r")\b", re.IGNORECASE) if _EN_KEYS_SORTED else None
_ZH_TERM_RE = re.compile("(" + "|".join(re.escape(t) for t in _ZH_KEYS_SORTED) + ")") if _ZH_KEYS_SORTED else None


# -------------------- 离线规则翻译（兜底） --------------------
def _offline(text: str, source: str, target: str) -> str:
    if _norm_lang(source) == _norm_lang(target) or not text.strip():
        return text
    src = source.lower()
    tgt = target.lower()
    out = text
    # 英文 → 中文：用预计算映射逐术语替换（长优先）
    if (src.startswith("en") or src == "auto") and tgt.startswith("zh"):
        for term in _EN_KEYS_SORTED:
            out = re.sub(r"\b" + re.escape(term) + r"\b", _EN2ZH[term], out, flags=re.IGNORECASE)
        return out
    # 中文 → 英文
    if src.startswith("zh") and (tgt.startswith("en") or tgt == "auto"):
        for zh in _ZH_KEYS_SORTED:
            if zh in out:
                out = out.replace(zh, " " + _ZH2EN[zh] + " ")
        return " ".join(out.split())
    return text


# -------------------- 术语对齐 / 置信度 --------------------
def _match_terms(original: str) -> List[str]:
    """扫描原文匹配的医学术语。用预编译的合并正则单遍 findall，
    取代以往每请求对数千术语逐个 re.search（O(术语数) → O(1 遍扫描)）。"""
    lower = original.lower()
    matched: List[str] = []
    if _EN_TERM_RE is not None:
        matched.extend(m.lower() for m in _EN_TERM_RE.findall(lower))
    if _ZH_TERM_RE is not None:
        matched.extend(_ZH_TERM_RE.findall(original))
    # 去重、限制数量
    seen: set = set()
    result: List[str] = []
    for m in matched:
        if m and m not in seen:
            seen.add(m)
            result.append(m)
        if len(result) >= 20:
            break
    return result


def _confidence(matched: int, engine_used: str) -> float:
    if engine_used == "groq":
        base = 92.0
    elif engine_used == "mymemory":
        base = 78.0  # 通用翻译引擎，但不是医学专用
    elif engine_used == "same-language":
        base = 95.0
    else:
        base = 55.0
    boost = min(8.0, matched * 1.2)
    conf = base + boost
    # 限制范围
    conf = round(min(99.0, max(30.0, conf)), 1)
    return conf


def risk_level(confidence: float) -> str:
    if confidence >= 85:
        return "low"
    if confidence >= 65:
        return "medium"
    if confidence >= 45:
        return "high"
    return "critical"


# -------------------- 公共 API --------------------
def translate(text: str, source: str, target: str) -> Tuple[str, float, List[str], str, List[str]]:
    """返回：(译文, 置信度, 匹配术语, 引擎名称：groq|mymemory|offline|same-language|error, RAG上下文)"""
    text = (text or "").strip()
    if not text:
        return "", 0.0, [], "empty", []

    src = _norm_lang(source)
    tgt = _norm_lang(target)

    # 0) 缓存命中：相同 (text, src, tgt) 直接返回上次结果，省掉 RAG 检索 + 外部翻译调用。
    #    仅缓存成功的在线/同语种结果（见末尾 _trans_cache_put），输出与首次完全一致。
    cache_key = (text, src, tgt)
    cached = _trans_cache_get(cache_key)
    if cached is not None:
        return cached

    # 1) RAG 检索：保存供前端在"医学参考"区显示，但**不**塞进翻译 prompt（避免模型复述语料）
    rag_tuples = retrieve(text, top_k=5)
    rag_context = [ctx for ctx, _ in rag_tuples]

    # 2) 术语匹配（用于置信度估计和前端高亮）
    matched = _match_terms(text)

    if src == tgt:
        result = (text, 95.0, matched, "same-language", rag_context)
        _trans_cache_put(cache_key, result)
        return result

    # 3) 首选 Groq LLM 翻译（纯翻译：RAG 上下文不传进 prompt）
    translated = _call_groq(text, source, target)
    if translated:
        result = (translated, _confidence(len(matched), "groq"), matched, "groq", rag_context)
        _trans_cache_put(cache_key, result)
        return result

    # 4) 备选 MyMemory 免费翻译（全球可用，无需 key）
    translated = _call_mymemory(text, source, target)
    if translated:
        result = (translated, _confidence(len(matched), "mymemory"), matched, "mymemory", rag_context)
        _trans_cache_put(cache_key, result)
        return result

    # 5) 兜底离线翻译（不缓存：属降级/瞬时失败，下次请求可能 Groq 成功）
    logger.warning("All online translators failed — falling back to offline rule-based translation")
    offline = _offline(text, source, target)
    return offline, _confidence(len(matched), "offline"), matched, "offline", rag_context


def translate_with_rag(text: str, source: str, target: str) -> Dict:
    """返回包含 RAG 上下文的完整翻译结果，供调试接口使用。"""
    text = (text or "").strip()
    if not text:
        return {"translated": "", "confidence": 0.0, "matched_terms": [], "engine": "empty",
                "rag_context": []}

    rag_tuples = retrieve(text, top_k=5)
    rag_context = [{"content": ctx, "score": s} for ctx, s in rag_tuples]

    translated, conf, matched, engine, _ = translate(text, source, target)

    return {
        "translated": translated,
        "confidence": conf,
        "matched_terms": matched,
        "engine": engine,
        "rag_context": rag_context,
        "corpus_size": len(_RAG_DOCS),
    }
