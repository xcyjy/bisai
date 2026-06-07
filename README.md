# AI 小说转剧本工具

> 定位：**小说 → 结构化剧本（YAML）**，支持**影视 / 短剧双路**——默认产出通用影视剧本；选择短剧（`short_drama`）则把行业铁律（2~3 分钟一集、开场钩子、集尾扣子）算法化为可计算的分集产线。
>
> 七牛云 × XEngineer 暑期实训营 · 题目三 ｜ 当前版本 **v0.2**

- **后端**：Python + FastAPI。转换流水线（分章 → 人物抽取 → 逐场转换 → 专业字段装配 →〔短剧〕拆集 → 校验 → YAML），并提供**多 Agent 异步编排**与完整的 **C 端体系**（登录 / 作品库 / 积分计费 / 异步任务）。
- **前端**：Vue 3 + Vite + Pinia。营销首页 + 双栏编辑器（左原文 / 右可编辑剧本）+〔短剧〕分集体检 + Agent 实时流 + YAML 导出。
- **LLM**：Claude（`claude-opus-4-8`，tool-use 结构化输出，兼容中转站）；**无 API Key 时自动降级为离线规则引擎**，demo 仍可跑通。





视频链接：https://www.bilibili.com/video/BV11PEh61EdJ/?spm_id_from=333.1387.upload.video_card.click

## ✨ 核心特性

| 能力 | 说明 |
|------|------|
| **三引擎可选** | 离线规则（免费/零依赖）· AI 精修（单次 Claude）· **多 Agent 旗舰**（并发编排 + 实时流） |
| **多 Agent 编排** | 逐章并发 + 双层缓存（结果缓存 0 token / Prompt 缓存）+ 智能模型路由（量活走快模型）+ 单 Agent 自检改写 + Critic 回环 + Token 账本，全程 SSE 可视化 |
| **专业字段装配** | 装配期确定性补全：溯源 `source_ref`、出场 `cast`、预估时长 `est_duration_sec`、日夜 `day_night`——无论在线/离线都产出 |
| **短剧拆集** | 按口播时长贪心成集，每集自带钩子 / 扣子 / 时长 + 四项产能体检（钩子/扣子/时长/互动） |
| **三重降级** | 任一 Agent / 在线调用失败 → 回落离线规则，保证「再差也有合法 YAML」 |
| **C 端产品化** | 邮箱注册登录（JWT）· 作品库与版本化剧本 · 积分计费 · 后台异步任务 · 套餐/积分包（mock 支付） |

## 目录结构

```
bisai/
├── backend/                      # Python + FastAPI 后端
│   ├── app/
│   │   ├── main.py               # FastAPI 入口（匿名接口 + 多 Agent SSE）
│   │   ├── schema.py             # 剧本 Pydantic 模型 + 校验（validate_screenplay）
│   │   ├── chapters.py           # 分章 / 分段
│   │   ├── converter.py          # 转换核心（Claude tool-use + 离线规则引擎）
│   │   ├── pipeline.py           # 同步流水线 + 专业字段装配
│   │   ├── orchestrator.py       # 多 Agent 异步编排（并发/缓存/自检/Critic/账本）
│   │   ├── episodes.py           # 短剧拆集（钩子/扣子/时长/体检）
│   │   ├── exporter.py           # YAML 导出
│   │   ├── agentcache.py         # Agent 结果缓存（命中=0 token，内存+磁盘）
│   │   ├── models.py             # 中转站可用模型列表 + 质量/均衡/经济分档
│   │   ├── core/                 # config 配置 · security/deps 鉴权 · billing 计费 · plans 套餐
│   │   ├── db/                   # SQLModel 模型（users/projects/screenplays/jobs/orders/usage_logs）+ 会话
│   │   └── api/                  # 登录态路由：auth / projects / jobs / orders / account
│   ├── cli.py                    # 命令行端到端入口
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/                     # Vue 3 + Vite 前端
│   ├── src/
│   │   ├── main.js  App.vue  api.js   # 入口 / 全局壳 / 接口封装（JWT·SSE）
│   │   ├── router/index.js            # 路由 + 鉴权守卫
│   │   ├── stores/auth.js             # Pinia 登录态
│   │   └── views/                     # Landing·Login·Workspace·MyWorks·Pricing·Account
│   ├── index.html  nginx.conf  Dockerfile  package.json
├── docs/                         # 方案文档（06 为剧本 Schema 定稿，核心交付物）
├── samples/                      # 原创示例小说 + 输出 YAML
├── docker-compose.yml            # 本地一键起（SQLite）
└── docker-compose.cloud.yml      # 云部署（PostgreSQL）
```

## 快速开始

### 1. 后端
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # 可选：填 ANTHROPIC_API_KEY 启用 Claude；不填则离线规则引擎
uvicorn app.main:app --reload --port 8000
# 首次启动自动建表（SQLite，零配置）
```

### 2. 前端
```bash
cd frontend
npm install
npm run dev        # 打开 http://localhost:5173
```

### 3. 命令行（不开前端也能验证核心链路）
```bash
cd backend
python cli.py ../samples/sample_novel.txt --title 旧城轨迹 -o out.yaml
```

### 4. Docker（一键起前后端）
```bash
docker compose up --build              # 本地：SQLite
# 云部署（PostgreSQL）：见 docker-compose.cloud.yml 与 .env.cloud.example
```

## 环境变量

复制 `backend/.env.example` 为 `.env` 按需填写：

| 变量 | 默认 | 说明 |
|------|------|------|
| `ANTHROPIC_API_KEY` | 空 | 填入则启用 Claude；不填自动走离线引擎 |
| `ANTHROPIC_BASE_URL` | 空 | 兼容 Anthropic 协议的中转站入口；留空用官方 API |
| `SCRIPT_MODEL` | `claude-opus-4-8` | 分场主模型 |
| `FAST_MODEL` | `claude-haiku-4-5-20251001` | 「量活」快模型（人物抽取/自检），智能路由用 |
| `FORCE_OFFLINE` | `false` | 强制离线（即使配了 key，调试时可关 AI） |
| `FREE_SIGNUP_CREDITS` | `3` | 注册赠送积分 |
| `DATABASE_URL` | `sqlite:///./local.db` | 云上改 `postgresql+psycopg://...` |
| `JWT_SECRET` | `dev-secret-...` | ⚠️ 生产务必改随机长串 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `10080` | Token 有效期（7 天） |
| `CORS_ORIGINS` | `localhost:5173,...` | 逗号分隔的前端来源 |

