<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  fetchStats, listPlans, listOrders, createOrder, payOrder, updateProfile,
} from '../api.js'
import { useAuthStore } from '../stores/auth.js'

const router = useRouter()
const auth = useAuthStore()

const stats = ref(null)
const plans = ref([])
const orders = ref([])
const loading = ref(true)
const errorMsg = ref('')
const okMsg = ref('')
const buying = ref('')        // 正在购买的 sku
const paying = ref(0)         // 正在支付的 order id

// 编辑昵称
const editing = ref(false)
const nickInput = ref('')
const saving = ref(false)

const name = computed(() => auth.user?.nickname || auth.user?.email || '创作者')
const initial = computed(() => name.value.trim().charAt(0).toUpperCase())
const isMember = computed(() => stats.value?.is_member ?? auth.isMember)
const joinDate = computed(() =>
  auth.user?.created_at ? new Date(auth.user.created_at).toLocaleDateString() : null)

const isPlan = (p) => p.kind === 'plan'
const fmtDate = (s) => (s ? new Date(s).toLocaleDateString() : '')
const fmtDateTime = (s) => (s ? new Date(s).toLocaleString() : '')

const ORDER_STATUS = {
  paid: { text: '已支付', cls: 'ok' },
  pending: { text: '待支付', cls: 'pending' },
  failed: { text: '已失败', cls: 'bad' },
}

function flash(msg) { okMsg.value = msg; setTimeout(() => { okMsg.value = '' }, 3000) }

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    await auth.refresh()
    const [s, p, o] = await Promise.all([fetchStats(), listPlans(), listOrders()])
    stats.value = s; plans.value = p; orders.value = o
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

function startEdit() {
  nickInput.value = auth.user?.nickname || ''
  editing.value = true
}
async function saveNick() {
  const v = nickInput.value.trim()
  if (!v) return
  saving.value = true; errorMsg.value = ''
  try {
    await updateProfile({ nickname: v })
    await auth.refresh()
    editing.value = false
    flash('资料已更新')
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    saving.value = false
  }
}

async function buy(sku) {
  errorMsg.value = ''; buying.value = sku
  try {
    const order = await createOrder(sku)
    const res = await payOrder(order.order_id)
    await auth.refresh()
    const [s, o] = await Promise.all([fetchStats(), listOrders()])
    stats.value = s; orders.value = o
    flash(`支付成功！当前积分 ${res.credits}，身份 ${res.plan === 'pro' ? 'PRO 会员' : '免费'}。`)
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    buying.value = ''
  }
}

async function payNow(orderId) {
  errorMsg.value = ''; paying.value = orderId
  try {
    await payOrder(orderId)
    await auth.refresh()
    const [s, o] = await Promise.all([fetchStats(), listOrders()])
    stats.value = s; orders.value = o
    flash('支付成功，权益已到账。')
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    paying.value = 0
  }
}

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}

onMounted(load)
</script>

