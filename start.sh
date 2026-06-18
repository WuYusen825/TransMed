#!/bin/bash
# TransMed 一键启动脚本（Groq 版）
# 用法:
#   export TRANSMED_GROQ_API_KEY="gsk_..."
#   ./start.sh

# 注意：不要把 API key 写进脚本里——用环境变量传入！
export TRANSMED_GROQ_MODEL="${TRANSMED_GROQ_MODEL:-llama-3.3-70b-versatile}"
export TRANSMED_GROQ_BASE_URL="${TRANSMED_GROQ_BASE_URL:-https://api.groq.com/openai/v1}"
export TRANSMED_JWT_SECRET="${TRANSMED_JWT_SECRET:-transmed-dev-secret-change-me}"

if [ -z "$TRANSMED_GROQ_API_KEY" ] || [ ${#TRANSMED_GROQ_API_KEY} -lt 20 ]; then
  echo "⚠️  TRANSMED_GROQ_API_KEY 未设置。请先："
  echo "   export TRANSMED_GROQ_API_KEY=\"<你的 Groq API key>\""
  echo "   申请地址: https://console.groq.com/keys"
  exit 1
fi

PORT="${PORT:-8000}"
echo "🚀 TransMed starting on http://127.0.0.1:$PORT"
echo "   👉 Groq key 已加载 (${#TRANSMED_GROQ_API_KEY} 字符), model=${TRANSMED_GROQ_MODEL}"
exec python3 -m uvicorn transmed_app.backend:app --host 0.0.0.0 --port "$PORT"
