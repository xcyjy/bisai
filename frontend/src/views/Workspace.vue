<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  createProject, getProject, saveScreenplay, sampleNovel, health, getJob, makeEpisodes,
  exportYaml as apiExportYaml, fetchModels, streamAgents,
} from '../api.js'
import { useAuthStore } from '../stores/auth.js'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const ELEMENT_TYPES = [
  { value: 'action', label: '动作 / 场景描述' },
  { value: 'dialogue', label: '对白' },
  { value: 'voiceover', label: '画外音 / 内心独白' },
  { value: 'transition', label: '转场' },
]
const INTEXT_OPTIONS = [
  { value: 'INT', label: '内（室内）' },
  { value: 'EXT', label: '外（室外）' },
  { value: 'INT/EXT', label: '内外' },
]
const TIME_OPTIONS = ['日', '夜', '清晨', '黄昏', '白天', '夜晚']
function intExtCN(v) { return ({ INT: '内', EXT: '外', 'INT/EXT': '内外' })[v] || v || '内' }

const projectId = ref(route.params.id ? Number(route.params.id) : null)
const novelText = ref('')
const title = ref('未命名剧本')
const author = ref('')
const engineChoice = ref('offline')   // offline | ai | agents
const loading = ref(false)
const saving = ref(false)
const errorMsg = ref('')
const engine = ref('')

// 模型下拉（多 Agent / AI 用）
const models = ref([])
const modelsAvailable = ref(false)
const model = ref('')

// 多 Agent 实时活动流
const agentEvents = ref([])
const agentStats = ref(null)
const AGENT_ICON = { start: '▶', done: '✓', cache: '⚡', error: '⚠', review: '🔎' }
function agentIcon(s) { return AGENT_ICON[s] || '·' }
const afTokens = computed(() => {
  const t = agentStats.value?.tokens
  return t ? (t.in + t.out) : 0
})
const afHitRate = computed(() => {
  const c = agentStats.value?.cache
  return c ? Math.round((c.hit_rate || 0) * 100) : 0
})
const afWall = computed(() => {
  const ms = agentStats.value?.timing?.wall_ms
  return ms == null ? '' : (ms >= 1000 ? (ms / 1000).toFixed(1) + 's' : ms + 'ms')
})

const screenplay = ref(null)
const stats = ref(null)
const compare = ref(false)
const editing = ref(null)
const savedFlash = ref(0)
const showScript = ref(false)
const copied = ref(false)

// YAML 导出（结构化交付物）
const showYaml = ref(false)
const yamlText = ref('')
const yamlBusy = ref(false)
const yamlCopied = ref(false)

// 异步转换任务
const converting = ref(false)
const job = ref(null)             // { status, progress, total }
let pollTimer = null

// 拆集
const showEpisodes = ref(false)
const makingEp = ref(false)
const targetMin = ref(2.5)
const episodes = computed(() => screenplay.value?.episodes || [])
const epSummary = computed(() => {
  const eps = episodes.value
  if (!eps.length) return null
  const healthy = eps.filter((e) => !e.warnings?.length).length
  const avg = Math.round(eps.reduce((s, e) => s + e.est_seconds, 0) / eps.length)
  return { count: eps.length, healthy, avg }
})

onMounted(async () => {
  try { engine.value = (await health()).engine } catch { engine.value = '后端未连接' }
  try {
    const m = await fetchModels()
    models.value = m.models || []
    modelsAvailable.value = m.available
    if (models.value.length) model.value = models.value[0].id
  } catch { /* 模型列表拉取失败不影响离线 */ }
  if (projectId.value) await loadProject(projectId.value)
})
onUnmounted(() => { if (pollTimer) clearTimeout(pollTimer) })

watch(() => route.params.id, async (id) => {
  projectId.value = id ? Number(id) : null
  editing.value = null
  if (pollTimer) clearTimeout(pollTimer)
  if (projectId.value) await loadProject(projectId.value)
  else resetNew()
})

function resetNew() {
  novelText.value = ''; title.value = '未命名剧本'; author.value = ''
  screenplay.value = null; stats.value = null; showScript.value = false
  converting.value = false; job.value = null
}

