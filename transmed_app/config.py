"""TransMed 配置集中管理 —— 路径 / DB / JWT / 默认凭据 / Groq API 等。"""
from __future__ import annotations

import os
from pathlib import Path


# ——— 基础路径 ———
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings:
    # 数据库：默认 SQLite，可通过环境变量切换到 MySQL / PostgreSQL
    DATABASE_URL: str = os.environ.get(
        "TRANSMED_DATABASE_URL",
        f"sqlite:///{(DATA_DIR / 'transmed.db').as_posix()}",
    )

    # JWT
    JWT_SECRET: str = os.environ.get("TRANSMED_JWT_SECRET", "transmed-dev-secret-change-me")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天

    # 默认管理员
    DEFAULT_ADMIN_EMAIL: str = os.environ.get("TRANSMED_ADMIN_EMAIL", "admin@transmed.io")
    DEFAULT_ADMIN_PASSWORD: str = os.environ.get("TRANSMED_ADMIN_PASSWORD", "admin123")

    # 应用信息
    APP_NAME: str = "TransMed"
    APP_VERSION: str = "1.0.0"

    # CORS
    CORS_ORIGINS: list = ["*"]

    # ——— Groq API（核心翻译引擎，OpenAI 兼容格式，超快响应）———
    # 通过环境变量 TRANSMED_GROQ_API_KEY 设置
    GROQ_API_KEY: str = os.environ.get("TRANSMED_GROQ_API_KEY", "")
    GROQ_MODEL: str = os.environ.get(
        "TRANSMED_GROQ_MODEL",
        "llama-3.3-70b-versatile",
    )
    GROQ_BASE_URL: str = os.environ.get(
        "TRANSMED_GROQ_BASE_URL",
        "https://api.groq.com/openai/v1",
    )


settings = Settings()
