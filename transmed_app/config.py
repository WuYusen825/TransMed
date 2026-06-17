"""TransMed 配置集中管理 —— 路径 / DB / JWT / 默认凭据 / DeepSeek API 等。"""
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

    # JWT — 通过环境变量设置私钥，不要使用默认的演示值
    JWT_SECRET: str = os.environ.get("TRANSMED_JWT_SECRET", "")
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

    # ——— DeepSeek API（核心翻译引擎）———
    # ⚠️ 不要在代码中硬编码 API key！请通过环境变量 TRANSMED_DEEPSEEK_API_KEY 设置
    #    例如：export TRANSMED_DEEPSEEK_API_KEY="sk-your-key-here"
    DEEPSEEK_API_KEY: str = os.environ.get("TRANSMED_DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL: str = os.environ.get(
        "TRANSMED_DEEPSEEK_MODEL",
        "deepseek-v4-pro",
    )
    DEEPSEEK_BASE_URL: str = os.environ.get(
        "TRANSMED_DEEPSEEK_BASE_URL",
        "https://api.deepseek.com/v1",
    )


settings = Settings()
