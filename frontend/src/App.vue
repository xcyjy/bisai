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
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar-inner">
        <h1 class="brand" @click="router.push('/')">🎬 小说转剧本</h1>
        <nav v-if="auth.isLoggedIn" class="nav">
          <router-link to="/works">我的作品</router-link>
          <router-link to="/workspace">+ 新建</router-link>
          <span class="divider"></span>
          <router-link to="/pricing" class="credits" title="剩余 AI 精修次数">⚡ {{ auth.credits }}</router-link>
          <span class="user">{{ auth.user?.nickname || auth.user?.email }}</span>
          <span class="plan" :class="{ pro: auth.isMember }">{{ auth.isMember ? 'PRO' : 'FREE' }}</span>
          <button class="btn ghost small" @click="logout">退出</button>
        </nav>
        <nav v-else class="nav">
          <button class="btn primary small" @click="router.push({ name: 'login' })">登录 / 注册</button>
        </nav>
      </div>
    </header>

    <main class="app">
      <router-view />
    </main>
  </div>
</template>

<style>
:root {
  --bg: #f3eee3;
  --surface: #ffffff;
  --surface-2: #faf6ee;
  --border: #ebe1cd;
  --border-strong: #ddcfb0;
  --text: #2a2622;
  --text-2: #6f6450;
  --text-3: #a99c83;
  --brand: #c0612f;
  --brand-d: #a44e22;
  --brand-soft: rgba(192, 97, 47, .10);
  --ok: #2e7d32;
  --bad: #c0392b;
  --r: 12px;
  --r-sm: 8px;
  --shadow: 0 1px 2px rgba(90, 60, 20, .05), 0 6px 18px rgba(90, 60, 20, .06);
  --shadow-lg: 0 14px 36px rgba(120, 80, 30, .14);
}

* { box-sizing: border-box; }
html, body { margin: 0; }
body {
  font-family: system-ui, -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
  background: var(--bg);
  color: var(--text);
  font-size: 15px;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}

/* ---- 布局 ---- */
.app-shell { min-height: 100vh; }
.app { max-width: 1160px; margin: 0 auto; padding: 24px 20px 64px; }

/* ---- 顶栏 ---- */
.topbar {
  position: sticky; top: 0; z-index: 50;
  background: rgba(248, 244, 236, .85);
  backdrop-filter: saturate(1.4) blur(10px);
  border-bottom: 1px solid var(--border);
}
.topbar-inner {
  max-width: 1160px; margin: 0 auto; padding: 10px 20px;
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;
}
.brand { font-size: 19px; font-weight: 800; margin: 0; cursor: pointer; letter-spacing: .3px; }
.nav { display: flex; gap: 8px; align-items: center; font-size: 14px; }
.nav a { color: var(--text-2); text-decoration: none; padding: 6px 12px; border-radius: 999px; transition: background .15s, color .15s; }
.nav a:hover { background: var(--brand-soft); color: var(--brand); }
.nav a.router-link-active { background: var(--brand); color: #fff; font-weight: 600; }
.nav .divider { width: 1px; height: 18px; background: var(--border-strong); margin: 0 4px; }
.nav .user { font-weight: 600; }
.nav .plan { font-size: 12px; color: var(--text-3); background: var(--surface-2); border: 1px solid var(--border); padding: 3px 9px; border-radius: 999px; letter-spacing: .5px; }
.nav .plan.pro { color: #fff; background: linear-gradient(90deg, var(--brand), #e0894f); border-color: transparent; font-weight: 700; }
.nav .credits { color: var(--brand); background: var(--brand-soft); padding: 3px 10px; border-radius: 999px; font-weight: 700; font-size: 13px; text-decoration: none; }
.nav .credits:hover { background: var(--brand); color: #fff; }

/* ---- 按钮 ---- */
.btn, button.primary, button.ghost {
  cursor: pointer; border: 1px solid transparent; border-radius: var(--r-sm);
  padding: 9px 16px; font-size: 14px; font-weight: 600; font-family: inherit;
  transition: transform .12s, box-shadow .15s, background .15s, border-color .15s;
  display: inline-flex; align-items: center; gap: 6px; line-height: 1;
}
.btn.primary, button.primary { background: var(--brand); color: #fff; box-shadow: 0 4px 12px rgba(192, 97, 47, .22); }
.btn.primary:hover, button.primary:hover { background: var(--brand-d); transform: translateY(-1px); box-shadow: 0 8px 18px rgba(192, 97, 47, .3); }
.btn.primary:disabled, button.primary:disabled { opacity: .55; cursor: not-allowed; transform: none; box-shadow: none; }
.btn.ghost, button.ghost { background: var(--surface); color: var(--text-2); border-color: var(--border-strong); }
.btn.ghost:hover, button.ghost:hover { background: var(--surface-2); border-color: var(--brand); color: var(--brand); }
.btn.small, button.small { padding: 6px 12px; font-size: 13px; }
.btn.big, .big { padding: 13px 24px; font-size: 16px; border-radius: 10px; }
.btn.del, button.del { background: transparent; border: none; color: var(--text-3); padding: 4px 8px; font-weight: 600; }
.btn.del:hover, button.del:hover { color: var(--bad); }

/* ---- 表单控件 ---- */
input, textarea, select {
  font-family: inherit; font-size: 14px; color: var(--text);
  background: var(--surface); border: 1px solid var(--border-strong); border-radius: var(--r-sm);
  padding: 9px 11px; transition: border-color .15s, box-shadow .15s; outline: none;
}
input:focus, textarea:focus, select:focus { border-color: var(--brand); box-shadow: 0 0 0 3px var(--brand-soft); }
input::placeholder, textarea::placeholder { color: var(--text-3); }
textarea { width: 100%; min-height: 120px; resize: vertical; line-height: 1.7; }

/* ---- 通用 ---- */
.error { color: var(--bad); font-size: 14px; }
.empty { color: var(--text-3); margin-top: 40px; text-align: center; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r); box-shadow: var(--shadow); }

/* ---- 作品列表（MyWorks 共用） ---- */
.works-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 16px; margin-top: 18px; }
.work-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r); padding: 18px; cursor: pointer; box-shadow: var(--shadow); transition: transform .15s, box-shadow .15s; }
.work-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-lg); }
.work-card h3 { margin: 0 0 8px; font-size: 17px; }
.work-card .meta { font-size: 12px; color: var(--text-3); }
.work-card .card-foot { display: flex; justify-content: space-between; align-items: center; margin-top: 14px; }

/* ---- 登录页 ---- */
.auth-wrap { max-width: 400px; margin: 7vh auto; background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 32px; box-shadow: var(--shadow-lg); }
.auth-wrap h2 { margin: 0 0 20px; font-size: 22px; }
.auth-wrap label { display: block; font-size: 13px; color: var(--text-2); margin: 12px 0 5px; font-weight: 600; }
.auth-wrap input { width: 100%; }
.auth-wrap .primary { width: 100%; justify-content: center; margin-top: 20px; padding: 11px; }
.auth-switch { margin-top: 16px; font-size: 14px; text-align: center; color: var(--text-2); }
.auth-switch a { color: var(--brand); cursor: pointer; font-weight: 600; }
</style>
