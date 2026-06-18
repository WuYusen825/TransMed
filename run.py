"""TransMed 启动脚本。运行：python3 run.py"""
from __future__ import annotations
import os
import sys

# Groq API key —— 请通过环境变量 TRANSMED_GROQ_API_KEY 设置（不要在代码中写入）
# 申请地址: https://console.groq.com/keys

os.environ.setdefault("TRANSMED_GROQ_MODEL", "llama-3.3-70b-versatile")
os.environ.setdefault("TRANSMED_GROQ_BASE_URL", "https://api.groq.com/openai/v1")
os.environ.setdefault("TRANSMED_JWT_SECRET", "transmed-dev-secret-change-me")

KEY = os.environ.get("TRANSMED_GROQ_API_KEY", "")
if not KEY or len(KEY) < 20:
    print("⚠️  TRANSMED_GROQ_API_KEY 未设置。请先设置：")
    print("   export TRANSMED_GROQ_API_KEY=\"<你的 Groq API key>\"")
    print("   然后重新运行：python3 run.py")
    sys.exit(1)

import uvicorn


if __name__ == "__main__":
    print("🚀 TransMed starting on http://127.0.0.1:8000")
    print("   👉 前端页面: http://127.0.0.1:8000")
    print("   👉 Swagger API docs: http://127.0.0.1:8000/docs")
    print("   👉 SQLite DB: ./data/transmed.db")
    print("   👉 默认管理员: admin@transmed.io / admin123")
    print("   👉 演示用户: demo@transmed.io / demo123")
    print(f"   🔑 Groq key 已加载 ({len(KEY)} 字符), model={os.environ.get('TRANSMED_GROQ_MODEL')}")
    uvicorn.run("transmed_app.backend:app", host="127.0.0.1", port=8000, log_level="info", reload=False)
