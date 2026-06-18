#!/usr/bin/env bash
# TransMed 一键启动脚本（Groq + 高德 AMap）
# 使用：
#   ./start.sh
#   或手动设置：export TRANSMED_GROQ_API_KEY=... 然后再 ./start.sh
# 监听端口：默认 8000，可通过 PORT=8080 ./start.sh 覆盖

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

PORT="${PORT:-8000}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "========================================"
echo " TransMed 启动"
echo "  工作目录: $SCRIPT_DIR"
echo "  监听端口: $PORT"
echo "========================================"

# —— 加载 .env（只要变量没显式设置就从 .env 读取；含 = 等符号也 OK）——
if [ -f "$ENV_FILE" ]; then
    LOADED_COUNT=0
    while IFS= read -r line || [ -n "$line" ]; do
        # 去掉 \r（Windows 兼容）
        line="${line%$'\r'}"
        # 跳过空行
        [ -z "${line// }" ] && continue
        # 跳过整行注释
        case "$line" in \#*) continue ;; esac
        # 必须包含 = 才是 key=value
        case "$line" in *=*) ;; *) continue ;; esac
        # 截取 key（第一个 = 之前）
        K="${line%%=*}"
        # 截取 value（第一个 = 之后所有字符）
        V="${line#*=}"
        # 去掉 value 首尾可能存在的引号（单双引号都兼容）
        V="${V#\"}" ; V="${V%\"}"
        V="${V#\'}" ; V="${V%\'}"
        # 只在变量未显式设置（空）时采用 .env 的值
        if [ -z "${!K:-}" ]; then
            export "$K=$V"
            LOADED_COUNT=$((LOADED_COUNT + 1))
        fi
    done < "$ENV_FILE"
    echo "✅ .env 已加载 ($LOADED_COUNT 个变量)"
else
    echo "ℹ️  未发现 $ENV_FILE，使用 shell 中已 export 的环境变量"
fi

# —— 检查关键 Key 是否加载成功 ——
MISSING=0

if [ -z "${TRANSMED_GROQ_API_KEY:-}" ] || [ "${#TRANSMED_GROQ_API_KEY}" -lt 10 ]; then
    echo "❌ TRANSMED_GROQ_API_KEY 缺失或无效 —— 翻译引擎将回退到离线术语匹配"
    MISSING=1
else
    echo "✅ Groq API Key 已加载 (${#TRANSMED_GROQ_API_KEY} chars)"
fi

if [ -z "${TRANSMED_AMAP_KEY:-}" ]; then
    echo "⚠️  TRANSMED_AMAP_KEY 缺失 —— 医院列表将显示本地 demo 数据"
    MISSING=1
else
    echo "✅ AMap Web Key 已加载 (${#TRANSMED_AMAP_KEY} chars)"
fi

if [ -z "${TRANSMED_AMAP_JS_KEY:-}" ]; then
    echo "⚠️  TRANSMED_AMAP_JS_KEY 缺失 —— 导航页地图将不可见（会显示坐标文本）"
    MISSING=1
else
    echo "✅ AMap JS  Key 已加载 (${#TRANSMED_AMAP_JS_KEY} chars)"
fi

echo ""
echo "🚀 正在启动后端服务（uvicorn）..."
echo "   浏览器打开: http://127.0.0.1:$PORT"
echo ""

cd "$SCRIPT_DIR"
exec "$PYTHON_BIN" -m uvicorn transmed_app.backend:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --log-level info
