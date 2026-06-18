# Render.com / Docker 部署用 Dockerfile
FROM python:3.12-slim

WORKDIR /app

# 构建依赖（尽量减小镜像）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码
COPY . .

# 运行时环境变量（API key 在 Render 控制台设置，不写进镜像）
ENV PORT=8000
ENV TRANSMED_GROQ_MODEL=llama-3.3-70b-versatile
ENV TRANSMED_GROQ_BASE_URL=https://api.groq.com/openai/v1

EXPOSE 8000

# 启动命令（Render 会把 $PORT 自动注入）
CMD ["sh", "-c", "python -m uvicorn transmed_app.backend:app --host 0.0.0.0 --port ${PORT:-8000}"]
