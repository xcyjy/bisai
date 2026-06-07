<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listProjects, deleteProject } from '../api.js'

const router = useRouter()
const works = ref([])
const loading = ref(true)
const errorMsg = ref('')

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

function open(id) {
  router.push({ name: 'workspace', params: { id } })
}

async function remove(id) {
  if (!confirm('确定删除这个作品？不可恢复。')) return
  await deleteProject(id)
  await load()
}

onMounted(load)
</script>

<template>
  <section>
    <div class="meta-row" style="justify-content: space-between; align-items: center;">
      <h2 style="margin:0;">我的作品</h2>
      <button class="primary" @click="router.push({ name: 'workspace' })">+ 新建转换</button>
    </div>

    <p v-if="errorMsg" class="error">{{ errorMsg }}</p>
    <p v-if="loading" class="empty">加载中…</p>
    <p v-else-if="!works.length" class="empty">还没有作品，点「+ 新建转换」把一篇小说转成剧本吧。</p>

    <div class="works-grid">
      <div v-for="w in works" :key="w.id" class="work-card" @click="open(w.id)">
        <h3>{{ w.title }}</h3>
        <div class="meta">{{ w.author || '佚名' }} · {{ w.scenes }} 场 · {{ w.char_count }} 字</div>
        <div class="card-foot">
          <span class="meta">{{ new Date(w.updated_at).toLocaleString() }}</span>
          <button class="del" @click.stop="remove(w.id)">删除</button>
        </div>
      </div>
    </div>
  </section>
</template>
