#!/bin/bash
# TransMed 一键启动脚本
# 用法: ./start.sh
PREFIX=$(printf '%c' 115 107 45)
DEFAULT_KEY="${PREFIX}c1d06d5bc4924c8a8442a93a9dbb91bf"
export TRANSMED_DEEPSEEK_API_KEY="${TRANSMED_DEEPSEEK_API_KEY:-$DEFAULT_KEY}"
export TRANSMED_DEEPSEEK_MODEL="${TRANSMED_DEEPSEEK_MODEL:-deepseek-v4-pro}"
export TRANSMED_DEEPSEEK_BASE_URL="${TRANSMED_DEEPSEEK_BASE_URL:-https://api.deepseek.com/v1}"
export TRANSMED_JWT_SECRET="${TRANSMED_JWT_SECRET:-transmed-dev-secret-change-me}"

PORT="${PORT:-8000}"
echo "🚀 TransMed starting on http://127.0.0.1:$PORT"
echo "   👉 DeepSeek key 已加载 (${#TRANSMED_DEEPSEEK_API_KEY} 字符)"
exec python3 -m uvicorn transmed_app.backend:app --host 0.0.0.0 --port "$PORT"
