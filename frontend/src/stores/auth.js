import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as api from '../api.js'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref(api.getToken())
  const isLoggedIn = computed(() => !!token.value)
  const credits = computed(() => user.value?.credits ?? 0)
  const isMember = computed(() => user.value?.plan === 'pro')

  function _setSession(resp) {
    token.value = resp.access_token
    user.value = resp.user
    api.setToken(resp.access_token)
  }

  async function login(payload) {
    _setSession(await api.login(payload))
  }
  async function register(payload) {
    _setSession(await api.register(payload))
  }
  async function loadMe() {
    if (!token.value) return
    try {
      user.value = await api.fetchMe()
    } catch {
      // 不要因网络抖动/后端重启就登出（否则用户被无故弹回登录）。
      // 真正的 401 已由 api.request 的全局处理器清 token 并跳转登录，这里只需保留会话。
    }
  }
  // 购买 / 转换后刷新用户态（积分、会员）
  async function refresh() {
    if (!token.value) return
    try {
      user.value = await api.fetchMe()
    } catch { /* 忽略 */ }
  }
  function logout() {
    user.value = null
    token.value = ''
    api.setToken('')
  }

  return { user, token, isLoggedIn, credits, isMember, login, register, loadMe, refresh, logout }
})
