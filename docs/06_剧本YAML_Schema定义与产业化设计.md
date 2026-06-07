# 剧本 YAML Schema 定义与产业化设计（v1.0 定稿）

> 本文是项目的**数据地基**与**核心交付物**。
> 题目要求：「能将 3 个章节以上的小说文本自动转换为结构化剧本（YAML 格式），让作者快速获得**可编辑、可进一步打磨**的剧本初稿。请额外写一篇文档，定义剧本的 YAML Schema，并**说明该 Schema 的设计原因**。」
>
> 本文档定位：在《02_YAML_Schema设计文档》v0.1 讨论稿基础上**定稿**，并补齐一个被反复追问、却最关键的问题——
> **「用户明明可以自己调大模型，为什么要来用我们的产品？」**
> 答案不在「我们也调大模型」，而在 **Schema 本身**：Schema 是把「一次性聊天输出」沉淀为「可校验、可溯源、可协作、可流水线」的工程资产的那张契约。本文逐字段论证这一点。

---

## 〇、一句话定位

> **我们卖的不是「调用大模型」，而是「一份永远合法、可溯源到原著、可被人和程序反复打磨的结构化剧本」。**
> 大模型是发动机，**Schema 是底盘 + 仪表盘 + 安全带**。没有底盘，发动机只是一堆会乱跑的马力。

---

## 一、产业化护城河：为什么不是「直接调大模型」？（⭐ 深度思考）

这是评审与投资人一定会问的问题。先把「裸调大模型」的真实体验摆出来，再逐条说明 Schema 化产品如何把每个痛点变成壁垒。

### 1.1 「裸调大模型」长什么样

作者打开 ChatGPT/Claude，粘贴三章小说，输入「帮我改成剧本」。他会得到：

- 一段**格式飘忽**的文本：这次是 Fountain，下次是 Markdown 表格，再下次是大段散文，无法被任何软件二次处理。
- **上下文一截就忘**：第三章里「林记者」其实就是第一章的「林然」，模型早已忘记，人物前后不一致。
- **长文必爆上下文**：真实小说动辄十几万字，单次喂不进去；分段喂，则人物表/场号/风格全断裂。
- **改一句要重跑全篇**：作者想把第 7 场某句台词改冷一点，只能重新生成，结果**其他 99% 也全变了**，前面的打磨白做。
- **无法溯源**：哪一场对应原著哪一段？情节漏了没有？模型不会告诉你，作者得自己逐字比对。
- **不可团队协作**：编剧、责编、制片想各改一部分，面对一坨文本无从下手、无法 diff、无法合并。
- **质量不可度量**：「心理描写有没有正确转成画外音」「人物归属对不对」——没有结构，就无法量化、无法 QA。

> 结论：**裸调大模型解决的是「生成」，而作者真正的工作是「生成之后的一切」**——校验、定位、修改、协作、导出、复用。Schema 正是为「之后的一切」而设计。

### 1.2 Schema 把每个痛点变成产品壁垒

| 裸调大模型的痛点 | 我们用 Schema + 工程做的事 | 形成的壁垒 |
|---|---|---|
| 格式飘忽、不可解析 | **强约束结构化输出**（pydantic `output_format`）+ 导出前 `validate_screenplay` 校验 | 产出**永远合法**，可被编辑器/导出器/统计直接消费 |
| 上下文遗忘、人物错乱 | **全局 `characters` 表 + `aliases`**，逐章转换时回注，跨章消歧 | 长篇下的**一致性**，裸聊做不到 |
| 长文爆上下文 | **分章流水线**（`split_chapters` → 逐章转 → 装配 + 连续编号） | 支持**任意长度**小说，工程化而非碰运气 |
| 改一句要重跑全篇 | YAML 是**结构化文档**，场/元素可**局部编辑**，改哪场只动哪场 | 「AI 出初稿 + 人精打磨」的**增量工作流** |
| 无法溯源 | `scene.source_ref`（章节 + 片段）+ `meta.source_chapters` | **原文 ↔ 剧本对照**、情节保留率可度量 |
| 不可协作 / 不可 diff | YAML 纯文本、字段稳定、`scene_number` 稳定 | 可进 Git、可 review、可多人分场认领 |
| 质量不可度量 | `element.type` 离散枚举（action/dialogue/voiceover/transition） | 「心理→画外音转化率」「对白归属准确率」**可统计、可 QA** |
| 一次性、不可复用 | `meta.generated_by`（ai-draft / human-edited）+ 持久化落库 | 作品资产化，可版本管理、可二次创作 |

