<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { convert, exportYaml, health, sampleNovel } from './api.js'

const ELEMENT_TYPES = [
  { value: 'action', label: '动作' },
  { value: 'dialogue', label: '对白' },
  { value: 'voiceover', label: '旁白' },
  { value: 'transition', label: '转场' },
]

const novelText = ref('')
const title = ref('未命名剧本')
const author = ref('')
const loading = ref(false)
const errorMsg = ref('')
const engine = ref('')

const screenplay = ref(null)   // 可编辑的剧本对象
const stats = ref(null)
const yamlText = ref('')
const showYaml = ref(false)

onMounted(async () => {
  try {
    const h = await health()
    engine.value = h.engine
  } catch (e) {
    engine.value = '后端未连接'
  }
})

function loadSample() {
  novelText.value = sampleNovel()
  title.value = '旧城轨迹'
  author.value = '改编自原创短篇'
}

async function doConvert() {
  errorMsg.value = ''
  if (novelText.value.trim().length < 50) {
    errorMsg.value = '请先粘贴或载入小说文本（建议 ≥3 章）。'
    return
  }
  loading.value = true
  try {
    const res = await convert({
      text: novelText.value,
      title: title.value,
      author: author.value,
    })
    screenplay.value = res.screenplay
    stats.value = res.stats
    yamlText.value = res.yaml
    engine.value = res.stats.engine
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

// 原文按场号粗略对照：直接展示整段原文（MVP 用左栏只读展示）
const originalParas = computed(() =>
  novelText.value.split(/\n+/).map((s) => s.trim()).filter(Boolean)
)

function addElement(scene) {
  scene.elements.push({ type: 'action', text: '' })
}
function removeElement(scene, idx) {
  scene.elements.splice(idx, 1)
}
function removeScene(idx) {
  screenplay.value.scenes.splice(idx, 1)
  // 重新编号
  screenplay.value.scenes.forEach((s, i) => (s.scene_number = i + 1))
}

async function doExport() {
  try {
    const res = await exportYaml(screenplay.value)
    yamlText.value = res.yaml
    stats.value = { ...stats.value, valid: res.valid, problems: res.problems }
    showYaml.value = true
  } catch (e) {
    errorMsg.value = e.message
  }
}

function downloadYaml() {
  const blob = new Blob([yamlText.value], { type: 'text/yaml;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${title.value || 'screenplay'}.yaml`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="app">
    <header class="topbar">
      <h1>🎬 AI 小说转剧本工具</h1>
      <span class="engine">引擎：{{ engine || '...' }}</span>
    </header>

    <!-- 输入区 -->
    <section class="input-bar">
      <div class="meta-row">
        <input v-model="title" placeholder="剧本标题" />
        <input v-model="author" placeholder="作者/改编者" />
        <button class="ghost" @click="loadSample">载入示例小说</button>
        <button class="primary" :disabled="loading" @click="doConvert">
          {{ loading ? '转换中…' : '一键转换' }}
        </button>
      </div>
      <textarea
        v-model="novelText"
        placeholder="在此粘贴小说全文（建议至少 3 个章节，章节标题如「第一章」会自动识别）…"
      />
      <p v-if="errorMsg" class="error">{{ errorMsg }}</p>
    </section>

    <!-- 统计 -->
    <section v-if="stats" class="stats">
      <span>章节 {{ stats.chapters }}</span>
      <span>人物 {{ stats.characters }}</span>
      <span>场次 {{ stats.scenes }}</span>
      <span>对白 {{ stats.dialogues }}</span>
      <span>旁白 {{ stats.voiceovers }}</span>
      <span :class="stats.valid ? 'ok' : 'bad'">
        Schema 校验：{{ stats.valid ? '通过 ✓' : '有 ' + stats.problems.length + ' 个问题' }}
      </span>
      <button class="primary" @click="doExport">导出 / 刷新 YAML</button>
    </section>

    <!-- 双栏 -->
    <section v-if="screenplay" class="panes">
      <!-- 左：原文 -->
      <div class="pane">
        <h2>原文</h2>
        <div class="original">
          <p v-for="(p, i) in originalParas" :key="i">{{ p }}</p>
        </div>
      </div>

      <!-- 右：可编辑剧本 -->
      <div class="pane">
        <h2>剧本（可编辑）</h2>

        <div class="characters">
          <strong>人物表：</strong>
          <span v-for="c in screenplay.characters" :key="c.id" class="chip">{{ c.name }}</span>
        </div>

        <div v-for="(scene, si) in screenplay.scenes" :key="si" class="scene">
          <div class="scene-head">
            <span class="scene-no">场 {{ scene.scene_number }}</span>
            <select v-model="scene.heading.int_ext">
              <option>INT</option><option>EXT</option><option>INT/EXT</option>
            </select>
            <input v-model="scene.heading.location" placeholder="地点" />
            <input v-model="scene.heading.time" placeholder="时间" />
            <button class="del" @click="removeScene(si)">删除场</button>
          </div>

          <input class="synopsis" v-model="scene.synopsis" placeholder="本场梗概" />

          <div v-for="(el, ei) in scene.elements" :key="ei" class="element" :class="el.type">
            <select v-model="el.type">
              <option v-for="t in ELEMENT_TYPES" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
            <input
              v-if="el.type === 'dialogue' || el.type === 'voiceover'"
              class="char" v-model="el.character" placeholder="说话人"
            />
            <input
              v-if="el.type === 'dialogue'"
              class="paren" v-model="el.parenthetical" placeholder="(怎么说)"
            />
            <textarea class="el-text" v-model="el.text" rows="1" placeholder="内容" />
            <button class="del" @click="removeElement(scene, ei)">×</button>
          </div>

          <button class="ghost small" @click="addElement(scene)">+ 添加元素</button>
        </div>
      </div>
    </section>

    <!-- YAML 输出 -->
    <section v-if="showYaml" class="yaml-out">
      <div class="yaml-head">
        <h2>YAML 输出</h2>
        <button class="primary" @click="downloadYaml">下载 .yaml</button>
        <button class="ghost" @click="showYaml = false">收起</button>
      </div>
      <ul v-if="stats && !stats.valid" class="problems">
        <li v-for="(p, i) in stats.problems" :key="i">⚠ {{ p }}</li>
      </ul>
      <pre>{{ yamlText }}</pre>
    </section>
  </div>
</template>

<style>
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, "Microsoft YaHei", sans-serif; background: #f4f1ea; color: #2b2b2b; }
.app { max-width: 1200px; margin: 0 auto; padding: 16px; }
.topbar { display: flex; align-items: center; justify-content: space-between; }
.topbar h1 { font-size: 22px; margin: 8px 0; }
.engine { font-size: 13px; color: #8a6f4a; background: #efe7d6; padding: 4px 10px; border-radius: 12px; }

.input-bar { margin: 12px 0; }
.meta-row { display: flex; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.meta-row input { flex: 1; min-width: 140px; padding: 8px; border: 1px solid #d8ccae; border-radius: 6px; }
textarea { width: 100%; min-height: 120px; padding: 10px; border: 1px solid #d8ccae; border-radius: 6px; font-family: inherit; resize: vertical; }
.error { color: #b00020; }

button { cursor: pointer; border: none; border-radius: 6px; padding: 8px 14px; font-size: 14px; }
button.primary { background: #c0612f; color: #fff; }
button.primary:disabled { opacity: .6; cursor: not-allowed; }
button.ghost { background: #efe7d6; color: #6b5436; }
button.small { padding: 4px 10px; font-size: 13px; }
button.del { background: transparent; color: #b00020; padding: 2px 8px; }

.stats { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; background: #fff; border: 1px solid #e3d8bf; border-radius: 8px; padding: 10px 14px; margin: 10px 0; font-size: 14px; }
.stats .ok { color: #2e7d32; font-weight: 600; }
.stats .bad { color: #b00020; font-weight: 600; }

.panes { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.pane { background: #fff; border: 1px solid #e3d8bf; border-radius: 8px; padding: 14px; max-height: 70vh; overflow: auto; }
.pane h2 { font-size: 16px; margin: 0 0 10px; }
.original p { line-height: 1.7; margin: 0 0 8px; color: #444; }

.characters { margin-bottom: 12px; }
.chip { display: inline-block; background: #efe7d6; color: #6b5436; padding: 2px 8px; border-radius: 10px; margin: 0 4px 4px 0; font-size: 13px; }

.scene { border: 1px solid #ece2cb; border-radius: 8px; padding: 10px; margin-bottom: 12px; }
.scene-head { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin-bottom: 6px; }
.scene-no { font-weight: 700; color: #c0612f; }
.scene-head select, .scene-head input { padding: 4px 6px; border: 1px solid #d8ccae; border-radius: 5px; }
.synopsis { width: 100%; padding: 6px; border: 1px dashed #d8ccae; border-radius: 5px; margin-bottom: 8px; font-style: italic; }

.element { display: flex; gap: 6px; align-items: flex-start; margin-bottom: 6px; }
.element select { padding: 4px; border: 1px solid #d8ccae; border-radius: 5px; }
.element .char { width: 80px; }
.element .paren { width: 90px; }
.element input { padding: 4px 6px; border: 1px solid #d8ccae; border-radius: 5px; }
.el-text { flex: 1; min-height: 32px; }
.element.voiceover .el-text { background: #fff8e8; }
.element.dialogue .el-text { background: #eef6ff; }
.element.transition .el-text { background: #f0f0f0; font-weight: 600; }

.yaml-out { margin-top: 16px; background: #fff; border: 1px solid #e3d8bf; border-radius: 8px; padding: 14px; }
.yaml-head { display: flex; gap: 10px; align-items: center; }
.yaml-head h2 { flex: 1; font-size: 16px; margin: 0; }
.problems { color: #b00020; }
pre { background: #2b2b2b; color: #e8e8e8; padding: 14px; border-radius: 8px; overflow: auto; max-height: 50vh; font-size: 13px; }

@media (max-width: 860px) { .panes { grid-template-columns: 1fr; } }
</style>
