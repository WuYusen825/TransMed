# TransMed — 在华外籍人士全流程智能就医陪护平台

> 多语种医疗翻译 + 智能分诊 + 真实医院推荐 + 页面内地图导航 + 用药管理。  
> Bilingual medical companion for foreigners in China — translating, triaging, recommending real hospitals, navigating, and managing medications.

> 🎨 **2026 改版**：浅色「Claude 奶油风」+ 苹果式滚动动效的全新前端；导航升级为页面内真实路线 + 转向步骤 + 一键跳转地图 App；医院推荐升级为「症状 → 分诊 → 按匹配度排序 + 推荐理由 + 真实评价」。

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

**TransMed** 是面向在华外籍人士的医疗陪护平台，覆盖 12 种语言，提供：

| 模块 | 说明 |
|------|------|
| 🗣️ **多语种翻译** | 多语互译 + 349 个医学术语自动对齐，置信度评分 + 4 级风险提示 |
| 🩺 **智能分诊** | 55 条症状规则，识别紧急情况（胸痛、呼吸困难等）并推荐科室 |
| 🏥 **医院推荐** | 高德 POI 真实医院数据：症状 → 按匹配度排序，给出推荐理由 + 真实评价（高德 + 好大夫） |
| 🗺️ **地图导航** | 高德 JS 地图：起点/终点标记 + 真实路线折线 + 转向步骤 + 一键跳转 Apple/Google/高德/百度地图 |
| 💊 **用药管理** | 16 种常用药库（剂量、警告、副作用）+ 个人用药提醒（增删改查） |
| 🔐 **隐私合规** | GDPR 风格的数据一键导出 / 清除；可选登录，最小化留存 |

---

## ✨ 功能特性

- **真实数据，非空壳**：医院来自高德 POI 实时检索（真实坐标 / 评分 / 评价数），药品、症状规则均为真实医学信息
- **浅色 Claude 奶油风前端**：暖奶油底 + 珊瑚色点缀 + 衬线大标题 + 苹果式滚动入场/视差/毛玻璃；桌面 / 平板 / 手机自适应，支持 `prefers-reduced-motion`
- **持久化存储**：SQLite 数据库自动初始化，支持 MySQL / PostgreSQL
- **JWT 认证**：注册、登录、密码修改、会话管理（前端 localStorage 持久会话）
- **RESTful API**：30+ 端点，OpenAPI 文档自动生成
- **在线 + 离线双栈翻译**：在线 Groq LLM 翻译 + 离线医疗术语兜底，断网也能给出带置信度的结果

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
│   ├── data.py                ← 静态知识库（医院 / 药品 / 术语）
│   ├── amap.py                ← 高德 POI 检索 / 路线 / 前端配置（含安全密钥）
│   └── reviews.py             ← 医院真实评价（高德 + 好大夫）
├── build_appjs.py            ← 前端 app.js 的「源文件」（JS 内嵌，运行后生成两份）
├── transmed_web/              ← 前端（后端 FastAPI 提供静态服务）
│   ├── index.html             ← 主页面
│   ├── style.css              ← 浅色 Claude 主题样式
│   └── app.js                 ← 交互逻辑（由 build_appjs.py 生成，勿手改）
└── docs/                      ← 与 transmed_web 同步的镜像（供 GitHub Pages）
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
| `/api/hospitals` | GET | 医院列表（高德 POI，支持症状/专科/语言/评分筛选） |
| `/api/recommendations` | POST | 症状 → 分诊 + 按匹配度排序的医院推荐（含推荐理由） |
| `/api/hospitals/{id}` | GET | 医院详情（含真实评价） |
| `/api/hospitals/{id}/reviews` | GET | 医院真实评价（高德 + 好大夫） |
| `/api/navigation` | GET | 室外导航：目标坐标 + 路线摘要 + 地图 App 链接 |
| `/api/amap/config` | GET | 前端高德配置（JS Key + 安全密钥，不泄露 Web 服务 Key） |
| `/api/medications` | GET | 药品库（支持搜索、处方过滤） |
| `/api/medications/{key}` | GET | 药品详情 |
| `/api/medications/record` | GET/POST/PUT/DELETE | 个人用药计划 CRUD |
| `/api/medical_terms` | GET | 医学术语检索 |
| `/api/feedback` | POST | 提交反馈 |
| `/api/privacy/export` | GET | 导出所有个人数据 |
| `/api/privacy/wipe` | POST | 清除所有个人数据 |
| `/api/stats` | GET | 平台统计 |
| `/health` | GET | 健康检查 |

---

## 🧭 使用指南

### 🌐 场景 1：外籍患者就诊

1. **打开前端** → 在 **Translate** 面板输入英文症状
   - 例：`I have severe chest pain and difficulty breathing`
