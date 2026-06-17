"""SQLAlchemy ORM 模型 —— TransMed 核心业务实体。"""
from __future__ import annotations

from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Boolean, Text, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    """用户（外籍患者 / 医生 / 管理员）。"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(190), unique=True, index=True, nullable=False)
    full_name = Column(String(100))
    password_hash = Column(String(255), nullable=False)
    language = Column(String(10), default="en")  # preferred language
    country = Column(String(60))
    role = Column(String(20), default="patient")  # patient / doctor / admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联
    translation_logs = relationship("TranslationLog", back_populates="user", cascade="all, delete-orphan")
    medications = relationship("Medication", back_populates="user", cascade="all, delete-orphan")
    triage_records = relationship("TriageRecord", back_populates="user", cascade="all, delete-orphan")
    insurance_claims = relationship("InsuranceClaim", back_populates="user", cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="user", cascade="all, delete-orphan")


class Hospital(Base):
    """合作医院。"""
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True)
    external_id = Column(String(40), unique=True, index=True)  # 例如 pumch / cmuh
    name = Column(String(200), nullable=False)
    name_zh = Column(String(200))
    address = Column(Text)
    address_zh = Column(Text)
    rating = Column(Float, default=4.5)
    distance_km = Column(Float, default=5.0)
    wait_minutes = Column(Integer, default=30)
    accepted_insurance = Column(String(500))  # "BUPA,Cigna,Aetna"
    registration_fee = Column(Float, default=200)
    consultation_fee = Column(Float, default=500)
    internal_map_data = Column(Text)  # JSON: 室内导航节点/路径

    departments = relationship("Department", back_populates="hospital", cascade="all, delete-orphan")


class Department(Base):
    """医院科室。"""
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"))
    name = Column(String(100))
    name_zh = Column(String(100))
    wait_minutes = Column(Integer, default=20)

    hospital = relationship("Hospital", back_populates="departments")


class TranslationLog(Base):
    """翻译请求日志（含置信度与用户确认）—— 尽职免责核心证据链。"""
    __tablename__ = "translation_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String(40), index=True)
    source_text = Column(Text, nullable=False)
    translated_text = Column(Text, nullable=False)
    source_lang = Column(String(10), default="en")
    target_lang = Column(String(10), default="zh")
    confidence = Column(Float)
    risk_level = Column(String(20))
    matched_terms = Column(Text)  # JSON string list
    user_confirmed = Column(Boolean, default=False)
    confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="translation_logs")


class TriageRecord(Base):
    """智能分诊记录。"""
    __tablename__ = "triage_records"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    symptoms = Column(Text, nullable=False)
    department_en = Column(String(100))
    department_zh = Column(String(100))
    advice_en = Column(Text)
    advice_zh = Column(Text)
    is_urgent = Column(Boolean, default=False)
    matched_terms = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="triage_records")


class Medication(Base):
    """用户个人用药计划。"""
    __tablename__ = "medications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    medication_key = Column(String(100))  # e.g. paracetamol
    custom_name = Column(String(200))
    dosage = Column(String(200))
    times_per_day = Column(Integer, default=2)
    reminder_times = Column(String(200))  # "08:00,14:00,20:00"
    notes = Column(Text)
    start_date = Column(Date, default=date.today)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="medications")


class InsuranceClaim(Base):
    """保险理赔申请记录。"""
    __tablename__ = "insurance_claims"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    provider = Column(String(40))
    status = Column(String(20), default="draft")  # draft/submitted/paid/rejected
    estimated_amount = Column(Float)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="insurance_claims")


class Feedback(Base):
    """用户反馈 / 纠错学习数据（Human-in-the-loop）。"""
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    category = Column(String(40))  # translation / hospital / medication / feature
    content = Column(Text)
    rating = Column(Integer)  # 1-5
    reviewed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="feedbacks")
