"""TransMed backend — FastAPI application with real medical data.

Endpoints:
    /health
    /api/translate      — bilingual medical translation (engine + term overlay)
    /api/translate/logs — personal translation history (login required)
    /api/translate/{id}/confirm — confirm a translation (safety loop)
    /api/triage         — symptom triage with department recommendation
    /api/hospitals      — hospital list with filters (specialty, insurance, wait-time)
    /api/hospitals/{id} — hospital detail with departments
    /api/navigation     — indoor navigation from A to B (with path + SVG coords)
    /api/navigation/map — full node/path list for visualisation
    /api/medications    — medication list with detailed info (search)
    /api/medications/{key} — single medication detail
    /api/insurance      — insurance providers + in-network hospitals
    /api/medical_terms  — medical term dictionary (EN↔ZH)
    /api/feedback       — submit feedback (anonymous or login)
    /api/privacy/export — export my personal data (login required)
    /api/privacy/wipe   — remove my personal data (login required)
    /api/stats          — platform stats (counts)
    /api/auth/register  — user registration
    /api/auth/login     — JWT login
    /api/auth/me        — current user
    /api/auth/profile   — update profile
    /api/auth/password  — change password
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path as _Path
from pydantic import BaseModel, EmailStr, Field

from .config import settings
from .database import SessionLocal, engine, Base, get_db
from . import models
from .translator import translate as do_translate, translate_with_rag, risk_level
from .auth import (hash_password, verify_password, create_jwt,
                   decode_jwt, require_current_user, get_current_user_optional)
from .data import (HOSPITALS, TRIAGE_RULES, URGENT_SYMPTOMS, MEDICAL_TERMS,
                   MEDICATIONS, INSURANCE_PROVIDERS, INDOOR_MAP)

# ------------------------------------------------------------------ initialise DB
models.Base.metadata.create_all(bind=engine)
db_init = SessionLocal()
try:
    # default admin
    if not db_init.query(models.User).filter(models.User.email == settings.DEFAULT_ADMIN_EMAIL).first():
        db_init.add(models.User(email=settings.DEFAULT_ADMIN_EMAIL, full_name="Administrator",
                                password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                                role="admin", language="en"))
    # demo user
    if not db_init.query(models.User).filter(models.User.email == "demo@transmed.io").first():
        db_init.add(models.User(email="demo@transmed.io", full_name="Demo User",
                                password_hash=hash_password("demo123"),
                                role="patient", language="en"))
    db_init.commit()
finally:
    db_init.close()

app = FastAPI(title=settings.APP_NAME, version="0.1.0")
app.add_middleware(CORSMiddleware,
                   allow_origins=["*"],  # 包含 null/localhost/任意协议；内部对 credentials 场景会回显真实 Origin
                   allow_methods=["*"],
                   allow_headers=["*"],
                   allow_credentials=True,
                   max_age=3600)

# ——— 挂载前端静态页面：http://127.0.0.1:8000/ 直接打开 TransMed UI ———
_WEB_DIR = _Path(__file__).resolve().parent.parent / "transmed_web"
if _WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_WEB_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def _root():
        return FileResponse(str(_WEB_DIR / "index.html"))

    @app.get("/index.html", include_in_schema=False)
    def _index_html():
        return FileResponse(str(_WEB_DIR / "index.html"))
else:
    logger.warning("transmed_web/ not found at %s — / will serve JSON only", _WEB_DIR)

# 基础日志配置 —— 让翻译引擎的警告/信息能出现在后端日志中
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


# ================================================================== schemas
class HealthOut(BaseModel):
    status: str = "ok"
    hospitals: int
    medications: int
    triage_rules: int
    medical_terms: int
    insurance_providers: int


class TranslateIn(BaseModel):
    text: str
    source: str = "en"
    target: str = "zh"


class TranslateOut(BaseModel):
    translated: str
    confidence: float
    risk_level: str
    matched_terms: List[str]
    source: str
    target: str
    original: str
    engine: str  # online | offline | same-language
    id: Optional[int] = None


class TriageIn(BaseModel):
    symptoms: str
    language: str = "en"


class TriageOut(BaseModel):
    department_en: str
    department_zh: str
    recommendation_en: str
    recommendation_zh: str
    urgent: bool
    matched_symptoms: List[str]


class HospitalOut(BaseModel):
    id: str
    name: str
    name_zh: str
    address: str
    address_zh: str
    phone: str
    hours: str
    rating: float
    wait_minutes: int
    distance_km: float
    lat: Optional[float] = None
    lng: Optional[float] = None
    specialties: List[str]
    insurance: List[str]
    languages: List[str]
    departments: List[Dict[str, Any]]


class NavNode(BaseModel):
    id: str
    label: str
    floor: int
    x: int
    y: int


class NavRoute(BaseModel):
    node_id: str
    instruction: str
    floor: int
    x: int
    y: int


class NavIn(BaseModel):
    hospital_id: str = "default"
    from_node: str = "entrance"
    to: str = "pharmacy"


class NavOut(BaseModel):
    entry: str
    destination: str
    route: List[NavRoute]
    total_distance: float


class MedicationOut(BaseModel):
    key: str
    name: str
    name_zh: str
    category: str
    category_zh: str
    dosage: str
    dosage_zh: str
    warnings: List[str]
    warnings_zh: List[str]
    side_effects: List[str]
    rx_required: bool
    price_cny: int


class InsuranceProvider(BaseModel):
    name: str
    name_zh: str
    website: str
    claims_hotline: str
    notes: str
    notes_zh: str
    coverage_types: List[str]
    in_network_hospitals: List[str]


class MedTerm(BaseModel):
    english: str
    chinese: str
    latin: str


class StatsOut(BaseModel):
    hospitals: int
    medications: int
    triage_rules: int
    medical_terms: int
    insurance_providers: int
    users: int
    translations: int
    urgent_events: int


class LoginIn(BaseModel):
    email: str
    password: str


class RegisterIn(BaseModel):
    email: str
    full_name: str = ""
    password: str
    language: str = "en"
    country: Optional[str] = None


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    language: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


class FeedbackIn(BaseModel):
    rating: int = 5
    comment: str = ""
    category: str = "general"  # general, translation, hospital, navigation, insurance


class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


# ================================================================== utilities
def _serialise_user(u: models.User):
    return {"id": u.id, "email": u.email, "full_name": u.full_name,
            "role": u.role, "language": u.language, "country": u.country,
            "created_at": u.created_at.isoformat() if u.created_at else None}


def _find_hospital(hospital_id: str):
    for h in HOSPITALS:
        if h["id"] == hospital_id:
            return h
    return None


def _hospital_to_out(h: dict) -> HospitalOut:
    def _norm_department(d):
        if isinstance(d, dict):
            return {"name": d.get("name", ""), "name_zh": d.get("name_zh", ""),
                    "wait": d.get("wait", 0), "fee": d.get("fee", 0)}
        # tuple/list format: (name, name_zh, wait[, fee])
        if isinstance(d, (tuple, list)) and len(d) >= 2:
            name = str(d[0])
            name_zh = str(d[1])
            wait = int(d[2]) if len(d) > 2 else 0
            fee = float(d[3]) if len(d) > 3 else 0
            return {"name": name, "name_zh": name_zh, "wait": wait, "fee": fee}
        return {"name": str(d), "name_zh": str(d), "wait": 0, "fee": 0}

    return HospitalOut(
        id=h["id"], name=h["name"], name_zh=h["name_zh"],
        address=h["address"], address_zh=h["address_zh"],
        phone=h.get("phone", ""), hours=h.get("hours", ""),
        rating=h.get("rating", 0), wait_minutes=h.get("wait_minutes", 0),
        distance_km=h.get("distance_km", 0),
        lat=h.get("lat"), lng=h.get("lng"),
        specialties=h.get("specialties", []),
        insurance=h.get("insurance", []),
        languages=h.get("languages", []),
        departments=[_norm_department(d) for d in h.get("departments", [])],
    )


# ================================================================== endpoints
@app.get("/health", response_model=HealthOut)
def health():
    return HealthOut(hospitals=len(HOSPITALS), medications=len(MEDICATIONS),
                     triage_rules=len(TRIAGE_RULES), medical_terms=len(MEDICAL_TERMS),
                     insurance_providers=len(INSURANCE_PROVIDERS))


# -------------------------------------------------------------- translate
@app.post("/api/translate", response_model=TranslateOut)
def translate_api(body: TranslateIn,
                  auth: Optional[str] = Header(default=None, alias="Authorization"),
                  db=Depends(get_db)):
    if not body.text or not body.text.strip():
        raise HTTPException(400, "text is required")
    translated, confidence, matched, engine = do_translate(body.text, body.source, body.target)
    # --- optionally log
    tid = None
    user = None
    if auth and auth.lower().startswith("bearer "):
        try:
            token = auth.split(" ", 1)[1].strip()
            payload = decode_jwt(token)
            user = db.query(models.User).filter(models.User.id == int(payload["sub"])).first()
        except Exception:
            user = None
    if user:
        log = models.TranslationLog(user_id=user.id, source_text=body.text,
                                     translated_text=translated, source_lang=body.source,
                                     target_lang=body.target, confidence=confidence,
                                     risk_level=risk_level(confidence),
                                     matched_terms=",".join(matched[:50]))
        db.add(log); db.commit(); db.refresh(log); tid = log.id
    return TranslateOut(translated=translated, confidence=confidence,
                        risk_level=risk_level(confidence), matched_terms=matched,
                        source=body.source, target=body.target,
                        original=body.text, engine=engine, id=tid)


@app.post("/api/translate/rag")
def translate_rag_api(body: TranslateIn):
    """调试用：返回翻译 + RAG 检索上下文。"""
    if not body.text or not body.text.strip():
        raise HTTPException(400, "text is required")
    return translate_with_rag(body.text, body.source, body.target)


@app.get("/api/translate/config")
def translate_config_api():
    """返回翻译引擎配置信息（不泄露完整 API key）。"""
    api_key = settings.GROQ_API_KEY
    masked = api_key[:6] + "****" + api_key[-4:] if api_key and len(api_key) > 10 else "not set"
    return {
        "engine": "Groq",
        "model": settings.GROQ_MODEL,
        "base_url": settings.GROQ_BASE_URL,
        "api_key_masked": masked,
    }


@app.get("/api/translate/logs")
def my_translation_logs(current_user=Depends(require_current_user), db=Depends(get_db)):
    logs = (db.query(models.TranslationLog)
            .filter(models.TranslationLog.user_id == current_user.id)
            .order_by(models.TranslationLog.created_at.desc()).limit(100).all())
    return [{"id": l.id, "original": l.source_text, "translated": l.translated_text,
             "source": l.source_lang, "target": l.target_lang,
             "confidence": l.confidence, "risk_level": l.risk_level,
             "matched_terms": (l.matched_terms or "").split(",") if l.matched_terms else [],
             "confirmed": l.user_confirmed,
             "created_at": l.created_at.isoformat() if l.created_at else None}
            for l in logs]


@app.post("/api/translate/{log_id}/confirm")
def confirm_translation(log_id: int, current_user=Depends(require_current_user),
                        db=Depends(get_db)):
    log = (db.query(models.TranslationLog)
           .filter(models.TranslationLog.id == log_id,
                   models.TranslationLog.user_id == current_user.id)
           .first())
    if not log:
        raise HTTPException(404, "log not found")
    log.user_confirmed = True
    log.confirmed_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "id": log.id, "confirmed": True}


# -------------------------------------------------------------- triage
@app.post("/api/triage", response_model=TriageOut)
def triage(body: TriageIn,
           auth: Optional[str] = Header(default=None, alias="Authorization"),
           db=Depends(get_db)):
    text = body.symptoms.lower().strip()
    if not text:
        raise HTTPException(400, "symptoms are required")

    matched: List[str] = []
    best_dep_en, best_dep_zh = "General Medicine / Family Practice", "全科 / 内科"
    best_rec_en, best_rec_zh = ("Your symptoms are general. It's recommended to see a family "
                                  "medicine doctor or general practitioner.",
                                 "您的症状比较普遍。建议看全科或内科医生。")
    is_urgent = any(w in text for w in URGENT_SYMPTOMS)
    # check rule by rule
    for key, (dep_en, dep_zh, rec_en, rec_zh, urgent) in TRIAGE_RULES.items():
        if key in text:
            matched.append(key)
            # only set if no earlier (more urgent) match or if this matches specifically
            if urgent or not matched:
                best_dep_en, best_dep_zh = dep_en, dep_zh
                best_rec_en, best_rec_zh = rec_en, rec_zh
            is_urgent = is_urgent or urgent

    if not matched:
        best_rec_en = ("No specific department could be identified from your keywords. "
                        "Please consult a general practitioner or contact our support for a "
                        "more detailed assessment.")
        best_rec_zh = ("根据您输入的关键词未能识别具体科室。建议咨询全科医生，或联系我们的客服 "
                        "进行更详细的评估。")

    result = TriageOut(department_en=best_dep_en, department_zh=best_dep_zh,
                       recommendation_en=best_rec_en, recommendation_zh=best_rec_zh,
                       urgent=is_urgent, matched_symptoms=matched)

    # 如果用户已登录，自动保存分诊记录
    uid = None
    if auth and auth.lower().startswith("bearer "):
        try:
            token = auth.split(" ", 1)[1].strip()
            payload = decode_jwt(token)
            uid = int(payload["sub"])
        except Exception:
            uid = None
    if uid:
        try:
            rec = models.TriageRecord(user_id=uid, symptoms=body.symptoms,
                                      department_en=result.department_en,
                                      department_zh=result.department_zh,
                                      is_urgent=result.urgent,
                                      matched_terms=",".join(result.matched_symptoms[:20]))
            db.add(rec); db.commit()
        except Exception:
            pass
    return result


# -------------------------------------------------------------- hospitals
@app.get("/api/hospitals")
def hospitals_list(specialty: Optional[str] = None, insurance: Optional[str] = None,
                    language: Optional[str] = None, urgent: bool = False,
                    max_wait: Optional[int] = None, min_rating: Optional[float] = None):
    results = []
    for h in HOSPITALS:
        if specialty and specialty not in h.get("specialties", []):
            continue
        if insurance and insurance not in h.get("insurance", []):
            continue
        if language and language not in h.get("languages", []) and language.lower() not in map(str.lower, h.get("languages", [])):
            continue
        if urgent and h.get("wait_minutes", 999) > 30:
            continue
        if max_wait is not None and h.get("wait_minutes", 0) > max_wait:
            continue
        if min_rating is not None and h.get("rating", 0) < min_rating:
            continue
        results.append(_hospital_to_out(h))
    results.sort(key=lambda x: (x.rating, -x.wait_minutes), reverse=True)
    return {"hospitals": results, "count": len(results)}


@app.get("/api/hospitals/{hospital_id}")
def hospital_detail(hospital_id: str):
    h = _find_hospital(hospital_id)
    if not h:
        raise HTTPException(404, "hospital not found")
    return _hospital_to_out(h)


# -------------------------------------------------------------- navigation
def _build_map_for(hospital_id: str):
    """Return nodes/paths. For now we use INDOOR_MAP for every hospital — but
    it's easy to extend to per-hospital maps later."""
    nodes = {n["id"]: n for n in INDOOR_MAP["nodes"]}
    paths = list(INDOOR_MAP["paths"])
    return nodes, paths