async function loadProject(id) {
  loading.value = true
  try {
    const res = await getProject(id)
    title.value = res.title
    author.value = res.author
    novelText.value = res.source_text
    if (res.screenplay && res.screenplay.scenes) {
      screenplay.value = res.screenplay
      converting.value = false
    } else if (res.job && (res.job.status === 'queued' || res.job.status === 'running')) {
      // 仍在后台转换，继续轮询
      startPoll(res.job.id)
    } else if (res.job && res.job.status === 'failed') {
      errorMsg.value = res.job.error || '转换失败'
    }
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

function loadSample() {
  novelText.value = sampleNovel()
  title.value = '旧城轨迹'
  author.value = '改编自原创短篇'
}

// ---- 上传 .txt 文件（按钮选择 / 拖拽）----
const fileInput = ref(null)
const dragging = ref(false)

function pickFile() { fileInput.value?.click() }

function readFile(file) {
  if (!file) return
  const name = (file.name || '').toLowerCase()
  const okType = name.endsWith('.txt') || file.type === 'text/plain' || file.type === ''
  if (!okType) { errorMsg.value = '目前仅支持 .txt 纯文本文件'; return }
  if (file.size > 5 * 1024 * 1024) { errorMsg.value = '文件过大（>5MB），请精简后再上传。'; return }
  const reader = new FileReader()
  reader.onload = () => {
    novelText.value = String(reader.result || '')
    if (!title.value || title.value === '未命名剧本') {
      title.value = (file.name || '').replace(/\.txt$/i, '').trim() || '未命名剧本'
    }
    errorMsg.value = ''
  }
  reader.onerror = () => { errorMsg.value = '读取文件失败，请重试。' }
  reader.readAsText(file, 'utf-8')
}

function onFileChange(e) {
  readFile(e.target.files?.[0])
  e.target.value = ''   // 允许重复选择同一文件
}
function onDrop(e) {
  dragging.value = false
  readFile(e.dataTransfer?.files?.[0])
}

const canUseAI = computed(() => auth.credits >= 1)
const AGENT_COST = 2
const canUseAgents = computed(() => auth.credits >= AGENT_COST)

// ---- 超长文本：客户端按章节智能分段（≤单次上限），让用户清楚地分段转换 ----
const SEG_MAX = 90000          // 单段上限（留余量，后端硬上限 10 万字）
const SEG_WARN = 30000         // 超过此字数开始提示
const CHAPTER_RE = /^\s*(第\s*[0-9零一二三四五六七八九十百千两\s]+[章回节卷]|chapter\s+\d+|楔子|序章?|引子|后记|尾声|番外)/i

function _splitChaptersJS(text) {
  const lines = text.split(/\r?\n/)
  const out = []
  let title = null
  let body = []
  const flush = () => {
    const b = body.join('\n')
    if (title !== null || b.trim()) out.push({ title: title || '正文', body: b })
  }
  for (const line of lines) {
    const s = line.trim()
    if (s && s.length <= 40 && CHAPTER_RE.test(s)) { flush(); title = s; body = [] }
    else body.push(line)
  }
  flush()
  return out.filter((c) => c.body.trim() || c.title !== '正文')
}

function _segText(chapters) {
  return chapters.map((c) => (c.title === '正文' ? c.body : c.title + '\n' + c.body)).join('\n\n')
}

function _buildSegments(text) {
  if (text.length <= SEG_MAX) return []
  const chs = _splitChaptersJS(text)
  const mk = (cs) => ({
    text: _segText(cs), chars: _segText(cs).length, chapterCount: cs.length,
    range: cs.length ? `${cs[0].title} — ${cs[cs.length - 1].title}` : '',
  })
  if (!chs.length) { // 无章节标题：按字数硬切
    const segs = []
    for (let i = 0; i < text.length; i += SEG_MAX) {
      segs.push({ text: text.slice(i, i + SEG_MAX), chars: Math.min(SEG_MAX, text.length - i),
        chapterCount: 0, range: `第 ${i + 1}–${Math.min(text.length, i + SEG_MAX)} 字` })
    }
    return segs
  }
  const segs = []
  let cur = []
  let curLen = 0
  for (const c of chs) {
    const clen = c.title.length + c.body.length + 2
    if (clen > SEG_MAX) { // 单章超长：先收尾，再硬切这章
      if (cur.length) { segs.push(mk(cur)); cur = []; curLen = 0 }
      const full = c.title + '\n' + c.body
      for (let i = 0; i < full.length; i += SEG_MAX) {
        segs.push({ text: full.slice(i, i + SEG_MAX), chars: Math.min(SEG_MAX, full.length - i),
          chapterCount: 1, range: `${c.title}（第 ${Math.floor(i / SEG_MAX) + 1} 部分）` })
      }
      continue
    }
    if (cur.length && curLen + clen > SEG_MAX) { segs.push(mk(cur)); cur = []; curLen = 0 }
    cur.push(c); curLen += clen
  }
  if (cur.length) segs.push(mk(cur))
  return segs
}

const charCount = computed(() => novelText.value.length)
const chapterCountJS = computed(() => _splitChaptersJS(novelText.value).length)
const segments = ref([])
const selectedSeg = ref(0)
watch(novelText, (t) => { segments.value = _buildSegments(t || ''); selectedSeg.value = 0 })
const needsSegment = computed(() => segments.value.length > 1)
function conversionText() {
  return needsSegment.value ? (segments.value[selectedSeg.value]?.text || novelText.value) : novelText.value
}

// 新建：提交转换 -> 后台任务
async function doConvert() {
  errorMsg.value = ''
  if (conversionText().trim().length < 50) {
    errorMsg.value = '请先粘贴或载入小说文本（建议 ≥3 章）。'
    return
  }
  if (engineChoice.value === 'agents') return doAgentConvert()
  loading.value = true
  try {
    const res = await createProject({
      text: conversionText(), title: title.value, author: author.value,
      engine: engineChoice.value,
    })
    projectId.value = res.project_id
    router.replace({ name: 'workspace', params: { id: res.project_id } })
    startPoll(res.job_id)
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

function startPoll(jobId) {
  converting.value = true
  errorMsg.value = ''
  const tick = async () => {
    try {
      const j = await getJob(jobId)
      job.value = j
      if (j.status === 'done') {
        converting.value = false
        await auth.refresh()          // 积分可能已扣
        await loadProject(projectId.value)
      } else if (j.status === 'failed') {
        converting.value = false
        errorMsg.value = j.error || '转换失败'
      } else {
        pollTimer = setTimeout(tick, 1200)
      }
    } catch (e) {
      converting.value = false
      errorMsg.value = e.message
    }
  }
  tick()
}

// 多 Agent 编排：SSE 实时活动流 + 渐进式出稿（边转边把完成的章节渲染出来）
const partialChars = ref([])
const partialByChapter = ref({})
const streaming = ref(false)   // 是否处于渐进式预览阶段

function rebuildPartial() {
  const byCh = partialByChapter.value
  const idxs = Object.keys(byCh).map(Number).sort((a, b) => a - b)
  let n = 0
  const scenes = []
  for (const i of idxs) {
    for (const s of byCh[i]) scenes.push({ ...s, scene_number: ++n })
  }
  screenplay.value = {
    meta: { title: title.value, generated_by: 'ai-draft' },
    characters: partialChars.value,
    scenes,
  }
}

async function doAgentConvert() {
  agentEvents.value = []
  agentStats.value = null
  screenplay.value = null
  stats.value = null
  partialChars.value = []
  partialByChapter.value = {}
  errorMsg.value = ''
  converting.value = true
  streaming.value = true
  job.value = null
  await streamAgents(
    {
      text: conversionText(),
      title: title.value,
      author: author.value,
      engine: modelsAvailable.value ? 'agents' : 'offline',
      model: model.value || undefined,
    },
    {
      onEvent: (e) => { agentEvents.value = [...agentEvents.value, e] },
      onPartial: (p) => {
        if (p.kind === 'characters') partialChars.value = p.characters || []
        else if (p.kind === 'chapter') {
          partialByChapter.value = { ...partialByChapter.value, [p.chapter_index]: p.scenes || [] }
        }
        rebuildPartial()
      },
      onResult: (r) => {
        screenplay.value = r.screenplay   // 用最终校验过的完整稿替换渐进稿
        stats.value = r.stats
        agentStats.value = r.stats
        converting.value = false
        streaming.value = false
      },
      onError: (err) => { errorMsg.value = err.message; converting.value = false; streaming.value = false },
    },
  )
}

const progressPct = computed(() => {
  if (!job.value || !job.value.total) return 8
  return Math.max(8, Math.round((job.value.progress / job.value.total) * 100))
})

// 一键拆集
async function doSplit() {
  if (!projectId.value) return
  makingEp.value = true
  errorMsg.value = ''
  try {
    const res = await makeEpisodes(projectId.value, targetMin.value)
    if (screenplay.value) screenplay.value.episodes = res.episodes
    showEpisodes.value = true
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    makingEp.value = false
  }
}

function fmtDur(sec) {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return m ? `${m}分${String(s).padStart(2, '0')}秒` : `${s}秒`
}

// 导出分集台词本（交付物）
function exportEpisodes() {
  const sp = screenplay.value
  const byNo = {}
  sp.scenes.forEach((s) => { byNo[s.scene_number] = s })
  const out = [`${title.value || '剧本'} · 分集台词本`, '']
  episodes.value.forEach((ep) => {
    out.push(`【第${ep.episode_number}集】${ep.title}  （约 ${ep.duration_text}）`)
    out.push(`钩子：${ep.hook || '（无）'}`)
    ep.scene_numbers.forEach((n) => {
      const s = byNo[n]
      if (!s) return
      const h = s.heading
      out.push(`  ◇ ${[h.time, intExtCN(h.int_ext), h.location].filter(Boolean).join(' ')}`)
      s.elements.forEach((el) => {
        if (el.type === 'dialogue') out.push(`  ${el.character || ''}${el.parenthetical ? '（' + el.parenthetical + '）' : ''}：${el.text || ''}`)
        else if (el.type === 'voiceover') out.push(`  ${el.character || ''}（画外音）：${el.text || ''}`)
        else if (el.type === 'action') out.push(`  △ ${el.text || ''}`)
        else out.push(`  ${el.text || ''}`)
      })
    })
    out.push(`扣子：${ep.cliffhanger || '（无）'}`)
    out.push('')
  })
  const blob = new Blob([out.join('\n')], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `${title.value || '剧本'}-分集台词本.txt`; a.click()
  URL.revokeObjectURL(url)
}

const originalParas = computed(() =>
  novelText.value.split(/\n+/).map((s) => s.trim()).filter(Boolean)
)

// ---- 点哪改哪 ----
function edit(key) { editing.value = key }
function doneEdit() { editing.value = null }
function addElement(scene, si, type = 'action') {
  scene.elements.push({ type, text: '', character: '', parenthetical: '' })
  editing.value = `el:${si}:${scene.elements.length - 1}`
}
function removeElement(scene, idx) { scene.elements.splice(idx, 1); editing.value = null }
function removeScene(idx) {
  if (!confirm('删除整场？')) return
  screenplay.value.scenes.splice(idx, 1)
  screenplay.value.scenes.forEach((s, i) => (s.scene_number = i + 1))
  editing.value = null
}

async function doSave() {
  if (!projectId.value) return
  saving.value = true
  errorMsg.value = ''
  editing.value = null
  try {
    const res = await saveScreenplay(projectId.value, screenplay.value)
    stats.value = { ...(stats.value || {}), valid: res.valid, problems: res.problems }
    savedFlash.value = res.version
    setTimeout(() => { savedFlash.value = 0 }, 2600)
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    saving.value = false
  }
}

// ---- 可读剧本文本（短剧规范） ----
function buildScript() {
  const sp = screenplay.value
  const out = []
  out.push(title.value || '未命名剧本')
  if (author.value) out.push(`编剧：${author.value}`)
  out.push('')
  if (sp.characters?.length) {
    out.push(`【人物】${sp.characters.map((c) => c.name).join('、')}`)
    out.push('')
  }
  sp.scenes.forEach((s) => {
    const h = s.heading
    out.push(`第${s.scene_number}场　${[h.time, intExtCN(h.int_ext), h.location].filter(Boolean).join(' ')}`)
    if (s.synopsis) out.push(`（${s.synopsis}）`)
    s.elements.forEach((el) => {
      if (el.type === 'action') out.push(`△ ${el.text || ''}`)
      else if (el.type === 'transition') out.push(el.text || '')
      else if (el.type === 'voiceover') out.push(`${el.character || ''}（画外音）：${el.text || ''}`)
      else {
        const p = el.parenthetical ? `（${el.parenthetical}）` : ''
        out.push(`${el.character || ''}${p}：${el.text || ''}`)
      }
    })
    out.push('')
  })
  return out.join('\n')
}
function exportScript() {
  const blob = new Blob([buildScript()], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `${title.value || '剧本'}.txt`; a.click()
  URL.revokeObjectURL(url)
}
async function copyScript() {
  try {
    await navigator.clipboard.writeText(buildScript())
    copied.value = true
    setTimeout(() => { copied.value = false }, 1800)
  } catch { errorMsg.value = '复制失败，请手动选择文本复制。' }
}

// ---- YAML（结构化交付物）：调用后端 /api/export，对当前/编辑后的剧本重新生成 + 校验 ----
async function loadYaml() {
  if (!screenplay.value) return ''
  yamlBusy.value = true
  errorMsg.value = ''
  try {
    const res = await apiExportYaml(screenplay.value)
    yamlText.value = res.yaml || ''
    if (stats.value) stats.value = { ...stats.value, valid: res.valid, problems: res.problems }
    return yamlText.value
  } catch (e) {
    errorMsg.value = e.message
    return ''
  } finally {
    yamlBusy.value = false
  }
}
async function toggleYaml() {
  showYaml.value = !showYaml.value
  if (showYaml.value) await loadYaml()   // 每次打开都取最新（含编辑）
}
async function exportYamlFile() {
  const y = await loadYaml()
  if (!y) return
  const blob = new Blob([y], { type: 'text/yaml;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `${title.value || '剧本'}.yaml`; a.click()
  URL.revokeObjectURL(url)
}
async function copyYaml() {
  const y = yamlText.value || (await loadYaml())
  if (!y) return
  try {
    await navigator.clipboard.writeText(y)
    yamlCopied.value = true
    setTimeout(() => { yamlCopied.value = false }, 1800)
  } catch { errorMsg.value = '复制失败，请手动选择文本复制。' }
}
</script>

<template>
  <div>
    <!-- 新建：输入区 -->
    <section v-if="!screenplay && !converting && !loading" class="new-card card">
      <h2>新建转换</h2>
      <p class="hint">粘贴整篇小说，自动分章、切场、识别对白与心理独白，生成可直接阅读、可导出的剧本。</p>
      <div class="new-meta">
        <input v-model="title" placeholder="剧本标题" />
        <input v-model="author" placeholder="编剧 / 改编者（可选）" />
      </div>
      <div class="dropzone" :class="{ dragging }"
           @dragover.prevent="dragging = true"
           @dragleave.prevent="dragging = false"
           @drop.prevent="onDrop">
        <textarea v-model="novelText"
          placeholder="在此粘贴小说全文，或把 .txt 文件拖到这里（建议至少 3 个章节，「第一章」等标题会自动识别）…" />
        <div v-if="dragging" class="drop-overlay">📄 松开以载入 .txt 文件</div>
      </div>
      <input ref="fileInput" type="file" accept=".txt,text/plain"
             style="display:none" @change="onFileChange" />

      <!-- 字数 / 章节 提示 -->
      <div class="text-meta">
        <span>{{ charCount.toLocaleString() }} 字<template v-if="chapterCountJS"> · 约 {{ chapterCountJS }} 章</template></span>
        <span v-if="charCount > SEG_WARN && !needsSegment" class="tm-warn">文本较长，转换可能稍慢</span>
      </div>

      <!-- 超长文本：智能分段 -->
      <div v-if="needsSegment" class="seg-panel">
        <div class="seg-head">
          ⚠ 文本较长（{{ charCount.toLocaleString() }} 字），超过单次上限 {{ (SEG_MAX / 10000) }} 万字，
          已按章节切为 <b>{{ segments.length }}</b> 段，请逐段转换：
        </div>
        <label v-for="(s, i) in segments" :key="i" class="seg-row" :class="{ on: selectedSeg === i }">
          <input type="radio" :value="i" v-model="selectedSeg" />
          <span class="seg-idx">第 {{ i + 1 }} 段</span>
          <span class="seg-range">{{ s.range }}</span>
          <span class="seg-chars">{{ s.chars.toLocaleString() }} 字<template v-if="s.chapterCount"> · {{ s.chapterCount }} 章</template></span>
        </label>
        <p class="seg-tip">转换完一段可继续选下一段；各段独立成稿，导出后可自行拼接。</p>
      </div>

      <!-- 引擎选择 -->
      <div class="engine-pick">
        <label class="ep-opt" :class="{ on: engineChoice === 'offline' }">
          <input type="radio" value="offline" v-model="engineChoice" />
          <div>
            <div class="ep-title">⚡ 快速版 <span class="ep-free">免费</span></div>
            <div class="ep-desc">离线规则即时出稿，适合预览结构</div>
          </div>
        </label>
        <label class="ep-opt" :class="{ on: engineChoice === 'ai', disabled: !canUseAI }">
          <input type="radio" value="ai" v-model="engineChoice" :disabled="!canUseAI" />
          <div>
            <div class="ep-title">✨ AI 精修版 <span class="ep-cost">消耗 1 积分（剩 {{ auth.credits }}）</span></div>
            <div class="ep-desc">大模型分场更准、心理戏转画外音更自然</div>
            <router-link v-if="!canUseAI" to="/pricing" class="ep-up">积分不足，去升级 →</router-link>
          </div>
        </label>
        <label class="ep-opt ep-wide" :class="{ on: engineChoice === 'agents', disabled: modelsAvailable && !canUseAgents }">
          <input type="radio" value="agents" v-model="engineChoice" :disabled="modelsAvailable && !canUseAgents" />
          <div>
            <div class="ep-title">⚡ 多 Agent 编排 <span class="ep-flag">旗舰</span>
              <span v-if="modelsAvailable" class="ep-cost">消耗 {{ AGENT_COST }} 积分（剩 {{ auth.credits }}）</span>
              <span v-else class="ep-free">离线运行 · 免费</span>
              <span class="ep-new">实时 · 并发 · 缓存</span>
            </div>
            <div class="ep-desc">多 Agent 并发转换 + Critic 自检改写，质量更高；实时看活动流、附 token 账本</div>
            <router-link v-if="modelsAvailable && !canUseAgents" to="/pricing" class="ep-up">积分不足（需 {{ AGENT_COST }}），去升级 →</router-link>
          </div>
        </label>
      </div>
      <p class="bill-rule">计费规则：✨ AI 精修每次成功转换扣 1 积分；⚡ 多 Agent 编排（旗舰）扣 {{ AGENT_COST }} 积分；失败不扣；快速版与离线模式免费、0 token。</p>

      <!-- 模型选择（多 Agent / AI 用）-->
      <div v-if="engineChoice === 'agents' && modelsAvailable" class="model-pick">
        <span class="mp-label">模型</span>
        <select v-model="model" class="mp-select">
          <option v-for="m in models" :key="m.id" :value="m.id">
            {{ m.label }} · {{ m.tier }}（{{ m.desc }}）
          </option>
        </select>
      </div>
      <p v-else-if="engineChoice === 'agents' && !modelsAvailable" class="model-note">
        未配置 AI 入口，多 Agent 将以离线引擎运行（0 token，演示编排与缓存）。
      </p>

      <p v-if="errorMsg" class="error">{{ errorMsg }}</p>
      <div class="new-actions">
        <button class="ghost" @click="pickFile">📄 上传 .txt</button>
        <button class="ghost" @click="loadSample">载入示例小说</button>
        <button class="primary" :disabled="loading" @click="doConvert">
          {{ loading ? '提交中…' : (needsSegment ? `转换第 ${selectedSeg + 1} 段 →` : '开始转换 →') }}
        </button>
      </div>
    </section>

    <!-- 转换中：进度（离线/AI 后台任务）-->
    <section v-if="converting && engineChoice !== 'agents'" class="convert-card card">
      <div class="spinner"></div>
      <h3>正在转换…</h3>
      <p class="cv-sub" v-if="job && job.total">已完成 {{ job.progress }} / {{ job.total }} 章</p>
      <p class="cv-sub" v-else>正在解析章节…</p>
      <div class="bar"><div class="bar-fill" :style="{ width: progressPct + '%' }"></div></div>
      <p class="cv-tip">{{ engineChoice === 'ai' ? 'AI 精修中，长篇可能需要一会儿' : '离线快速转换中' }}</p>
    </section>

    <!-- 多 Agent 实时活动流 -->
    <section v-if="agentEvents.length" class="agent-flow card">
      <div class="af-head">
        <h3>⚡ Agent 活动流 <span v-if="converting" class="af-live">● 实时</span></h3>
        <div v-if="agentStats" class="af-sum">
          <span>总 token <b>{{ afTokens }}</b></span>
          <span>缓存命中 <b>{{ afHitRate }}%</b></span>
          <span v-if="agentStats.tokens.cache_read">prompt缓存 <b>{{ agentStats.tokens.cache_read }}</b></span>
          <span>耗时 <b>{{ afWall }}</b></span>
          <span>Critic <b>{{ agentStats.rounds }}</b> 轮</span>
          <span>校验 <b :class="{ bad: !agentStats.valid }">{{ agentStats.valid ? '通过 ✓' : '未通过' }}</b></span>
        </div>
      </div>
      <ul class="af-list">
        <li v-for="e in agentEvents" :key="e.seq" class="af-row" :class="'af-' + e.status">
          <span class="af-ico">{{ agentIcon(e.status) }}</span>
          <span class="af-agent">{{ e.agent }}</span>
          <span class="af-note">{{ e.note || '' }}</span>
          <span v-if="e.status === 'done' && (e.in || e.out)" class="af-tok">
            in {{ e.in }} / out {{ e.out }}<template v-if="e.cache_read"> · ⚡read {{ e.cache_read }}</template>
          </span>
          <span v-if="e.ms != null" class="af-ms">{{ e.ms }}ms</span>
        </li>
      </ul>
    </section>

    <p v-if="loading && !converting" class="empty">加载中…</p>
    <p v-if="errorMsg && !screenplay && !converting" class="error" style="text-align:center;margin-top:16px">{{ errorMsg }}</p>

    <!-- 已转换：剧本视图 -->
    <template v-if="screenplay">
      <div v-if="streaming" class="streaming-banner card">
        <span class="sb-dot"></span>
        正在边转边出稿…已生成 <b>{{ screenplay.scenes.length }}</b> 场，写完即可编辑
      </div>
      <div class="ws-bar card">
        <div class="ws-title">
          <input v-model="title" class="title-input" placeholder="剧本标题" />
          <div class="ws-chips">
            <span class="chip-meta">{{ screenplay.scenes.length }} 场</span>
            <span v-if="stats && stats.valid !== undefined" class="chip-meta" :class="stats.valid ? 'good' : 'warn'">
              {{ stats.valid ? '检查通过 ✓' : '有 ' + (stats.problems?.length || 0) + ' 处待修正' }}
            </span>
          </div>
        </div>
        <div class="ws-actions">
          <transition name="fade">
            <span v-if="savedFlash" class="saved-flash">已保存 ✓ 第 {{ savedFlash }} 版</span>
          </transition>
          <button class="ghost small" :class="{ on: compare }" @click="compare = !compare">
            {{ compare ? '✓ 对照原文' : '对照原文' }}
          </button>
          <button class="ghost small" :class="{ on: showScript }" @click="showScript = !showScript">
            {{ showScript ? '关闭预览' : '预览全文' }}
          </button>
          <button class="ghost small" @click="exportScript">导出台词本 .txt</button>
          <button class="ghost small" :class="{ on: showYaml }" @click="toggleYaml">
            {{ showYaml ? '关闭 YAML' : '查看 YAML' }}
          </button>
          <button class="primary small" :disabled="yamlBusy" @click="exportYamlFile">
            {{ yamlBusy ? '生成中…' : '⬇ 导出 YAML' }}
          </button>
          <button v-if="episodes.length" class="ghost small" :class="{ on: showEpisodes }"
                  @click="showEpisodes = !showEpisodes">🎬 剧集 ({{ episodes.length }})</button>
          <button class="primary" :disabled="saving" @click="doSave">
            {{ saving ? '保存中…' : '保存修改' }}
          </button>
        </div>
      </div>

      <p v-if="errorMsg" class="error" style="margin:10px 0;">{{ errorMsg }}</p>

      <!-- 拆集 CTA（还没拆过） -->
      <section v-if="!episodes.length" class="split-cta card">
        <div class="sc-text">
          <strong>🎬 拆成短剧集</strong>
          <span>把整部剧本按节奏切成 2~3 分钟一集，自动生成钩子、扣子，并体检时长。</span>
        </div>
        <div class="sc-ctrl">
          <label>每集目标
            <select v-model.number="targetMin">
              <option :value="2">2 分钟</option>
              <option :value="2.5">2.5 分钟</option>
              <option :value="3">3 分钟</option>
            </select>
          </label>
          <button class="primary" :disabled="makingEp" @click="doSplit">
            {{ makingEp ? '拆集中…' : '一键拆集' }}
          </button>
        </div>
      </section>

      <!-- 剧集面板 -->
      <section v-if="episodes.length && showEpisodes" class="ep-panel card">
        <div class="ep-head">
          <h3>分集（{{ epSummary.count }} 集）</h3>
          <span class="ep-sum">
            <b class="ok">{{ epSummary.healthy }}</b> 集达标 ·
            <b class="bad">{{ epSummary.count - epSummary.healthy }}</b> 集待优化 ·
            平均 {{ fmtDur(epSummary.avg) }}
          </span>
          <span class="ep-actions">
            <label class="re">每集
              <select v-model.number="targetMin">
                <option :value="2">2分</option><option :value="2.5">2.5分</option><option :value="3">3分</option>
              </select>
            </label>
            <button class="ghost small" :disabled="makingEp" @click="doSplit">重新拆集</button>
            <button class="ghost small" @click="exportEpisodes">导出分集台词本</button>
          </span>
        </div>

        <div class="ep-grid">
          <div v-for="(ep, i) in episodes" :key="i" class="ep-card" :class="{ warn: ep.warnings.length }">
            <div class="ep-top">
              <span class="ep-no">第{{ ep.episode_number }}集</span>
              <span class="ep-dur" :class="{ bad: !ep.checks.within_duration }">⏱ {{ ep.duration_text }}</span>
            </div>
            <div class="ep-field">
              <label>🪝 钩子（开场抓人）</label>
              <textarea v-model="ep.hook" rows="2" placeholder="本集开场第一句，要抓人" />
            </div>
            <div class="ep-field">
              <label>🪤 扣子（集尾留悬念）</label>
              <textarea v-model="ep.cliffhanger" rows="2" placeholder="本集结尾，逼观众看下一集" />
            </div>
            <div class="ep-meta">涉及场次：{{ ep.scene_numbers.join('、') }}</div>
            <div class="ep-checks">
              <span :class="ep.checks.has_hook ? 'c-ok' : 'c-bad'">钩子</span>
              <span :class="ep.checks.has_cliffhanger ? 'c-ok' : 'c-bad'">扣子</span>
              <span :class="ep.checks.within_duration ? 'c-ok' : 'c-bad'">时长</span>
              <span :class="ep.checks.has_interaction ? 'c-ok' : 'c-bad'">冲突</span>
            </div>
            <div v-if="ep.warnings.length" class="ep-warn">⚠ {{ ep.warnings.join('；') }}</div>
          </div>
        </div>
        <p class="ep-tip">改完钩子/扣子记得点右上「保存修改」。导出台词本可直接发给导演/演员。</p>
      </section>

      <div class="editor" :class="{ split: compare }">
        <div v-if="compare" class="orig card">
          <div class="pane-tag">小说原文</div>
          <p v-for="(p, i) in originalParas" :key="i">{{ p }}</p>
        </div>

        <div class="stage">
          <div class="cast">
            <span class="cast-label">人物</span>
            <span v-for="c in screenplay.characters" :key="c.id" class="cast-chip">{{ c.name }}</span>
          </div>

          <div v-for="(scene, si) in screenplay.scenes" :key="si" class="scene-block">
            <div class="slug-row">
              <span class="slug-no">第{{ scene.scene_number }}场</span>
              <template v-if="editing === `head:${si}`">
                <select v-model="scene.heading.int_ext">
                  <option v-for="o in INTEXT_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</option>
                </select>
                <input v-model="scene.heading.location" placeholder="地点（如：客厅）" style="flex:1;min-width:100px" />
                <input v-model="scene.heading.time" list="time-opts" placeholder="时间（日/夜）" style="width:120px" />
                <datalist id="time-opts"><option v-for="t in TIME_OPTIONS" :key="t" :value="t" /></datalist>
                <button class="del" @click="removeScene(si)">删除整场</button>
                <button class="primary small" @click="doneEdit">完成</button>
              </template>
              <div v-else class="slug-text" @click="edit(`head:${si}`)">
                <span class="se-time">{{ scene.heading.time || '日' }}</span>
                <b>{{ intExtCN(scene.heading.int_ext) }}</b>
                <span>{{ scene.heading.location || '未定地点' }}</span>
                <span class="edit-hint">✎ 点击修改</span>
              </div>
            </div>

            <div v-if="editing === `syn:${si}`" class="syn-edit">
              <input v-model="scene.synopsis" placeholder="本场讲了什么（一句话）" style="flex:1" />
              <button class="primary small" @click="doneEdit">完成</button>
            </div>
            <p v-else class="synopsis" @click="edit(`syn:${si}`)">
              {{ scene.synopsis || '+ 添加本场梗概' }}<span class="edit-hint">✎</span>
            </p>

            <div v-for="(el, ei) in scene.elements" :key="ei" class="ln-wrap">
              <div v-if="editing === `el:${si}:${ei}`" class="el-edit">
                <div class="el-edit-top">
                  <select v-model="el.type">
                    <option v-for="t in ELEMENT_TYPES" :key="t.value" :value="t.value">{{ t.label }}</option>
                  </select>
                  <input v-if="el.type === 'dialogue' || el.type === 'voiceover'"
                         v-model="el.character" placeholder="谁说的" style="width:120px" />
                  <input v-if="el.type === 'dialogue'"
                         v-model="el.parenthetical" placeholder="语气/动作（可空）" style="width:150px" />
                </div>
                <textarea v-model="el.text" rows="2"
                          :placeholder="el.type === 'action' ? '描述这一刻发生了什么…' : '说的内容…'" />
                <div class="el-edit-foot">
                  <button class="del" @click="removeElement(scene, ei)">删除这句</button>
                  <button class="primary small" @click="doneEdit">完成</button>
                </div>
              </div>
              <div v-else class="ln" :class="'ln-' + el.type" @click="edit(`el:${si}:${ei}`)">
                <template v-if="el.type === 'dialogue' || el.type === 'voiceover'">
                  <div class="cue">
                    {{ el.character || '？' }}<span v-if="el.type === 'voiceover'" class="vo">（画外音）</span>
                    <span v-if="el.parenthetical" class="paren">（{{ el.parenthetical }}）</span>
                  </div>
                  <p class="cue-text">{{ el.text || '（空，点击编辑）' }}</p>
                </template>
                <p v-else-if="el.type === 'transition'" class="trans">{{ el.text || '转场' }}</p>
                <p v-else class="action"><span class="tri">△</span> {{ el.text || '（空动作行，点击编辑）' }}</p>
                <span class="edit-hint">✎</span>
              </div>
            </div>

            <div class="add-row">
              <span>插入：</span>
              <button class="ghost small" @click="addElement(scene, si, 'action')">动作</button>
              <button class="ghost small" @click="addElement(scene, si, 'dialogue')">对白</button>
              <button class="ghost small" @click="addElement(scene, si, 'voiceover')">画外音</button>
              <button class="ghost small" @click="addElement(scene, si, 'transition')">转场</button>
            </div>
          </div>
        </div>
      </div>

      <section v-if="showScript" class="script-out card">
        <div class="script-head">
          <h3>剧本全文（可直接复制）</h3>
          <button class="ghost small" @click="copyScript">{{ copied ? '已复制 ✓' : '复制全文' }}</button>
          <button class="ghost small" @click="exportScript">导出台词本 .txt</button>
        </div>
        <ul v-if="stats && stats.valid === false" class="problems">
          <li v-for="(p, i) in stats.problems" :key="i">⚠ {{ p }}</li>
        </ul>
        <pre class="script-paper">{{ buildScript() }}</pre>
      </section>

      <section v-if="showYaml" class="script-out card">
        <div class="script-head">
          <h3>剧本 YAML（结构化交付物 · Schema v1.0）</h3>
          <span v-if="stats" class="yaml-valid" :class="{ bad: stats.valid === false }">
            {{ stats.valid === false ? '⚠ 校验未通过' : '✓ 校验通过' }}
          </span>
          <button class="ghost small" :disabled="yamlBusy" @click="copyYaml">
            {{ yamlCopied ? '已复制 ✓' : '复制 YAML' }}
          </button>
          <button class="ghost small" :disabled="yamlBusy" @click="exportYamlFile">导出 .yaml</button>
        </div>
        <ul v-if="stats && stats.valid === false" class="problems">
          <li v-for="(p, i) in stats.problems" :key="i">⚠ {{ p }}</li>
        </ul>
        <p v-if="yamlBusy" class="hint">生成中…</p>
        <pre v-else class="script-paper">{{ yamlText }}</pre>
      </section>
    </template>
  </div>
</template>

<style scoped>
.new-card { max-width: 760px; margin: 3vh auto; padding: 28px; }
.new-card h2 { margin: 0 0 6px; font-size: 20px; }
.new-card .hint { margin: 0 0 18px; color: var(--text-2); font-size: 14px; }
.new-meta { display: flex; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.new-meta input { flex: 1; min-width: 160px; }
.new-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 16px; }

/* 文件拖拽区 */
.dropzone { position: relative; border-radius: var(--r-sm); transition: box-shadow .15s; }
.dropzone.dragging { box-shadow: 0 0 0 2px var(--brand); }
.dropzone.dragging textarea { border-color: var(--brand); }
.drop-overlay {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  background: var(--brand-soft); border: 2px dashed var(--brand); border-radius: var(--r-sm);
  color: var(--brand); font-weight: 700; font-size: 15px; pointer-events: none;
}

/* 引擎选择 */
.engine-pick { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 14px; }
.ep-opt { display: flex; gap: 10px; align-items: flex-start; border: 1.5px solid var(--border-strong); border-radius: var(--r-sm); padding: 12px 14px; cursor: pointer; transition: border-color .15s, background .15s; }
.ep-opt.on { border-color: var(--brand); background: var(--brand-soft); }
.ep-opt.disabled { opacity: .7; }
.ep-opt input { margin-top: 3px; }
.ep-title { font-weight: 700; font-size: 14px; }
.ep-free { color: var(--ok); font-size: 12px; margin-left: 4px; }
.ep-cost { color: var(--brand); font-size: 12px; font-weight: 600; margin-left: 4px; }
.ep-desc { font-size: 12px; color: var(--text-2); margin-top: 3px; }
.ep-up { display: inline-block; margin-top: 6px; font-size: 12px; color: var(--brand); font-weight: 600; }
.bill-rule { margin: 10px 2px 0; font-size: 12px; color: var(--text-3); line-height: 1.6; }

/* 字数提示 + 智能分段 */
.text-meta { display: flex; justify-content: space-between; align-items: center; margin-top: 6px; font-size: 12px; color: var(--text-2); }
.tm-warn { color: var(--brand); font-weight: 600; }
.seg-panel { margin-top: 12px; border: 1.5px solid var(--brand); border-radius: var(--r-sm); padding: 12px 14px; background: var(--brand-soft); }
.seg-head { font-size: 13px; color: var(--text); margin-bottom: 10px; line-height: 1.6; }
.seg-row { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 8px; cursor: pointer; font-size: 13px; }
.seg-row.on { background: #fff; box-shadow: 0 0 0 1.5px var(--brand) inset; }
.seg-row:hover { background: rgba(255,255,255,.6); }
.seg-idx { font-weight: 700; min-width: 56px; }
.seg-range { flex: 1; color: var(--text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.seg-chars { font-variant-numeric: tabular-nums; color: var(--text-2); }
.seg-tip { margin: 8px 2px 0; font-size: 12px; color: var(--text-2); }
.ep-wide { grid-column: 1 / -1; }
.ep-new { color: var(--brand); font-size: 12px; font-weight: 600; margin-left: 4px; }
.ep-flag { font-size: 11px; font-weight: 700; color: #fff; background: linear-gradient(90deg, var(--brand), #e0894f); padding: 1px 8px; border-radius: 999px; margin-left: 4px; }
@media (max-width: 640px) { .engine-pick { grid-template-columns: 1fr; } }

/* 模型下拉 */
.model-pick { display: flex; align-items: center; gap: 10px; margin-top: 12px; }
.mp-label { font-size: 13px; color: var(--text-2); font-weight: 600; }
.mp-select { flex: 1; padding: 8px 10px; border: 1.5px solid var(--border-strong); border-radius: var(--r-sm); background: #fff; font-size: 13px; }
.model-note { margin-top: 10px; font-size: 12px; color: var(--text-2); }

/* Agent 活动流 */
.agent-flow { max-width: 860px; margin: 3vh auto; padding: 20px 22px; }
.af-head { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; }
.af-head h3 { margin: 0; font-size: 16px; flex: 1; }
.af-live { color: var(--brand); font-size: 12px; animation: pulse 1.2s ease-in-out infinite; }
@keyframes pulse { 50% { opacity: .35; } }
.af-sum { display: flex; flex-wrap: wrap; gap: 14px; font-size: 12px; color: var(--text-2); }
.af-sum b { color: var(--text); }
.af-sum b.bad { color: var(--bad); }
.af-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px; max-height: 56vh; overflow: auto; }
.af-row { display: flex; align-items: center; gap: 10px; padding: 6px 10px; border-radius: 6px; font-size: 13px; }
.af-row:nth-child(odd) { background: rgba(0,0,0,.025); }
.af-ico { width: 18px; text-align: center; }
.af-agent { font-weight: 600; min-width: 150px; }
.af-note { flex: 1; color: var(--text-2); font-size: 12px; }
.af-tok { font-variant-numeric: tabular-nums; color: var(--text-2); font-size: 12px; }
.af-ms { font-variant-numeric: tabular-nums; color: var(--text-3, #999); font-size: 12px; min-width: 56px; text-align: right; }
.af-done .af-ico { color: var(--ok, #2e9e5b); }
.af-cache { background: var(--brand-soft) !important; }
.af-cache .af-ico { color: var(--brand); }
.af-error .af-ico { color: var(--bad); }
.af-error .af-note { color: var(--bad); }
.af-start .af-ico { color: var(--brand); }

/* 渐进式出稿横幅 */
.streaming-banner { max-width: 980px; margin: 0 auto 10px; padding: 10px 16px; display: flex; align-items: center; gap: 10px; font-size: 14px; color: var(--brand); background: var(--brand-soft); }
.sb-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--brand); animation: pulse 1.1s ease-in-out infinite; }

/* 转换中 */
.convert-card { max-width: 560px; margin: 8vh auto; padding: 36px; text-align: center; }
.convert-card h3 { margin: 14px 0 6px; font-size: 18px; }
.cv-sub { color: var(--text-2); margin: 0 0 16px; }
.cv-tip { color: var(--text-3); font-size: 12px; margin: 12px 0 0; }
.spinner { width: 38px; height: 38px; border: 3px solid var(--border); border-top-color: var(--brand); border-radius: 50%; margin: 0 auto; animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.bar { height: 8px; background: var(--surface-2); border-radius: 999px; overflow: hidden; }
.bar-fill { height: 100%; background: linear-gradient(90deg, var(--brand), #e0894f); border-radius: 999px; transition: width .4s; }

/* 拆集 CTA */
.split-cta { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 16px 20px; margin-bottom: 16px; flex-wrap: wrap; border-left: 4px solid var(--brand); }
.split-cta .sc-text strong { font-size: 15px; }
.split-cta .sc-text span { display: block; color: var(--text-2); font-size: 13px; margin-top: 4px; }
.split-cta .sc-ctrl { display: flex; gap: 10px; align-items: center; }
.split-cta select { padding: 6px 8px; }

/* 剧集面板 */
.ep-panel { padding: 18px 20px; margin-bottom: 16px; }
.ep-head { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
.ep-head h3 { margin: 0; font-size: 16px; }
.ep-sum { font-size: 13px; color: var(--text-2); }
.ep-sum .ok { color: var(--ok); } .ep-sum .bad { color: var(--bad); }
.ep-actions { margin-left: auto; display: flex; gap: 8px; align-items: center; }
.ep-actions .re { font-size: 12px; color: var(--text-2); }
.ep-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; }
.ep-card { border: 1px solid var(--border); border-radius: var(--r); padding: 14px; background: var(--surface-2); }
.ep-card.warn { border-color: #eecaca; }
.ep-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.ep-no { font-weight: 700; color: var(--brand); }
.ep-dur { font-size: 13px; color: var(--text-2); }
.ep-dur.bad { color: var(--bad); font-weight: 600; }
.ep-field { margin-bottom: 8px; }
.ep-field label { display: block; font-size: 12px; color: var(--text-2); margin-bottom: 3px; }
.ep-field textarea { width: 100%; min-height: 42px; font-size: 13px; background: var(--surface); }
.ep-meta { font-size: 12px; color: var(--text-3); margin: 6px 0; }
.ep-checks { display: flex; gap: 6px; flex-wrap: wrap; }
.ep-checks span { font-size: 11px; padding: 2px 9px; border-radius: 999px; }
.c-ok { color: var(--ok); background: #f0f8f0; }
.c-ok::before { content: '✓ '; }
.c-bad { color: var(--bad); background: #fcf0ef; }
.c-bad::before { content: '✕ '; }
.ep-warn { font-size: 12px; color: var(--bad); margin-top: 8px; }
.ep-tip { font-size: 12px; color: var(--text-3); margin: 14px 0 0; }

/* 工具栏 */
.ws-bar { display: flex; justify-content: space-between; align-items: center; gap: 14px; padding: 12px 16px; margin-bottom: 16px; flex-wrap: wrap; }
.title-input { font-size: 18px; font-weight: 700; border: 1px solid transparent; background: transparent; padding: 4px 8px; border-radius: 6px; }
.title-input:hover { border-color: var(--border-strong); }
.ws-chips { display: flex; gap: 8px; margin-top: 6px; flex-wrap: wrap; }
.chip-meta { font-size: 12px; color: var(--text-2); background: var(--surface-2); border: 1px solid var(--border); padding: 3px 10px; border-radius: 999px; }
.chip-meta.good { color: var(--ok); border-color: #bfe0c0; background: #f0f8f0; }
.chip-meta.warn { color: var(--bad); border-color: #eecaca; background: #fcf0ef; }
.ws-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.ws-actions .ghost.on { color: var(--brand); border-color: var(--brand); background: var(--brand-soft); }
.saved-flash { font-size: 13px; color: var(--ok); font-weight: 600; margin-right: 4px; }
.fade-enter-active, .fade-leave-active { transition: opacity .3s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.editor.split { display: grid; grid-template-columns: 1fr 1.2fr; gap: 18px; align-items: start; }
.orig { padding: 18px 20px; max-height: 78vh; overflow: auto; position: sticky; top: 80px; }
.orig p { line-height: 1.85; margin: 0 0 10px; color: var(--text-2); }
.pane-tag { font-size: 12px; font-weight: 700; color: var(--text-3); letter-spacing: .5px; margin-bottom: 10px; }
.stage { max-width: 820px; margin: 0 auto; width: 100%; }
.editor:not(.split) .stage { max-width: 760px; }

.cast { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r); padding: 12px 16px; margin-bottom: 16px; box-shadow: var(--shadow); }
.cast-label { font-size: 12px; font-weight: 700; color: var(--text-3); margin-right: 8px; }
.cast-chip { display: inline-block; background: var(--brand-soft); color: var(--brand); padding: 3px 11px; border-radius: 999px; margin: 0 6px 4px 0; font-size: 13px; font-weight: 600; }

.scene-block { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r); padding: 18px 22px; margin-bottom: 16px; box-shadow: var(--shadow); }
.slug-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 8px; }
.slug-no { flex: none; padding: 5px 12px; border-radius: 7px; background: var(--brand); color: #fff; font-weight: 700; font-size: 14px; }
.slug-text { flex: 1; display: flex; align-items: baseline; gap: 10px; cursor: pointer; font-size: 16px; padding: 4px 10px; border-radius: 6px; }
.slug-text:hover { background: var(--brand-soft); }
.slug-text .se-time { color: var(--text-2); }
.slug-text b { color: var(--brand); font-weight: 800; }

.synopsis { color: var(--text-2); font-style: italic; font-size: 14px; cursor: pointer; padding: 4px 10px; border-radius: 6px; margin: 0 0 12px; }
.synopsis:hover { background: var(--brand-soft); }
.syn-edit { display: flex; gap: 8px; margin-bottom: 12px; }

.ln-wrap { position: relative; }
.ln { position: relative; cursor: text; padding: 7px 12px; border-radius: 6px; transition: background .12s; }
.ln:hover { background: var(--brand-soft); }
.edit-hint { opacity: 0; font-size: 12px; color: var(--brand); transition: opacity .12s; }
.slug-text:hover .edit-hint, .synopsis:hover .edit-hint { opacity: .7; margin-left: 6px; }
.ln:hover .edit-hint { opacity: .7; }
.ln .edit-hint { position: absolute; right: 10px; top: 7px; }

.ln-action .action { margin: 0; line-height: 1.9; color: var(--text); }
.ln-action .tri { color: var(--brand); font-weight: 700; margin-right: 4px; }
.ln-dia, .ln-vo { padding-left: 60px; }
.cue { font-weight: 700; letter-spacing: .5px; color: var(--text); }
.cue .vo { color: var(--brand); font-weight: 600; }
.cue .paren { font-weight: 400; color: var(--text-3); font-size: 13px; }
.cue-text { margin: 2px 0 0; line-height: 1.85; }
.ln-vo .cue-text { color: #8a6a2a; }
.ln-trans .trans { margin: 0; text-align: center; font-weight: 700; letter-spacing: 2px; color: var(--text-2); }

.el-edit { background: var(--surface-2); border: 1px solid var(--brand); border-radius: var(--r-sm); padding: 12px; margin: 6px 0; }
.el-edit-top { display: flex; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.el-edit textarea { min-height: 60px; }
.el-edit-foot { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; }

.add-row { display: flex; gap: 8px; align-items: center; margin-top: 12px; padding-top: 12px; border-top: 1px dashed var(--border); font-size: 13px; color: var(--text-3); flex-wrap: wrap; }

.script-out { margin-top: 18px; padding: 18px 20px; }
.script-head { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.script-head h3 { flex: 1; margin: 0; font-size: 16px; }
.yaml-valid { font-size: 13px; color: var(--ok, #2e9e5b); font-weight: 600; }
.yaml-valid.bad { color: var(--bad); }
.problems { color: var(--bad); font-size: 13px; }
.script-paper {
  background: #fffdf8; color: var(--text); border: 1px solid var(--border);
  padding: 24px 28px; border-radius: var(--r-sm); overflow: auto; max-height: 56vh;
  font-family: "Songti SC", "SimSun", serif; font-size: 15px; line-height: 2;
  white-space: pre-wrap; word-break: break-word;
}

@media (max-width: 860px) {
  .editor.split { grid-template-columns: 1fr; }
  .orig { position: static; max-height: 300px; }
  .ln-dia, .ln-vo { padding-left: 24px; }
}
</style>
