"""
API-based medical terminology RAG retrieval.

Uses free public APIs — no registration required for basic access:
  • RxNorm (NIH/NLM)  — drug names, brand/generic, RXCUI identifiers
  • NCBI E-utils/MeSH — disease, procedure, anatomy concepts & definitions

Results are cached in-process with a 1-hour TTL to minimise API latency
and avoid hammering public infrastructure.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── In-process TTL cache ───────────────────────────────────────────────────────
_CACHE: Dict[str, Tuple[object, float]] = {}
_TTL = 3600.0  # seconds

def _cache_get(key: str) -> Optional[object]:
    entry = _CACHE.get(key)
    if entry and (time.time() - entry[1]) < _TTL:
        return entry[0]
    return None

def _cache_set(key: str, val: object) -> None:
    _CACHE[key] = (val, time.time())


# ── RxNorm API (NIH/NLM, completely free, no API key) ─────────────────────────
_RXNORM_BASE = "https://rxnav.nlm.nih.gov/REST"
_API_TIMEOUT = 5  # seconds — keep translation snappy


def _rxnorm_approx(term: str) -> List[Dict]:
    """Approximate drug-name search via RxNorm /approximateTerm endpoint."""
    cache_key = f"rx:{term.lower()[:60]}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    results: List[Dict] = []
    try:
        import requests
        resp = requests.get(
            f"{_RXNORM_BASE}/approximateTerm.json",
            params={"term": term, "maxEntries": 4},
            timeout=_API_TIMEOUT,
        )
        if resp.status_code == 200:
            candidates = (
                resp.json()
                .get("approximateGroup", {})
                .get("candidate", [])
            )
            for c in candidates:
                if not c.get("name"):
                    continue
                # RxNorm 的 score 是浮点字符串（如 "10.36"）；int() 会抛 ValueError，
                # 必须用 float 解析（这正是之前 RxNorm 始终返回空的根因）。
                try:
                    score = float(c.get("score", 0) or 0)
                except (TypeError, ValueError):
                    score = 0.0
                results.append({
                    "name": c.get("name", ""),
                    "rxcui": c.get("rxcui", ""),
                    "score": score,
                })
    except Exception as exc:
        logger.debug("RxNorm request failed for '%s': %s", term, exc)

    _cache_set(cache_key, results)
    return results


# ── NCBI E-utils / MeSH API (free, no key for basic use) ──────────────────────
_NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_NCBI_TOOL = "transmed"
_NCBI_EMAIL = "admin@transmed.io"


def _mesh_search(query: str) -> List[Dict]:
    """Search NCBI MeSH for medical concept names and scope notes (definitions)."""
    cache_key = f"mesh:{query.lower()[:80]}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    results: List[Dict] = []
    try:
        import requests

        # Step 1 — esearch: get MeSH unique IDs
        sr = requests.get(
            f"{_NCBI_BASE}/esearch.fcgi",
            params={
                "db": "mesh",
                "term": query,
                "retmax": 3,
                "retmode": "json",
                "tool": _NCBI_TOOL,
                "email": _NCBI_EMAIL,
            },
            timeout=_API_TIMEOUT,
        )
        if sr.status_code != 200:
            _cache_set(cache_key, [])
            return []

        ids = sr.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            _cache_set(cache_key, [])
            return []

        # Step 2 — esummary: fetch concept details
        sumr = requests.get(
            f"{_NCBI_BASE}/esummary.fcgi",
            params={
                "db": "mesh",
                "id": ",".join(ids[:3]),
                "retmode": "json",
                "tool": _NCBI_TOOL,
                "email": _NCBI_EMAIL,
            },
            timeout=_API_TIMEOUT,
        )
        if sumr.status_code != 200:
            _cache_set(cache_key, [])
            return []

        data = sumr.json().get("result", {})
        for uid in ids[:3]:
            item = data.get(uid)
            if not isinstance(item, dict):
                continue
            terms = item.get("ds_meshterms") or []
            name = terms[0] if terms else query
            scope = item.get("ds_scopenote", "") or ""
            results.append({
                "name": name,
                "scope": scope[:300],
                "uid": uid,
            })
    except Exception as exc:
        logger.debug("MeSH request failed for '%s': %s", query, exc)

    _cache_set(cache_key, results)
    return results


# ── WHO ICD-11 API (authoritative disease classification, multilingual incl. zh) ──
# OAuth2 client-credentials flow. Token cached ~1h. Requires client_id/secret
# from https://icd.who.int/icdapi — when absent, ICD lookups are skipped silently.
_ICD_TOKEN: Dict[str, object] = {"value": None, "exp": 0.0}
_HTML_TAG = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """ICD-11 search titles wrap the match in <em class='found'>…</em>."""
    return _HTML_TAG.sub("", text or "").strip()


def _icd_token() -> Optional[str]:
    """Fetch & cache an ICD-11 OAuth2 access token (valid ~1 hour)."""
    from .config import settings

    cid = settings.ICD_CLIENT_ID
    secret = settings.ICD_CLIENT_SECRET
    if not cid or not secret:
        return None

    now = time.time()
    tok = _ICD_TOKEN.get("value")
    if tok and now < float(_ICD_TOKEN.get("exp", 0.0)):
        return tok  # type: ignore[return-value]

    try:
        import requests
        resp = requests.post(
            settings.ICD_TOKEN_URL,
            data={
                "client_id": cid,
                "client_secret": secret,
                "scope": "icdapi_access",
                "grant_type": "client_credentials",
            },
            timeout=_API_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("access_token")
            expires_in = int(data.get("expires_in", 3600))
            _ICD_TOKEN["value"] = token
            _ICD_TOKEN["exp"] = now + expires_in - 60  # refresh 60s early
            return token
        logger.debug("ICD token HTTP %s: %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.debug("ICD token request failed: %s", exc)
    return None


def _icd_search(query: str, lang: str = "zh") -> List[Dict]:
    """Search WHO ICD-11 for disease titles + ICD-11 codes in `lang` (zh/en)."""
    cache_key = f"icd:{lang}:{query.lower()[:80]}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    token = _icd_token()
    if not token:
        return []

    results: List[Dict] = []
    try:
        import requests
        from .config import settings
        resp = requests.get(
            f"{settings.ICD_BASE_URL}/icd/entity/search",
            params={"q": query, "flatResults": "true"},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Accept-Language": lang,
                "API-Version": "v2",
            },
            timeout=_API_TIMEOUT,
        )
        if resp.status_code == 200:
            entities = resp.json().get("destinationEntities", []) or []
            for e in entities[:4]:
                title = _strip_html(e.get("title", ""))
                code = e.get("theCode", "") or ""
                if title:
                    results.append({"title": title, "code": code})
    except Exception as exc:
        logger.debug("ICD search failed for '%s': %s", query, exc)

    _cache_set(cache_key, results)
    return results


# ── Public retrieval function ──────────────────────────────────────────────────
_EN_TOKEN = re.compile(r"[A-Za-z][A-Za-z\-']{2,}")


def retrieve_via_api(query: str, top_k: int = 5) -> List[Tuple[str, float]]:
    """
    Retrieve medical-terminology context for `query` via external APIs.

    Returns a list of (content_string, relevance_score) tuples, up to `top_k`.
    This replaces the BM25-over-local-corpus approach in translator.py.
    Failures are silently swallowed — an empty list is a valid result.
    """
    query = (query or "").strip()
    if not query:
        return []

    results: List[Tuple[str, float]] = []

    # Unique English tokens (order-preserved)
    en_tokens = list(dict.fromkeys(t.lower() for t in _EN_TOKEN.findall(query)))

    # 0. WHO ICD-11 (authoritative disease classification, zh+en, highest priority)
    icd_zh = {d["code"]: d["title"] for d in _icd_search(query, lang="zh") if d["code"]}
    icd_en = {d["code"]: d["title"] for d in _icd_search(query, lang="en") if d["code"]}
    for code in list(dict.fromkeys(list(icd_en.keys()) + list(icd_zh.keys())))[:3]:
        parts = [p for p in (icd_zh.get(code, ""), icd_en.get(code, "")) if p]
        if parts:
            results.append((f"[ICD-11疾病] {' / '.join(parts)} (ICD-11: {code})", 4.0))

    # 1. RxNorm: try the query itself then individual long tokens
    tried_rx: set = set()
    seen_rxcui: set = set()
    for candidate in ([query[:80]] + en_tokens[:3]):
        if candidate in tried_rx or len(candidate) < 3:
            continue
        tried_rx.add(candidate)
        cand_first = candidate.split()[0].lower() if candidate.split() else ""
        for drug in _rxnorm_approx(candidate)[:3]:
            name = drug.get("name", "")
            rxcui = drug.get("rxcui", "")
            # 过滤模糊匹配噪音：要求药品名首词 == 查询词首词。否则疾病/症状词会被 RxNorm
            # 模糊匹配到名字里含该词的无关药品商品名（diabetes→"Diabetic Tussin"、
            # fever→"Little Fevers"、headache→"BC Headache"），污染医学参考。
            # score 阈值无效（这类噪音 score 与真药品重叠），首词匹配才能区分。
            name_first = name.split()[0].lower() if name.split() else ""
            # 同一 RXCUI 的多个大小写 / 来源变体（Aspirin / aspirin / ASPIRIN）只保留一个
            if name and name_first == cand_first and rxcui not in seen_rxcui:
                seen_rxcui.add(rxcui)
                label = f"[RxNorm药品] {name}"
                if rxcui:
                    label += f" (RXCUI:{rxcui})"
                results.append((label, 3.0))

    # 2. MeSH: full query → concept definitions
    for m in _mesh_search(query)[:3]:
        name = m.get("name", "")
        scope = m.get("scope", "")
        if name:
            label = f"[MeSH医学概念] {name}"
            if scope:
                label += f": {scope[:200]}"
            results.append((label, 2.5))

    # 3. MeSH: individual English tokens as supplementary coverage
    seen_mesh: set = set()
    for tok in en_tokens[:3]:
        if tok in seen_mesh or len(tok) < 4:
            continue
        seen_mesh.add(tok)
        for m in _mesh_search(tok)[:1]:
            name = m.get("name", "")
            if name:
                label = f"[MeSH] {name}"
                scope = m.get("scope", "")
                if scope:
                    label += f": {scope[:150]}"
                results.append((label, 1.5))

    # Deduplicate by content prefix
    seen: set = set()
    deduped: List[Tuple[str, float]] = []
    for content, score in results:
        k = content[:60]
        if k not in seen:
            seen.add(k)
            deduped.append((content, score))

    # Highest-authority sources (ICD-11 4.0 > RxNorm 3.0 > MeSH) float to the top
    deduped.sort(key=lambda x: x[1], reverse=True)
    return deduped[:top_k]
