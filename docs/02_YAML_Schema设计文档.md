# 剧本 YAML Schema 设计文档

> 本文是**竞赛硬性交付物**之一，也是整个项目的数据地基。
> 题目要求："请额外写一篇文档，定义剧本的 YAML Schema，并**说明该 Schema 的设计原因**。"
> 类型定位：**竖屏微短剧（short_drama）**。剧本以「场（scene）」为最小叙事单元，
> 在其上叠加「集（episode）」分集结构——这是短剧区别于传统影视剧本的核心。

---

## 一、设计目标

1. **结构化**：能被程序解析、校验、再生成（满足"YAML 格式"硬指标）。
2. **可编辑**：人类可读、可手动修改（满足"可编辑、可进一步打磨"）——这是选 YAML 而非 JSON/PDF 的根本原因。
3. **忠于剧本工业**：字段对标好莱坞标准格式 / Fountain，便于未来导出标准剧本。
4. **保序**：保留剧本元素的先后顺序（顺序即叙事节奏）。
5. **一致性**：跨场、跨集人物/地点统一。
6. **短剧原生**：天然承载分集（episode）、开场钩子（hook）、集尾扣子（cliffhanger）与单集时长——短剧的行业铁律直接写进数据结构。

---

## 二、完整 Schema 定义

```yaml
# ===== 顶层：剧本元信息 =====
meta:
  title: 凉掉的咖啡                 # 剧本标题
  original_work: 某小说             # 原著名
  author: 改编者署名
  script_type: short_drama         # 固定为 short_drama（本工具定位：竖屏微短剧）
  logline: 七年后重逢的两人，在一杯凉透的咖啡前签下离婚协议。  # 一句话故事
  language: zh                     # 语种
  source_chapters: [1, 2, 3]       # 改编自原著哪几章（满足≥3章可追溯）
  generated_by: ai-draft           # ai-draft | human-edited（区分初稿/已打磨）

# ===== 全局人物表：跨场一致性的来源 =====
characters:
  - id: char_lin                   # 全局唯一ID，场内通过 id/name 引用
    name: 林然
    aliases: [小林, 林记者]         # 别名，用于消歧
    description: 男主角，记者，放不下过去
  - id: char_su
    name: 苏晴
    aliases: []
    description: 女主角，林然前妻

# ===== 全局地点表（可选，便于制片统计与一致性）=====
locations:
  - id: loc_cafe
    name: 咖啡馆
    int_ext: INT
  - id: loc_bridge
    name: 公司楼下天桥
    int_ext: EXT

# ===== 剧本主体：场的有序列表 =====
scenes:
  - scene_number: 1                # 场号（从1递增）
    heading:                       # 场头 = 行业 Slug Line
      int_ext: INT                 # INT（内景）| EXT（外景）| INT/EXT
      location: 咖啡馆
      time: 黄昏                   # DAY | NIGHT | 黄昏 | 第二天清晨 ...
    synopsis: 林然赴约，苏晴递上离婚协议。   # 本场梗概，供作者快速浏览/编辑
    source_ref:                    # 溯源：对应原文位置，支持"原文↔剧本对照"
      chapter: 1
      excerpt: "林然推开咖啡馆的门时…"
    elements:                      # ★核心：有序列表，承载所有剧本元素
      - type: action              # 动作/场景描述
        text: 雨下了一整夜。林然推门而入，灯光在湿玻璃上晕开。
      - type: voiceover           # 旁白/画外音（心理描写转化而来）
        character: 林然            # 旁白归属角色
        text: 我以为七年足够忘干净，可心跳还是快了。
      - type: dialogue            # 对白
        character: 苏晴
        parenthetical: null       # 表演提示，可为空
        text: 你迟到了。
      - type: dialogue
        character: 林然
        parenthetical: 努力让声音平静
        text: 路上堵车。你……还好吗？
      - type: action
        text: 苏晴把一份文件推到桌子中央——离婚协议。
      - type: transition          # 转场
        text: CUT TO

  - scene_number: 2
    heading: { int_ext: EXT, location: 公司楼下天桥, time: 第二天清晨 }
    synopsis: 林然独自面对没签字的协议，明白一切无法挽回。
    source_ref: { chapter: 2, excerpt: "第二天清晨，林然站在天桥上…" }
    elements:
      - type: action
        text: 林然攥着没签字的文件，城市在脚下苏醒，车流如河。
      - type: voiceover
        character: 林然
        text: 有些东西一旦凉了，就再也热不回来了。

# ===== 分集结构：短剧的核心产物 =====
# scenes 是叙事的最小单元；episodes 在其上按口播时长贪心打包成"集"。
# 每集自带钩子/扣子/时长，直接对应短剧的行业铁律。
episodes:
  - episode_number: 1                # 集号（从1递增）
    title: 凉掉的咖啡                 # 本集标题（取自首场梗概）
    scene_numbers: [1]               # 本集包含哪些场（引用 scenes.scene_number）
    hook: 你迟到了。                  # 开场钩子：前几秒抓人的台词/梗概
    cliffhanger: 苏晴把离婚协议推到桌子中央。  # 集尾扣子：逼着观众看下一集
    est_seconds: 95                  # 预估时长（秒），按口播字数估算
    duration_text: 1分35秒           # 时长的可读文本
  - episode_number: 2
    title: 没签字的协议
    scene_numbers: [2]
    hook: 林然攥着没签字的文件。
    cliffhanger: 有些东西一旦凉了，就再也热不回来了。
    est_seconds: 88
    duration_text: 1分28秒
```

