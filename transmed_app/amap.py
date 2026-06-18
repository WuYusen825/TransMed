"""高德地图 AMap 封装：医院 POI 搜索、路径规划、配置接口。

Key 类型说明（不要混用）：
  ┌────────────────────┬─────────────────────────────────────────────────┐
  │  应用类型           │  用途                                            │
  ├────────────────────┼─────────────────────────────────────────────────┤
  │  Web 服务 API       │  后端 Python 调用 restapi.amap.com （POI/路径/地理编码）│
  │  Web 端 (JS API)    │  前端浏览器加载 webapi.amap.com/maps （地图展示、路线绘制）│
  │  Android / iOS SDK  │  移动端（本项目不需要）                           │
  └────────────────────┴─────────────────────────────────────────────────┘
  常见错误码：
    10009  USERKEY_PLAT_NOMATCH  —— Key 类型与请求平台不匹配（把 JS Key 用作 Web 服务）
    10008  INVALID_USER_SCODE    —— 签名错误
    10001  INVALID_PARAMS        —— 参数错误
    10003  INVALID_USER_KEY      —— Key 无效或已过期
  申请地址：https://console.amap.com/dev/key/app

如果没有配置 Key 或调用失败，则自动回退到本地 demo 数据（data.py 的 HOSPITALS）。
"""
from __future__ import annotations

import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlencode

import requests

from .config import settings
from .data import HOSPITALS

logger = logging.getLogger(__name__)

_POI_URL = "https://restapi.amap.com/v3/place/text"
_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"
_DIRECTION_WALKING = "https://restapi.amap.com/v3/direction/walking"
_DIRECTION_DRIVING = "https://restapi.amap.com/v3/direction/driving"
_TIMEOUT = 8.0

# POI 分类：医院/综合医院/专科医院
# 详见 https://lbs.amap.com/api/webservice/guide/api/search/#text
_HOSPITAL_TYPES = "090100|090101|090102"

# 高德常见业务错误码 → 人类可读的排错建议
# 参考：https://lbs.amap.com/api/webservice/guide/tools/info
_AMAP_ERR_TIPS: Dict[str, str] = {
    "10001": "INVALID_USER_KEY —— Key 无效/已删除。请到 https://console.amap.com/ 重新生成。",
    "10002": "SERVICE_NOT_AVAILABLE —— 服务不可用（可能是该 Key 未勾选「POI 搜索」权限）。",
    "10003": "DAILY_QUERY_OVER_LIMIT —— 今日调用次数已超过配额上限。",
    "10004": "ACCESS_TOO_FREQUENT —— 调用过于频繁，请稍后重试。",
    "10005": "NO_EFFECTIVE_PRIVILEGE —— Key 缺少权限（请在控制台为该 Key 勾选「Web 服务」）。",
    "10008": "INVALID_USER_SCODE —— 签名校验失败（检查控制台是否要求 MD5 签名）。",
    "10009": "USERKEY_PLAT_NOMATCH —— Key 类型与请求平台不匹配。\n"
             "       → 当前 key 是「JS API」类型，但后端需要「Web 服务」类型。\n"
             "       → 请到 https://console.amap.com/dev/key/app 新建一个应用，\n"
             "         应用类型选择「Web 服务」，用那个 key 填入 TRANSMED_AMAP_KEY 即可。",
    "10010": "IP_QUERY_OUT_OF_LIMIT —— IP 调用超过限制。",
    "10011": "NO_DOMAIN_BINDING —— 当前 Key 未绑定域名（在控制台添加允许的域名）。",
    "10012": "NO_APPROVED —— 应用审核中或未通过。",
    "20000": "INVALID_PARAMS —— 请求参数错误（检查 city / keywords 是否为空）。",
}

