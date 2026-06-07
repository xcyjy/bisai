<script setup>
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth.js'

const auth = useAuthStore()
const router = useRouter()

const menuOpen = ref(false)
const menuRef = ref(null)

const displayName = computed(() => auth.user?.nickname || auth.user?.email || '创作者')
const initial = computed(() => displayName.value.trim().charAt(0).toUpperCase())

function onClickOutside(e) {
  if (menuOpen.value && menuRef.value && !menuRef.value.contains(e.target)) {
    menuOpen.value = false
  }
}

onMounted(() => {
  auth.loadMe()
  document.addEventListener('click', onClickOutside)
})
onUnmounted(() => document.removeEventListener('click', onClickOutside))

function go(name) {
  menuOpen.value = false
  router.push({ name })
}

function logout() {
  menuOpen.value = false
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar-inner">
        <div class="brand" @click="router.push('/')" title="墨幕 Inkscene · 笔墨成幕，小说一键成剧">
          <span class="brand-mark">墨</span>
          <span class="brand-words">
            <span class="brand-cn">墨幕</span>
            <span class="brand-en">INKSCENE</span>
          </span>
        </div>
        <nav v-if="auth.isLoggedIn" class="nav">
          <router-link to="/works">我的作品</router-link>
          <router-link to="/workspace">+ 新建</router-link>
          <span class="divider"></span>
          <router-link to="/pricing" class="credits" title="剩余 AI 精修次数">⚡ {{ auth.credits }}</router-link>
          <div class="usermenu" ref="menuRef">
            <button class="user-btn" :class="{ open: menuOpen }" @click="menuOpen = !menuOpen">
              <span class="avatar">{{ initial }}</span>
              <span class="uname">{{ displayName }}</span>
              <span class="plan" :class="{ pro: auth.isMember }">{{ auth.isMember ? 'PRO' : 'FREE' }}</span>
              <span class="caret">▾</span>
            </button>
            <transition name="dd">
              <div v-if="menuOpen" class="dropdown">
                <a @click="go('account')">👤 我的信息</a>
                <a @click="go('pricing')">💳 升级会员</a>
                <div class="dd-divider"></div>
                <a class="danger" @click="logout">⏻ 退出登录</a>
              </div>
            </transition>
          </div>
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
.brand { display: flex; align-items: center; gap: 10px; cursor: pointer; user-select: none; }
.brand-mark {
  width: 32px; height: 32px; flex: none; border-radius: 9px;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, var(--brand), #e0894f);
  color: #fff; font-size: 19px; font-weight: 800;
  font-family: "KaiTi", "STKaiti", "Microsoft YaHei", serif;
  box-shadow: 0 3px 9px rgba(192, 97, 47, .32);
  transition: transform .15s, box-shadow .15s;
}
.brand:hover .brand-mark { transform: translateY(-1px) rotate(-3deg); box-shadow: 0 6px 14px rgba(192, 97, 47, .4); }
.brand-words { display: flex; flex-direction: column; line-height: 1.05; }
.brand-cn { font-size: 18px; font-weight: 800; letter-spacing: 3px; color: var(--text); }
.brand-en { font-size: 9px; font-weight: 600; letter-spacing: 2.5px; color: var(--text-3); }
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

/* ---- 用户菜单（头像 + 下拉） ---- */
.usermenu { position: relative; }
.user-btn {
  display: flex; align-items: center; gap: 8px; cursor: pointer;
  background: var(--surface); border: 1px solid var(--border-strong); border-radius: 999px;
  padding: 4px 10px 4px 4px; font-family: inherit; transition: border-color .15s, box-shadow .15s;
}
.user-btn:hover, .user-btn.open { border-color: var(--brand); box-shadow: 0 0 0 3px var(--brand-soft); }
.user-btn .avatar {
  width: 28px; height: 28px; border-radius: 50%; flex: none;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, var(--brand), #e0894f); color: #fff;
  font-weight: 800; font-size: 14px;
}
.user-btn .uname { font-weight: 600; color: var(--text); font-size: 14px; max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.user-btn .caret { color: var(--text-3); font-size: 11px; }
.dropdown {
  position: absolute; right: 0; top: calc(100% + 8px); min-width: 168px; z-index: 60;
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--r);
  box-shadow: var(--shadow-lg); padding: 6px;
}
.dropdown a {
  display: flex; align-items: center; gap: 8px; padding: 9px 12px; border-radius: var(--r-sm);
  font-size: 14px; color: var(--text-2); cursor: pointer; text-decoration: none;
}
.dropdown a:hover { background: var(--brand-soft); color: var(--brand); }
.dropdown a.danger:hover { background: #fcf0ef; color: var(--bad); }
.dd-divider { height: 1px; background: var(--border); margin: 6px 4px; }
.dd-enter-active, .dd-leave-active { transition: opacity .14s, transform .14s; }
.dd-enter-from, .dd-leave-to { opacity: 0; transform: translateY(-6px); }

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
