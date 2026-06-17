"""应用启动初始化：建表 → 默认管理员 → 示例医院/科室数据。"""
from __future__ import annotations

import json

from .auth import hash_password
from .config import settings
from .database import Base, engine, SessionLocal
from .models import User, Hospital, Department
from .data import HOSPITALS as DEMO_HOSPITALS, INDOOR_MAP


def create_tables():
    Base.metadata.create_all(bind=engine)


def seed_hospitals(db):
    """从 data.py 的静态数据补齐医院数据（若不存在）。"""
    for h in DEMO_HOSPITALS:
        exists = db.query(Hospital).filter(Hospital.external_id == h["id"]).first()
        if exists:
            continue
        hospital = Hospital(
            external_id=h["id"],
            name=h["name"],
            name_zh=h.get("name_zh"),
            address=h.get("address"),
            address_zh=h.get("address_zh"),
            rating=h.get("rating", 4.5),
            distance_km=h.get("distance_km", 5.0),
            wait_minutes=h.get("wait_minutes", 30),
            accepted_insurance=",".join(h.get("insurance", [])),
            registration_fee=h.get("registration_fee", 200),
            consultation_fee=h.get("consultation_fee", 500),
            internal_map_data=json.dumps(INDOOR_MAP.get(h["id"], {})),
        )
        db.add(hospital)
        db.flush()
        for dept in h.get("departments", []):
            db.add(Department(
                hospital_id=hospital.id,
                name=dept.get("name"),
                name_zh=dept.get("name_zh"),
                wait_minutes=dept.get("wait", 20),
            ))
    db.commit()


def seed_default_admin(db):
    exists = db.query(User).filter(User.email == settings.DEFAULT_ADMIN_EMAIL).first()
    if not exists:
        admin = User(
            email=settings.DEFAULT_ADMIN_EMAIL,
            full_name="TransMed Administrator",
            password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
            language="en",
            country="International",
            role="admin",
        )
        db.add(admin)
        db.commit()


def seed_demo_user(db):
    """提供一个演示用户 demo@transmed.io / demo123，方便前端直接体验。"""
    email = "demo@transmed.io"
    exists = db.query(User).filter(User.email == email).first()
    if not exists:
        db.add(User(
            email=email,
            full_name="Demo User",
            password_hash=hash_password("demo123"),
            language="en",
            country="United Kingdom",
            role="patient",
        ))
        db.commit()


def initialize():
    create_tables()
    db = SessionLocal()
    try:
        seed_hospitals(db)
        seed_default_admin(db)
        seed_demo_user(db)
    finally:
        db.close()
