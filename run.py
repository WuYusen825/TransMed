"""TransMed 启动脚本。运行：python3 run.py"""
from __future__ import annotations
import uvicorn


if __name__ == "__main__":
    print("🚀 TransMed starting on http://127.0.0.1:8000")
    print("   👉 Swagger API docs: http://127.0.0.1:8000/docs")
    print("   👉 SQLite DB: ./data/transmed.db")
    print("   👉 默认管理员: admin@transmed.io / admin123")
    print("   👉 演示用户: demo@transmed.io / demo123")
    uvicorn.run("transmed_app.backend:app", host="127.0.0.1", port=8000, log_level="info", reload=False)