---

## 三、字段说明

### 3.1 element.type 枚举（剧本元素类型）

| type | 必填字段 | 可选字段 | 说明 |
|------|---------|---------|------|
| `action` | text | — | 动作/场景描述（可拍的画面） |
| `dialogue` | character, text | parenthetical | 对白；character 引用人物 |
| `voiceover` | character, text | — | 旁白/独白（心理描写转化） |
| `transition` | text | — | 转场，如 CUT TO / 淡出 |
| `subheading` | text | — | （可选）场内小节标题，如时间推移 |

### 3.2 heading（场头）
| 字段 | 取值 | 说明 |
|------|------|------|
| int_ext | INT / EXT / INT/EXT | 内外景 |
| location | 字符串 | 地点，建议与 locations 表一致 |
| time | DAY/NIGHT/具体描述 | 时间 |

### 3.3 episode（集）字段 —— 短剧核心结构
| 字段 | 必填 | 说明 |
|------|------|------|
| episode_number | ✓ | 集号，从 1 连续递增 |
| title | ✓ | 本集标题（默认取首场梗概） |
| scene_numbers | ✓ | 本集包含的场号列表，引用 `scenes.scene_number` |
| hook | 建议 | 开场钩子：本集第一句台词（无台词则取首场梗概） |
| cliffhanger | 建议 | 集尾扣子：本集最后一句台词，制造悬念逼下一集 |
| est_seconds / duration_text | — | 按口播字数（≈5 字/秒）估算的单集时长 |

> **设计取舍**：`episodes` 与 `scenes` 是「分层而非内嵌」——场是叙事单元、集是播放单元，
> 一集对应一组连续的场（`scene_numbers` 引用）。这样既不破坏 `scenes` 的有序连贯，
> 又能让作者自由调整分集边界（改 `scene_numbers` 即可重新分集），互不耦合。

---

## 四、设计原因（⭐ 评分核心，逐条论证）

> 题目明确要求"说明设计原因"。每个关键决策都给出"为什么"。

### 4.1 为什么用 `elements` 有序列表，而不是分 `dialogues`/`actions` 数组？
> 剧本里动作和对白是**交错出现**的：动作→对白→动作→对白……**这个顺序本身就是叙事节奏**。如果拆成 `actions: [...]` 和 `dialogues: [...]` 两个数组，就丢失了它们的相对顺序，无法还原成正确的剧本。用单一有序列表 + `type` 字段区分，才能 100% 保留时序。

### 4.2 为什么 `heading` 拆成 int_ext / location / time 三个字段？
> 对标剧本工业的 **Slug Line 标准**（`INT. 咖啡馆 - 黄昏`）。结构化拆分后：① 便于程序导出标准剧本格式；② 便于制片统计（如"共有多少个外景"）；③ 便于按地点/时间做一致性校验。若只存一个字符串，这些都做不到。

### 4.3 为什么有全局 `characters` 表，场内还用 `character` 引用？
> **一致性约束**。小说里同一角色常有多种称呼（"林然/小林/林记者"），若每场各写各的，剧本人物会乱。全局人物表 + `aliases` 别名，让程序能消歧、统一；场内引用保证"换名"只需改一处。

