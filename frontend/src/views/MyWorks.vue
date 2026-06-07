<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listProjects, deleteProject, createProject, sampleNovel } from '../api.js'
import { useAuthStore } from '../stores/auth.js'

const router = useRouter()
const auth = useAuthStore()
const works = ref([])
const loading = ref(true)
const trying = ref(false)
const errorMsg = ref('')

const search = ref('')
const typeFilter = ref('all')   // all | short_drama | film

const greeting = computed(() => auth.user?.nickname || auth.user?.email || '创作者')
const dramaCount = computed(() => works.value.filter((w) => w.script_type === 'short_drama').length)

const filtered = computed(() => {
  const kw = search.value.trim().toLowerCase()
  return works.value.filter((w) => {
    if (typeFilter.value === 'short_drama' && w.script_type !== 'short_drama') return false
    if (typeFilter.value === 'film' && w.script_type === 'short_drama') return false
    if (kw && !(`${w.title} ${w.author || ''}`.toLowerCase().includes(kw))) return false
    return true
  })
})

async function load() {
  loading.value = true
  try {
    works.value = await listProjects()
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

function open(id) { router.push({ name: 'workspace', params: { id } }) }
function newWork() { router.push({ name: 'workspace' }) }

// 一键体验：内置示例 + 免费快速版，跳进工作台
async function tryExample() {
  errorMsg.value = ''
  trying.value = true
  try {
    const res = await createProject({
      text: sampleNovel(), title: '旧城轨迹（示例）', author: '改编自原创短篇', engine: 'offline',
    })
    router.push({ name: 'workspace', params: { id: res.project_id } })
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    trying.value = false
  }
}

async function remove(id) {
  if (!confirm('确定删除这个作品？不可恢复。')) return
  await deleteProject(id)
  await load()
}

const STATUS = {
  converting: { text: '转换中…', cls: 'badge-run' },
  failed: { text: '转换失败', cls: 'badge-bad' },
  empty: { text: '未生成', cls: 'badge-bad' },
}
const isDrama = (w) => w.script_type === 'short_drama'

onMounted(load)
</script>

<template>
  <section>
    <p v-if="errorMsg" class="error">{{ errorMsg }}</p>
    <p v-if="loading" class="empty">加载中…</p>

    <!-- 空状态：欢迎引导 -->
    <div v-else-if="!works.length" class="onboard">
      <div class="hero">
        <h2>你好，{{ greeting }} 👋</h2>
        <p class="sub">把一篇小说变成规范的剧本，只需三步。还没有作品，先体验一下吧。</p>
        <div class="steps">
          <div class="step"><span class="n">1</span><div><strong>粘贴小说</strong><br />章节标题自动识别</div></div>
          <div class="step"><span class="n">2</span><div><strong>一键转换</strong><br />拆场景、分对白、识别人物</div></div>
          <div class="step"><span class="n">3</span><div><strong>编辑导出</strong><br />在线微调，导出剧本</div></div>
        </div>
        <div class="cta-row">
          <button class="primary big" :disabled="trying" @click="tryExample">
            {{ trying ? '生成中…' : '⚡ 一键体验示例' }}
          </button>
          <button class="ghost big" @click="newWork">✍️ 粘贴我的小说</button>
        </div>
        <p class="tip">「一键体验」用内置示例《旧城轨迹》立即生成作品，可随时删除。</p>
      </div>
    </div>

    <!-- 有作品 -->
    <template v-else>
      <div class="works-head">
        <div>
          <h2 style="margin:0;">我的作品</h2>
          <p class="count">共 {{ works.length }} 部作品<span v-if="dramaCount"> · {{ dramaCount }} 部短剧</span></p>
        </div>
        <button class="primary" @click="newWork">+ 新建转换</button>
      </div>

      <!-- 工具栏 -->
      <div class="toolbar">
        <input v-model="search" class="search" placeholder="🔎 搜索标题 / 作者…" />
        <div class="chips">
          <button :class="{ on: typeFilter === 'all' }" @click="typeFilter = 'all'">全部</button>
          <button :class="{ on: typeFilter === 'film' }" @click="typeFilter = 'film'">影视</button>
          <button :class="{ on: typeFilter === 'short_drama' }" @click="typeFilter = 'short_drama'">短剧</button>
        </div>
      </div>

      <p v-if="!filtered.length" class="empty">没有匹配的作品。</p>
      <div class="works-grid">
        <div v-for="w in filtered" :key="w.id" class="work-card" :class="{ drama: isDrama(w) }" @click="open(w.id)">
          <div class="wc-top">
            <h3>{{ w.title }}</h3>
            <div class="badges">
              <span class="type" :class="isDrama(w) ? 'b-drama' : 'b-film'">{{ isDrama(w) ? '短剧' : '影视' }}</span>
              <span v-if="w.status !== 'ready'" class="badge" :class="STATUS[w.status]?.cls">
                {{ STATUS[w.status]?.text }}
              </span>
            </div>
          </div>
          <div class="meta">
            {{ w.author || '佚名' }} · {{ w.scenes }} 场<span v-if="w.episodes"> · {{ w.episodes }} 集</span> · {{ w.char_count }} 字
          </div>
          <div class="card-foot">
            <span class="meta">{{ new Date(w.updated_at).toLocaleString() }}</span>
            <button class="del" @click.stop="remove(w.id)">删除</button>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.onboard { display: flex; justify-content: center; margin-top: 4vh; }
.hero { max-width: 720px; width: 100%; background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 40px; text-align: center; box-shadow: var(--shadow-lg); }
.hero h2 { margin: 0 0 8px; font-size: 26px; }
.hero .sub { color: var(--text-2); margin: 0 0 26px; }
.steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin: 0 0 28px; text-align: left; }
.step { display: flex; gap: 10px; align-items: flex-start; background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--r); padding: 16px; font-size: 13px; color: var(--text-2); line-height: 1.55; }
.step .n { flex: none; width: 26px; height: 26px; border-radius: 50%; background: var(--brand); color: #fff; font-weight: 700; display: flex; align-items: center; justify-content: center; }
.cta-row { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
.hero .tip { margin: 18px 0 0; font-size: 12px; color: var(--text-3); }

.works-head { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.count { margin: 4px 0 0; font-size: 13px; color: var(--text-3); }

/* 工具栏 */
.toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin: 16px 0 4px; }
.search { width: 280px; max-width: 100%; }
.chips { display: flex; gap: 6px; }
.chips button {
  cursor: pointer; font-family: inherit; font-size: 13px; font-weight: 600;
  padding: 6px 14px; border-radius: 999px; border: 1px solid var(--border-strong);
  background: var(--surface); color: var(--text-2); transition: all .15s;
}
.chips button:hover { border-color: var(--brand); color: var(--brand); }
.chips button.on { background: var(--brand); color: #fff; border-color: transparent; }

/* 卡片增强 */
.work-card { border-left: 3px solid var(--border-strong); }
.work-card.drama { border-left-color: var(--brand); }
.wc-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
.wc-top h3 { margin: 0 0 8px; }
.badges { display: flex; gap: 6px; flex: none; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
.type { font-size: 11px; font-weight: 700; padding: 2px 9px; border-radius: 999px; white-space: nowrap; }
.b-drama { color: var(--brand); background: var(--brand-soft); }
.b-film { color: var(--text-2); background: var(--surface-2); border: 1px solid var(--border); }
.badge { font-size: 11px; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
.badge-run { color: var(--brand); background: var(--brand-soft); }
.badge-bad { color: var(--bad); background: #fcf0ef; }
</style>
