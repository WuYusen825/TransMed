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
from collections import Counter
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


# 构建全局词频（用于 IDF）
_DOC_FREQ: Counter = Counter()
for doc in _RAG_DOCS:
    text = doc["content"].lower()
    uniq = set(_tokenize(text))
    for kw in (k.lower() for k in doc["keywords"] if k):
        uniq.add(kw)
    for t in uniq:
        _DOC_FREQ[t] += 1

_TOTAL_DOCS = max(len(_RAG_DOCS), 1)


def _bm25(query_tokens: List[str], doc: Dict, k1: float = 1.5, b: float = 0.75) -> float:
    """简化版 BM25 打分。"""
    doc_tokens = _tokenize(doc["content"])
    if not doc_tokens:
        return 0.0
    avg_len = 40  # 经验平均长度
    dl = len(doc_tokens)
    tf = Counter(doc_tokens)
    # 额外把 keywords 作为 boosted 词
    for kw in (k.lower() for k in doc["keywords"] if k):
        tf[kw] += 3

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
        "max_tokens": 1024,
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


# -------------------- 离线规则翻译（兜底） --------------------
def _offline(text: str, source: str, target: str) -> str:
    if _norm_lang(source) == _norm_lang(target) or not text.strip():
        return text
    src = source.lower()
    tgt = target.lower()
    out = text
    # 英文 → 中文：从专业语料库中逐个术语替换（长优先）
    if (src.startswith("en") or src == "auto") and tgt.startswith("zh"):
        # 合并 MEDICAL_TERMS + MEDICAL_CORPUS 英中映射
        en2zh: Dict[str, str] = {}
        for en, v in MEDICAL_TERMS.items():
            zh = v[0] if v else ""
            if zh:
                en2zh[en] = zh
        for key, info in MEDICAL_CORPUS.items():
            en = info.get("en", "")
            zh = info.get("zh", "")
            if en and zh:
                en2zh[en] = zh
        sorted_terms = sorted(en2zh.keys(), key=len, reverse=True)
        for term in sorted_terms:
            zh = en2zh[term]
            pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
            out = pattern.sub(zh, out)
        return out
    # 中文 → 英文
    if src.startswith("zh") and (tgt.startswith("en") or tgt == "auto"):
        zh_to_en: Dict[str, str] = {}
        for en, v in MEDICAL_TERMS.items():
            zh = v[0] if v else ""
            if zh:
                zh_to_en[zh] = en
        for key, info in MEDICAL_CORPUS.items():
            zh = info.get("zh", "")
            en = info.get("en", "")
            if zh and en and zh not in zh_to_en:
                zh_to_en[zh] = en
        sorted_zh = sorted(zh_to_en.keys(), key=len, reverse=True)
        for zh in sorted_zh:
            out = out.replace(zh, " " + zh_to_en[zh] + " ")
        return " ".join(out.split())
    return text


# -------------------- 术语对齐 / 置信度 --------------------
def _match_terms(original: str) -> List[str]:
    """扫描原文匹配的医学术语（合并 MEDICAL_TERMS + MEDICAL_CORPUS）。"""
    lower = original.lower()
    matched: List[str] = []
    # 英文术语匹配
    en_terms = set()
    for term in MEDICAL_TERMS.keys():
        en_terms.add(term.lower())
    for key in MEDICAL_CORPUS.keys():
        en_terms.add(key)
    # 按长度倒序匹配
    for term in sorted(en_terms, key=len, reverse=True):
        if len(term) < 3:
            continue
        if re.search(r"\b" + re.escape(term) + r"\b", lower):
            matched.append(term)
    # 中文术语匹配
    zh_terms = set()
    for v in MEDICAL_TERMS.values():
        zh = v[0] if v else ""
        if zh:
            zh_terms.add(zh)
    for info in MEDICAL_CORPUS.values():
        zh = info.get("zh", "")
        if zh:
            zh_terms.add(zh)
    for zh in sorted(zh_terms, key=len, reverse=True):
        if len(zh) < 2:
            continue
        if zh in original:
            matched.append(zh)
    # 去重、限制数量
    seen: set = set()
    result: List[str] = []
    for m in matched:
        if m not in seen:
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

    # 1) RAG 检索：保存供前端在"医学参考"区显示，但**不**塞进翻译 prompt（避免模型复述语料）
    rag_tuples = retrieve(text, top_k=5)
    rag_context = [ctx for ctx, _ in rag_tuples]

    # 2) 术语匹配（用于置信度估计和前端高亮）
    matched = _match_terms(text)

    if src == tgt:
        return text, 95.0, matched, "same-language", rag_context

    # 3) 首选 Groq LLM 翻译（纯翻译：RAG 上下文不传进 prompt）
    translated = _call_groq(text, source, target)
    if translated:
        return translated, _confidence(len(matched), "groq"), matched, "groq", rag_context

    # 4) 备选 MyMemory 免费翻译（全球可用，无需 key）
    translated = _call_mymemory(text, source, target)
    if translated:
        return translated, _confidence(len(matched), "mymemory"), matched, "mymemory", rag_context

    # 5) 兜底离线翻译
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

    translated, conf, matched, engine = translate(text, source, target)

    return {
        "translated": translated,
        "confidence": conf,
        "matched_terms": matched,
        "engine": engine,
        "rag_context": rag_context,
        "corpus_size": len(_RAG_DOCS),
    }