### 4.4 为什么单列 `voiceover` 类型？
> 这是**剧本 vs 小说的核心差异落点**。小说的心理描写无法直接拍摄，必须转成画外音。单设 `voiceover` 类型（而非塞进 action），既符合行业规范，也让我们能**量化评估**"心理描写转化得对不对"。

### 4.5 为什么保留 `synopsis` 和 `logline`？
> 题目要求"可编辑、可进一步打磨"。`logline`（一句话故事）和 `synopsis`（每场梗概）让作者**不必通读全文就能快速定位要改的场**，极大提升打磨效率。这是站在"作者真实工作流"角度的设计。

### 4.6 为什么有 `source_ref` 溯源字段？
> 对应用户痛点"怕丢失原著精华"。记录每场对应的原文章节和片段，支持"**原文↔剧本对照**"功能，也便于评估"情节保留率"。

### 4.7 为什么选 YAML 而不是 JSON？
> ① **人类可读、可手动编辑**（直接呼应"可编辑"硬指标）；② 支持**注释**，作者可在剧本里写批注；③ 缩进表达层级，比 JSON 的括号更适合长文本编辑。
> ⚠️ 工程注意：**LLM 不直接生成 YAML**（缩进敏感易出错），而是生成 JSON → pydantic 校验 → `yaml.dump()` 转 YAML，兼顾稳定性与可读性。

### 4.8 为什么用 `meta.generated_by` 区分 ai-draft / human-edited？
> 明确产品定位是"AI 出初稿 + 人打磨"。该字段标记某剧本是纯 AI 初稿还是已被作者编辑，便于版本管理与效果评估。

### 4.9 ⭐ 为什么把 `episodes` 设为一等结构，而不是只产出 scenes？
> **这是本工具定位为「短剧」的核心决策**。短剧的最小消费单元不是「场」而是「集」：每集 2~3 分钟、开场要有钩子、集尾要有扣子——这些行业铁律必须被数据结构承载，否则产出的只是普通剧本而非「短剧」。
> 采用**「场/集分层」**而非「在 scene 里塞 episode 字段」：① `scenes` 保持有序连贯，是叙事的单一事实来源；② `episodes` 通过 `scene_numbers` 引用一组连续场，是播放编排层；③ 作者重新分集只需改 `scene_numbers`，不动剧本正文，两层解耦。
> 拆集还自动算出 `est_seconds`（按口播 ≈5 字/秒估时）与 `hook`/`cliffhanger`，并对「缺钩子/缺扣子/时长超标/无互动」给出 warnings——把短剧的"产能体检"也算法化了。

---

## 五、校验规则（Schema Validation）

实现层用 **pydantic** 定义模型做校验（`backend/app/schema.py`），规则：

**场级（scene）结构**
1. `scene_number` 从 1 连续递增、不重复。
2. 所有 `dialogue/voiceover` 的 `character` 必须能在 `characters` 表中找到（id 或 name 或 alias）。
3. `element.type` 必须在枚举内；必填字段不为空。
4. `heading.int_ext` ∈ {INT, EXT, INT/EXT}。
5. 不允许空场（scene 的 elements 不为空）。

**集级（episode）结构**（已拆集时执行）
6. `episode_number` 从 1 连续递增。
7. 每集 `scene_numbers` 非空；所有场被**完整且不重复**地收录到各集（覆盖校验）。

> 说明：钩子/扣子/单集时长属于**内容健康度**，由拆集引擎以 `warnings` 形式提示（缺钩子、缺扣子、时长偏长/偏短、缺互动），**不计为硬错误**——避免一集恰好收在动作镜头时被误判为无效。

---

## 六、已定稿决策

| 议题 | 决策 | 理由 |
|------|------|------|
| 剧本类型 | **竖屏微短剧（short_drama）** | 差异化强、贴合网文 IP 改编短剧的千亿市场；见文档③第二节 |
| `time` 字段 | **自由文本** | 中文小说时间描述（"第二天清晨"）远比 DAY/NIGHT 丰富 |
| 分集结构 | **纳入核心**（`episodes` 一等字段，转换即自动拆集） | 短剧的最小消费单元是"集"，必须由数据结构承载 |
| `locations` 全局表 | 预留为 Roadmap，MVP 暂只用场内 location 字符串 | 制片统计非短剧核心诉求，避免增加复杂度 |
| `source_ref` 溯源 | 预留为 Roadmap | 支撑"原文↔剧本对照"加分项，核心链路跑通后再补 |