### 1.3 一句话护城河

> 大模型是**所有人都能买到的发动机**；我们的壁垒是**这张 Schema 契约**——它把模型的「一次性输出」锁进一个**合法、一致、可溯源、可协作、可流水线**的工程对象。换发动机（换模型）很容易，但「让产出永远可用、可打磨、可团队作业」这套契约与流水线，是我们沉淀的资产。

---

## 二、设计目标（Schema 的六条铁律）

1. **结构化**——能被程序解析、校验、再生成（兑现「YAML 格式」硬指标）。
2. **可编辑**——人类可读、可手改、可写批注（兑现「可编辑、可进一步打磨」，这是选 YAML 而非 JSON/PDF 的根因）。
3. **忠于剧本工业**——字段对标好莱坞标准格式 / Fountain，便于未来导出标准剧本与制片统计。
4. **保序**——保留剧本元素的先后顺序（**顺序即叙事节奏**）。
5. **一致性**——跨场、跨章的人物 / 地点统一。
6. **可扩展**——平滑支持微短剧、闪回等进阶形态，不破坏既有结构。

> 这六条不是凭空来的，正是第一节那些「裸调大模型痛点」反推出来的设计约束。

---

## 三、完整 Schema 定义

> 下面的 YAML 是**真实产出形态**。工程上 **LLM 不直接生成 YAML**（缩进敏感、易错），而是产出结构化对象 → pydantic 校验 → `yaml.dump()` 序列化（见 `backend/app/exporter.py`），兼顾稳定性与可读性。

> 字段按 **创作层 / 制片层 / 微短剧层** 三层组织（见第九节「为什么这样设计」）。除少数核心字段外**全部可选、可降级**：离线引擎只填能确定性推导的（day_night/cast/时长/溯源），AI 引擎尽量补全其余。

