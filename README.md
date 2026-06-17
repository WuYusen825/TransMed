# TransMed — 在华外籍人士全流程智能就医陪护平台

> 多语种医疗翻译 + 智能分诊 + 国际医院匹配 + 室内导航 + 用药与保险管理。  
> Bilingual medical companion for expats in China — translating, triaging, navigating, and managing medications.

---

## 📑 目录

- [项目概览](#-项目概览)
- [功能特性](#-功能特性)
- [目录结构](#-目录结构)
- [快速开始](#-快速开始)
- [默认账户](#-默认账户)
- [API 文档](#-api-文档)
- [使用指南](#-使用指南)
- [部署到生产环境](#-部署到生产环境)
- [数据与隐私](#-数据与隐私)
- [常见问题](#-常见问题)

---

## 🌍 项目概览

**TransMed** 是面向在华外籍人士的医疗陪护平台，覆盖 16 种语言，提供：

| 模块 | 说明 |
|------|------|
| 🗣️ **多语种翻译** | 中英双向翻译 + 349 个医学术语自动对齐，识别风险等级 |
| 🩺 **智能分诊** | 55 条症状规则，识别紧急情况（胸痛、呼吸困难等）并推荐科室 |
| 🏥 **医院匹配** | 6 家北京国际医院，按专科、保险、语言、等候时间筛选 |
| 🗺️ **室内导航** | 22 节点 / 21 路径，BFS 最短路径 + SVG 可视化 |
| 💊 **用药管理** | 16 种常用药，含剂量、警告、副作用、提醒时间 |
| 🛡️ **保险理赔** | 7 家国际保险公司，理赔申请与状态跟踪 |
| 🔐 **隐私合规** | GDPR 风格的数据导出 / 一键清除 |

---

## ✨ 功能特性

- **真实数据，非空壳**：所有医院、药品、保险、症状规则均为真实可用的医学信息
- **持久化存储**：SQLite 数据库自动初始化，支持 MySQL / PostgreSQL
- **JWT 认证**：注册、登录、密码修改、会话管理
- **RESTful API**：30+ 端点，OpenAPI 文档自动生成
- **响应式前端**：现代蓝色主题，桌面 / 平板 / 手机自适应
- **在线 + 离线双栈翻译**：在线翻译（Google / MyMemory）+ 离线医疗术语兜底

---

## 📂 目录结构

```
TransMed/
├── README.md                  ← 本文件
├── requirements.txt           ← Python 依赖
├── run.py                     ← 一键启动脚本
├── data/
│   └── transmed.db            ← SQLite 数据库（首次启动自动创建）
├── transmed_app/              ← 后端 (FastAPI)
│   ├── __init__.py
│   ├── backend.py             ← API 路由
│   ├── config.py              ← 配置管理
│   ├── database.py            ← SQLAlchemy 引擎
│   ├── models.py              ← ORM 模型 (User, TranslationLog, Medication, …)
│   ├── schemas.py             ← Pydantic 数据校验
│   ├── auth.py                ← JWT / 密码哈希
│   ├── translator.py          ← 翻译引擎（双栈 + 医学术语对齐）
│   ├── initializer.py         ← 启动初始化
│   └── data.py                ← 静态知识库（医院 / 药品 / 保险 / 术语）
├── transmed_web/              ← 前端
│   ├── index.html             ← 主页面
│   ├── style.css              ← 样式
│   └── app.js                 ← 交互逻辑
└── transmed_storage/          ← JSON 持久化（兼容旧版）
    ├── translation_log.json
    ├── medication.json
    └── privacy_tokens.json
```

---

## 🚀 快速开始

### 环境要求

- **Python 3.10+**（推荐 3.12）
- macOS / Linux / Windows 均可
- 约 200 MB 磁盘空间

### 1. 安装依赖

```bash
cd /Users/johnwoo/Documents/TransMed
pip install -r requirements.txt
```

> 💡 建议使用虚拟环境：
> ```bash
> python3 -m venv .venv
> source .venv/bin/activate   # Windows: .venv\Scripts\activate
> pip install -r requirements.txt
> ```

### 2. 启动后端

```bash
python3 run.py
```

启动成功后会看到：

```
🚀 TransMed starting on http://127.0.0.1:8000
   👉 Swagger API docs: http://127.0.0.1:8000/docs
   👉 SQLite DB: ./data/transmed.db
   👉 默认管理员: admin@transmed.io / admin123
   👉 演示用户: demo@transmed.io / demo123
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 3. 打开前端

两种方式任选：

**方式 A：直接打开 HTML 文件（推荐开发）**
```bash
open transmed_web/index.html        # macOS
xdg-open transmed_web/index.html    # Linux
start transmed_web/index.html       # Windows
```

**方式 B：通过 FastAPI 提供静态文件**  
在 `backend.py` 中挂载：
```python
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="transmed_web", html=True), name="web")
```
然后访问 http://127.0.0.1:8000

---

## 👤 默认账户

首次启动时会自动创建：

| 角色 | 邮箱 | 密码 |
|------|------|------|
| 管理员 | `admin@transmed.io` | `admin123` |
| 演示用户 | `demo@transmed.io` | `demo123` |

> ⚠️ 生产环境务必修改默认密码，并设置环境变量 `TRANSMED_JWT_SECRET` / `TRANSMED_ADMIN_PASSWORD`。

---

## 📚 API 文档

启动后访问：

- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc
- **OpenAPI JSON**: http://127.0.0.1:8000/openapi.json

### 核心端点速览

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/auth/register` | POST | 注册新用户 |
| `/api/auth/login` | POST | 登录获取 JWT |
| `/api/auth/password` | POST | 修改密码 |
| `/api/translate` | POST | 中英双向翻译 |
| `/api/translate/logs` | GET | 我的翻译历史 |
| `/api/triage` | POST | 智能分诊 |
| `/api/triage/records` | GET | 我的分诊记录 |
| `/api/hospitals` | GET | 医院列表（支持多条件筛选） |
| `/api/hospitals/{id}` | GET | 医院详情 |
| `/api/navigation` | GET/POST | 室内导航路径 |
| `/api/navigation/map` | GET | 医院地图节点 |
| `/api/medications` | GET | 药品库（支持搜索、处方过滤） |
| `/api/medications/{key}` | GET | 药品详情 |
| `/api/medications/record` | GET/POST/PUT/DELETE | 个人用药计划 CRUD |
| `/api/insurance` | GET | 保险公司列表 |
| `/api/insurance/claims` | GET/POST/PUT/DELETE | 理赔申请 CRUD |
| `/api/medical_terms` | GET | 医学术语检索 |
| `/api/feedback` | POST | 提交反馈 |
| `/api/privacy/export` | GET | 导出所有个人数据 |
| `/api/privacy/wipe` | POST | 清除所有个人数据 |
| `/api/stats` | GET | 平台统计 |
| `/health` | GET | 健康检查 |

---

## 🧭 使用指南

### 🌐 场景 1：外籍患者就诊

1. **打开前端** → 在 **Translation** 面板输入英文症状
   - 例：`I have severe chest pain and difficulty breathing`
2. 点击 **Translate** → 得到中文翻译：`我胸痛、呼吸困难……`
3. 系统自动识别医学术语（chest pain、shortness of breath）并评估风险
4. 切换到 **Triage** 面板 → 同样的症状文字
5. 系统推荐 **Cardiology / Emergency**（心内科 / 急诊），并标记为 🚨 紧急
6. 切换到 **Hospitals** 面板 → 按 Cardiology、等候时间、评分筛选
7. 选择目标医院 → 切换到 **Navigation** 面板
8. 选择起点（entrance）终点（cardiology）→ 获得最短路径与中英文指引
9. 前往 **Medications** 面板查看常用药详情，**Insurance** 面板了解直付流程

### 🏥 场景 2：医院运营 / 保险代理

通过 `/api/stats` 监控平台使用情况：
```bash
curl http://127.0.0.1:8000/api/stats
```

返回示例：
```json
{
  "hospitals": 6,
  "medications": 16,
  "triage_rules": 55,
  "medical_terms": 349,
  "insurance_providers": 7,
  "users": 12,
  "translations": 48,
  "urgent_events": 3
}
```

### 🔬 场景 3：API 集成方

使用 JWT 调用：
```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@transmed.io","password":"demo123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 调用任意受保护接口
curl -X POST http://127.0.0.1:8000/api/translate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"text":"headache and fever","source":"en","target":"zh"}'
```

---

## 🌐 部署到生产环境

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TRANSMED_DATABASE_URL` | `sqlite:///./data/transmed.db` | 切换 MySQL：`mysql+pymysql://user:pwd@host/db` |
| `TRANSMED_JWT_SECRET` | `transmed-dev-secret-change-me` | **必须改为强随机字符串** |
| `TRANSMED_ADMIN_EMAIL` | `admin@transmed.io` | 初始管理员邮箱 |
| `TRANSMED_ADMIN_PASSWORD` | `admin123` | 初始管理员密码（**首次登录后立即修改**） |

### 使用 Gunicorn（推荐生产）

```bash
pip install gunicorn
gunicorn transmed_app.backend:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### Docker（示例）

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
ENV TRANSMED_JWT_SECRET=please-change-me
CMD ["gunicorn", "transmed_app.backend:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
```

```bash
docker build -t transmed .
docker run -p 8000:8000 -v $(pwd)/data:/app/data transmed
```

### Nginx 反向代理（示例）

```nginx
server {
    listen 80;
    server_name transmed.example.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

---

## 🔐 数据与隐私

- **本地存储**：默认 SQLite 文件 `./data/transmed.db`
- **密码安全**：bcrypt 哈希（不存明文）
- **JWT**：7 天有效，HS256 签名
- **用户权利**：
  - 导出我的所有数据 → `GET /api/privacy/export`
  - 清除我的所有数据 → `POST /api/privacy/wipe`（保留账户）
- **后台不存储翻译原文给第三方**：在线翻译通过 `deep-translator` 调用，遵循其隐私政策
- **不在前端持久化敏感数据**：所有 token 存于 `localStorage`（可改 HttpOnly cookie）

---

## ❓ 常见问题

### Q1: 启动时 `Address already in use`
A: 8000 端口被占用。
```bash
lsof -ti:8000 | xargs kill -9   # macOS / Linux
```

### Q2: bcrypt 报错 `module 'bcrypt' has no attribute '__about__'`
A: 固定 `bcrypt==4.1.3`（已在 `requirements.txt` 锁定）。如已安装 5.x 版本：
```bash
pip install "bcrypt==4.1.3"
```

### Q3: 在线翻译失败，是否还能用？
A: 可以。系统会自动 fallback 到离线医学术语库，仍能输出带置信度的翻译。

### Q4: 如何重置数据库？
```bash
rm -f data/transmed.db
python3 run.py   # 重新初始化
```

### Q5: 如何重置默认管理员密码？
```bash
TRANSMED_ADMIN_PASSWORD=mynewpass python3 run.py
rm -f data/transmed.db   # 删除旧库，让新密码生效
```

### Q6: 前端如何对接正式后端域名？
A: 修改 `transmed_web/app.js` 顶部的 `API_BASE` 常量。

### Q7: 支持哪些语言？
A: 16 种 — 英语、中文（简/繁）、日语、韩语、法语、德语、西班牙语、意大利语、俄语、阿拉伯语、葡萄牙语、荷兰语、土耳其语、波兰语、瑞典语、希腊语。

---

## 📜 License

仅供学习与内部演示使用。医疗数据仅供参考，**不可替代专业医师诊断**。如有紧急情况，请立即拨打 120（中国大陆）或前往最近急诊。

---

## 🤝 反馈

提交 Issue 或通过前端 **Feedback** 面板 / `POST /api/feedback` 提供建议。
