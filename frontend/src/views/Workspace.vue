<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  createProject, getProject, saveScreenplay, sampleNovel, health,
} from '../api.js'

const route = useRoute()
const router = useRouter()

const ELEMENT_TYPES = [
  { value: 'action', label: '动作' },
  { value: 'dialogue', label: '对白' },
  { value: 'voiceover', label: '旁白' },
  { value: 'transition', label: '转场' },
]

const projectId = ref(route.params.id ? Number(route.params.id) : null)
const novelText = ref('')
const title = ref('未命名剧本')
const author = ref('')
const loading = ref(false)
const saving = ref(false)
const errorMsg = ref('')
const engine = ref('')

const screenplay = ref(null)
const stats = ref(null)
const yamlText = ref('')
const showYaml = ref(false)

onMounted(async () => {
  try { engine.value = (await health()).engine } catch { engine.value = '后端未连接' }
  if (projectId.value) await loadProject(projectId.value)
})

watch(() => route.params.id, async (id) => {
  projectId.value = id ? Number(id) : null
  if (projectId.value) await loadProject(projectId.value)
  else resetNew()
})

function resetNew() {
  novelText.value = ''; title.value = '未命名剧本'; author.value = ''
  screenplay.value = null; stats.value = null; yamlText.value = ''; showYaml.value = false
}

async function loadProject(id) {
  loading.value = true
  try {
    const res = await getProject(id)
    title.value = res.title
    author.value = res.author
    novelText.value = res.source_text
    screenplay.value = res.screenplay
    yamlText.value = res.yaml
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

// 新建：转换并保存为一个作品
async function doConvertAndSave() {
  errorMsg.value = ''
  if (novelText.value.trim().length < 50) {
    errorMsg.value = '请先粘贴或载入小说文本（建议 ≥3 章）。'
    return
  }
  loading.value = true
  try {
    const res = await createProject({
      text: novelText.value, title: title.value, author: author.value,
    })
    projectId.value = res.project_id
    screenplay.value = res.screenplay
    stats.value = res.stats
    yamlText.value = res.yaml
    engine.value = res.stats.engine
    // 把地址换成带 id 的，刷新不丢
    router.replace({ name: 'workspace', params: { id: res.project_id } })
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

const originalParas = computed(() =>
  novelText.value.split(/\n+/).map((s) => s.trim()).filter(Boolean)
)

function addElement(scene) { scene.elements.push({ type: 'action', text: '' }) }
function removeElement(scene, idx) { scene.elements.splice(idx, 1) }
function removeScene(idx) {
  screenplay.value.scenes.splice(idx, 1)
  screenplay.value.scenes.forEach((s, i) => (s.scene_number = i + 1))
}

// 保存编辑（生成新版本）
async function doSave() {
  if (!projectId.value) return
  saving.value = true
  errorMsg.value = ''
  try {
    const res = await saveScreenplay(projectId.value, screenplay.value)
    yamlText.value = res.yaml
    stats.value = { ...(stats.value || {}), valid: res.valid, problems: res.problems }
    showYaml.value = true
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    saving.value = false
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
  <div>
    <div style="display:flex; justify-content:flex-end; margin:6px 0;">
      <span class="engine">引擎：{{ engine || '...' }}</span>
    </div>

    <!-- 输入区（仅新建时显示编辑入口；已保存后原文只读在左栏） -->
    <section v-if="!projectId" class="input-bar">
      <div class="meta-row">
        <input v-model="title" placeholder="剧本标题" />
        <input v-model="author" placeholder="作者/改编者" />
        <button class="ghost" @click="loadSample">载入示例小说</button>
        <button class="primary" :disabled="loading" @click="doConvertAndSave">
          {{ loading ? '转换中…' : '转换并保存' }}
        </button>
      </div>
      <textarea
        v-model="novelText"
        placeholder="在此粘贴小说全文（建议至少 3 个章节，章节标题如「第一章」会自动识别）…"
      />
      <p v-if="errorMsg" class="error">{{ errorMsg }}</p>
    </section>

    <p v-if="projectId && errorMsg" class="error">{{ errorMsg }}</p>
    <p v-if="loading && projectId" class="empty">加载中…</p>

    <!-- 统计 + 保存 -->
    <section v-if="screenplay" class="stats">
      <strong>{{ title }}</strong>
      <span v-if="stats">章节 {{ stats.chapters }}</span>
      <span v-if="stats">人物 {{ stats.characters }}</span>
      <span>场次 {{ screenplay.scenes.length }}</span>
      <span v-if="stats && stats.valid !== undefined" :class="stats.valid ? 'ok' : 'bad'">
        校验：{{ stats.valid ? '通过 ✓' : '有 ' + (stats.problems?.length || 0) + ' 个问题' }}
      </span>
      <button class="primary" :disabled="saving" @click="doSave">
        {{ saving ? '保存中…' : '保存修改' }}
      </button>
    </section>

    <!-- 双栏 -->
    <section v-if="screenplay" class="panes">
      <div class="pane">
        <h2>原文</h2>
        <div class="original">
          <p v-for="(p, i) in originalParas" :key="i">{{ p }}</p>
        </div>
      </div>

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
      <ul v-if="stats && stats.valid === false" class="problems">
        <li v-for="(p, i) in stats.problems" :key="i">⚠ {{ p }}</li>
      </ul>
      <pre>{{ yamlText }}</pre>
    </section>
  </div>
</template>