```yaml
# ===== 顶层：剧本元信息 =====
meta:
  title: 旧城轨迹                    # 剧本标题
  original_work: 某原著              # 原著名（可空）
  author: 改编者署名                 # 可空
  script_type: film                 # film | tv | short_drama（剧本类型）
  schema_version: "1.0"             # Schema 版本，保证下游解析的前向兼容
  logline: 七年后归乡的男人，在一场未说出口的重逢里，与无法挽回的过去和解。  # 一句话故事（创作层）
  genre: 都市情感                    # 类型（创作层）
  tone: 写实克制                     # 基调（创作层）
  language: zh                      # 语种
  source_chapters: [第一章 归来, 第二章 旧宅, 第三章 钟楼]  # 改编自原著哪几章（兑现 ≥3 章可追溯）
  generated_by: ai-draft            # ai-draft | human-edited（区分初稿 / 已打磨）

# ===== 全局人物表：跨场 / 跨章一致性的唯一来源 =====
characters:
  - id: char_01                     # 全局唯一 ID，场内通过 name 引用
    name: 沈墨
    aliases: [小沈, 沈记者]          # 别名，用于跨章消歧
    description: 男主角，七年后归乡，放不下过去
    role: protagonist               # 叙事角色：主角/反派/配角/龙套（创作层，便于选角）
    gender: 男                       # 选角参考（制片层）
    age: 30 出头                     # 选角参考（制片层）
    arc: 从逃避到与过去和解           # 人物弧光（创作层）
  - id: char_02
    name: 林晚
    description: 女主角，沈墨的旧识
    role: supporting

# ===== 全局地点表（可选，便于制片统计与一致性）=====
locations:
  - id: loc_station
    name: 火车站月台
    int_ext: EXT
  - id: loc_house
    name: 旧宅
    int_ext: INT

# ===== 剧本主体：场（scene）的有序列表 =====
scenes:
  - scene_number: 1                 # 场号，从 1 连续递增
    heading:                        # 场头 = 行业 Slug Line
      int_ext: EXT                  # INT（内景）| EXT（外景）| INT/EXT
      location: 火车站月台
      time: 雨夜                    # 自由文本：DAY/NIGHT/黄昏/第二天清晨/雨夜……
      day_night: NIGHT              # 归一化日/夜（制片层，排期与灯光统筹用）
    synopsis: 沈墨七年后归乡，在月台与林晚重逢。   # 本场梗概，供作者快速浏览 / 定位
    act: 1                          # 三幕（创作层）
    beat: inciting_incident         # 叙事节拍（创作层）
    est_duration_sec: 48            # 预估时长，秒（制片层，时长体检）
    source_ref:                     # 溯源：对应原文位置，支撑「原文 ↔ 剧本对照」
      chapter: 第一章 归来
      excerpt: "火车进站时，雨正下得密。沈墨提着一只旧皮箱站在月台上……"
    breakdown:                      # 制片分解表（制片层，一份剧本直接出通告单基础数据）
      cast: [沈墨, 林晚]            # 出场角色（程序确定性统计）
      extras: [路人甲, 出站旅客]
      props: [旧皮箱, 藏青色伞]
      wardrobe: [沈墨-深色风衣]
      vehicles: [绿皮火车]
      sfx: [雨]
    elements:                       # ★核心：有序列表，承载所有剧本元素
      - type: action               # 动作 / 场景描述（可拍的画面）
        text: 火车进站，雨下得密。沈墨提着旧皮箱站在月台，望着斑驳的站牌。
      - type: voiceover            # 旁白 / 画外音（由心理描写转化而来）
        character: 沈墨            # 旁白归属角色
        text: 他没想到自己真的会回来。当年走得那么决绝，连一句道别都没留下。
      - type: dialogue             # 对白
        character: 林晚
        parenthetical: 撑着伞，淡淡地   # 表演提示（怎么说），可空
        text: 沈墨？
      - type: dialogue
        character: 沈墨
        parenthetical: 努力让声音平静
        text: 是我。好久不见。
      - type: action
        text: 雨水顺着伞骨滴下，在两人之间砸出一小片水花。
      - type: transition           # 转场
        text: CUT TO

# ===== 微短剧示例（script_type: short_drama 时启用的扩展位）=====
  - scene_number: 2
    episode: 1                      # 集号（微短剧层）
    heading: { int_ext: INT, location: 旧宅, time: 第二天清晨, day_night: DAY }
    synopsis: 沈墨回到无人的旧宅，发现一封未拆的信。
    hook: 七年后他跪在她面前       # 开场黄金 3 秒钩子（微短剧层）
    cliffhanger: 信封上的名字，竟是他以为已死去的母亲   # 集尾扣子（微短剧层）
    pay_point: true                 # 付费卡点（微短剧层）
    highlights: [反转, 悬念]        # 爽点 / 反转标签（微短剧层）
    elements:
      - type: action
        text: 沈墨推开吱呀作响的木门，尘埃在斜射的晨光里浮动。
      - type: voiceover
        character: 沈墨
        text: 有些东西一旦凉了，就再也热不回来了。
      - type: dialogue             # 电话另一头的声音 → 用 extension 标注
        character: 林晚
        extension: INTO PHONE
        text: 别开那封信。
```

---

## 四、字段说明

### 4.1 `meta`（剧本元信息）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | 是 | 剧本标题 |
| original_work | string | 否 | 原著名 |
| author | string | 否 | 改编者署名 |
| script_type | enum `film` / `tv` / `short_drama` | 是 | 剧本类型，决定是否启用微短剧扩展位 |
| schema_version | string | 是 | Schema 版本号（当前 `1.0`），保证下游解析的前向兼容 |
| logline | string | 否 | 一句话故事，帮助作者与读者一眼抓住主线（创作层） |
| genre | string | 否 | 类型，如 都市/悬疑/言情/古装（创作层） |
| tone | string | 否 | 基调，如 写实克制/热血爽感（创作层） |
| language | string | 是 | 语种（默认 `zh`） |
| source_chapters | string[] | 是 | 改编自原著的章节标题列表，兑现「≥3 章可追溯」 |
| generated_by | enum `ai-draft` / `human-edited` | 是 | 标记纯 AI 初稿还是已被作者打磨 |

### 4.2 `characters`（全局人物表）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 全局唯一 ID，如 `char_01` |
| name | string | 是 | 角色名（场内 `character` 引用此名） |
| aliases | string[] | 否 | 别名，用于「林然 / 小林 / 林记者」跨章消歧 |
| description | string | 否 | 一句话人物简介 |
| role | enum `protagonist`/`antagonist`/`supporting`/`minor` | 否 | 叙事角色，便于选角与重点把控（创作层） |
| gender | string | 否 | 性别，选角参考（制片层） |
| age | string | 否 | 年龄 / 年龄段，选角参考（制片层） |
| arc | string | 否 | 人物弧光：一句话概括其转变（创作层） |

