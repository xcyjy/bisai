import { createRouter, createWebHistory } from 'vue-router'
import { getToken, setToken } from '../api.js'

const routes = [
  { path: '/', name: 'landing', component: () => import('../views/Landing.vue') },
  { path: '/login', name: 'login', component: () => import('../views/Login.vue') },
  {
    path: '/works',
    name: 'works',
    component: () => import('../views/MyWorks.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/workspace/:id?',
    name: 'workspace',
    component: () => import('../views/Workspace.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/pricing',
    name: 'pricing',
    component: () => import('../views/Pricing.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/account',
    name: 'account',
    component: () => import('../views/Account.vue'),
    meta: { requiresAuth: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫：未登录访问受保护页 → 跳登录
router.beforeEach((to) => {
  if (to.meta.requiresAuth && !getToken()) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && getToken()) {
    return { name: 'works' }
  }
})

// api.js 抛出的 401 事件 → 清登录态并跳登录
window.addEventListener('n2s-unauthorized', () => {
  setToken('')
  if (router.currentRoute.value.name !== 'login') {
    router.push({ name: 'login' })
  }
})

export default router
