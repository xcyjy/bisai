// 与后端交互的薄封装。自动携带 JWT；401 时清除登录态并跳登录页。

const TOKEN_KEY = 'n2s_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}
export function setToken(t) {
  if (t) localStorage.setItem(TOKEN_KEY, t)
  else localStorage.removeItem(TOKEN_KEY)
}

// FastAPI 的 detail 可能是字符串，也可能是 422 校验错误数组；统一成可读文本
function formatDetail(detail) {
  if (!detail) return ''
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((e) => e.msg || JSON.stringify(e)).join('；')
  }
  return typeof detail === 'object' ? JSON.stringify(detail) : String(detail)
}

async function request(url, { method = 'GET', body, auth = true } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth && getToken()) headers['Authorization'] = `Bearer ${getToken()}`

  const resp = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (resp.status === 401) {
    setToken('')
    // 交给路由守卫处理跳转
    window.dispatchEvent(new Event('n2s-unauthorized'))
  }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(formatDetail(err.detail) || '请求失败')
  }
  return resp.json()
}

// ---- 认证 ----
export const register = (payload) =>
  request('/api/auth/register', { method: 'POST', body: payload, auth: false })
export const login = (payload) =>
  request('/api/auth/login', { method: 'POST', body: payload, auth: false })
export const fetchMe = () => request('/api/auth/me')

// ---- 作品 ----
export const listProjects = () => request('/api/projects')
export const createProject = (payload) =>
  request('/api/projects', { method: 'POST', body: payload })
export const getProject = (id) => request(`/api/projects/${id}`)
export const saveScreenplay = (id, screenplay) =>
  request(`/api/projects/${id}/screenplay`, { method: 'PUT', body: { screenplay } })
export const deleteProject = (id) =>
  request(`/api/projects/${id}`, { method: 'DELETE' })

// ---- 导出 YAML（把当前/编辑后的剧本重新生成干净 YAML + 校验）----
export const exportYaml = (screenplay) =>
  request('/api/export', { method: 'POST', body: { screenplay }, auth: false })

// ---- 可用模型（中转站 claude 系，分档）----
export const fetchModels = () => request('/api/models', { auth: false })

// ---- 多 Agent 编排（SSE 流式）：实时回调每个 Agent 事件，结束回调 result ----
export async function streamAgents(payload, { onEvent, onPartial, onResult, onError } = {}) {
  let resp
  try {
    const headers = { 'Content-Type': 'application/json' }
    if (getToken()) headers['Authorization'] = `Bearer ${getToken()}`
    resp = await fetch('/api/convert/agents', {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    })
  } catch (e) {
    onError && onError(new Error('无法连接后端'))
    return
  }
  if (!resp.ok || !resp.body) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    onError && onError(new Error(formatDetail(err.detail) || '请求失败'))
    return
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buf.indexOf('\n\n')) !== -1) {
      const chunk = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      let ev = 'message'
      let data = ''
      for (const ln of chunk.split('\n')) {
        if (ln.startsWith('event:')) ev = ln.slice(6).trim()
        else if (ln.startsWith('data:')) data += ln.slice(5).trim()
      }
      if (!data) continue
      let obj
      try { obj = JSON.parse(data) } catch { continue }
      if (ev === 'agent') onEvent && onEvent(obj)
      else if (ev === 'partial') onPartial && onPartial(obj)
      else if (ev === 'result') onResult && onResult(obj)
      else if (ev === 'error') onError && onError(new Error(obj.message || '转换失败'))
    }
  }
}

// ---- 异步任务 ----
export const getJob = (id) => request(`/api/jobs/${id}`)

// ---- 拆集（短剧产线核心） ----
export const makeEpisodes = (id, targetMinutes = 2.5) =>
  request(`/api/projects/${id}/episodes`, { method: 'POST', body: { target_minutes: targetMinutes } })

// ---- 账户 / 计费 ----
export const fetchStats = () => request('/api/me/stats')
export const listPlans = () => request('/api/plans')
export const createOrder = (sku) =>
  request('/api/orders', { method: 'POST', body: { sku } })
export const payOrder = (orderId) =>
  request(`/api/orders/${orderId}/pay`, { method: 'POST', body: {} })

// ---- 其它 ----
export async function health() {
  const resp = await fetch('/api/health')
  return resp.json()
}

const SAMPLE = `旧城轨迹

第一章 归来

　　火车进站时，雨正下得密。沈墨提着一只旧皮箱站在月台上，看着头顶斑驳的站牌。七年了，这座小城的站台还是老样子。
　　他没想到自己真的会回来。当年走得那么决绝，可此刻站在熟悉的雨里，心口还是不争气地发紧。
　　"沈墨？"一个女声从身后传来。他回过头，看见林晚撑着一把藏青色的伞。
　　"是我。"沈墨努力让声音听起来平静，"好久不见。"
　　"七年。"林晚淡淡地说，"你父亲的事，我听说了。节哀。"

第二章 旧宅

　　第二天清晨，沈墨独自回到老宅。院子里那棵石榴树枯了大半。
　　他忽然想起小时候，父亲就坐在那把藤椅上给他讲旧事。那时候他总觉得啰嗦，现在却宁愿再听一万遍。
　　桌上压着一封没寄出的信，信封上是父亲的字迹。他拆开，里面只有一行：城东的老钟楼下，我替你留了样东西。

第三章 钟楼

　　黄昏，城东的老钟楼。夕阳把影子拉得很长。
　　沈墨在石缝里摸索许久，掏出一个锈迹斑斑的铁皮盒子，里面是一沓泛黄的照片和一块旧怀表。
　　"原来你一直都记得。"沈墨的声音哽住了。他终于明白，有些爱从来不说出口，却一直藏在最深的地方。
　　林晚走过来，轻声说："找到了？"
　　"嗯。"沈墨把怀表攥在掌心，"我想，我大概不会再走了。"`

export function sampleNovel() {
  return SAMPLE
}
