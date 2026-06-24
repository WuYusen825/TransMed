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
        "groq/compound",
    )
    GROQ_BASE_URL: str = os.environ.get(
        "TRANSMED_GROQ_BASE_URL",
        "https://api.groq.com/openai/v1",
    )

    # ——— 高德地图 AMap ———
    # ⚠️ 两种 Key 不要混用！
    #   · TRANSMED_AMAP_KEY  (AMAP_WEB_KEY): 必须是「Web 服务」类型，用于后端 REST API
    #   · TRANSMED_AMAP_JS_KEY (AMAP_JS_KEY):  必须是「Web 端 JS API」类型，用于前端地图
    # 申请地址：https://console.amap.com/dev/key/app
    # 在一个应用下可以添加两个 Key：一个「Web 服务」，一个「Web 端」。
    # 如果把 JS API 的 key 当作 Web 服务 key，会收到：USERKEY_PLAT_NOMATCH (infocode=10009)
    AMAP_WEB_KEY: str = os.environ.get("TRANSMED_AMAP_KEY", "bdbaa3cb0db2e16f98321b7c9a10a52e")
    AMAP_JS_KEY: str = os.environ.get("TRANSMED_AMAP_JS_KEY", "81d33fbdcf7d450c41c8bbb817fd959e")

    # ——— WHO ICD-11 API（权威疾病分类术语库，官方多语含中文）———
    # 免费，但需注册获取 OAuth2 凭据：
    #   1) 访问 https://icd.who.int/icdapi 注册并登录
    #   2) 点击 "View API access key" 获取 Client Id / Client Secret
    #   3) 把两者填入下面两个环境变量（本地 .env 或 Render env）
    # 未配置时 ICD-11 检索自动跳过，RAG 退回 RxNorm + MeSH，不会报错。
    ICD_CLIENT_ID: str = os.environ.get("TRANSMED_ICD_CLIENT_ID", "")
    ICD_CLIENT_SECRET: str = os.environ.get("TRANSMED_ICD_CLIENT_SECRET", "")
    ICD_TOKEN_URL: str = os.environ.get(
        "TRANSMED_ICD_TOKEN_URL",
        "https://icdaccessmanagement.who.int/connect/token",
    )
    ICD_BASE_URL: str = os.environ.get("TRANSMED_ICD_BASE_URL", "https://id.who.int")


settings = Settings()
