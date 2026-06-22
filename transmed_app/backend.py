"""TransMed backend — FastAPI application with real medical data.

Endpoints:
    /health
    /api/translate      — bilingual medical translation (engine + term overlay)
    /api/translate/logs — personal translation history (login required)
    /api/translate/{id}/confirm — confirm a translation (safety loop)
    /api/triage         — symptom triage with department recommendation
    /api/hospitals      — hospital list with filters (specialty, wait-time)
    /api/hospitals/{id} — hospital detail with departments
    /api/medications    — medication list with detailed info (search)
    /api/medications/{key} — single medication detail
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
                   MEDICATIONS,
                   SYMPTOM_TO_SPECIALTIES, SPECIALTY_ALIASES, HOSPITAL_STRENGTH)
from .corpus_medical import MEDICAL_CORPUS as _MEDICAL_CORPUS
from . import reviews as _reviews
from . import amap as _amap

# 真实可检索的医学术语总量 = 基础词典(MEDICAL_TERMS) + ICD-10 专业语料(MEDICAL_CORPUS)
TOTAL_MEDICAL_TERMS = len(MEDICAL_TERMS) + len(_MEDICAL_CORPUS)

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


class TranslateIn(BaseModel):
    text: str
    source: str = "en"
    target: str = "zh"


class TranslateOut(BaseModel):
    translated: str
    confidence: float
    risk_level: str
    matched_terms: List[str]
    rag_context: List[str] = []
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
    languages: List[str]
    departments: List[Dict[str, Any]]


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


class MedTerm(BaseModel):
    english: str
    chinese: str
    latin: str


class StatsOut(BaseModel):
    hospitals: int
    medications: int
    triage_rules: int
    medical_terms: int
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
    category: str = "general"  # general, translation, hospital, navigation


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
        languages=h.get("languages", []),
        departments=[_norm_department(d) for d in h.get("departments", [])],
    )


# ================================================================== endpoints
@app.get("/health", response_model=HealthOut)
def health():
    return HealthOut(hospitals=len(HOSPITALS), medications=len(MEDICATIONS),
                     triage_rules=len(TRIAGE_RULES), medical_terms=TOTAL_MEDICAL_TERMS)


# -------------------------------------------------------------- translate
@app.post("/api/translate", response_model=TranslateOut)
def translate_api(body: TranslateIn,
                  auth: Optional[str] = Header(default=None, alias="Authorization"),
                  db=Depends(get_db)):
    if not body.text or not body.text.strip():
        raise HTTPException(400, "text is required")
    translated, confidence, matched, engine, rag_ctx = do_translate(body.text, body.source, body.target)
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
                        rag_context=rag_ctx,
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
    """返回翻译引擎配置与在线状态（不泄露完整 API key）。"""
    api_key = settings.GROQ_API_KEY
    masked = api_key[:6] + "****" + api_key[-4:] if api_key and len(api_key) > 10 else "not set"
    status = "online" if api_key else "offline"
    error_message = None

    if api_key:
        try:
            import requests
            test_resp = requests.get(
                settings.GROQ_BASE_URL.rstrip("/") + "/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=6.0,
            )
            if test_resp.status_code == 200:
                status = "online"
            else:
                status = "error"
                try:
                    msg = test_resp.json().get("error", {}).get("message") or test_resp.text[:120]
                except Exception:
                    msg = f"HTTP {test_resp.status_code}"
                error_message = f"Groq API returned HTTP {test_resp.status_code}: {msg}"
                logger.warning("Groq key health-check failed: HTTP %s — %s",
                               test_resp.status_code, error_message)
        except Exception as e:
            status = "error"
            error_message = f"Network error reaching Groq: {e}"
            logger.warning("Groq health-check network error: %s", e)

    return {
        "engine": "Groq",
        "model": settings.GROQ_MODEL,
        "base_url": settings.GROQ_BASE_URL,
        "api_key_masked": masked,
        "api_key_configured": bool(api_key),
        "status": status,          # online | offline | error
        "error_message": error_message,
        "fallback": "本地术语匹配（专业词替换，非 AI 完整翻译）" if status != "online" else None,
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


# ============================================================================
# 推荐引擎辅助函数
# ============================================================================
def _hospital_specialty_canonical(text: str) -> Optional[str]:
    """Return canonical specialty name if text matches any alias. Case-insensitive."""
    if not text:
        return None
    t = text.strip().lower()
    for canonical, aliases in SPECIALTY_ALIASES.items():
        if t == canonical.lower():
            return canonical
    for canonical, aliases in SPECIALTY_ALIASES.items():
        for alias in aliases:
            if t == alias.lower():
                return canonical
    # substring fallback (slower): scan all aliases for substring
    for canonical, aliases in SPECIALTY_ALIASES.items():
        for alias in aliases:
            alias_l = alias.lower()
            if alias_l and (alias_l in text or text in alias_l):
                return canonical
    return None


def _parse_symptoms_to_specialty_scores(text: str) -> dict[str, float]:
    """Parse symptoms text → {canonical_specialty: score}.

    Algorithm:
      - Iterate over SYMPTOM_TO_SPECIALTIES keys.
      - For each keyword found add weight.
      - Return aggregated score per specialty.
    """
    if not text:
        return {}
    t = text.lower()
    scores: dict[str, float] = {}
    matched_symptoms: List[str] = []
    for key, info in SYMPTOM_TO_SPECIALTIES.items():
        if key in t:
            matched_symptoms.append(key)
            w = float(info.get("weight", 50))
            for sp in info.get("specialties", []):
                scores[sp] = scores.get(sp, 0.0) + w
    return scores


# Keywords in hospital name → specialty boost. If any token appears in hospital
# name/zh-name, treat hospital as having that specialty with the given score.
_HOSPITAL_KEYWORD_TO_SPECIALTY: dict[str, list[tuple[str, float]]] = {
    "obstetrics": [("Obstetrics & Gynecology", 90.0), ("Gynecology", 85.0), ("Pediatrics", 70.0)],
    "gynecology": [("Obstetrics & Gynecology", 90.0), ("Gynecology", 85.0)],
    "妇产科": [("Obstetrics & Gynecology", 90.0), ("Gynecology", 85.0), ("Pediatrics", 70.0)],
    "妇产": [("Obstetrics & Gynecology", 85.0), ("Gynecology", 80.0)],
    "maternity": [("Obstetrics & Gynecology", 85.0), ("Gynecology", 80.0)],
    "child": [("Pediatrics", 90.0), ("Pediatric Surgery", 75.0)],
    "children": [("Pediatrics", 90.0), ("Pediatric Surgery", 75.0)],
    "pediatric": [("Pediatrics", 90.0), ("Pediatric Surgery", 75.0)],
    "儿科": [("Pediatrics", 90.0), ("Pediatric Surgery", 70.0)],
    "儿研": [("Pediatrics", 90.0)],
    "stomatology": [("Dental", 95.0)],
    "dental": [("Dental", 90.0), ("Oral Surgery", 85.0)],
    "口腔": [("Dental", 95.0), ("Oral Surgery", 85.0)],
    "tooth": [("Dental", 80.0)],
    "tongrentang": [("Traditional Chinese Medicine", 90.0), ("Internal Medicine", 60.0), ("Dermatology", 65.0)],
    "同仁堂": [("Traditional Chinese Medicine", 90.0), ("Internal Medicine", 65.0), ("Dermatology", 65.0)],
    "中医": [("Traditional Chinese Medicine", 90.0), ("Internal Medicine", 60.0)],
    "traditional chinese": [("Traditional Chinese Medicine", 90.0)],
    "ophthalmology": [("Ophthalmology", 95.0)],
    "eye hospital": [("Ophthalmology", 90.0)],
    "同仁": [("Ophthalmology", 95.0), ("ENT", 90.0)],
    "tongren": [("Ophthalmology", 90.0), ("ENT", 85.0)],
    "ent": [("ENT", 90.0)],
    "耳鼻喉": [("ENT", 90.0)],
    "cancer": [("Oncology", 95.0), ("Surgical Oncology", 85.0)],
    "肿瘤": [("Oncology", 95.0), ("Surgical Oncology", 85.0)],
    "fuwai": [("Cardiology", 95.0), ("Cardiovascular Surgery", 90.0), ("Emergency", 80.0)],
    "阜外": [("Cardiology", 95.0), ("Cardiovascular Surgery", 90.0), ("Emergency", 80.0)],
    "心脏": [("Cardiology", 90.0), ("Cardiovascular Surgery", 85.0)],
    "心血管": [("Cardiology", 90.0), ("Cardiovascular Surgery", 85.0)],
    "tiantan": [("Neurology", 95.0), ("Neurosurgery", 90.0)],
    "天坛": [("Neurology", 95.0), ("Neurosurgery", 90.0)],
    "神经": [("Neurology", 85.0), ("Neurosurgery", 80.0)],
    "union medical": [("Internal Medicine", 90.0), ("Cardiology", 90.0), ("Neurology", 95.0), ("Pediatrics", 75.0), ("Oncology", 90.0), ("Emergency", 90.0)],
    "协和": [("Internal Medicine", 90.0), ("Cardiology", 90.0), ("Neurology", 90.0), ("Pediatrics", 75.0), ("Oncology", 90.0), ("Emergency", 90.0), ("Endocrinology", 85.0), ("Rheumatology", 75.0)],
    "peking union": [("Internal Medicine", 90.0), ("Cardiology", 90.0), ("Neurology", 95.0), ("Oncology", 90.0), ("Emergency", 90.0)],
    "beijing hospital": [("Geriatrics", 95.0), ("Cardiology", 85.0), ("Endocrinology", 90.0), ("Internal Medicine", 90.0), ("Neurology", 80.0)],
    "北京医院": [("Geriatrics", 95.0), ("Cardiology", 85.0), ("Endocrinology", 90.0), ("Internal Medicine", 90.0), ("Neurology", 80.0)],
    "中日": [("Respiratory", 85.0), ("Internal Medicine", 80.0), ("Cardiology", 75.0)],
    "china-japan": [("Pulmonary / Respiratory", 85.0), ("Internal Medicine", 80.0), ("Cardiology", 75.0)],
    "第三医院": [("Orthopedics", 95.0), ("Sports Medicine", 85.0), ("Cardiology", 75.0), ("Ophthalmology", 70.0)],
    "北医三院": [("Orthopedics", 95.0), ("Sports Medicine", 85.0)],
    "pku 3rd": [("Orthopedics", 95.0), ("Sports Medicine", 85.0)],
    "people's hospital": [("Internal Medicine", 85.0), ("Cardiology", 80.0), ("Hematology", 75.0)],
    "人民医院": [("Internal Medicine", 85.0), ("Cardiology", 80.0), ("Hematology", 75.0)],
    "first hospital": [("Internal Medicine", 85.0), ("General Surgery", 80.0), ("Cardiology", 75.0)],
    "骨科": [("Orthopedics", 90.0)],
    "皮肤": [("Dermatology", 90.0)],
    "psychiatric": [("Mental Health / Psychiatry", 90.0)],
    "精神": [("Mental Health / Psychiatry", 90.0)],
}


def _hospital_has_specialty(hospital: dict, canonical_specialty: str) -> float:
    """Return 'match strength' (0-100) of a hospital for a canonical specialty."""
    hid = hospital.get("id", "") or ""
    name = (hospital.get("name") or "") + " " + (hospital.get("name_zh") or "")
    name_l = name.lower()

    if hid and hid in HOSPITAL_STRENGTH:
        strength = HOSPITAL_STRENGTH.get(hid, {})
        if canonical_specialty in strength:
            return float(strength[canonical_specialty])

    # keyword → specialty direct map
    kw_scores: list[float] = []
    for keyword, tuples in _HOSPITAL_KEYWORD_TO_SPECIALTY.items():
        if keyword and keyword in name_l:
            for sp, score in tuples:
                if sp == canonical_specialty:
                    kw_scores.append(score)
    if kw_scores:
        return float(max(kw_scores))

    sp_list = [s for s in hospital.get("specialties", [])]
    dept_list = []
    for d in hospital.get("departments", []):
        if isinstance(d, (tuple, list)) and len(d) >= 2:
            dept_list.append(str(d[0]))
        elif isinstance(d, dict):
            dept_list.append(str(d.get("name", "")))

    aliases = SPECIALTY_ALIASES.get(canonical_specialty, [])
    aliases_lower = [a.lower() for a in aliases]
    candidate_names = [canonical_specialty.lower()] + aliases_lower
    found: List[str] = []
    for sp in sp_list + dept_list:
        if not isinstance(sp, str):
            continue
        sp_l = sp.lower()
        if sp_l in candidate_names:
            found.append(sp)
            continue
        for alias_l in aliases_lower:
            if alias_l and (sp_l == alias_l or alias_l in sp_l or sp_l in alias_l):
                found.append(sp)
                break
    if found:
        return 60.0
    return 10.0


# --------------------------------------------------------------------------
# 权威专科榜单（依据复旦版《中国医院专科声誉排行榜》+ 国家临床重点专科，北京）。
# 作用：按「症状 → 专科」推荐时，确保该专科的全国领先医院进入候选并排在前列，
# 并给出事实型理由（医院等级 / 专科全国领先），不杜撰评分或点评数量。
# frag = 用于在医院名中做子串匹配的判别片段；q = 缺失时按名检索高德的查询词。
# --------------------------------------------------------------------------
SPECIALTY_LEADERS: dict[str, list[dict]] = {
    "Cardiology": [{"q": "中国医学科学院阜外医院", "frag": "阜外"}, {"q": "北京安贞医院", "frag": "安贞"}],
    "Cardiovascular Surgery": [{"q": "中国医学科学院阜外医院", "frag": "阜外"}, {"q": "北京安贞医院", "frag": "安贞"}],
    "Neurology": [{"q": "首都医科大学宣武医院", "frag": "宣武"}, {"q": "北京天坛医院", "frag": "天坛"}],
    "Neurosurgery": [{"q": "北京天坛医院", "frag": "天坛"}, {"q": "首都医科大学宣武医院", "frag": "宣武"}],
    "Oncology": [{"q": "中国医学科学院肿瘤医院", "frag": "医学科学院肿瘤"}, {"q": "北京大学肿瘤医院", "frag": "北京大学肿瘤"}],
    "Surgical Oncology": [{"q": "中国医学科学院肿瘤医院", "frag": "医学科学院肿瘤"}, {"q": "北京大学肿瘤医院", "frag": "北京大学肿瘤"}],
    "Pediatrics": [{"q": "北京儿童医院", "frag": "儿童医院"}, {"q": "首都儿科研究所", "frag": "儿科研究所"}],
    "Pediatric Surgery": [{"q": "北京儿童医院", "frag": "儿童医院"}, {"q": "首都儿科研究所", "frag": "儿科研究所"}],
    "Obstetrics & Gynecology": [{"q": "北京妇产医院", "frag": "妇产"}, {"q": "北京协和医院", "frag": "协和"}],
    "Gynecology": [{"q": "北京妇产医院", "frag": "妇产"}, {"q": "北京协和医院", "frag": "协和"}],
    "Ophthalmology": [{"q": "北京同仁医院", "frag": "同仁"}],
    "ENT": [{"q": "北京同仁医院", "frag": "同仁"}],
    "Orthopedics": [{"q": "北京积水潭医院", "frag": "积水潭"}, {"q": "北京大学第三医院", "frag": "北京大学第三"}],
    "Sports Medicine": [{"q": "北京大学第三医院", "frag": "北京大学第三"}, {"q": "北京积水潭医院", "frag": "积水潭"}],
    "Dermatology": [{"q": "北京大学第一医院", "frag": "北京大学第一"}, {"q": "中日友好医院", "frag": "中日友好"}],
    "Dental": [{"q": "北京大学口腔医院", "frag": "口腔"}],
    "Oral Surgery": [{"q": "北京大学口腔医院", "frag": "口腔"}],
    "Respiratory": [{"q": "中日友好医院", "frag": "中日友好"}, {"q": "首都医科大学附属北京朝阳医院", "frag": "朝阳医院"}],
    "Pulmonary / Respiratory": [{"q": "中日友好医院", "frag": "中日友好"}, {"q": "首都医科大学附属北京朝阳医院", "frag": "朝阳医院"}],
    "Gastroenterology": [{"q": "首都医科大学附属北京友谊医院", "frag": "友谊"}, {"q": "北京协和医院", "frag": "协和"}],
    "Endocrinology": [{"q": "北京协和医院", "frag": "协和"}, {"q": "中日友好医院", "frag": "中日友好"}],
    "Urology": [{"q": "北京大学第一医院", "frag": "北京大学第一"}, {"q": "中国人民解放军总医院", "frag": "解放军总医院"}],
    "Mental Health / Psychiatry": [{"q": "北京大学第六医院", "frag": "北京大学第六"}, {"q": "北京安定医院", "frag": "安定"}],
    "Rheumatology": [{"q": "北京协和医院", "frag": "协和"}, {"q": "北京大学人民医院", "frag": "北京大学人民"}],
    "Hematology": [{"q": "北京大学人民医院", "frag": "北京大学人民"}, {"q": "北京大学第一医院", "frag": "北京大学第一"}],
    "Nephrology": [{"q": "北京大学第一医院", "frag": "北京大学第一"}, {"q": "中国人民解放军总医院", "frag": "解放军总医院"}],
    "Geriatrics": [{"q": "北京医院", "frag": "北京医院"}, {"q": "首都医科大学宣武医院", "frag": "宣武"}],
    "Infectious Diseases": [{"q": "北京地坛医院", "frag": "地坛"}, {"q": "北京佑安医院", "frag": "佑安"}],
    "Traditional Chinese Medicine": [{"q": "中国中医科学院广安门医院", "frag": "广安门"}, {"q": "北京中医药大学东直门医院", "frag": "东直门"}],
    "Emergency": [{"q": "北京协和医院", "frag": "协和"}, {"q": "首都医科大学附属北京朝阳医院", "frag": "朝阳医院"}],
    "General Medicine": [{"q": "北京协和医院", "frag": "协和"}, {"q": "中国人民解放军总医院", "frag": "解放军总医院"}],
}


def _build_leader_index() -> dict[str, set]:
    idx: dict[str, set] = {}
    for sp, leaders in SPECIALTY_LEADERS.items():
        for ld in leaders:
            idx.setdefault(ld["frag"], set()).add(sp)
    return idx


# 合并子代理扩充的全国专科领先榜（更多专科 + 更多城市），按 frag 去重
try:
    from .hospital_dataset import SPECIALTY_LEADERS_EXT as _SPECIALTY_LEADERS_EXT
    for _sp, _leaders in _SPECIALTY_LEADERS_EXT.items():
        _cur = SPECIALTY_LEADERS.setdefault(_sp, [])
        _frags = {l.get("frag") for l in _cur}
        for _ld in _leaders:
            if _ld.get("frag") and _ld["frag"] not in _frags:
                _cur.append({"q": _ld.get("q", ""), "frag": _ld["frag"]})
                _frags.add(_ld["frag"])
except Exception:  # pragma: no cover - expansion file optional
    pass

_LEADER_INDEX = _build_leader_index()


def _hospital_leader_specialties(name: str) -> set:
    """该医院（按名片段）是哪些专科的全国领先单位。"""
    if not name:
        return set()
    out: set = set()
    for frag, sps in _LEADER_INDEX.items():
        if frag in name:
            out |= sps
    return out


def _recommendation_score(hospital: dict, specialty_scores: dict[str, float], language: str = "", urgent: bool = False) -> dict:
    """Calculate aggregate recommendation score + list of reasons for hospital.
    Returns {"score": float, "reasons": List[str], "matched_specialties": List[str], "matched_language": bool}"""
    reasons: List[str] = []
    specialty_score_sum = 0.0
    matched_specialties: List[str] = []
    for sp, weight in specialty_scores.items():
        strength = _hospital_has_specialty(hospital, sp)
        if strength > 15:
            matched_specialty_score = (strength * (weight / 100.0))
            specialty_score_sum += matched_specialty_score
            matched_specialties.append(sp)
            reasons.append(f"{sp}: specialty score {round(strength)} match with your symptoms")

    # 权威加权：该医院是否为命中专科的全国领先单位（复旦榜 / 国家临床重点专科）
    leader_sps = _hospital_leader_specialties((hospital.get("name_zh") or "") + " " + (hospital.get("name") or ""))
    leadership_score = 0.0
    leader_matched: List[str] = []
    for sp, weight in specialty_scores.items():
        if sp in leader_sps and weight > 0:
            leadership_score += 35.0 * (weight / 100.0) + 18.0
            leader_matched.append(sp)
            if sp not in matched_specialties:
                matched_specialties.append(sp)
    if leader_matched:
        reasons.insert(0, f"National leader in {leader_matched[0]}")

    # 医院等级（三级甲等）作为质量信号
    grade = str(hospital.get("grade") or "")
    grade_score = 12.0 if ("三级甲等" in grade or "三甲" in grade) else 0.0

    # Rating: 0-5 scale → normalized to 0-40 points of score
    _r = hospital.get("rating")
    try:
        rating = float(_r) if _r is not None else 0.0
    except (TypeError, ValueError):
        rating = 0.0
    rating_score = rating * 8.0

    # distance penalty: shorter better
    _d = hospital.get("distance_km")
    try:
        distance_km = float(_d) if _d is not None else 10.0
    except (TypeError, ValueError):
        distance_km = 10.0
    distance_score = max(0.0, 40.0 - distance_km * 2.0)

    # wait minutes: less wait, better
    _w = hospital.get("wait_minutes")
    try:
        wait_min = float(_w) if _w is not None else 30.0
    except (TypeError, ValueError):
        wait_min = 30.0
    wait_score = max(0.0, 30.0 - wait_min)

    # language filter
    matched_language = False
    if language and language.strip():
        langs = [l.strip() for l in hospital.get("languages", [])]
        if language.lower() in [l.lower() for l in langs]:
            matched_language = True

    total = specialty_score_sum + leadership_score + grade_score + rating_score + distance_score + wait_score
    if matched_language:
        total += 10
        reasons.append("Speaks your language")
    if urgent:
        emergency_strength = _hospital_has_specialty(hospital, "Emergency")
        if emergency_strength > 15:
            total += 20
            reasons.append("Has strong emergency services")
        else:
            total -= 10

    return {
        "score": round(total, 2),
        "specialty_score": round(specialty_score_sum, 2),
        "leadership_score": round(leadership_score, 2),
        "grade_score": round(grade_score, 2),
        "rating_score": round(rating_score, 2),
        "distance_score": round(distance_score, 2),
        "wait_score": round(wait_score, 2),
        "reasons": reasons[:5],
        "matched_specialties": matched_specialties,
        "leader_specialties": leader_matched,
        "grade": grade,
        "matched_language": matched_language,
    }


# -------------------------------------------------------------- triage (new)
def _triage_core(text: str) -> TriageOut:
    """Pure triage logic — returns a TriageOut without touching DB/headers."""
    text = (text or "").strip()
    if not text:
        raise HTTPException(400, "symptoms are required")
    text_l = text.lower()

    specialty_scores: Dict[str, float] = {}
    matched: List[str] = []
    is_urgent = False
    for key, info in SYMPTOM_TO_SPECIALTIES.items():
        if key in text_l:
            matched.append(key)
            w = float(info.get("weight", 50))
            is_urgent = is_urgent or bool(info.get("urgent"))
            for sp in info.get("specialties", []):
                specialty_scores[sp] = specialty_scores.get(sp, 0.0) + w

    ranked = sorted(specialty_scores.items(), key=lambda kv: kv[1], reverse=True)
    if ranked:
        best_dep_en = ranked[0][0]
        best_dep_zh = ""
        for alias in SPECIALTY_ALIASES.get(best_dep_en, []):
            if any(ord(ch) > 127 for ch in alias):
                best_dep_zh = alias
                break
        top3 = [r[0] for r in ranked[:3]]
        matched_display = ", ".join(matched[:5]) or "unspecified"
        also = ", ".join(top3[1:3]) if len(top3) > 1 else "general practice"
        rec_en = (f"Based on your symptoms ({matched_display}), "
                   f"the recommended department is: {best_dep_en}. "
                   f"Also consider: {also}. "
                   f"If symptoms worsen, please consult a professional immediately.")
        rec_zh = f"根据您描述的症状 ({matched_display})，建议科室：{best_dep_en}（{best_dep_zh}）"
        return TriageOut(department_en=best_dep_en, department_zh=best_dep_zh,
                         recommendation_en=rec_en, recommendation_zh=rec_zh,
                         urgent=is_urgent, matched_symptoms=matched)

    best_dep_en, best_dep_zh = "General Medicine / Family Practice", "全科 / 内科"
    rec_en = ("No specific department could be identified from your keywords. "
               "Please consult a general practitioner or contact our support for a "
               "more detailed assessment.")
    rec_zh = ("根据您输入的关键词未能识别具体科室。建议咨询全科医生，或联系我们的客服 "
               "进行更详细的评估。")
    return TriageOut(department_en=best_dep_en, department_zh=best_dep_zh,
                     recommendation_en=rec_en, recommendation_zh=rec_zh,
                     urgent=False, matched_symptoms=matched)


@app.post("/api/triage", response_model=TriageOut)
def triage(body: TriageIn,
           auth: Optional[str] = Header(default=None, alias="Authorization"),
           db=Depends(get_db)):
    result = _triage_core(body.symptoms)

    # save record if signed-in user
    uid = None
    auth_str = auth if isinstance(auth, str) else None
    if auth_str and auth_str.lower().startswith("bearer "):
        try:
            token = auth_str.split(" ", 1)[1].strip()
            payload = decode_jwt(token)
            uid = int(payload["sub"])
        except Exception:
            uid = None
    if uid and db is not None:
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


# -------------------------------------------------------------- hospitals (enhanced)
@app.get("/api/hospitals")
def hospitals_list(keyword: Optional[str] = "",
                   city: Optional[str] = "北京",
                   specialty: Optional[str] = None,
                   language: Optional[str] = None,
                   urgent: bool = False,
                   symptom: Optional[str] = None,
                   max_wait: Optional[int] = None,
                   min_rating: Optional[float] = None,
                   limit: int = 20):
    """医院列表。优先使用高德 POI 搜索（真实数据），无 key 时回退到本地 demo。

    新特性：`symptom` 会启动基于症状→专科→医院优势的推荐评分，返回 `recommendation` 字段。
    """
    result = _amap.search_hospitals(keyword=keyword or "", city=city or "北京", limit=limit)
    hospitals = result.get("hospitals", [])

    # ---- 基于症状计算专科权重
    specialty_scores: dict[str, float] = {}
    if symptom and symptom.strip():
        specialty_scores = _parse_symptoms_to_specialty_scores(symptom)
        # 若 symptom 有意义且用户同时传入 specialty，则也将它加入加权
        if specialty and specialty.strip():
            canonical = _hospital_specialty_canonical(specialty) or specialty
            specialty_scores[canonical] = specialty_scores.get(canonical, 0.0) + 80.0
    elif specialty and specialty.strip():
        # explicit specialty filter
        canonical = _hospital_specialty_canonical(specialty) or specialty
        specialty_scores[canonical] = 100.0

    # --- 过滤
    filtered = []
    for h in hospitals:
        # specialty/language filter
        if specialty and specialty.strip():
            haystack = " ".join([str(s).lower() for s in (h.get("specialties") or [])])
            if specialty.lower() not in haystack and specialty.lower() not in str(h.get("name", "")).lower():
                continue
        if language:
            langs = h.get("languages") or []
            if language not in langs and language.lower() not in [l.lower() for l in langs]:
                continue
        if urgent and (h.get("wait_minutes", 999) or 999) > 30:
            continue
        if max_wait is not None and (h.get("wait_minutes", 0) or 0) > max_wait:
            continue
        if min_rating is not None and (h.get("rating") or 0) < min_rating:
            continue
        filtered.append(h)

    # --- 推荐评分（若有症状或专科则排序）
    enriched = []
    if specialty_scores:
        scored_h = []
        for h in filtered:
            rec = _recommendation_score(h, specialty_scores, language=language or "", urgent=urgent)
            h_copy = dict(h)
            h_copy["recommendation"] = rec
            scored_h.append((h_copy, rec["score"]))
        scored_h.sort(key=lambda pair: pair[1], reverse=True)
        enriched = [h for h, _ in scored_h]
    else:
        # 无特殊评分，则按 rating 排序
        enriched = sorted(filtered, key=lambda h: float(h.get("rating") or 0), reverse=True)

    # --- 追加真实评价数据（评分、点评数、点评片段）
    try:
        enriched = _reviews.enrich_hospital_list(enriched[:20])
    except Exception:
        pass

    return {"hospitals": enriched, "count": len(enriched),
            "data_source": result.get("data_source", "demo"),
            "city": result.get("city"),
            "symptom": symptom, "specialty_scores": specialty_scores}


# -------------------------------------------------------------- 智能推荐：POST 版本
class RecommendationIn(BaseModel):
    symptoms: str
    city: str = "北京"
    language: Optional[str] = None
    max_wait: Optional[int] = None
    specialty_override: Optional[str] = None
    limit: int = 10


# 专科 → 高德 POI 搜索关键词（中文），用于"按需"检索对症医院
SPECIALTY_TO_AMAP_KEYWORD: dict[str, str] = {
    "Cardiology": "心血管", "Cardiovascular Surgery": "心血管", "Neurology": "神经",
    "Neurosurgery": "神经外科", "Oncology": "肿瘤", "Surgical Oncology": "肿瘤",
    "Pediatrics": "儿童", "Pediatric Surgery": "儿童", "Obstetrics & Gynecology": "妇产",
    "Gynecology": "妇产", "Ophthalmology": "眼科", "ENT": "耳鼻喉", "Orthopedics": "骨科",
    "Sports Medicine": "骨科", "Dermatology": "皮肤", "Dental": "口腔", "Oral Surgery": "口腔",
    "Emergency": "急诊", "Respiratory": "呼吸", "Pulmonary / Respiratory": "呼吸",
    "Gastroenterology": "消化", "Endocrinology": "内分泌", "Urology": "泌尿",
    "Mental Health / Psychiatry": "精神", "Rheumatology": "风湿免疫", "Hematology": "血液",
    "Nephrology": "肾内", "Geriatrics": "老年", "Infectious Diseases": "感染",
    "Traditional Chinese Medicine": "中医",
}


def _fetch_candidate_hospitals(specialty_scores: dict, city: str, limit: int) -> dict:
    """按需检索：用症状对应的 Top 专科中文关键词搜对症医院，并与综合医院结果合并去重。
    这样候选集本身就贴合需求，而非千篇一律的"医院"。"""
    ranked_specs = sorted(specialty_scores.items(), key=lambda kv: kv[1], reverse=True)
    keywords: list[str] = []
    for sp, _ in ranked_specs[:2]:
        kw = SPECIALTY_TO_AMAP_KEYWORD.get(sp)
        if kw and kw not in keywords:
            keywords.append(kw)
    # 始终附带一次综合检索，保证协和/301 等强综合医院在候选内。
    # 这些查询并行批量执行（高德调用从串行 3~7 次 → 一次并发批），显著降低推荐延迟。
    queries = keywords + [""]
    city_q = city or "北京"
    merged: dict[str, dict] = {}
    data_source = "demo"
    try:
        batch = _amap.search_hospitals_many(queries, city=city_q, limit=max(12, limit))
    except Exception:
        batch = []
    for res in batch:
        if not isinstance(res, dict):
            continue
        data_source = res.get("data_source", data_source)
        for h in res.get("hospitals", []):
            key = h.get("id") or h.get("name")
            if key and key not in merged:
                merged[key] = h

    # 确保 Top 专科的全国领先医院在候选集中：缺失则按名并发补检索（含真实坐标/电话）
    present = " ".join((h.get("name_zh") or h.get("name") or "") for h in merged.values())
    want: list[dict] = []
    for sp, _ in ranked_specs[:2]:
        for ld in SPECIALTY_LEADERS.get(sp, []):
            if ld["frag"] not in present and all(ld["frag"] != w["frag"] for w in want):
                want.append(ld)
    want = want[:6]
    if want:
        try:
            lead_batch = _amap.search_hospitals_many([w["q"] for w in want], city=city_q, limit=2)
        except Exception:
            lead_batch = []
        for ld, res in zip(want, lead_batch):
            if not isinstance(res, dict):
                continue
            for h in res.get("hospitals", []):
                if ld["frag"] in (h.get("name_zh") or h.get("name") or ""):
                    h.setdefault("grade", "三级甲等")  # 榜单领先医院均为三甲（事实）
                    key = h.get("id") or h.get("name")
                    if key and key not in merged:
                        merged[key] = h
                    break
    return {"hospitals": list(merged.values()), "data_source": data_source}


@app.post("/api/recommendations")
def recommendations_api(body: RecommendationIn):
    """根据症状 → 专科 → 医院优势进行推荐。
    返回: triage_result + hospitals (按推荐分排序，含匹配理由)
    """
    text = body.symptoms.strip()
    if not text:
        raise HTTPException(400, "symptoms are required")

    # 分诊
    triage_out = _triage_core(text)

    # 专科分数（symptom → specialty score map）
    specialty_scores = _parse_symptoms_to_specialty_scores(text)
    if body.specialty_override and body.specialty_override.strip():
        canonical = _hospital_specialty_canonical(body.specialty_override) or body.specialty_override
        specialty_scores[canonical] = specialty_scores.get(canonical, 0.0) + 120.0

    # 按需检索候选医院：用对症专科关键词 + 综合检索合并（而非千篇一律的"医院"）
    hospitals_result = _fetch_candidate_hospitals(specialty_scores, body.city or "北京", body.limit * 3)
    hospitals = hospitals_result.get("hospitals", [])

    scored_h = []
    for h in hospitals:
        rec = _recommendation_score(
            h, specialty_scores,
            language=body.language or "",
            urgent=triage_out.urgent,
        )
        h_copy = dict(h)
        h_copy["recommendation"] = rec
        scored_h.append((h_copy, rec["score"]))
    scored_h.sort(key=lambda pair: pair[1], reverse=True)
    ranked = [h for h, _ in scored_h[: body.limit]]

    # 仅保留事实型信号：医院等级（三甲）+ 专科全国领先；不再注入模板化点评。
    for h in ranked:
        rec = h.get("recommendation") or {}
        if not h.get("grade") and rec.get("grade"):
            h["grade"] = rec["grade"]
        if not h.get("grade") and rec.get("leader_specialties"):
            h["grade"] = "三级甲等"

    return {
        "triage": {
            "department_en": triage_out.department_en,
            "department_zh": triage_out.department_zh,
            "recommendation_en": triage_out.recommendation_en,
            "recommendation_zh": triage_out.recommendation_zh,
            "urgent": triage_out.urgent,
            "matched_symptoms": triage_out.matched_symptoms,
        },
        "specialty_scores": specialty_scores,
        "hospitals": ranked,
        "count": len(ranked),
        "data_source": hospitals_result.get("data_source", "demo"),
        "city": body.city,
    }


@app.get("/api/hospitals/{hospital_id}")
def hospital_detail(hospital_id: str):
    h = _find_hospital(hospital_id)
    if not h:
        raise HTTPException(404, "hospital not found")
    # 追加点评
    try:
        h = _reviews.enrich_hospital_list([h])[0]
    except Exception:
        pass
    out = _hospital_to_out(h)
    # 将点评字段附加到返回字典
    result = out.model_dump() if hasattr(out, "model_dump") else out.dict()
    result["review_count"] = h.get("review_count", 0)
    result["photo_count"] = h.get("photo_count", 0)
    result["reviews"] = h.get("reviews", [])
    result["review_source"] = h.get("review_source", "fallback")
    return result


# -------------------------------------------------------------- reviews
@app.get("/api/hospitals/{hospital_id}/reviews")
def hospital_reviews(hospital_id: str, name: Optional[str] = None, city: str = "北京"):
    """返回指定医院的真实评价数据。
    - 若提供 `hospital_id` 是高德 POI id（不包含空格），会优先调用高德 POI 详情
    - 否则通过 `name` 参数走本地 + 好大夫在线回退
    """
    poi_id = None
    h_name = None
    # 尝试从本地 hospitals 查找
    local = _find_hospital(hospital_id)
    if local:
        h_name = local.get("name_zh") or local.get("name")
    # 判断是否是 POI ID（纯字母数字且长度 > 5）
    if hospital_id and len(hospital_id) >= 5 and hospital_id.replace("-", "").isalnum():
        poi_id = hospital_id
    # 回退：如果有 name 参数覆盖
    if name and name.strip():
        h_name = name.strip()
    if not poi_id and not h_name:
        raise HTTPException(400, "either a valid hospital_id or name is required")
    result = _reviews.get_hospital_reviews(poi_id=poi_id, hospital_name=h_name, city=city)
    return {"hospital": h_name or hospital_id, **result}


# -------------------------------------------------------------- navigation（室外导航）
def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    import math
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@app.get("/api/navigation")
def navigate(hospital_id: Optional[str] = None,
             to_lng: Optional[float] = None,
             to_lat: Optional[float] = None,
             name: Optional[str] = None,
             from_lng: Optional[float] = None,
             from_lat: Optional[float] = None,
             mode: str = "walking"):
    """室外导航：返回目标医院的位置信息、路线摘要和外部地图链接。

    使用方式（二选一）：
    - hospital_id: 从 /api/hospitals 或本地 HOSPITALS 列表中的 id
    - to_lng + to_lat + name: 直接传入坐标
    """
    hospital: Optional[Dict[str, Any]] = None

    # 方式 1：直接坐标参数（最可靠，避免 ID 查找失败）
    if to_lng is not None and to_lat is not None:
        hospital = {
            "id": "poi-direct",
            "name": name or "hospital",
            "name_zh": name or "医院",
            "lng": to_lng,
            "lat": to_lat,
            "address": None,
            "address_zh": None,
            "phone": None,
            "hours": None,
            "rating": None,
            "specialties": [],
            "departments": [],
        }
    elif hospital_id:
        # 方式 2：先查本地 HOSPITALS
        for h in HOSPITALS:
            if h["id"] == hospital_id:
                hospital = h
                break
        if not hospital:
            # 方式 2b：查 AMap（先尝试精确 POI ID 匹配，再尝试关键词搜索）
            try:
                search = _amap.search_hospitals(keyword=hospital_id or "", city="北京", limit=3)
                if search.get("hospitals"):
                    # 优先找 id 精确匹配的，否则用第一个结果
                    for h in search["hospitals"]:
                        if h.get("id") == hospital_id:
                            hospital = h
                            break
                    if not hospital:
                        hospital = search["hospitals"][0]
            except Exception:
                hospital = None

    if not hospital:
        # 默认 fallback：用第一个本地医院
        if HOSPITALS:
            hospital = HOSPITALS[0]
    if not hospital:
        raise HTTPException(404, "hospital not found. call /api/hospitals for a list")

    _to_lng = hospital.get("lng") or hospital.get("longitude")
    _to_lat = hospital.get("lat") or hospital.get("latitude")
    if _to_lng is None or _to_lat is None:
        raise HTTPException(400, "hospital has no coordinates")

    # Default origin — Beijing Tiananmen square, used for display-only distance when not provided
    origin_lat = from_lat if from_lat is not None else 39.9042
    origin_lng = from_lng if from_lng is not None else 116.4074
    straight_line_km = _haversine_km(origin_lat, origin_lng, _to_lat, _to_lng)

    # Direction (attempt AMap; graceful fallback to an estimate)
    direction_result: Dict[str, Any] = {
        "status": "estimated",
        "distance_m": round(straight_line_km * 1200),
        "duration_min": max(3, round(straight_line_km * (20 if mode == "driving" else (12 if mode == "transit" else 8)))),
        "steps": [],
    }
    if (from_lng is not None and from_lat is not None):
        try:
            amap_r = _amap.direction(from_lng, from_lat, _to_lng, _to_lat, mode=mode)
            if amap_r and amap_r.get("status") and amap_r["status"].startswith("ok"):
                direction_result = amap_r
        except Exception:
            pass

    # External map links
    enc_name = hospital.get("name") or "hospital"
    google_maps = f"https://www.google.com/maps/search/?api=1&query={_to_lat},{_to_lng}"
    amap_link = f"https://uri.amap.com/marker?position={_to_lng},{_to_lat}&name={enc_name}"
    apple_maps = f"https://maps.apple.com/?ll={_to_lat},{_to_lng}&q={enc_name}"
    baidu_map = f"https://api.map.baidu.com/geocoder?location={_to_lat},{_to_lng}&output=html"

    # Include department highlights from hospital (department info)
    depts = []
    for d in hospital.get("departments", []) or []:
        if isinstance(d, (tuple, list)) and len(d) >= 2:
            depts.append({"name": str(d[0]), "name_zh": str(d[1])})
        elif isinstance(d, dict):
            depts.append({"name": d.get("name", ""), "name_zh": d.get("name_zh", "")})

    return {
        "hospital": {
            "id": hospital.get("id"),
            "name": hospital.get("name"),
            "name_zh": hospital.get("name_zh") or hospital.get("name"),
            "address": hospital.get("address"),
            "address_zh": hospital.get("address_zh") or hospital.get("address"),
            "phone": hospital.get("phone"),
            "hours": hospital.get("hours"),
            "rating": hospital.get("rating"),
            "lng": _to_lng,
            "lat": _to_lat,
        },
        "departments": depts,
        "specialties": hospital.get("specialties", []),
        "mode": mode,
        "origin": {
            "lng": origin_lng,
            "lat": origin_lat,
            "provided": (from_lng is not None and from_lat is not None),
        },
        "straight_line_km": round(straight_line_km, 2),
        "direction": direction_result,
        "maps": {
            "google": google_maps,
            "amap": amap_link,
            "apple": apple_maps,
            "baidu": baidu_map,
        },
    }


@app.get("/api/amap/config")
def amap_config():
    """返回高德地图前端配置（不泄露 Web 服务 key）。"""
    return _amap.public_config()


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
    db.query(models.TriageRecord).filter(models.TriageRecord.user_id == current_user.id).delete()
    db.query(models.Feedback).filter(models.Feedback.user_id == current_user.id).delete()
    db.commit()
    return {"ok": True, "message": "All personal data wiped"}


# -------------------------------------------------------------- stats
@app.get("/api/stats", response_model=StatsOut)
def stats(db=Depends(get_db)):
    return StatsOut(
        hospitals=len(HOSPITALS), medications=len(MEDICATIONS),
        triage_rules=len(TRIAGE_RULES), medical_terms=TOTAL_MEDICAL_TERMS,
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