# 常见中英文城市（默认搜索范围）
_CITY_ALIASES: Dict[str, str] = {
    "beijing": "北京", "bj": "北京", "bjs": "北京",
    "shanghai": "上海", "sh": "上海",
    "guangzhou": "广州", "gz": "广州",
    "shenzhen": "深圳", "sz": "深圳",
    "hangzhou": "杭州", "hz": "杭州",
    "chengdu": "成都", "cd": "成都",
    "nanjing": "南京", "nj": "南京",
    "wuhan": "武汉", "wh": "武汉",
    "xian": "西安", "xa": "西安",
    "tianjin": "天津", "tj": "天津",
    "chongqing": "重庆", "cq": "重庆",
    "suzhou": "苏州", "sz2": "苏州",
}


def _normalize_city(city: str) -> str:
    if not city:
        return "北京"
    c = city.strip().lower()
    return _CITY_ALIASES.get(c, city.strip())


def _has_web_key() -> bool:
    return bool(settings.AMAP_WEB_KEY and settings.AMAP_WEB_KEY.strip() and
                not settings.AMAP_WEB_KEY.lower().startswith("your-"))


def _parse_lnglat(s: str) -> Tuple[Optional[float], Optional[float]]:
    """把 "lng,lat" 解析为 (lng, lat)。"""
    try:
        lng, lat = s.split(",")
        return float(lng), float(lat)
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# 医院 POI 搜索
# ---------------------------------------------------------------------------
def search_hospitals(keyword: str = "", city: str = "北京", limit: int = 20) -> Dict[str, Any]:
    """调用高德 POI 文本搜索获取医院信息。

    返回：{"hospitals": [...], "count": n, "data_source": "amap" | "demo"}
    每个医院包含：id, name, name_zh, address, phone, rating, distance_km,
                  specialties, insurance, languages, departments, lat, lng
    """
    city_zh = _normalize_city(city)

    if not _has_web_key():
        logger.info("AMAP key not configured — falling back to demo hospitals")
        return _demo_hospitals(city_zh, keyword, limit)

    kw = (keyword or "").strip() or "医院"
    params = {
        "key": settings.AMAP_WEB_KEY,
        "keywords": kw,
        "types": _HOSPITAL_TYPES,
        "city": city_zh,
        "citylimit": "true",
        "extensions": "all",
        "offset": str(max(1, min(limit, 50))),
        "page": 1,
        "output": "json",
    }
    try:
        t0 = time.time()
        resp = requests.get(_POI_URL, params=params, timeout=_TIMEOUT)
        data = resp.json()
        status = str(data.get("status", "0"))
        if status != "1":
            # 高德返回业务错误（如 Key 类型不匹配 / 过期 / 配额不足）
            info = str(data.get("info", "unknown"))
            code = str(data.get("infocode", ""))
            human = _AMAP_ERR_TIPS.get(code, f"{info} (infocode={code})")
            logger.warning(
                "AMAP poi search rejected: status=%s infocode=%s info=%s — %s",
                status, code, info, human,
            )
            return _demo_hospitals(city_zh, keyword, limit, amap_error=human)
        logger.info("AMAP poi search: %s rows in %.2fs",
                    data.get("count", "?"), time.time() - t0)
    except Exception as e:
        logger.warning("AMAP poi search failed: %s", e)
        return _demo_hospitals(city_zh, keyword, limit, amap_error=str(e))

    pois = data.get("pois") or []
    results: List[Dict[str, Any]] = []
    for p in pois:
        if not isinstance(p, dict):
            continue
        lng, lat = _parse_lnglat(p.get("location", ""))
        name = p.get("name") or ""
        addr = p.get("address") or p.get("pname", "") + p.get("cityname", "") + p.get("adname", "")
        phone = (p.get("tel") or "").replace(";", " / ").strip()
        # rating：高德通常放在 biz_ext.rating 下，直接的 rating 可能没有
        # 两个字段都可能是字符串 "4.8" 或空数组 [] / ""
        rating_raw = ""
        biz_ext = p.get("biz_ext") if isinstance(p.get("biz_ext"), dict) else None
        if biz_ext:
            r = biz_ext.get("rating")
            if isinstance(r, str) and r:
                rating_raw = r
            elif isinstance(r, (int, float)) and r:
                rating_raw = str(r)
        if not rating_raw:
            r = p.get("rating")
            if isinstance(r, str) and r:
                rating_raw = r
            elif isinstance(r, (int, float)) and r:
                rating_raw = str(r)
        rating: Optional[float] = None
        try:
            rating = float(rating_raw) if rating_raw else None
        except (ValueError, TypeError):
            rating = None
        # hours： biz_ext 里有时有 open_time
        hours = ""
        if biz_ext:
            ot = biz_ext.get("open_time") or biz_ext.get("opentime2") or ""
            if isinstance(ot, str) and ot:
                hours = ot
        # distance：高德返回字符串米数，有时是 []
        dist_raw = p.get("distance")
        dist_km: Optional[float] = None
        if isinstance(dist_raw, (int, float, str)) and str(dist_raw):
            try:
                dist_km = round(float(dist_raw) / 1000.0, 2)
            except ValueError:
                dist_km = None
        specialties: List[str] = []
        if isinstance(p.get("type"), str):
            # type 形如 "医疗保健服务;综合医院;综合医院"
            for part in p["type"].split("|"):
                subs = part.split(";")
                for s in subs:
                    s = s.strip()
                    if s and s not in specialties and len(s) < 20:
                        specialties.append(s)
        results.append({
            "id": p.get("id") or f"poi-{len(results)}",
            "name": name,
            "name_zh": name,
            "address": addr,
            "address_zh": addr,
            "phone": phone,
            "hours": hours,
            "rating": round(rating, 2) if rating is not None else None,
            "wait_minutes": 0,  # 高德不提供
            "distance_km": dist_km,
            "specialties": specialties[:6],
            "insurance": [],
            "languages": ["Chinese"],
            "departments": [],
            "lat": lat,
            "lng": lng,
        })

    if not results:
        return _demo_hospitals(city_zh, keyword, limit)

    return {"hospitals": results, "count": len(results), "data_source": "amap", "city": city_zh}