def _shortest_path(from_id: str, to_id: str, nodes: dict, paths):
    """BFS with weighted distance (using Euclidean coords)."""
    if from_id not in nodes or to_id not in nodes:
        return None, 0
    # build adjacency
    adj: Dict[str, List[Dict[str, Any]]] = {nid: [] for nid in nodes}
    for (a, b, desc) in paths:
        if a in nodes and b in nodes:
            ax, ay = nodes[a]["x"], nodes[a]["y"]
            bx, by = nodes[b]["x"], nodes[b]["y"]
            dist = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
            adj[a].append({"to": b, "desc": desc, "dist": dist})
            adj[b].append({"to": a, "desc": f"← {desc}", "dist": dist})

    # Dijkstra (small graph — fine)
    import heapq
    dists = {nid: float("inf") for nid in nodes}
    parents: Dict[str, Optional[str]] = {nid: None for nid in nodes}
    descs: Dict[str, str] = {nid: "" for nid in nodes}
    dists[from_id] = 0
    pq = [(0, from_id)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dists[u]:
            continue
        for edge in adj[u]:
            nd = d + edge["dist"]
            if nd < dists[edge["to"]]:
                dists[edge["to"]] = nd
                parents[edge["to"]] = u
                descs[edge["to"]] = edge["desc"]
                heapq.heappush(pq, (nd, edge["to"]))

    if dists[to_id] == float("inf"):
        return None, 0
    # rebuild path
    path_ids: List[str] = []
    cur = to_id
    while cur is not None:
        path_ids.append(cur)
        cur = parents[cur]
    path_ids.reverse()
    return path_ids, dists[to_id]


@app.post("/api/navigation", response_model=NavOut)
def navigate_post(body: NavIn):
    return _navigate_impl(body.hospital_id, body.from_node, body.to)


@app.get("/api/navigation")
def navigate_get(hospital_id: str = "ufh", from_node: str = "entrance", to: str = "pharmacy"):
    return _navigate_impl(hospital_id, from_node, to)


def _navigate_impl(hospital_id: str, from_node: str, to: str):
    nodes, paths = _build_map_for(hospital_id)
    if from_node not in nodes:
        raise HTTPException(404, f"start node '{from_node}' not found. available: {list(nodes.keys())[:20]}")
    if to not in nodes:
        raise HTTPException(404, f"destination node '{to}' not found. available: {list(nodes.keys())[:20]}")

    path_ids, total = _shortest_path(from_node, to, nodes, paths)
    if not path_ids:
        raise HTTPException(400, "no path found between nodes")

    route: List[NavRoute] = []
    for i, pid in enumerate(path_ids):
        n = nodes[pid]
        instr = ""
        if i == 0:
            instr = f"You are at {n['label']} — start"
        elif i == len(path_ids) - 1:
            instr = f"You have reached {n['label']}"
        else:
            instr = f"Proceed to {n['label']}"
        route.append(NavRoute(node_id=pid, instruction=instr,
                               floor=n["floor"], x=n["x"], y=n["y"]))
    return NavOut(entry=from_node, destination=to, route=route,
                  total_distance=round(total, 1))


@app.get("/api/navigation/map")
def nav_map(hospital_id: str = "ufh"):
    nodes, paths = _build_map_for(hospital_id)
    return {"hospital_id": hospital_id,
            "nodes": [{"id": n["id"], "label": n["label"], "floor": n["floor"],
                       "x": n["x"], "y": n["y"]} for n in nodes.values()],
            "paths": [{"from": p[0], "to": p[1], "description": p[2]} for p in paths]}


@app.get("/api/languages")
def languages():
    return {
        "en": "English", "zh": "中文", "ja": "日本語", "ko": "한국어",
        "fr": "Français", "de": "Deutsch", "es": "Español", "it": "Italiano",
        "ru": "Русский", "ar": "العربية", "hi": "हिन्दी", "pt": "Português",
        "nl": "Nederlands", "tr": "Türkçe", "vi": "Tiếng Việt", "th": "ไทย",
    }


# -------------------------------------------------------------- medications
@app.get("/api/medications")
def medications_list(q: Optional[str] = None, rx_required: Optional[bool] = None,
                     category: Optional[str] = None):
    results = []
    for key, m in MEDICATIONS.items():
        if rx_required is not None and m.get("rx_required") != rx_required:
            continue
        if category and category.lower() not in (m.get("category", "") + " " + m.get("category_zh", "")).lower():
            continue
        if q:
            ql = q.lower()
            haystack = " ".join([str(v) for v in [m.get("name"), m.get("name_zh"), m.get("category"),
                                                   m.get("category_zh"), key] if v])
            if ql not in haystack.lower():
                continue
        results.append(MedicationOut(
            key=key, name=m["name"], name_zh=m.get("name_zh", ""),
            category=m.get("category", ""), category_zh=m.get("category_zh", ""),
            dosage=m.get("dosage", ""), dosage_zh=m.get("dosage_zh", ""),
            warnings=m.get("warnings", []), warnings_zh=m.get("warnings_zh", []),
            side_effects=m.get("side_effects", []),
            rx_required=m.get("rx_required", False), price_cny=m.get("price_cny", 0)
        ))
    results.sort(key=lambda x: (x.rx_required, x.name_zh))
    return {"medications": results, "count": len(results)}


class MedRecordIn(BaseModel):
    medication_key: str
    custom_name: Optional[str] = None
    dosage: str = ""
    reminder_times: str = ""
    notes: str = ""
    is_active: bool = True


@app.get("/api/medications/records")
@app.get("/api/medications/record")
def med_records_list(current_user=Depends(require_current_user), db=Depends(get_db)):
    recs = (db.query(models.Medication)
            .filter(models.Medication.user_id == current_user.id)
            .order_by(models.Medication.created_at.desc()).all())
    return [{"id": r.id, "medication_key": r.medication_key, "custom_name": r.custom_name,
             "dosage": r.dosage, "reminder_times": r.reminder_times, "notes": r.notes,
             "is_active": r.is_active,
             "created_at": r.created_at.isoformat() if r.created_at else None} for r in recs]


@app.post("/api/medications/record")
def med_record_add(body: MedRecordIn,
                   current_user=Depends(require_current_user), db=Depends(get_db)):
    key = body.medication_key.strip().lower()
    if key not in MEDICATIONS:
        raise HTTPException(400, f"unknown medication key: {body.medication_key}. Available: {', '.join(sorted(MEDICATIONS.keys())[:20])}")
    r = models.Medication(user_id=current_user.id, medication_key=key,
                                custom_name=body.custom_name, dosage=body.dosage,
                                reminder_times=body.reminder_times, notes=body.notes,
                                is_active=body.is_active)
    db.add(r); db.commit(); db.refresh(r)
    return {"id": r.id, "ok": True}


@app.put("/api/medications/record/{rid}")
def med_record_update(rid: int, body: MedRecordIn,
                      current_user=Depends(require_current_user), db=Depends(get_db)):
    r = (db.query(models.Medication)
         .filter(models.Medication.id == rid,
                 models.Medication.user_id == current_user.id).first())
    if not r:
        raise HTTPException(404, "record not found")
    r.medication_key = body.medication_key.strip().lower()
    r.custom_name = body.custom_name
    r.dosage = body.dosage
    r.reminder_times = body.reminder_times
    r.notes = body.notes
    r.is_active = body.is_active
    db.commit()
    return {"ok": True, "id": r.id}


@app.delete("/api/medications/record/{rid}")
def med_record_delete(rid: int,
                      current_user=Depends(require_current_user), db=Depends(get_db)):
    r = (db.query(models.Medication)
         .filter(models.Medication.id == rid,
                 models.Medication.user_id == current_user.id).first())
    if not r:
        raise HTTPException(404, "record not found")
    db.delete(r); db.commit()
    return {"ok": True, "id": rid}


@app.get("/api/medications/{key}")
def medication_detail(key: str):
    m = MEDICATIONS.get(key)
    if not m:
        raise HTTPException(404, "medication not found. try keys like paracetamol, ibuprofen, amoxicillin, metformin, sertraline...")
    return MedicationOut(
        key=key, name=m["name"], name_zh=m.get("name_zh", ""),
        category=m.get("category", ""), category_zh=m.get("category_zh", ""),
        dosage=m.get("dosage", ""), dosage_zh=m.get("dosage_zh", ""),
        warnings=m.get("warnings", []), warnings_zh=m.get("warnings_zh", []),
        side_effects=m.get("side_effects", []),
        rx_required=m.get("rx_required", False), price_cny=m.get("price_cny", 0)
    )


# -------------------------------------------------------------- insurance
@app.get("/api/insurance")
def insurance_list(provider: Optional[str] = None):
    results = []
    for p in INSURANCE_PROVIDERS:
        if provider and provider.lower() not in p["name"].lower():
            continue
        results.append(InsuranceProvider(
            name=p["name"], name_zh=p["name_zh"], website=p["website"],
            claims_hotline=p.get("claims_hotline", ""),
            notes=p.get("notes", ""), notes_zh=p.get("notes_zh", ""),
            coverage_types=p.get("coverage_types", []),
            in_network_hospitals=p.get("in_network_hospitals", [])
        ))
    return {"providers": results, "count": len(results)}


# -------------------------------------------------------------- medical terms
@app.get("/api/medical_terms")
def medical_terms_list(q: Optional[str] = None, limit: int = 50):
    results = []
    for en, (zh, latin) in MEDICAL_TERMS.items():
        if q and q.lower() not in en and (not zh or q not in zh):
            continue
        results.append(MedTerm(english=en, chinese=zh, latin=latin))
        if len(results) >= limit:
            break
    return {"terms": results, "count": min(len(results), limit),
            "total_available": len(MEDICAL_TERMS)}


# -------------------------------------------------------------- feedback
@app.post("/api/feedback")
def feedback(body: FeedbackIn,
             auth: Optional[str] = Header(default=None, alias="Authorization"),
             db=Depends(get_db)):
    uid = None
    if auth and auth.lower().startswith("bearer "):
        try:
            token = auth.split(" ", 1)[1].strip()
            payload = decode_jwt(token)
            uid = int(payload["sub"])
        except Exception:
            uid = None
    fb = models.Feedback(user_id=uid, rating=body.rating, content=body.comment,
                         category=body.category)
    db.add(fb); db.commit()
    return {"ok": True, "id": fb.id}


# -------------------------------------------------------------- privacy
@app.get("/api/privacy/export")
def privacy_export(current_user=Depends(require_current_user), db=Depends(get_db)):
    logs = db.query(models.TranslationLog).filter(models.TranslationLog.user_id == current_user.id).all()
    meds = db.query(models.Medication).filter(models.Medication.user_id == current_user.id).all()
    claims = db.query(models.InsuranceClaim).filter(models.InsuranceClaim.user_id == current_user.id).all()
    triages = db.query(models.TriageRecord).filter(models.TriageRecord.user_id == current_user.id).all()
    feedback = db.query(models.Feedback).filter(models.Feedback.user_id == current_user.id).all()
    return {
        "user": _serialise_user(current_user),
        "translations": [{"id": l.id, "original": l.source_text, "translated": l.translated_text,
                          "from": l.source_lang, "to": l.target_lang,
                          "confidence": l.confidence, "risk_level": l.risk_level,
                          "confirmed": l.user_confirmed, "created_at": l.created_at.isoformat() if l.created_at else None}
                         for l in logs],
        "medication_records": [{"id": m.id, "medication_key": m.medication_key, "dosage": m.dosage,
                                "notes": m.notes, "is_active": m.is_active,
                                "created_at": m.created_at.isoformat() if m.created_at else None}
                               for m in meds],
        "insurance_claims": [{"id": c.id, "provider": c.provider, "status": c.status,
                              "amount": c.estimated_amount, "notes": c.notes,
                              "created_at": c.created_at.isoformat() if c.created_at else None}
                            for c in claims],
        "triages": [{"id": t.id, "symptoms": t.symptoms, "department": t.department_en,
                     "urgent": t.is_urgent, "created_at": t.created_at.isoformat() if t.created_at else None}
                    for t in triages],
        "feedback": [{"id": f.id, "rating": f.rating, "comment": f.content,
                      "category": f.category, "created_at": f.created_at.isoformat() if f.created_at else None}
                     for f in feedback],
    }


@app.post("/api/privacy/wipe")
def privacy_wipe(current_user=Depends(require_current_user), db=Depends(get_db)):
    # delete all user data but keep the account (otherwise user couldn't re-login)
    db.query(models.TranslationLog).filter(models.TranslationLog.user_id == current_user.id).delete()
    db.query(models.Medication).filter(models.Medication.user_id == current_user.id).delete()
    db.query(models.InsuranceClaim).filter(models.InsuranceClaim.user_id == current_user.id).delete()
    db.query(models.TriageRecord).filter(models.TriageRecord.user_id == current_user.id).delete()
    db.query(models.Feedback).filter(models.Feedback.user_id == current_user.id).delete()
    db.commit()
    return {"ok": True, "message": "All personal data wiped"}


# -------------------------------------------------------------- stats
@app.get("/api/stats", response_model=StatsOut)
def stats(db=Depends(get_db)):
    return StatsOut(
        hospitals=len(HOSPITALS), medications=len(MEDICATIONS),
        triage_rules=len(TRIAGE_RULES), medical_terms=len(MEDICAL_TERMS),
        insurance_providers=len(INSURANCE_PROVIDERS),
        users=db.query(models.User).count(),
        translations=db.query(models.TranslationLog).count(),
        urgent_events=db.query(models.TriageRecord).filter(models.TriageRecord.is_urgent == True).count(),
    )


# -------------------------------------------------------------- auth
@app.post("/api/auth/register", response_model=AuthOut)
def register(body: RegisterIn, db=Depends(get_db)):
    if db.query(models.User).filter(models.User.email == body.email).first():
        raise HTTPException(409, "email already registered")
    if len(body.password) < 6:
        raise HTTPException(400, "password must be at least 6 characters")
    user = models.User(email=body.email, full_name=body.full_name or body.email.split("@")[0],
                       password_hash=hash_password(body.password),
                       language=body.language or "en",
                       country=body.country, role="patient")
    db.add(user); db.commit(); db.refresh(user)
    token = create_jwt(user.id, user.email, user.role)
    return AuthOut(access_token=token, user=_serialise_user(user))


@app.post("/api/auth/login", response_model=AuthOut)
def login(body: LoginIn, db=Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "invalid email or password")
    token = create_jwt(user.id, user.email, user.role)
    return AuthOut(access_token=token, user=_serialise_user(user))


@app.get("/api/auth/me")
def me(current_user=Depends(require_current_user)):
    return _serialise_user(current_user)


@app.put("/api/auth/profile")
def update_profile(body: ProfileUpdate,
                   current_user=Depends(require_current_user), db=Depends(get_db)):
    if body.full_name is not None:
        current_user.full_name = body.full_name
    if body.language is not None:
        current_user.language = body.language
    if body.country is not None:
        current_user.country = body.country
    db.commit(); db.refresh(current_user)
    return _serialise_user(current_user)


@app.post("/api/auth/password")
def change_password(body: PasswordChange,
                    current_user=Depends(require_current_user), db=Depends(get_db)):
    if not verify_password(body.old_password, current_user.password_hash):
        raise HTTPException(401, "old password is wrong")
    if len(body.new_password) < 6:
        raise HTTPException(400, "new password must be at least 6 characters")
    current_user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}