### 4.3 `scene.element.type`（剧本元素类型枚举）

| type | 必填字段 | 可选字段 | 说明 |
|------|---------|---------|------|
| `action` | text | — | 动作 / 场景描述（看得见的画面） |
| `dialogue` | character, text | parenthetical | 对白；`character` 必须引用人物表中的名字 |
| `voiceover` | character, text | — | 旁白 / 内心独白（**由小说心理描写转化**） |
| `transition` | text | — | 转场，如 `CUT TO` / `DISSOLVE TO` / `SMASH CUT` / 淡出 |
| `shot` | text | — | 镜头 / 景别提示，如 CLOSE ON / POV / INSERT（拍摄稿，可选） |
| `subheading` | text | — | 场内次场头（如时间推移、INTERCUT），按需启用 |

`dialogue` / `voiceover` 还支持可选 `extension`（声音处理），对标行业对白角标：

| extension | 含义 |
|------|------|
| `V.O.` | Voice Over，画外音（叙述 / 心理） |
| `O.S.` / `O.C.` | Off-Screen / Off-Camera，在场但不在画内 |
| `CONT'D` | 同一人台词被动作打断后接续 |
| `INTO PHONE` / `FILTERED` | 对着电话说 / 电话听筒里的滤音 |
| `SUBTITLE` | 配字幕（外语 / 特殊语言） |

### 4.4 `scene.heading`（场头 / Slug Line）

| 字段 | 取值 | 说明 |
|------|------|------|
| int_ext | `INT` / `EXT` / `INT/EXT` | 内 / 外景 |
| location | string | 地点，建议与 `locations` 表一致 |
| time | string（自由文本） | 时间，如 DAY / NIGHT / 黄昏 / 雨夜 |
| day_night | enum `DAY` / `NIGHT` / `DAWN` / `DUSK` | 归一化日 / 夜（制片层），由 `time` 推导，供排期与灯光统筹 |

### 4.5 `scene` 的创作层 / 制片层字段

| 字段 | 类型 | 层 | 说明 |
|------|------|----|------|
| act | int | 创作 | 所属幕 1 / 2 / 3（三幕结构） |
| beat | string | 创作 | 叙事节拍：setup / inciting_incident / turning_point / midpoint / climax / resolution |
| est_duration_sec | int | 制片 | 预估时长（秒），程序按元素体量估算，用于**时长体检** |
| source_ref | object | 制片 | 原文溯源（见下） |
| breakdown | object | 制片 | 制片分解表（见下） |

**`scene.source_ref`（溯源，可选但强烈建议）**

| 字段 | 类型 | 说明 |
|------|------|------|
| chapter | string | 本场对应的原著章节（流水线确定性给出） |
| excerpt | string | 对应原文起始片段，支撑「原文 ↔ 剧本」对照与情节保留率度量 |

**`scene.breakdown`（制片分解表 / Script Breakdown）**——一份剧本直接产出通告单的基础数据：

| 字段 | 类型 | 说明 |
|------|------|------|
| cast | string[] | 本场出场角色（**程序确定性统计**，扫描场内人名 / 别名） |
| extras | string[] | 群演 / 背景人物 |
| props | string[] | 关键道具 |
| wardrobe | string[] | 服装造型 |
| vehicles | string[] | 交通工具 |
| sfx | string[] | 特效 / 特技 / 氛围（雨、雪、爆破等） |

### 4.6 微短剧扩展位（`script_type: short_drama` 时启用）

| 字段 | 类型 | 说明 |
|------|------|------|
| episode | int | 集号（微短剧分集） |
| hook | string | 开场钩子（黄金 3 秒） |
| cliffhanger | string | 集尾扣子 / 悬念 |
| pay_point | bool | 是否付费卡点 |
| highlights | string[] | 爽点 / 反转 / 名场面标签，如 `[反转, 打脸]` |

