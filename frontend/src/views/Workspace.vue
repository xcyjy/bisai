<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  createProject, getProject, saveScreenplay, sampleNovel, health, getJob,
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
const engineChoice = ref('offline')   // offline | ai
const loading = ref(false)
const saving = ref(false)
const errorMsg = ref('')
const engine = ref('')

const screenplay = ref(null)
const stats = ref(null)
const compare = ref(false)
const editing = ref(null)
const savedFlash = ref(0)
const showScript = ref(false)
const copied = ref(false)

// 异步转换任务
const converting = ref(false)
const job = ref(null)             // { status, progress, total }
let pollTimer = null

onMounted(async () => {
  try { engine.value = (await health()).engine } catch { engine.value = '后端未连接' }
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

const canUseAI = computed(() => auth.credits >= 1)

// 新建：提交转换 -> 后台任务
async function doConvert() {
  errorMsg.value = ''
  if (novelText.value.trim().length < 50) {
    errorMsg.value = '请先粘贴或载入小说文本（建议 ≥3 章）。'
    return
  }
  loading.value = true
  try {
    const res = await createProject({
      text: novelText.value, title: title.value, author: author.value,
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

const progressPct = computed(() => {
  if (!job.value || !job.value.total) return 8
  return Math.max(8, Math.round((job.value.progress / job.value.total) * 100))
})

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
      <textarea v-model="novelText"
        placeholder="在此粘贴小说全文（建议至少 3 个章节，「第一章」等标题会自动识别）…" />

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
      </div>

      <p v-if="errorMsg" class="error">{{ errorMsg }}</p>
      <div class="new-actions">
        <button class="ghost" @click="loadSample">载入示例小说</button>
        <button class="primary" :disabled="loading" @click="doConvert">
          {{ loading ? '提交中…' : '开始转换 →' }}
        </button>
      </div>
    </section>

    <!-- 转换中：进度 -->
    <section v-if="converting" class="convert-card card">
      <div class="spinner"></div>
      <h3>正在转换…</h3>
      <p class="cv-sub" v-if="job && job.total">已完成 {{ job.progress }} / {{ job.total }} 章</p>
      <p class="cv-sub" v-else>正在解析章节…</p>
      <div class="bar"><div class="bar-fill" :style="{ width: progressPct + '%' }"></div></div>
      <p class="cv-tip">{{ engineChoice === 'ai' ? 'AI 精修中，长篇可能需要一会儿' : '离线快速转换中' }}</p>
    </section>

    <p v-if="loading && !converting" class="empty">加载中…</p>
    <p v-if="errorMsg && !screenplay && !converting" class="error" style="text-align:center;margin-top:16px">{{ errorMsg }}</p>

    <!-- 已转换：剧本视图 -->
    <template v-if="screenplay">
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
          <button class="ghost small" @click="exportScript">导出剧本</button>
          <button class="primary" :disabled="saving" @click="doSave">
            {{ saving ? '保存中…' : '保存修改' }}
          </button>
        </div>
      </div>

      <p v-if="errorMsg" class="error" style="margin:10px 0;">{{ errorMsg }}</p>

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
          <button class="ghost small" @click="exportScript">导出 .txt</button>
        </div>
        <ul v-if="stats && stats.valid === false" class="problems">
          <li v-for="(p, i) in stats.problems" :key="i">⚠ {{ p }}</li>
        </ul>
        <pre class="script-paper">{{ buildScript() }}</pre>
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
@media (max-width: 640px) { .engine-pick { grid-template-columns: 1fr; } }

/* 转换中 */
.convert-card { max-width: 560px; margin: 8vh auto; padding: 36px; text-align: center; }
.convert-card h3 { margin: 14px 0 6px; font-size: 18px; }
.cv-sub { color: var(--text-2); margin: 0 0 16px; }
.cv-tip { color: var(--text-3); font-size: 12px; margin: 12px 0 0; }
.spinner { width: 38px; height: 38px; border: 3px solid var(--border); border-top-color: var(--brand); border-radius: 50%; margin: 0 auto; animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.bar { height: 8px; background: var(--surface-2); border-radius: 999px; overflow: hidden; }
.bar-fill { height: 100%; background: linear-gradient(90deg, var(--brand), #e0894f); border-radius: 999px; transition: width .4s; }

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