# -------------------------------------------------------------- insurance claims
class ClaimIn(BaseModel):
    provider: str
    status: str = "draft"
    estimated_amount: Optional[float] = None
    notes: str = ""


@app.get("/api/insurance/claims")
def claims_list(current_user=Depends(require_current_user), db=Depends(get_db)):
    recs = (db.query(models.InsuranceClaim)
            .filter(models.InsuranceClaim.user_id == current_user.id)
            .order_by(models.InsuranceClaim.created_at.desc()).all())
    return [{"id": r.id, "provider": r.provider, "status": r.status,
             "amount": r.estimated_amount, "notes": r.notes,
             "created_at": r.created_at.isoformat() if r.created_at else None} for r in recs]


@app.post("/api/insurance/claims")
def claim_add(body: ClaimIn,
              current_user=Depends(require_current_user), db=Depends(get_db)):
    r = models.InsuranceClaim(user_id=current_user.id, provider=body.provider,
                              status=body.status, estimated_amount=body.estimated_amount or 0,
                              notes=body.notes)
    db.add(r); db.commit(); db.refresh(r)
    return {"id": r.id, "ok": True}


@app.put("/api/insurance/claims/{cid}")
def claim_update(cid: int, body: ClaimIn,
                 current_user=Depends(require_current_user), db=Depends(get_db)):
    r = (db.query(models.InsuranceClaim)
         .filter(models.InsuranceClaim.id == cid,
                 models.InsuranceClaim.user_id == current_user.id).first())
    if not r:
        raise HTTPException(404, "not found")
    r.provider = body.provider; r.status = body.status
    r.estimated_amount = body.estimated_amount or 0; r.notes = body.notes
    db.commit()
    return {"ok": True, "id": r.id}


