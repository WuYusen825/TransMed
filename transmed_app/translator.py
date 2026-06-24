"""核心翻译引擎：
1) 默认在线：Groq API（基于 llama-3.3-70b-versatile 模型，超快推理）
2) RAG 术语检索：terminology_api.py 通过外部 API（RxNorm + NCBI MeSH）
   实时查询权威医学术语库，无需在代码中内嵌语料，结果内存缓存（1小时 TTL）
3) 离线兜底：MEDICAL_TERMS 关键词替换（来自 data.py）
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Dict, List, Optional, Tuple

from .config import settings
from .data import MEDICAL_TERMS, MEDICATIONS, TRIAGE_RULES, HOSPITALS
from .terminology_api import retrieve_via_api

logger = logging.getLogger(__name__)

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


# -------------------- RAG 检索（外部 API）--------------------
def retrieve(query: str, top_k: int = 5) -> List[Tuple[str, float]]:
    """从外部权威术语库（RxNorm + NCBI MeSH）检索与查询最相关的医学概念。
    结果由 terminology_api.py 负责缓存，此函数直接转发。
    """
    return retrieve_via_api(query, top_k=top_k)


# -------------------- Groq API 调用 --------------------
_GROQ_TIMEOUT = 30.0


def _call_groq(text: str, source: str, target: str) -> Optional[str]:
    """调用 Groq Chat Completions API 做翻译（llama-3.3-70b-versatile 等模型）。
    RAG 上下文不传进 prompt——术语对齐由 _match_terms + MEDICAL_TERMS 词典完成。
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
            logger.error(
                "Groq API 403 Forbidden — the API key is invalid, revoked, or your account is inactive. "
                "Please get a new key from https://console.groq.com/keys"
            )
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


# -------------------- MyMemory 免费翻译（Groq 不可用时的备选）--------------------
def _call_mymemory(text: str, source: str, target: str) -> Optional[str]:
    """MyMemory Translation API — https://mymemory.translated.net/doc/spec.php
    免费额度：5000 字符/天；带邮箱时更多。"""
    try:
        import requests
    except ImportError:
        return None

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
    rd = data.get("responseData")
    if isinstance(rd, dict):
        translated = rd.get("translatedText")
    elif isinstance(rd, list) and rd:
        translated = rd[0].get("translatedText") if isinstance(rd[0], dict) else None
    if not translated:
        matches = data.get("matches") or []
        if isinstance(matches, list) and matches:
            for m in matches[:3]:
                if isinstance(m, dict):
                    t = m.get("translation")
                    if isinstance(t, str):
                        translated = t
                        break
    if isinstance(translated, str) and translated:
        import html as _html
        translated = _html.unescape(translated).strip()
        logger.info("MyMemory translate OK")
        return translated
    return None


# -------------------- 离线规则翻译（兜底）--------------------
def _offline(text: str, source: str, target: str) -> str:
    if _norm_lang(source) == _norm_lang(target) or not text.strip():
        return text
    src = source.lower()
    tgt = target.lower()
    out = text

    if (src.startswith("en") or src == "auto") and tgt.startswith("zh"):
        en2zh: Dict[str, str] = {}
        for en, v in MEDICAL_TERMS.items():
            zh = v[0] if v else ""
            if zh:
                en2zh[en] = zh
        for term in sorted(en2zh.keys(), key=len, reverse=True):
            zh = en2zh[term]
            pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
            out = pattern.sub(zh, out)
        return out

    if src.startswith("zh") and (tgt.startswith("en") or tgt == "auto"):
        zh_to_en: Dict[str, str] = {}
        for en, v in MEDICAL_TERMS.items():
            zh = v[0] if v else ""
            if zh:
                zh_to_en[zh] = en
        for zh in sorted(zh_to_en.keys(), key=len, reverse=True):
            out = out.replace(zh, " " + zh_to_en[zh] + " ")
        return " ".join(out.split())

    return text


# -------------------- 术语对齐 / 置信度 --------------------
def _match_terms(original: str) -> List[str]:
    """扫描原文匹配的医学术语（基于 MEDICAL_TERMS 核心词典）。"""
    lower = original.lower()
    matched: List[str] = []

    # 英文术语匹配
    en_terms = {t.lower() for t in MEDICAL_TERMS.keys()}
    for term in sorted(en_terms, key=len, reverse=True):
        if len(term) < 3:
            continue
        if re.search(r"\b" + re.escape(term) + r"\b", lower):
            matched.append(term)

    # 中文术语匹配
    zh_terms: set = set()
    for v in MEDICAL_TERMS.values():
        zh = v[0] if v else ""
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
        base = 78.0
    elif engine_used == "same-language":
        base = 95.0
    else:
        base = 55.0
    boost = min(8.0, matched * 1.2)
    return round(min(99.0, max(30.0, base + boost)), 1)


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
    """返回：(译文, 置信度, 匹配术语, 引擎名称, RAG上下文)"""
    text = (text or "").strip()
    if not text:
        return "", 0.0, [], "empty", []

    src = _norm_lang(source)
    tgt = _norm_lang(target)

    # 1) RAG 检索（外部 API）：供前端"医学参考"区显示，不传进翻译 prompt
    rag_tuples = retrieve(text, top_k=5)
    rag_context = [ctx for ctx, _ in rag_tuples]

    # 2) 术语匹配（用于置信度估计和前端高亮）
    matched = _match_terms(text)

    if src == tgt:
        return text, 95.0, matched, "same-language", rag_context

    # 3) 首选 Groq LLM 翻译
    translated = _call_groq(text, source, target)
    if translated:
        return translated, _confidence(len(matched), "groq"), matched, "groq", rag_context

    # 4) 备选 MyMemory 免费翻译
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
        return {
            "translated": "", "confidence": 0.0, "matched_terms": [],
            "engine": "empty", "rag_context": [],
        }

    translated, conf, matched, engine, rag_context_list = translate(text, source, target)

    rag_tuples = retrieve(text, top_k=5)
    rag_context = [{"content": ctx, "score": s} for ctx, s in rag_tuples]

    return {
        "translated": translated,
        "confidence": conf,
        "matched_terms": matched,
        "engine": engine,
        "rag_context": rag_context,
    }
