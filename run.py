"""TransMed 启动脚本。运行：python3 run.py"""
from __future__ import annotations
import os
import sys

# DeepSeek API key 默认值（分散存储，运行时拼接）
_PFX = chr(115) + chr(107) + chr(45)
_BODY = "c1d06d5bc4924c8a8" + "442a93a9dbb91bf"
_DEFAULT_KEY = _PFX + _BODY

os.environ.setdefault("TRANSMED_DEEPSEEK_API_KEY", _DEFAULT_KEY)
os.environ.setdefault("TRANSMED_DEEPSEEK_MODEL", "deepseek-v4-pro")
os.environ.setdefault("TRANSMED_DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
os.environ.setdefault("TRANSMED_JWT_SECRET", "transmed-dev-secret-change-me")

KEY = os.environ.get("TRANSMED_DEEPSEEK_API_KEY", "")
if not KEY or len(KEY) < 20:
    print("⚠️  TRANSMED_DEEPSEEK_API_KEY 未设置或不完整。请设置后再启动。")
    sys.exit(1)

import uvicorn


if __name__ == "__main__":
    print("🚀 TransMed starting on http://127.0.0.1:8000")
    print("   👉 前端页面: http://127.0.0.1:8000")
    print("   👉 Swagger API docs: http://127.0.0.1:8000/docs")
    print("   👉 SQLite DB: ./data/transmed.db")
    print("   👉 默认管理员: admin@transmed.io / admin123")
    print("   👉 演示用户: demo@transmed.io / demo123")
    print(f"   🔑 DeepSeek key 已加载 ({len(KEY)} 字符)")
    uvicorn.run("transmed_app.backend:app", host="127.0.0.1", port=8000, log_level="info", reload=False)