```yaml
scenes:
  - scene_number: 1
    episode: 1                          # 集号（微短剧分集）
    heading: { int_ext: INT, location: 客厅, time: 夜晚, day_night: NIGHT }
    hook: "她竟是他失散多年的姐姐！"      # 开场黄金 3 秒钩子
    cliffhanger: "门一开，站着的是本该死去的人"   # 集尾扣子
    pay_point: true                      # 付费卡点
    highlights: [反转, 悬念]
    ...
```

> 与短剧产线「一键拆集（钩子 / 扣子 / 时长体检）」能力对接：`episode` 承载分集，`hook` / `cliffhanger` 承载钩子扣子，`est_duration_sec` 支撑每集时长体检。

---

## 五、设计原因（⭐ 评分核心，逐条论证「为什么这样设计」）

> 每条都回到第一节那个母问题：**这条设计如何让产品比「裸调大模型」更值得用？**

### 5.1 为什么用 `elements` 有序列表，而不是分 `dialogues` / `actions` 两个数组？

剧本里动作和对白**交错出现**：动作 → 对白 → 动作 → 对白……**这个顺序本身就是叙事节奏**。若拆成 `actions: [...]` 与 `dialogues: [...]`，相对顺序丢失，无法还原成正确剧本。单一有序列表 + `type` 字段区分，才能 **100% 保留时序**。
→ 对应壁垒：裸聊输出的散文虽然「看着有序」，却不可被程序复用；我们的有序列表是**可编辑、可重排、可统计**的结构。

### 5.2 为什么 `heading` 拆成 int_ext / location / time 三个字段？

对标剧本工业的 **Slug Line 标准**（`EXT. 火车站月台 - 雨夜`）。结构化拆分后：① 便于导出标准剧本格式；② 便于制片统计（「共多少个外景」）；③ 便于按地点 / 时间做一致性校验。若只存一个字符串，这些全做不到。

### 5.3 为什么有全局 `characters` 表，场内还要 `character` 引用？

**一致性约束——这是长篇下裸调大模型最先崩的地方。** 小说里同一角色常有多种称呼（「林然 / 小林 / 林记者」），逐章生成时模型会忘记前文，人物前后错乱。全局人物表 + `aliases` 别名让程序能消歧、统一；场内只引用 `name`，「换名」只需改一处。
→ 对应壁垒：**跨章一致性是工程能力，不是模型能力**。

### 5.4 为什么单列 `voiceover` 类型？

这是**剧本 vs 小说的核心差异落点**。小说的心理描写（「他没想到」「他明白」）无法直接拍摄，必须转成画外音。单设 `voiceover`（而非塞进 action），既符合行业规范，又让我们能**量化评估**「心理描写转化得对不对」。
→ 对应壁垒：**质量可度量**。裸聊无法告诉你「心理→画外音」转化率，我们能。

### 5.5 为什么保留 `logline` 和 `synopsis`？

兑现「可编辑、可进一步打磨」。`logline`（一句话故事）与 `synopsis`（每场梗概）让作者**不必通读全文就能快速定位要改的场**，极大提升打磨效率。这是站在**作者真实工作流**角度的设计——作者 80% 的时间花在「改」而非「生成」。

### 5.6 为什么有 `source_ref` 溯源字段？

对应作者核心顾虑「怕丢失原著精华」。记录每场对应的原文章节与片段，支撑「**原文 ↔ 剧本对照**」，并让「**情节保留率**」可度量。
→ 对应壁垒：裸聊改完，作者得自己逐字比对原著查漏；我们把溯源**焊进数据结构**。

### 5.7 为什么选 YAML 而不是 JSON？

① **人类可读、可手改**（直接呼应「可编辑」硬指标）；② 支持**注释**，作者可在剧本里写批注；③ 缩进表达层级，比 JSON 括号更适合长文本编辑；④ 纯文本利于 **Git diff / 团队 review / 多人分场协作**。
⚠️ 工程注意：**LLM 不直接产 YAML**（缩进敏感易错），而是产结构化对象 → pydantic 校验 → `yaml.dump()`，兼顾稳定与可读。

### 5.8 为什么用 `meta.generated_by` 区分 ai-draft / human-edited？

明确产品定位是「**AI 出初稿 + 人精打磨**」。该字段标记某剧本是纯 AI 初稿还是已被作者编辑，便于**版本管理与效果评估**，也是作品资产化、可复用的前提。

### 5.9 为什么 `time` 用自由文本而非枚举（DAY/NIGHT）？

