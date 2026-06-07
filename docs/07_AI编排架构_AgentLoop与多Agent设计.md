# AI 编排架构：模型切换 · Agent Loop · 多 Agent 编排（设计稿 v0.1）

> 目标：把当前「固定串行流水线」升级为「**可编排、可并发、可自我纠错**」的 Agent 架构，并支持**按中转站模型动态切换**。
> 本文先给架构与图，**实现分阶段**（见第七节）。

---

## 一、现状（基线）

当前 `pipeline.convert_novel` 是一条**固定串行流水线**：

```
故事元信息(1次) → 人物抽取(1次) → 逐章转换(顺序, N次) → 装配 → validate → YAML
```

- 优点：简单、确定、可降级（离线兜底）。
- 局限：① 串行——N 章就是 N 次顺序等待，慢；② 无自我纠错——校验失败只是报告 problems，不会自动修；③ 模型写死 `settings.script_model`，前端不能选；④ 制片分解/微短剧字段要么靠单次大 prompt 一把梭，要么没做精。

---

## 二、模型动态切换（小而快的增强，先落地）

中转站实测：仅 `claude-*`（Anthropic 协议 `/v1/messages`）可用。

```
中转站 /v1/models
      │  (后端拉取并白名单过滤 claude-*)
      ▼
后端 GET /api/models  ──►  [{id, label, tier}]      tier: 质量/均衡/经济
      │                     opus-4-8=质量  sonnet-4-6=均衡  haiku-4-5=经济
      ▼
前端「模型」下拉（紧挨「离线/AI」开关）
      │  转换请求体带 model
      ▼
convert 请求 {text,title,engine:'ai',model}
      │
      ▼
converter 用请求级 model（覆盖 settings.script_model）
```

要点：模型选择需从「全局配置」改为「**请求级参数**」，贯穿 `convert_novel → convert_chapter/_structured → messages.create(model=…)`。这是后续 Agent 架构里「按任务路由不同模型」的基础（贵活用 opus、量活用 haiku）。

---

## 三、目标架构图（Orchestrator + 多 Agent + 黑板 + Critic Loop）

```
                          ┌───────────────────────────────────────────────┐
                          │                 前端 (Vue 3)                    │
                          │  引擎/模型选择 · 进度条 · ★Agent 活动流(SSE)     │
                          └───────────────────────┬───────────────────────┘
                                                  │  SSE/WS：每个 Agent 的开始/结束/token
                          ┌───────────────────────▼───────────────────────┐
                          │           Orchestrator（编排器 = Agent Loop）   │
                          │  · Plan：把小说拆成任务图(DAG)                   │
                          │  · Dispatch：并发 fan-out / 顺序依赖 join        │
                          │  · Budget：token/积分预算与限流                 │
                          │  · Retry/Degrade：失败重试→降级离线             │
                          │  · Loop：读 Critic 工单 → 回派对应 Agent 修复    │
                          └──┬───────────┬───────────┬───────────┬──────────┘
              plan once      │  fan-out  │           │           │
            ┌────────────────┘  (并发)   │           │           │
            ▼                            ▼           ▼           ▼
   ┌──────────────────┐   ┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
   │ 人物 Agent        │   │ 分场转换 Agent ×N │ │ 制片分解 Agent│ │ 微短剧 Agent      │
   │ 全局1次, 产人物表 │   │ 每章1个, 并发执行 │ │ 每场, 可并发  │ │ 拆集/钩子/扣子    │
   │ tool-use 结构化   │   │ tool-use 结构化   │ │ tool-use      │ │ (script_type=短剧)│
   └────────┬─────────┘   └────────┬─────────┘ └──────┬───────┘ └────────┬─────────┘
            │ 写人物表             │ 写各章场次        │ 写breakdown        │ 写episode/hook
            └──────────┬──────────┴─────────┬─────────┴────────────────────┘
                       ▼                     ▼
              ┌─────────────────────────────────────┐
              │        共享黑板 Blackboard           │
              │  meta / characters / scenes /        │◄───────┐
              │  breakdown / episodes  (单一事实源)   │        │ 回环(loop back)
              └───────────────┬─────────────────────┘        │ 只重派出问题的环节
                              ▼                                │
                   ┌────────────────────────┐                 │
                   │   Critic / QA Agent     │─────────────────┘
                   │  · validate_screenplay  │  产出「修复工单」：
                   │  · 人物归属/场号/空场   │  如"第3场说话人不在人物表→重判该场"
                   │  · 原文↔剧本 情节保留率 │
                   └───────────┬────────────┘
                               ▼  通过(valid 且无工单)
                     装配 → exporter.to_yaml → YAML 交付
```

---

## 四、Agent Loop（编排器主循环）

编排器不是「一把梭 prompt」，而是一个**有状态的循环**：

```
state = Blackboard(novel)
plan  = orchestrator.plan(state)          # 1) 规划任务图(DAG)
while not done and budget.ok():
    ready = plan.ready_tasks(state)        # 2) 取无依赖阻塞的任务
    results = await gather(run(t) for t in ready)   # 3) 并发执行（见第六节）
    state.merge(results)                   # 4) 写回黑板
    issues = critic.review(state)          # 5) QA 审查
    if issues:
        plan.enqueue_fixes(issues)         # 6) 把"修哪场/哪个字段"作为新任务回环
    else:
        done = True
return assemble(state)                      # 7) 装配 + 导出 YAML
```

