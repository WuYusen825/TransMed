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
            results = [
                {
                    "name": c.get("name", ""),
                    "rxcui": c.get("rxcui", ""),
                    "score": int(c.get("score", 0)),
                }
                for c in candidates
                if c.get("name")
            ]
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

    # 1. RxNorm: try the query itself then individual long tokens
    tried_rx: set = set()
    for candidate in ([query[:80]] + en_tokens[:3]):
        if candidate in tried_rx or len(candidate) < 3:
            continue
        tried_rx.add(candidate)
        for drug in _rxnorm_approx(candidate)[:2]:
            name = drug.get("name", "")
            rxcui = drug.get("rxcui", "")
            if name:
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

    return deduped[:top_k]
