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
    # 不再硬编码 Key（已迁至 Render 环境变量）。本地开发请 export 对应变量，或写入 .env。
    AMAP_WEB_KEY: str = os.environ.get("TRANSMED_AMAP_KEY", "")
    AMAP_JS_KEY: str = os.environ.get("TRANSMED_AMAP_JS_KEY", "")
    # 安全密钥（securityJsCode）：高德 JS API 2.0 自 2021-12-02 起，新建的 JS Key
    # 必须配套一个「安全密钥」才能调用 路线规划 / 定位 服务（Walking/Driving/Transfer）。
    # 不配它，前端地图只能显示起点/终点两个标记，画不出路线（这正是导航"只看到两个点"的根因）。
    # 申请：高德控制台 → 应用管理 → 你的「Web端(JS API)」Key → 生成配套「安全密钥」。
    # 通过环境变量 TRANSMED_AMAP_SECURITY_JS_CODE 设置；为空时前端自动回退到「外部地图App + 文字路线」。
    AMAP_SECURITY_JS_CODE: str = os.environ.get("TRANSMED_AMAP_SECURITY_JS_CODE", "")


settings = Settings()
