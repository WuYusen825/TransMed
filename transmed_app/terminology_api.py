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
from concurrent.futures import ThreadPoolExecutor
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
_API_TIMEOUT = 8  # seconds — 三源并行后单请求可放宽；给 Render→WHO/NCBI 的较慢网络留余量，
                  # 避免 ICD search / entity fetch 超时丢结果（之前线上首个 query 丢 ICD 的隐患）


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


def _icd_entity_title(entity_url: str, lang: str, token: str) -> str:
    """取单个 ICD-11 entity 在 `lang` 下的标题（用于中英对照）。结果缓存。"""
    cache_key = f"icdent:{lang}:{entity_url[-24:]}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]
    title = ""
    try:
        import requests
        r = requests.get(
            entity_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Accept-Language": lang,
                "API-Version": "v2",
            },
            timeout=_API_TIMEOUT,
        )
        if r.status_code == 200:
            t = r.json().get("title")
            # ICD entity 详情的 title 是 {"@language":..,"@value":..} 形式
            title = _strip_html(t.get("@value") if isinstance(t, dict) else (t or ""))
    except Exception as exc:
        logger.debug("ICD entity fetch failed: %s", exc)
    _cache_set(cache_key, title)
    return title


def _icd_search(query: str, top_k: int = 3) -> List[Dict]:
    """搜 WHO ICD-11 MMS 线性化，返回 [{code, title, title_other}]（中英对照）。

    关键点（均来自实测，踩过的坑）：
      • 必须用 MMS 端点 /icd/release/11/{release}/mms/search —— foundation 的
        entity/search 返回的条目常无 theCode（如 TM2 传统医学「无翻译」条目）。
      • 搜索词语言必须与 Accept-Language 一致：英文 query 配 Accept-Language=zh
        会返回 0 条。故按 query 语言搜，再用 entity id 拉另一语言标题做对照。
    """
    query = (query or "").strip()
    if not query:
        return []
    cache_key = f"icd:{query.lower()[:80]}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    token = _icd_token()
    if not token:
        return []

    has_cjk = any("一" <= c <= "鿿" for c in query)
    search_lang = "zh" if has_cjk else "en"
    other_lang = "en" if has_cjk else "zh"

    results: List[Dict] = []
    try:
        import requests
        from .config import settings
        resp = requests.get(
            f"{settings.ICD_BASE_URL}/icd/release/11/{settings.ICD_RELEASE}/mms/search",
            params={"q": query, "flatResults": "true"},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Accept-Language": search_lang,
                "API-Version": "v2",
            },
            timeout=_API_TIMEOUT,
        )
        if resp.status_code == 200:
            entities = resp.json().get("destinationEntities", []) or []
            picked: List[Dict] = []
            for e in entities[:top_k]:
                title = _strip_html(e.get("title", ""))
                if not title:
                    continue
                picked.append({
                    "code": e.get("theCode", "") or "",
                    "title": title,
                    "title_other": "",
                    "_eid": e.get("id") or "",
                })
            # 仅前 2 条取另一语言对照，且并行取（2 次串行 entity fetch 会拖到 ~5s）
            to_fetch = [p for p in picked[:2] if p["_eid"]]
            if to_fetch:
                with ThreadPoolExecutor(max_workers=len(to_fetch)) as ex:
                    futs = {ex.submit(_icd_entity_title, p["_eid"], other_lang, token): p
                            for p in to_fetch}
                    for fut, p in futs.items():
                        p["title_other"] = fut.result()
            for p in picked:
                p.pop("_eid", None)
                results.append(p)
    except Exception as exc:
        logger.debug("ICD MMS search failed for '%s': %s", query, exc)

    _cache_set(cache_key, results)
    return results


# ── Public retrieval function ──────────────────────────────────────────────────
_EN_TOKEN = re.compile(r"[A-Za-z][A-Za-z\-']{2,}")


