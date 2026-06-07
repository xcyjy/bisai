<script setup>
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const mode = ref('login') // login | register
const email = ref('')
const password = ref('')
const nickname = ref('')
const loading = ref(false)
const errorMsg = ref('')

// 是否已经动过该字段（动过才显示红色错误，避免一进来就满屏标红）
const touched = ref({ email: false, password: false })

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const emailValid = computed(() => EMAIL_RE.test(email.value.trim()))
const passwordValid = computed(() => password.value.length >= 6)
const canSubmit = computed(() => emailValid.value && passwordValid.value && !loading.value)

async function submit() {
  // 提交时把所有字段标记为已动过，确保错误提示露出来
  touched.value.email = true
  touched.value.password = true
  errorMsg.value = ''
  if (!emailValid.value || !passwordValid.value) return

  loading.value = true
  try {
    if (mode.value === 'login') {
      await auth.login({ email: email.value.trim(), password: password.value })
    } else {
      await auth.register({
        email: email.value.trim(),
        password: password.value,
        nickname: nickname.value.trim(),
      })
    }
    router.push(route.query.redirect || { name: 'works' })
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

function switchMode(m) {
  mode.value = m
  errorMsg.value = ''
}
</script>

<template>
  <div class="auth-wrap">
    <h2>{{ mode === 'login' ? '登录' : '注册' }}</h2>

    <label>邮箱</label>
    <input
      v-model="email"
      type="email"
      placeholder="you@example.com"
      :class="{ bad: touched.email && !emailValid }"
      @blur="touched.email = true"
      @keyup.enter="submit"
    />
    <p v-if="touched.email && !emailValid" class="hint bad-text">
      请输入有效邮箱，需包含 @ 和域名，例如 name@demo.com
    </p>
    <p v-else class="hint">用于登录的邮箱，本地测试随便填一个真实格式即可</p>

    <template v-if="mode === 'register'">
      <label>昵称（可选）</label>
      <input v-model="nickname" placeholder="留空将用邮箱前缀" @keyup.enter="submit" />
    </template>

    <label>密码</label>
    <input
      v-model="password"
      type="password"
      placeholder="至少 6 位"
      :class="{ bad: touched.password && !passwordValid }"
      @blur="touched.password = true"
      @keyup.enter="submit"
    />
    <p class="hint" :class="{ 'bad-text': touched.password && !passwordValid, 'ok-text': passwordValid }">
      密码至少 6 位{{ passwordValid ? '（✓ 已满足）' : `（当前 ${password.length} 位）` }}
    </p>

    <p v-if="errorMsg" class="error">{{ errorMsg }}</p>

    <button class="primary" :disabled="!canSubmit" @click="submit">
      {{ loading ? '处理中…' : (mode === 'login' ? '登录' : '注册并登录') }}
    </button>

    <p class="auth-switch">
      <template v-if="mode === 'login'">
        还没有账号？<a @click="switchMode('register')">去注册</a>
      </template>
      <template v-else>
        已有账号？<a @click="switchMode('login')">去登录</a>
      </template>
    </p>
  </div>
</template>

<style scoped>
.hint { font-size: 12px; color: #99876a; margin: 4px 0 2px; }
.hint.bad-text, .bad-text { color: #b00020; }
.hint.ok-text, .ok-text { color: #2e7d32; }
.auth-wrap input.bad { border-color: #b00020; }
</style>