def _demo_hospitals(city_zh: str, keyword: str, limit: int, amap_error: Optional[str] = None) -> Dict[str, Any]:
    """本地 demo 数据回退。"""
    kw = (keyword or "").strip()
    results: List[Dict[str, Any]] = []
    for h in HOSPITALS:
        if kw:
            hay = " ".join([
                str(h.get("name", "")), str(h.get("name_zh", "")),
                str(h.get("address", "")), " ".join(h.get("specialties", [])),
            ])
            if kw.lower() not in hay.lower():
                continue
        results.append({
            "id": h["id"],
            "name": h["name"], "name_zh": h.get("name_zh", ""),
            "address": h.get("address", ""), "address_zh": h.get("address_zh", ""),
            "phone": h.get("phone", ""), "hours": h.get("hours", ""),
            "rating": h.get("rating", 0),
            "wait_minutes": h.get("wait_minutes", 0),
            "distance_km": h.get("distance_km", 0),
            "specialties": h.get("specialties", []),
            "insurance": h.get("insurance", []),
            "languages": h.get("languages", []),
            "departments": [
                {"name": d[0], "name_zh": d[1], "wait": d[2] if len(d) > 2 else 0, "fee": 0}
                for d in h.get("departments", [])
            ],
            "lat": h.get("lat"), "lng": h.get("lng"),
        })
        if len(results) >= limit:
            break
    out = {"hospitals": results, "count": len(results), "data_source": "demo", "city": city_zh}
    if amap_error:
        out["amap_error"] = amap_error
    return out


# ---------------------------------------------------------------------------
# 地理编码（城市名 → 中心点经纬度）
# ---------------------------------------------------------------------------
def geocode(address: str) -> Tuple[Optional[float], Optional[float]]:
    if not _has_web_key():
        return None, None
    try:
        params = {"key": settings.AMAP_WEB_KEY, "address": address, "output": "json"}
        resp = requests.get(_GEOCODE_URL, params=params, timeout=_TIMEOUT)
        data = resp.json()
        geocodes = data.get("geocodes") or []
        if not geocodes:
            return None, None
        return _parse_lnglat(geocodes[0].get("location", ""))
    except Exception as e:
        logger.warning("AMAP geocode failed: %s", e)
        return None, None