中文小说的时间表达极丰富（「雨夜」「第二天清晨」「多年后」），强行枚举会丢信息、增加转换出错率。自由文本更贴合中文语料，导出标准格式时再做归一即可。

### 5.10 为什么把微短剧字段做成「扩展位」而非默认字段？

遵循「**默认不臃肿，按需扩展**」。`episode` / `hook` 仅在 `script_type: short_drama` 时出现，既不污染通用剧本结构，又能平滑承接短剧产线「一键拆集」能力。

---

## 五·补、按产业流程的三层丰富化（⭐ 行业专业知识 → 为什么需要这样设计）

> 上面 5.1–5.10 论证的是「基础结构为什么这么设计」。本节回答你新提的问题：**为什么还要按行业专业知识把 Schema 继续丰富化？**
> 一句话：**一部剧本在工业里不止被一个人用**。同一份结构化剧本，会先后流经**编剧、制片统筹、（微短剧）操盘手**三种角色之手。我们把这三种角色各自需要的字段都焊进同一份 YAML——**一处生成，三处复用**。这正是裸调大模型给不了的：它只产一段文字，而我们产一个**可被整条产线消费的工业对象**。

### 5·补.1 创作层（面向编剧）——为什么要 `act` / `beat` / `role` / `arc` / `extension`

- **行业依据**：专业编剧打磨剧本时用的是**结构语言**——三幕（act）、节拍表（beat sheet，如 Save the Cat）、人物弧光（arc）、对白角标（V.O./O.S./CONT'D）。
- **为什么需要**：作者要「进一步打磨」，靠的不是逐字重写，而是**沿结构调整**——「第二幕中点不够强」「主角弧光在第 7 场断了」。没有 `act`/`beat`/`arc`，这些操作无从下手。`extension` 则让「电话里的声音、画外的呼喊」有规范表达，而非塞进括号里靠人脑猜。
- **对应壁垒**：把剧本从「一段文字」升级为「**有结构坐标的创作底稿**」，作者改得准、改得快。

### 5·补.2 制片层（面向统筹）——为什么要 `day_night` / `breakdown` / `est_duration_sec`

- **行业依据**：剧本一旦定稿，制片统筹做的第一件事就是**拆剧本（Script Breakdown）**——逐场列出**演员、群演、道具、服装、车辆、特效**，并按 **INT/EXT × 日/夜** 排通告、估时长。这是行业标准动作（Final Draft / 制片软件都内建）。
- **为什么需要**：`breakdown` 让一份剧本**直接产出通告单的基础数据**；`day_night` 是排期与灯光的硬约束（日戏夜戏不能混排）；`est_duration_sec` 支撑**时长体检**（尤其微短剧每集严格 60–90s）。其中 `cast` 我们**程序确定性计算**（扫描场内人名），不依赖模型也准确。
- **对应壁垒**：从「写完剧本」一步跨到「**能开拍的剧本**」，这是裸聊永远到不了的下游。

### 5·补.3 微短剧层（面向操盘手）——为什么要 `hook` / `cliffhanger` / `pay_point` / `highlights`

- **行业依据**：微短剧是**强节奏付费内容**，操盘逻辑高度套路化——**黄金 3 秒钩子（hook）**、**集尾扣子（cliffhanger）**、**付费卡点（pay_point）**、**爽点 / 反转（highlights）**。这些不是文学修辞，而是**变现结构**。
- **为什么需要**：把变现结构显式化，才能做「一键拆集、卡点体检、钩子强度评估」，直接对接已有短剧产线能力，让产出**可投放、可计费**。
- **对应壁垒**：我们不只生成剧本，还生成**商业可运营的剧本**。

### 5·补.4 为什么「全部可选 + 可降级」是关键设计

丰富 ≠ 臃肿。三层字段除少数核心外**全部可选**：

- **离线引擎**只填能**确定性推导**的（`day_night` 由时间词、`cast` 由人名扫描、`est_duration_sec` 由体量估算、`source_ref` 由章索引）——**无网、零成本也有专业产出**。
- **AI 引擎**再补全需要语义理解的（`beat`/`arc`/`props`/`hook` 等）。
- 导出时**空字段一律不写入**（`_compact` 剪枝），YAML 保持干净可读。

> 这条让 Schema 既「专业到能进产线」，又「轻到 demo 随时能跑」——可降级正是工程成熟度的体现。

---