2. 点击 **Translate** → 得到中文翻译 + 置信度评分 + 风险等级 + 识别出的医学术语
3. 切换到 **Hospitals** 面板 → 填入同样的症状，点击 **Analyze & recommend**
4. 系统分诊到 **Cardiology / 心内科**（标记 🚨 紧急），并按匹配度排序推荐真实医院
5. 每张医院卡片给出**推荐理由**（专科匹配 / 评分 / 距离 / 语言）+ 真实评价 + 匹配度环
6. 点卡片上的 **Navigate →** → 跳转 **Navigation** 面板，地图自动定位到该医院
7. 选择出行方式（步行/驾车/公交），查看页面内路线与转向步骤，或一键跳转手机地图 App
8. 前往 **Medication** 面板查看药品详情并设置用药提醒；**Account** 面板可一键导出/清除个人数据

### 🏥 场景 2：平台运营监控

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
| `TRANSMED_GROQ_API_KEY` | _(空)_ | Groq LLM 翻译引擎密钥；不填则回退离线术语匹配 |
| `TRANSMED_AMAP_KEY` | _(内置 demo)_ | 高德「**Web 服务**」Key：后端医院 POI 检索 / 地理编码 |
| `TRANSMED_AMAP_JS_KEY` | _(内置 demo)_ | 高德「**Web 端 (JS API)**」Key：前端地图 |
| `TRANSMED_AMAP_SECURITY_JS_CODE` | _(空)_ | 与 JS Key 配套的**安全密钥**；**不填则页面内画不出路线**（见下方「高德地图配置」） |

> ⚠️ 仓库内置的高德 Key 仅供本地试跑，**生产请在 Render 控制台填入你自己的 Key**（`render.yaml` 已留好 `sync:false` 占位）。

### 🗺️ 高德地图配置（含「安全密钥」申请，导航画线必读）

导航页要在**页面内画出真实路线 + 转向步骤**，依赖高德 JS API 2.0。自 2021-12-02 起，高德新建的 JS Key
**必须配套一个「安全密钥」(securityJsCode)** 才能调用 路线规划 / 定位 服务；**不配它，地图只会显示起点/终点两个标记，画不出线**——这正是改版前「导航只能看到两个点」的根因。

TransMed 已把它做成「**填了就生效，不填自动降级**」：

- 未配置安全密钥 → 导航页仍显示地图 + 起终点标记 + 直线距离/时间估算 + 一键跳转 Apple/Google/高德/百度地图 App。
- 配置后 → 自动在页面内画出真实路线折线 + 中文转向步骤 + 真实距离/用时。

#### 三步申请并配置

1. **登录高德开放平台控制台** → <https://console.amap.com/dev/key/app>
   - 用你申请 `TRANSMED_AMAP_JS_KEY` 的同一个账号、同一个「应用」。

2. **为「Web 端 (JS API)」Key 生成安全密钥**
   - 进入 **应用管理 → 我的应用**，找到你那把 **服务平台 = Web 端 (JS API)** 的 Key。
   - 如果这把 Key 还没有安全密钥，控制台会提示「**绑定安全密钥**」/「重新获取」；点击后会得到一串
     与该 Key 配对的 **安全密钥 (securityJsCode)**，形如 `4a1b...`（32 位）。
   - ⚠️ 安全密钥与 JS Key 一一配对；换了 JS Key 必须重新生成安全密钥。

3. **把安全密钥填进 Render 环境变量**
   - Render 控制台 → 你的 `transmed-api` 服务 → **Environment** → 新增：
     ```
     TRANSMED_AMAP_SECURITY_JS_CODE = <你的安全密钥>
     ```
   - 同时确认这三项都填了你自己的真实值（不要用仓库内置 demo）：
     `TRANSMED_AMAP_KEY`（Web 服务）、`TRANSMED_AMAP_JS_KEY`（Web 端）、`TRANSMED_AMAP_SECURITY_JS_CODE`（安全密钥）。
   - 保存后 Render 会自动重新部署；打开导航页选一家医院，即可看到画出的路线与转向步骤。

> **域名白名单**：高德 JS Key 可在控制台设置「域名白名单」。请把你的线上域名（如 `transmed.onrender.com`）
> 加进去，安全密钥以明文下发到前端是高德官方支持的简化用法，配合域名白名单即可防止 Key 被盗用。
> 若需更高安全性，可改用高德「代理服务器(serviceHost)」方案。

> **本地开发**：`export TRANSMED_AMAP_SECURITY_JS_CODE=<安全密钥>` 后再 `./start.sh` 即可本地验证画线。

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
A: 改 `transmed_web/index.html` 里的 `<meta name="api-base" content="...">`（同步改 `docs/index.html`）。

### Q7: 改了前端逻辑怎么生效？
A: 前端 `app.js` 由 `build_appjs.py` 生成。改完逻辑后运行 `python3 build_appjs.py`，会同时写入 `transmed_web/app.js` 和 `docs/app.js`。改 `index.html` / `style.css` 后记得手动 `cp` 一份到 `docs/`。

### Q8: 支持哪些语言？
A: 12 种 — 英语、中文、日语、韩语、法语、德语、西班牙语、意大利语、俄语、阿拉伯语、葡萄牙语、印地语。

---

## 📜 License

仅供学习与内部演示使用。医疗数据仅供参考，**不可替代专业医师诊断**。如有紧急情况，请立即拨打 120（中国大陆）或前往最近急诊。

---

## 🤝 反馈

提交 Issue 或通过前端 **Feedback** 面板 / `POST /api/feedback` 提供建议。
