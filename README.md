# AI 小说转剧本工具 — MVP

> 定位：**小说 → 结构化剧本（YAML）**，支持**影视 / 短剧双路**：默认产出通用影视剧本；选择短剧（short_drama）则进一步把行业铁律（2~3 分钟一集、开场钩子、集尾扣子）算法化为可计算的分集产线。

- **后端**：Python + FastAPI，转换流水线（分章 → 人物抽取 → 逐场转换 → 专业字段装配 →〔短剧〕拆集 → 校验 → YAML）
- **前端**：Vue 3 + Vite，双栏编辑器（左原文 / 右可编辑剧本）+〔短剧〕分集体检 + YAML 导出
- **LLM**：Claude（`claude-opus-4-8`，结构化输出）；**无 API Key 时自动降级为离线规则引擎**，demo 仍可跑通

## 目录结构
```
bisai/
├── backend/          # Python 后端
│   ├── app/
│   │   ├── schema.py     # 剧本 pydantic 模型 + 校验
│   │   ├── chapters.py   # 分章
│   │   ├── converter.py  # 核心转换（Claude + 离线规则）
│   │   ├── episodes.py   # 短剧拆集（钩子/扣子/时长/体检）
│   │   ├── pipeline.py   # 流水线装配（转换 →〔短剧〕拆集）
│   │   ├── exporter.py   # YAML 导出
│   │   └── main.py       # FastAPI 接口
│   ├── cli.py        # 命令行端到端入口
│   ├── requirements.txt
│   └── .env.example
├── frontend/         # Vue 3 + Vite 前端
│   ├── src/{main.js, App.vue, api.js}
│   ├── index.html
│   └── package.json
└── samples/sample_novel.txt   # 原创示例小说（3 章）
```

## 快速开始

### 1. 后端
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # 可选：填入 ANTHROPIC_API_KEY 用 Claude；不填则离线规则引擎
uvicorn app.main:app --reload --port 8000
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

## API
| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/health`  | 健康检查 + 当前引擎 |
| POST | `/api/convert` | `{text,title,author}` → 剧本对象 + YAML + 统计 |
| POST | `/api/export`  | `{screenplay}` → 编辑后重新生成 YAML + 校验 |

## 引擎说明
- 设置 `ANTHROPIC_API_KEY` → 使用 Claude 结构化输出，转换质量高（推荐演示）。
- 未设置 / `FORCE_OFFLINE=true` → 离线规则引擎（按引号识别对白、心理词识别旁白、时间词切场），
  质量有限但**零依赖跑通**，适合无网环境兜底。

## Schema
剧本 YAML Schema 与设计原因见定稿文档 `../docs/06_剧本YAML_Schema定义与产业化设计.md`（`02` 为 v0.1 历史稿）。

## MVP 已实现 / 待办
- [x] 上传/粘贴 ≥3 章小说 → 结构化剧本（影视 / 短剧双路）
- [x] 分章 / 切场 / 心理描写转旁白 / 对白归属
- [x] 创作/制片/微短剧三层专业字段（人物弧光、制片分解、时长、溯源等）
- [x] **短剧拆集**：按口播时长成集，每集带钩子/扣子/时长 + 产能体检
- [x] 双栏在线编辑（场头、梗概、元素增删改）
- [x] YAML 导出（短剧含 episodes 分集结构）+ Schema 校验
- [ ] 原文↔剧本高亮对照（加分项）
- [ ] Fountain/PDF 导出（加分项）
- [ ] 分集时间轴可视化 / 拖拽调整分集边界（加分项）
