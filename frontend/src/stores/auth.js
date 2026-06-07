import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as api from '../api.js'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref(api.getToken())
  const isLoggedIn = computed(() => !!token.value)

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
      logout()
    }
  }
  function logout() {
    user.value = null
    token.value = ''
    api.setToken('')
  }

  return { user, token, isLoggedIn, login, register, loadMe, logout }
})