<template>
  <section class="account">
    <p v-if="okMsg" class="toast">{{ okMsg }}</p>
    <p v-if="errorMsg" class="error" style="margin-bottom:12px">{{ errorMsg }}</p>
    <p v-if="loading" class="empty">加载中…</p>

    <div v-else class="grid">
      <!-- 左：个人资料卡 -->
      <aside class="profile-card">
        <div class="avatar-lg">{{ initial }}</div>

        <template v-if="!editing">
          <h2 class="pname">{{ name }}</h2>
          <p class="pmail">{{ auth.user?.email }}</p>
        </template>
        <div v-else class="edit-row">
          <input v-model="nickInput" maxlength="30" placeholder="输入新昵称"
                 @keyup.enter="saveNick" />
          <div class="edit-btns">
            <button class="btn primary small" :disabled="saving" @click="saveNick">
              {{ saving ? '保存中…' : '保存' }}
            </button>
            <button class="btn ghost small" @click="editing = false">取消</button>
          </div>
        </div>

        <div class="plan-badge" :class="{ pro: isMember }">
          {{ isMember ? '✦ PRO 会员' : '免费用户' }}
        </div>
        <p v-if="joinDate" class="join">{{ joinDate }} 加入</p>

        <button v-if="!editing" class="btn ghost edit-btn" @click="startEdit">编辑资料</button>
        <button class="logout" @click="logout">⏻ 退出登录</button>
      </aside>

      <!-- 右：内容区 -->
      <div class="content">
        <!-- 会员渐变大卡 -->
        <div class="member-card" :class="{ free: !isMember }">
          <div class="mc-left">
            <div class="mc-tag">{{ isMember ? '✦ PRO 会员' : '免费用户' }}</div>
            <div class="mc-sub" v-if="isMember && stats?.plan_expires_at">
              {{ fmtDate(stats.plan_expires_at) }} 到期
            </div>
            <div class="mc-sub" v-else>升级解锁 AI 精修引擎</div>
          </div>
          <div class="mc-right">
            <div class="mc-credits"><span class="ico">⚡</span>{{ stats?.credits ?? auth.credits }}</div>
            <div class="mc-credits-label">AI 积分</div>
          </div>
        </div>

        <!-- 统计三卡 -->
        <div class="stat-row">
          <div class="stat-card">
            <div class="sc-label">作品总数</div>
            <div class="sc-val">{{ stats?.project_count ?? 0 }}</div>
          </div>
          <div class="stat-card">
            <div class="sc-label">本月 AI 转换</div>
            <div class="sc-val">{{ stats?.ai_used_this_month ?? 0 }} <span class="u">次</span></div>
          </div>
          <div class="stat-card">
            <div class="sc-label">AI 引擎</div>
            <div class="sc-val" :class="stats?.ai_available ? 'ok' : 'muted'">
              {{ stats?.ai_available ? '✓ 可用' : '未开通' }}
            </div>
          </div>
        </div>

        <!-- 套餐 / 充值 -->
        <h3 class="sec-title">套餐 / 充值</h3>
        <div class="plans">
          <div v-for="p in plans" :key="p.sku" class="plan-c" :class="{ feature: isPlan(p) }">
            <div v-if="isPlan(p)" class="ribbon">推荐</div>
            <h4>{{ p.title }}</h4>
            <div class="price">¥{{ p.amount_cny }}<span v-if="isPlan(p)">/月</span></div>
            <p class="pdesc">{{ p.desc }}</p>
            <button class="btn primary" :disabled="buying === p.sku" @click="buy(p.sku)">
              {{ buying === p.sku ? '处理中…' : (isPlan(p) ? '开通会员' : '购买积分') }}
            </button>
          </div>
        </div>
        <p class="paynote">本地为<b>模拟支付</b>（点击即视为成功）；上线替换为微信/支付宝即可。</p>

        <!-- 订单记录 -->
        <h3 class="sec-title">订单记录</h3>
        <div v-if="!orders.length" class="ord-empty">暂无订单</div>
        <div v-else class="orders">
          <div v-for="o in orders" :key="o.id" class="ord-row">
            <div class="ord-main">
              <div class="ord-title">{{ o.title }}</div>
              <div class="ord-time">{{ fmtDateTime(o.paid_at || o.created_at) }}</div>
            </div>
            <div class="ord-amt">¥{{ o.amount_cny }}</div>
            <div class="ord-status">
              <span class="ost" :class="ORDER_STATUS[o.status]?.cls">
                {{ ORDER_STATUS[o.status]?.text || o.status }}
              </span>
            </div>
            <div class="ord-act">
              <button v-if="o.status === 'pending'" class="btn ghost small"
                      :disabled="paying === o.id" @click="payNow(o.id)">
                {{ paying === o.id ? '支付中…' : '去支付' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.account { max-width: 1000px; margin: 0 auto; }
.toast {
  position: sticky; top: 70px; z-index: 30; text-align: center;
  color: var(--ok); font-weight: 600; background: #f0f8f0; border: 1px solid #bfe0c0;
  border-radius: var(--r-sm); padding: 10px; margin: 0 0 14px;
}
.grid { display: grid; grid-template-columns: 280px 1fr; gap: 22px; align-items: start; }

/* 左：资料卡 */
.profile-card {
  position: sticky; top: 80px;
  background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
  box-shadow: var(--shadow); padding: 28px 22px; text-align: center;
}
.avatar-lg {
  width: 76px; height: 76px; border-radius: 50%; margin: 0 auto 14px;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, var(--brand), #e0894f); color: #fff;
  font-size: 34px; font-weight: 800; box-shadow: var(--shadow);
}
.pname { margin: 0 0 4px; font-size: 20px; }
.pmail { margin: 0 0 14px; font-size: 13px; color: var(--text-3); word-break: break-all; }
.plan-badge {
  display: inline-block; font-size: 13px; font-weight: 700; padding: 4px 14px;
  border-radius: 999px; color: var(--text-2); background: var(--surface-2); border: 1px solid var(--border);
}
.plan-badge.pro { color: #fff; background: linear-gradient(90deg, var(--brand), #e0894f); border-color: transparent; }
.join { margin: 10px 0 0; font-size: 12px; color: var(--text-3); }
.edit-btn { width: 100%; justify-content: center; margin-top: 18px; }
.logout {
  width: 100%; margin-top: 10px; cursor: pointer; font-family: inherit; font-weight: 600;
  background: transparent; border: none; color: var(--text-3); padding: 8px; border-radius: var(--r-sm);
}
.logout:hover { color: var(--bad); background: #fcf0ef; }
.edit-row { margin-bottom: 14px; }
.edit-row input { width: 100%; text-align: center; }
.edit-btns { display: flex; gap: 8px; margin-top: 8px; }
.edit-btns .btn { flex: 1; justify-content: center; }

/* 右：会员渐变卡 */
.member-card {
  display: flex; justify-content: space-between; align-items: center;
  background: linear-gradient(135deg, var(--brand), #e0894f); color: #fff;
  border-radius: 16px; padding: 24px 28px; box-shadow: var(--shadow-lg);
}
.member-card.free { background: linear-gradient(135deg, #8a8175, #b3a890); }
.mc-tag { font-size: 19px; font-weight: 800; }
.mc-sub { font-size: 13px; opacity: .9; margin-top: 4px; }
.mc-right { text-align: right; }
.mc-credits { font-size: 38px; font-weight: 800; line-height: 1; display: flex; align-items: center; gap: 6px; }
.mc-credits .ico { font-size: 26px; }
.mc-credits-label { font-size: 12px; opacity: .9; margin-top: 4px; }

/* 统计三卡 */
.stat-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-top: 16px; }
.stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r); padding: 16px 18px; box-shadow: var(--shadow); }
.sc-label { font-size: 12px; color: var(--text-3); }
.sc-val { font-size: 24px; font-weight: 800; margin-top: 4px; }
.sc-val .u { font-size: 14px; font-weight: 500; color: var(--text-3); }
.sc-val.ok { color: var(--ok); }
.sc-val.muted { color: var(--text-3); }

/* 区块标题 */
.sec-title { font-size: 16px; margin: 30px 0 14px; padding-left: 10px; border-left: 3px solid var(--brand); }

/* 套餐 */
.plans { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px; }
.plan-c { position: relative; background: var(--surface); border: 1px solid var(--border); border-radius: var(--r); padding: 20px; box-shadow: var(--shadow); display: flex; flex-direction: column; }
.plan-c.feature { border: 1.5px solid var(--brand); box-shadow: var(--shadow-lg); }
.ribbon { position: absolute; top: 12px; right: 0; background: var(--brand); color: #fff; font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 999px 0 0 999px; }
.plan-c h4 { margin: 0 0 4px; font-size: 16px; }
.price { font-size: 26px; font-weight: 800; color: var(--brand); margin: 4px 0; }
.price span { font-size: 13px; color: var(--text-3); font-weight: 500; }
.pdesc { color: var(--text-2); font-size: 12px; margin: 0 0 16px; line-height: 1.6; flex: 1; }
.plan-c .btn { justify-content: center; }
.paynote { color: var(--text-3); font-size: 12px; margin-top: 12px; }

/* 订单 */
.ord-empty { color: var(--text-3); font-size: 14px; padding: 16px; text-align: center; background: var(--surface-2); border-radius: var(--r); }
.orders { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r); overflow: hidden; box-shadow: var(--shadow); }
.ord-row { display: grid; grid-template-columns: 1fr auto 90px 92px; align-items: center; gap: 12px; padding: 14px 18px; border-bottom: 1px solid var(--border); }
.ord-row:last-child { border-bottom: none; }
.ord-title { font-weight: 600; font-size: 14px; }
.ord-time { font-size: 12px; color: var(--text-3); margin-top: 2px; }
.ord-amt { font-weight: 700; color: var(--text); }
.ost { font-size: 12px; padding: 3px 10px; border-radius: 999px; white-space: nowrap; }
.ost.ok { color: var(--ok); background: #f0f8f0; }
.ost.pending { color: var(--text-2); background: var(--surface-2); }
.ost.bad { color: var(--bad); background: #fcf0ef; }
.ord-act { text-align: right; }
.ord-act .btn { justify-content: center; }

/* 响应式 */
@media (max-width: 760px) {
  .grid { grid-template-columns: 1fr; }
  .profile-card { position: static; }
  .stat-row { grid-template-columns: 1fr; }
  .ord-row { grid-template-columns: 1fr auto; row-gap: 6px; }
  .ord-status, .ord-act { grid-column: span 1; }
}
</style>
