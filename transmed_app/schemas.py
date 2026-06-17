"""Pydantic 模式 —— 请求/响应校验。"""
from __future__ import annotations

from datetime import datetime, date
from typing import Optional, List, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ---------- 认证 ----------
class UserRegister(BaseModel):
    email: str = Field(min_length=3, max_length=190)
    full_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=6, max_length=100)
    language: str = "en"
    country: Optional[str] = None


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    full_name: Optional[str]
    language: str
    country: Optional[str]
    role: str
    created_at: datetime


# ---------- 通用 ----------
class MessageResponse(BaseModel):
    message: str


# ---------- 翻译 ----------
class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    source: str = "en"
    target: str = "zh"
    session_id: Optional[str] = None


class TranslateResponse(BaseModel):
    translated: str
    confidence: float
    risk_level: str
    matched_terms: List[str]
    session_id: str
    advice: str
    log_id: Optional[int] = None


# ---------- 分诊 ----------
class TriageRequest(BaseModel):
    symptoms: str = Field(min_length=2, max_length=2000)
    language: str = "en"


class TriageResponse(BaseModel):
    department_en: str
    department_zh: str
    advice_en: str
    advice_zh: str
    urgent: bool
    record_id: Optional[int] = None


# ---------- 医院 ----------
class HospitalSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    external_id: Optional[str]
    name: str
    name_zh: Optional[str]
    address: Optional[str]
    address_zh: Optional[str]
    rating: float
    distance_km: float
    wait_minutes: int
    accepted_insurance: Optional[str]
    registration_fee: float
    consultation_fee: float


class HospitalDetail(HospitalSchema):
    departments: List[dict] = []
    indoor: Optional[Any] = None


# ---------- 用药 ----------
class MedicationCreate(BaseModel):
    medication_key: str = ""
    custom_name: str = ""
    dosage: str = ""
    reminder_times: str = ""
    notes: str = ""
    is_active: bool = True


class MedicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    medication_key: str
    custom_name: str
    dosage: str
    reminder_times: str
    notes: str
    is_active: bool
    created_at: datetime


# ---------- 保险 ----------
class InsuranceClaimCreate(BaseModel):
    provider: str
    status: str = "draft"
    estimated_amount: float = 0
    notes: str = ""


class InsuranceClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    provider: str
    status: str
    estimated_amount: float
    notes: str
    created_at: datetime


# ---------- 反馈 ----------
class FeedbackCreate(BaseModel):
    category: str = "general"
    content: str = Field(min_length=2, max_length=2000)
    rating: int = Field(ge=1, le=5, default=5)


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category: str
    content: str
    rating: int
    reviewed: bool
    created_at: datetime


# ---------- 翻译日志 ----------
class TranslationLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    confidence: Optional[float]
    risk_level: Optional[str]
    user_confirmed: bool
    created_at: datetime


# ---------- 统计 ----------
class StatsResponse(BaseModel):
    users: int
    hospitals: int
    departments: int
    translations: int
    medications: int
    triage_records: int
    insurance_claims: int
    feedbacks: int
    terms_in_dictionary: int