## 引擎说明

| 引擎 | 触发 | 成本 | 特点 |
|------|------|------|------|
| **离线规则** | 未配 key / `FORCE_OFFLINE=true` / 匿名试用 | 免费（0 token / 0 积分） | 按引号识别对白、心理词识别旁白、时间词切场；质量有限但**零依赖跑通** |
| **AI 精修** | 作品转换选 `engine=ai` | 1 积分 | 单次 Claude tool-use 结构化输出，质量高 |
| **多 Agent 旗舰** | `POST /api/convert/agents` | 2 积分 | 并发编排 + 双层缓存 + 自检/Critic 回环 + Token 账本，SSE 实时流 |

> 离线转换不扣积分；AI / Agent 只有**真的调用了大模型**才扣分并记账（token → 美元成本写入 `usage_logs`）。

## API 一览

**匿名接口（可不登录试用）**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/health` | 健康检查 + 当前引擎 |
| POST | `/api/convert` | `{text,title,...}` → 剧本对象 + YAML + 统计（离线） |
| POST | `/api/export` | `{screenplay}` → 编辑后重新生成 YAML + 校验 |
| GET  | `/api/models` | 中转站可用 Claude 模型列表（分档），供前端下拉 |

**多 Agent（需登录 + 积分）**

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/convert/agents` | 多 Agent 编排转换（**SSE 流式**）：实时推送每个 Agent 事件 + 渐进式出稿，最后推 result |

**认证 `/api/auth`**

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 邮箱注册（送 `FREE_SIGNUP_CREDITS` 积分） |
| POST | `/api/auth/login` | 登录，返回 JWT |
| GET / PATCH | `/api/auth/me` | 当前用户 / 改昵称 |

**作品 `/api/projects`（需登录，按 user_id 强隔离）**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/projects` | 作品列表 |
| POST | `/api/projects` | 新建作品并发起后台转换任务（`engine=offline\|ai`） |
| GET  | `/api/projects/{id}` | 作品详情（剧本 + YAML + 任务状态） |
| PUT  | `/api/projects/{id}/screenplay` | 保存编辑（版本化）+ 校验 |
| POST | `/api/projects/{id}/episodes` | 一键拆集（短剧，免费规则引擎） |
| DELETE | `/api/projects/{id}` | 删除作品 |

**任务 / 账户 / 计费**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/jobs/{id}` | 异步转换任务状态（前端轮询进度） |
| GET  | `/api/me/stats` | 账户统计（积分/会员/本月用量/作品数） |
| GET  | `/api/plans` | 套餐 + 积分包目录 |
| POST | `/api/orders` | 下单（返回 mock 支付入口） |
| POST | `/api/orders/{id}/pay` | 模拟支付成功 → 发放权益（云上替换为支付回调） |
| GET  | `/api/orders` | 订单历史 |

## 数据模型（SQLModel）

`users`（积分/会员）· `projects`（一篇小说=一个作品）· `screenplays`（版本化剧本，支持回滚）· `jobs`（异步转换任务）· `usage_logs`（token/成本审计）· `orders`（会员/积分包订单）。本地 SQLite 零配置，云上切 PostgreSQL。

## Schema

剧本 YAML Schema 与设计原因见定稿文档 [`docs/06_剧本YAML_Schema定义与产业化设计.md`](docs/06_剧本YAML_Schema定义与产业化设计.md)（`02` 为 v0.1 历史稿）。Schema 按工业流程分三层、全部可选可降级：

- **创作层**（编剧）：logline / genre / tone、act / beat、人物 role / arc、对白 extension。
- **制片层**（统筹）：heading.day_night、scene.breakdown 分解表、est_duration_sec 时长。
- **微短剧层**（操盘）：episode / hook / cliffhanger / pay_point / highlights。

## 进度

- [x] 上传/粘贴 ≥3 章小说 → 结构化剧本（影视 / 短剧双路）
- [x] 分章 / 切场 / 心理描写转旁白 / 对白归属
- [x] 创作/制片/微短剧三层专业字段（人物弧光、制片分解、时长、溯源等）
- [x] **短剧拆集**：按口播时长成集，每集带钩子/扣子/时长 + 产能体检
- [x] **多 Agent 编排**：并发 + 双层缓存 + 自检/Critic 回环 + Token 账本 + SSE 实时流
- [x] 双栏在线编辑（场头、梗概、元素增删改）+ YAML 导出 + Schema 校验
- [x] **C 端体系**：注册登录、作品库与版本化、积分计费、异步任务、套餐/积分包
- [ ] 原文↔剧本高亮对照（加分项）
- [ ] Fountain / PDF 导出（加分项）
- [ ] 分集时间轴可视化 / 拖拽调整分集边界（加分项）