def _collect_icd(query: str) -> List[Tuple[str, float]]:
    """WHO ICD-11 疾病（最高优先级，中英对照 + 编码）。"""
    out: List[Tuple[str, float]] = []
    for d in _icd_search(query, top_k=3):
        title = d.get("title", "")
        if not title:
            continue
        other = d.get("title_other", "")
        code = d.get("code", "")
        pair = f"{title} / {other}" if other else title
        label = f"[ICD-11疾病] {pair}"
        if code:
            label += f" (ICD-11: {code})"
        out.append((label, 4.0))
    return out


def _collect_rxnorm(query: str, en_tokens: List[str]) -> List[Tuple[str, float]]:
    """RxNorm 药品（完整 query + 长 token，各 candidate 查询并行）。"""
    candidates: List[str] = []
    seen_cand: set = set()
    for c in ([query[:80]] + en_tokens[:3]):
        if len(c) >= 3 and c not in seen_cand:
            seen_cand.add(c)
            candidates.append(c)
    if not candidates:
        return []
    with ThreadPoolExecutor(max_workers=len(candidates)) as ex:
        per_cand = [(c, fut.result()) for fut, c in
                    [(ex.submit(_rxnorm_approx, c), c) for c in candidates]]
    out: List[Tuple[str, float]] = []
    seen_rxcui: set = set()
    for candidate, drugs in per_cand:
        cand_first = candidate.split()[0].lower() if candidate.split() else ""
        for drug in drugs[:3]:
            name = drug.get("name", "")
            rxcui = drug.get("rxcui", "")
            # 过滤模糊匹配噪音：药品名首词须 == 查询词首词（diabetes→"Diabetic Tussin"、
            # fever→"Little Fevers" 等噪音 score 与真药品重叠，只能靠首词区分）。
            name_first = name.split()[0].lower() if name.split() else ""
            if name and name_first == cand_first and rxcui not in seen_rxcui:
                seen_rxcui.add(rxcui)
                label = f"[RxNorm药品] {name}"
                if rxcui:
                    label += f" (RXCUI:{rxcui})"
                out.append((label, 3.0))
    return out


def _collect_mesh(query: str, en_tokens: List[str]) -> List[Tuple[str, float]]:
    """NCBI MeSH 概念（完整 query + token 补充，并行查询）。"""
    tokens = [t for t in en_tokens[:3] if len(t) >= 4]
    with ThreadPoolExecutor(max_workers=max(1, 1 + len(tokens))) as ex:
        f_full = ex.submit(_mesh_search, query)
        f_tokens = [(ex.submit(_mesh_search, t), t) for t in tokens]
        full_res = f_full.result()
        token_res = [(t, fut.result()) for fut, t in f_tokens]
    out: List[Tuple[str, float]] = []
    for m in full_res[:3]:
        name = m.get("name", "")
        if name:
            label = f"[MeSH医学概念] {name}"
            scope = m.get("scope", "")
            if scope:
                label += f": {scope[:200]}"
            out.append((label, 2.5))
    seen_mesh: set = set()
    for tok, res in token_res:
        if tok in seen_mesh:
            continue
        seen_mesh.add(tok)
        for m in res[:1]:
            name = m.get("name", "")
            if name:
                label = f"[MeSH] {name}"
                scope = m.get("scope", "")
                if scope:
                    label += f": {scope[:150]}"
                out.append((label, 1.5))
    return out


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

    en_tokens = list(dict.fromkeys(t.lower() for t in _EN_TOKEN.findall(query)))

    # 三个来源并行（各自内部也并行多请求）：整体延迟 = 最慢一路，而非三路之和。
    # 串行版首次可达 15s+（ICD search+对照 6–10s、RxNorm/MeSH 各多请求）；并行后约
    # 等于单路（≈3–5s 首次，命中 1h 缓存后≈0）。顺序保留：ICD → RxNorm → MeSH。
    with ThreadPoolExecutor(max_workers=3) as ex:
        f_icd = ex.submit(_collect_icd, query)
        f_rx = ex.submit(_collect_rxnorm, query, en_tokens)
        f_mesh = ex.submit(_collect_mesh, query, en_tokens)
        results = f_icd.result() + f_rx.result() + f_mesh.result()

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
