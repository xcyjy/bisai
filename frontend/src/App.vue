<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth.js'

const auth = useAuthStore()
const router = useRouter()

onMounted(() => auth.loadMe())

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="app">
    <header class="topbar">
      <h1 @click="router.push('/')" style="cursor:pointer">🎬 AI 小说转剧本工具</h1>
      <nav v-if="auth.isLoggedIn" class="nav">
        <router-link to="/works">我的作品</router-link>
        <router-link to="/workspace">+ 新建</router-link>
        <span class="user">{{ auth.user?.nickname || auth.user?.email }}</span>
        <span class="plan">{{ auth.user?.plan || 'free' }}</span>
        <button class="ghost small" @click="logout">退出</button>
      </nav>
      <nav v-else class="nav">
        <button class="primary small" @click="router.push({ name: 'login' })">登录 / 注册</button>
      </nav>
    </header>

    <router-view />
  </div>
</template>

<style>
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, "Microsoft YaHei", sans-serif; background: #f4f1ea; color: #2b2b2b; }
.app { max-width: 1200px; margin: 0 auto; padding: 16px; }
.topbar { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.topbar h1 { font-size: 22px; margin: 8px 0; }
.nav { display: flex; gap: 12px; align-items: center; font-size: 14px; }
.nav a { color: #8a6f4a; text-decoration: none; padding: 4px 8px; border-radius: 6px; }
.nav a.router-link-active { background: #efe7d6; color: #6b5436; font-weight: 600; }
.nav .user { color: #2b2b2b; font-weight: 600; }
.nav .plan { font-size: 12px; color: #8a6f4a; background: #efe7d6; padding: 2px 8px; border-radius: 10px; }
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

/* 登录页 */
.auth-wrap { max-width: 380px; margin: 8vh auto; background: #fff; border: 1px solid #e3d8bf; border-radius: 12px; padding: 28px; }
.auth-wrap h2 { margin: 0 0 18px; font-size: 20px; }
.auth-wrap label { display: block; font-size: 13px; color: #6b5436; margin: 10px 0 4px; }
.auth-wrap input { width: 100%; padding: 9px; border: 1px solid #d8ccae; border-radius: 6px; }
.auth-wrap .primary { width: 100%; margin-top: 18px; padding: 10px; }
.auth-switch { margin-top: 14px; font-size: 13px; text-align: center; color: #8a6f4a; }
.auth-switch a { color: #c0612f; cursor: pointer; }

/* 作品列表 */
.works-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 14px; margin-top: 16px; }
.work-card { background: #fff; border: 1px solid #e3d8bf; border-radius: 10px; padding: 14px; cursor: pointer; transition: box-shadow .15s; }
.work-card:hover { box-shadow: 0 3px 10px rgba(0,0,0,.08); }
.work-card h3 { margin: 0 0 6px; font-size: 16px; }
.work-card .meta { font-size: 12px; color: #8a7a5a; }
.work-card .card-foot { display: flex; justify-content: space-between; align-items: center; margin-top: 10px; }
.empty { color: #8a7a5a; margin-top: 24px; text-align: center; }

@media (max-width: 860px) { .panes { grid-template-columns: 1fr; } }
</style>