- **收敛保证**：每轮 Critic 工单必须「指名道姓」（第几场、哪个字段），回环只重跑该子任务，不整篇重来；设最大轮数 + token 预算双闸，避免死循环。
- **可降级**：任一 Agent 连续失败 → 该子任务降级到离线规则，循环继续，**整体不中断**。

---

## 五、多 Agent 通信（黑板模式，而非点对点喊话）

采用 **Blackboard（黑板）** 而非 Agent 互相直接对话：

- **单一事实源**：黑板就是那份 `screenplay dict`（meta/characters/scenes/…）。
- **读写契约**：每个 Agent 声明它「读哪些键、写哪些键」——
  - 人物 Agent：读 `novel` → 写 `characters`
  - 分场 Agent：读 `novel[chapter] + characters` → 写 `scenes[chapter]`
  - 制片 Agent：读 `scenes` → 写 `scenes[].breakdown`
  - Critic：读 `全部` → 写 `issues 工单`
- **好处**：解耦（Agent 不需知道彼此存在）、可并发（写不同键不冲突）、可观测（黑板每次变更都能推给前端 SSE 做「Agent 活动流」）。
- **冲突避免**：按「键分区」写入；同一分区（如同一章的场次）串行，跨分区并发。

---

## 六、并发工具调用（两个层级）

1. **Agent 级并发（fan-out）**：N 章的「分场转换 Agent」彼此独立 → `asyncio.gather` 一起跑。
   - 用 `anthropic.AsyncAnthropic(base_url=…)`，每个 Agent 一次 `messages.create(tools=[…], tool_choice=…)`。
   - 加 `Semaphore(并发上限)` 防止打爆中转站限流；失败单章重试/降级，不拖累其他章。
2. **单次响应内的多工具并发**：一次 `messages.create` 里挂多个 tool，模型可在一轮里**并行发起多个 tool_use**（如同时产出 `scenes` 和 `breakdown`）。编排器解析 `content` 中的多个 `tool_use` 块分别落库。

> 现状已具备地基：`converter._structured()` 已用 tool-use 拿结构化输出，改 `AsyncAnthropic` + `gather` 即可并发。

---

## 七、与现有代码的映射 + 分阶段落地

| 现有 | 目标 | 阶段 |
|---|---|---|
| `pipeline.convert_novel` 串行 for 循环 | Orchestrator + `asyncio.gather` 并发逐章 | **P1（高性价比）** |
| `converter._structured`（同步） | 增 `AsyncAnthropic` 异步版 + 信号量限流 | P1 |
| `settings.script_model` 写死 | 请求级 `model` 参数 + `GET /api/models` + 前端下拉 | **P0（小而快）** |
| `validate_screenplay` 只报告 | 升级为 Critic Agent：产「修复工单」并回环重判问题场 | **P2（提质量）** |
| 制片字段塞进分场大 prompt | 拆出「制片分解 Agent」按场并发精修 | P2 |
| 微短剧靠「一键拆集」后处理 | 「微短剧 Agent」入编排，原生产出 hook/扣子/卡点 | P3 |
| 无进度细节 | 黑板变更 → SSE「Agent 活动流」前端可视化 | P3 |

**建议顺序**：P0 模型切换（半天）→ P1 并发逐章（明显提速）→ P2 Critic 自纠错（提质量，最有「Agent」感）→ P3 微短剧 Agent + 可视化。

---

## 七·补、缓存命中 与 Token 账本（亮点与省钱核心）

### 双层缓存
1. **结果缓存（语义级，命中即 0 token）**
   `key = sha256(model | schema_version | agent | 输入文本)` → 结构化结果 dict。
   内存 + 磁盘（`backend/.cache/agents.json`）持久化。同一小说/同一章再转 → **毫秒级、0 token、0 积分**。
   事件标记 `cache_hit: result`，可视化里显示「⚡命中缓存」。
2. **Prompt 缓存（token 级，跨章省钱）**
   把**静态前缀**（转换铁律 RULES + 全局人物表 + 工具 schema）放进 `system` 并打 `cache_control: ephemeral`。
   一次运行内 N 章共享同一前缀 → 第 2 章起 `usage.cache_read_input_tokens` 命中，输入 token 大幅下降。
   （实测中转站 usage 已返回 `cache_creation_input_tokens / cache_read_input_tokens`，可直接记账。）

### Token 账本（每 Agent + 汇总）
每个 Agent 记录：`input / output / cache_read / cache_creation` token、`耗时 ms`、`是否命中`。
汇总进 `stats`：

```
tokens : { in, out, cache_read, cache_creation }
cache  : { result_hits / result_total, hit_rate, prompt_cache_read_tokens, 省下token估算 }
timing : { wall_ms, agent_count }       # wall_ms ≈ 最慢 Agent，体现并发提速
rounds : critic_rounds                    # Critic 回环轮数
```

前端「Agent 活动流」逐条展示，底部汇总「总 token / 缓存命中率 / 耗时 / 估算成本」。

## 八、取舍与风险（诚实评估）

- **真值**：① 并发逐章=实打实提速；② Critic 回环=实打实提质量（自动修非法产出）；③ 模型路由=实打实省钱（量活走 haiku）。这三件最值得做。
- **慎用**：「多 Agent 互相对话」很炫但易失控、烧 token、难复现。本设计用**黑板 + 指名工单**把它收敛成可控的有向任务图，而非自由群聊。
- **预算闸**：必须有「最大轮数 + token/积分预算」双重上限，否则 Critic 回环可能反复刷。
- **降级闸**：任何 Agent 失败都能落回离线规则，保证「再差也有合法 YAML」这条产品承诺不破。