# ---------------------------------------------------------------------------
# 路径规划（返回简要信息，真正画线在前端用高德 JS API）
# ---------------------------------------------------------------------------
def direction(from_lng: float, from_lat: float,
              to_lng: float, to_lat: float,
              mode: str = "walking") -> Dict[str, Any]:
    """简单的路径规划。前端主要用高德 JS API 画线，这里仅返回距离/耗时。"""
    if not _has_web_key():
        return {"status": "no_key", "distance_m": 0, "duration_min": 0, "steps": []}
    mode = (mode or "walking").lower()
    url = _DIRECTION_DRIVING if mode == "driving" else _DIRECTION_WALKING
    params = {
        "key": settings.AMAP_WEB_KEY,
        "origin": f"{from_lng:.6f},{from_lat:.6f}",
        "destination": f"{to_lng:.6f},{to_lat:.6f}",
        "output": "json",
    }
    try:
        resp = requests.get(url, params=params, timeout=_TIMEOUT)
        data = resp.json()
        route = (data.get("route") or {})
        paths = route.get("paths") or []
        if not paths:
            return {"status": "ok", "distance_m": 0, "duration_min": 0, "steps": []}
        p = paths[0]
        return {
            "status": "ok",
            "distance_m": float(p.get("distance", 0)) or 0,
            "duration_min": round(float(p.get("duration", 0)) / 60.0, 1) if p.get("duration") else 0,
            "steps": [
                {"instruction": s.get("instruction", ""),
                 "distance_m": float(s.get("distance", 0)) or 0}
                for s in (p.get("steps") or [])[:20]
            ],
        }
    except Exception as e:
        logger.warning("AMAP direction failed: %s", e)
        return {"status": "error", "distance_m": 0, "duration_min": 0, "steps": []}


# ---------------------------------------------------------------------------
# 给前端用的配置（只暴露 JS key，不暴露 Web 服务 key）
# ---------------------------------------------------------------------------
def public_config() -> Dict[str, Any]:
    """前端使用的高德配置。对 Web 服务 Key 做一次轻量健康检查，
    如果失败会把原因写到 web_error 字段，前端据此提示用户。"""
    js_key = settings.AMAP_JS_KEY or ""
    has_js = bool(js_key and not js_key.lower().startswith("your-"))
    has_web = _has_web_key()

    web_error: Optional[str] = None
    if has_web:
        try:
            resp = requests.get(
                _POI_URL,
                params={"key": settings.AMAP_WEB_KEY, "keywords": "医院",
                        "city": "北京", "citylimit": "true",
                        "extensions": "base", "offset": 1, "page": 1, "output": "json"},
                timeout=_TIMEOUT,
            )
            data = resp.json()
            if str(data.get("status", "0")) != "1":
                code = str(data.get("infocode", ""))
                info = str(data.get("info", "unknown"))
                web_error = _AMAP_ERR_TIPS.get(code, f"{info} (infocode={code})")
                logger.warning("AMAP web-key health-check failed: %s", web_error)
        except Exception as e:
            web_error = f"网络异常：{e}"
            logger.warning("AMAP web-key health-check error: %s", e)

    return {
        "js_key": js_key,
        "has_js_key": has_js,
        "has_web_key": has_web,
        "web_error": web_error,
        "default_city": "北京",
        "cities": [
            {"name": "北京", "en": "Beijing"},
            {"name": "上海", "en": "Shanghai"},
            {"name": "广州", "en": "Guangzhou"},
            {"name": "深圳", "en": "Shenzhen"},
            {"name": "杭州", "en": "Hangzhou"},
            {"name": "成都", "en": "Chengdu"},
            {"name": "南京", "en": "Nanjing"},
            {"name": "武汉", "en": "Wuhan"},
            {"name": "西安", "en": "Xian"},
            {"name": "天津", "en": "Tianjin"},
        ],
    }