@app.delete("/api/insurance/claims/{cid}")
def claim_delete(cid: int,
                 current_user=Depends(require_current_user), db=Depends(get_db)):
    r = (db.query(models.InsuranceClaim)
         .filter(models.InsuranceClaim.id == cid,
                 models.InsuranceClaim.user_id == current_user.id).first())
    if not r:
        raise HTTPException(404, "not found")
    db.delete(r); db.commit()
    return {"ok": True, "id": cid}


# -------------------------------------------------------------- triage records
@app.post("/api/triage/record")
def triage_record(body: TriageIn,
                  auth: Optional[str] = Header(default=None, alias="Authorization"),
                  db=Depends(get_db)):
    result = triage(body)  # reuse existing triage logic
    uid = None
    if auth and auth.lower().startswith("bearer "):
        try:
            token = auth.split(" ", 1)[1].strip()
            payload = decode_jwt(token)
            uid = int(payload["sub"])
        except Exception:
            uid = None
    if uid:
        rec = models.TriageRecord(user_id=uid, symptoms=body.symptoms,
                                  department_en=result.department_en,
                                  department_zh=result.department_zh,
                                  is_urgent=result.urgent,
                                  matched_terms=",".join(result.matched_symptoms[:20]))
        db.add(rec); db.commit()
        return {"ok": True, "record_id": rec.id, "result": result}
    return {"ok": True, "message": "triage computed (not logged — login to save)",
            "result": result}


@app.get("/api/triage/records")
def triage_records_list(current_user=Depends(require_current_user), db=Depends(get_db)):
    recs = (db.query(models.TriageRecord)
            .filter(models.TriageRecord.user_id == current_user.id)
            .order_by(models.TriageRecord.created_at.desc()).limit(50).all())
    return [{"id": r.id, "symptoms": r.symptoms, "department": r.department_en,
             "department_zh": r.department_zh, "urgent": r.is_urgent,
             "matched_terms": (r.matched_terms or "").split(",") if r.matched_terms else [],
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in recs]
