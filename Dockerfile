FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8000
# 🔐 在云平台（Railway/Render/Fly.io）控制台设置环境变量：
#    TRANSMED_DEEPSEEK_API_KEY=（你的 DeepSeek key，格式以 sk- 开头）
#    不要把完整 key 写进 Dockerfile 或提交的代码里
ENV TRANSMED_DEEPSEEK_API_KEY=""
ENV TRANSMED_DEEPSEEK_MODEL=deepseek-v4-pro
ENV TRANSMED_DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
EXPOSE 8000
CMD ["python3", "run.py"]