## 六、校验规则（Schema Validation）

实现层用 **pydantic** 定义模型（`backend/app/schema.py`），导出前由 `validate_screenplay()` 做一致性检查：

1. `scene_number` 从 1 连续递增、不重复。
2. 所有 `dialogue` / `voiceover` 的 `character` 必须能在 `characters` 表中找到（name 或 alias）。
3. `element.type` 必须在枚举内（action/dialogue/voiceover/transition/shot/subheading）；必填字段不为空。
4. `heading.int_ext` ∈ {INT, EXT, INT/EXT}。
5. 不允许空场（scene 的 `elements` 不为空）。
6. 导出前统一做：人物名校验、空场检测、场号连续性检查。
7. **专业增强字段宽容校验**：`day_night`、`episode` 等**存在才校验取值**，不强制存在——保证离线产出与 AI 产出都能通过（核心严格、增强宽容）。

> **这套校验就是产品对用户的承诺**：你拿到的 YAML **永远合法、永远能被下游消费**。裸调大模型给不了这个承诺。

---

## 七、Schema ↔ 代码实现现状（诚实对照）

> 本节如实标注：哪些字段当前代码已产出，哪些是已定稿、待补的「下一步开发」。便于评审区分「已实现」与「路线图」。

| 字段 / 能力 | 层 | 当前代码（`backend/app/`） | 状态 |
|---|---|---|---|
| `meta`（含 `schema_version`） + 双引擎 + 分章流水线 + YAML 导出 | 基础 | `pipeline.py` / `converter.py` / `exporter.py` | ✅ 已实现 |
| `scenes[].scene_number / heading / synopsis / elements` + 有序 + 校验 | 基础 | `schema.py` + `validate_screenplay` | ✅ 已实现 |
| `element.type` 扩为 6 类（+`shot`/`subheading`）+ `extension` 角标 | 创作 | `schema.py` `SceneElement` | ✅ 已实现（AI 填充） |
| `meta.logline / genre / tone` | 创作 | `converter.extract_story_meta`（AI） | ✅ 已实现（离线留空） |
| `characters[].aliases / role / gender / age / arc` | 创作/制片 | `schema.Character` + AI 抽取 | ✅ 已实现（离线留空） |
| `scene.act / beat` | 创作 | `schema.Scene` + AI 抽取 | ✅ 已实现（AI 填充） |
| `heading.day_night` | 制片 | `converter.derive_day_night` + 装配兜底 | ✅ 已实现（在线/离线均产出） |
| `scene.breakdown.cast` | 制片 | `pipeline._scene_cast`（确定性） | ✅ 已实现（在线/离线均产出） |
| `scene.breakdown.props/wardrobe/vehicles/sfx/extras` | 制片 | AI 抽取 | ✅ 已实现（AI 填充） |
| `scene.est_duration_sec` + `stats.est_total_sec` | 制片 | `pipeline._estimate_seconds`（确定性） | ✅ 已实现（在线/离线均产出） |
| `scene.source_ref`（chapter + excerpt） | 制片 | `pipeline._enrich_scene`（确定性） | ✅ 已实现（在线/离线均产出） |
| 微短剧 `episode/hook/cliffhanger/pay_point/highlights` | 微短剧 | `schema.Scene` 扩展位，与短剧产线对接 | ✅ 字段就绪 / 🔗 待与拆集打通 |
| `locations` 全局表 | 制片 | 暂未产出 | 🔜 可选增强 |

> 说明：标「确定性」的字段（`cast`/`est_duration_sec`/`source_ref`/`day_night`）**无论在线/离线都产出**——这是离线 demo 也具备专业产出的关键；标「AI 填充」的字段需语义理解，离线留空、由 `_compact` 自动剪枝，不污染 YAML。

---

## 八、版本

- **v1.0（本文，定稿）**：确立 Schema 为产业化护城河；逐字段论证设计原因；**按影视/短剧工业流程做创作/制片/微短剧三层丰富化**（第五·补节），并**全部落地为代码**（`schema.py`/`converter.py`/`pipeline.py`，见第七节状态表）。核心字段严格、增强字段宽容、空字段剪枝，三者保证「专业到能进产线、轻到 demo 随时能跑」。
- v0.1（《02_YAML_Schema设计文档》，讨论稿）：首版结构草拟与开放问题清单，本文已逐条收敛定稿。
