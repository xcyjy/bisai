<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listPlans, createOrder, payOrder, fetchStats } from '../api.js'
import { useAuthStore } from '../stores/auth.js'

const router = useRouter()
const auth = useAuthStore()

const plans = ref([])
const stats = ref(null)
const buying = ref('')      // 正在购买的 sku
const msg = ref('')
const errorMsg = ref('')

async function load() {
  try {
    plans.value = await listPlans()
    stats.value = await fetchStats()
  } catch (e) {
    errorMsg.value = e.message
  }
}

async function buy(sku) {
  errorMsg.value = ''; msg.value = ''
  buying.value = sku
  try {
    // 1) 下单 -> 2) mock 支付（真实环境这里跳支付平台）
    const order = await createOrder(sku)
    const res = await payOrder(order.order_id)
    await auth.refresh()
    stats.value = await fetchStats()
    msg.value = `支付成功！当前积分 ${res.credits}，身份 ${res.plan === 'pro' ? 'PRO 会员' : '免费'}。`
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    buying.value = ''
  }
}

const isPlan = (p) => p.kind === 'plan'

onMounted(load)
</script>

<template>
  <section class="pricing">
    <header class="ph">
      <h2>升级，解锁 AI 精修</h2>
      <p class="sub">
        免费版用离线规则快速出稿；<b>AI 精修版</b>调用大模型，分场、归属对白、心理转画外音更准。
        1 次 AI 转换 = 1 积分。
      </p>
      <div v-if="stats" class="now">
        当前：<b>{{ stats.is_member ? 'PRO 会员' : '免费用户' }}</b>
        · 剩余 <b>⚡ {{ stats.credits }}</b> 积分
        <span v-if="stats.is_member && stats.plan_expires_at">
          · 到期 {{ new Date(stats.plan_expires_at).toLocaleDateString() }}
        </span>
      </div>
    </header>

    <p v-if="msg" class="ok-banner">{{ msg }}</p>
    <p v-if="errorMsg" class="error" style="text-align:center">{{ errorMsg }}</p>

    <div class="cards">
      <div v-for="p in plans" :key="p.sku" class="plan-card" :class="{ feature: isPlan(p) }">
        <div v-if="isPlan(p)" class="ribbon">推荐</div>
        <h3>{{ p.title }}</h3>
        <div class="price">¥{{ p.amount_cny }}<span v-if="isPlan(p)">/月</span></div>
        <p class="desc">{{ p.desc }}</p>
        <ul class="feat">
          <li>赠 {{ p.grant_credits }} 积分（{{ p.grant_credits }} 次 AI 转换）</li>
          <li v-if="isPlan(p)">作品不限量 · Word 导出</li>
          <li v-else>永久有效 · 叠加到账户</li>
        </ul>
        <button class="primary big" :disabled="buying === p.sku" @click="buy(p.sku)">
          {{ buying === p.sku ? '处理中…' : (isPlan(p) ? '开通会员' : '购买积分') }}
        </button>
      </div>
    </div>

    <p class="note">
      这是本地 <b>模拟支付</b>（点击即视为支付成功）。上线时把这一步替换为微信/支付宝即可，业务逻辑不变。
    </p>
    <div style="text-align:center;margin-top:12px">
      <button class="ghost" @click="router.push({ name: 'works' })">← 返回我的作品</button>
    </div>
  </section>
</template>

<style scoped>
.pricing { max-width: 980px; margin: 0 auto; }
.ph { text-align: center; margin: 2vh 0 24px; }
.ph h2 { font-size: 26px; margin: 0 0 8px; }
.ph .sub { color: var(--text-2); max-width: 640px; margin: 0 auto; }
.now { margin-top: 14px; font-size: 14px; color: var(--text-2); background: var(--surface-2); display: inline-block; padding: 8px 16px; border-radius: 999px; border: 1px solid var(--border); }
.ok-banner { text-align: center; color: var(--ok); font-weight: 600; background: #f0f8f0; border: 1px solid #bfe0c0; border-radius: var(--r-sm); padding: 10px; }

.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 18px; margin-top: 8px; }
.plan-card { position: relative; background: var(--surface); border: 1px solid var(--border); border-radius: var(--r); padding: 24px; box-shadow: var(--shadow); display: flex; flex-direction: column; }
.plan-card.feature { border-color: var(--brand); box-shadow: var(--shadow-lg); }
.ribbon { position: absolute; top: 14px; right: -1px; background: var(--brand); color: #fff; font-size: 12px; font-weight: 700; padding: 3px 12px; border-radius: 999px 0 0 999px; }
.plan-card h3 { margin: 0 0 6px; font-size: 18px; }
.price { font-size: 30px; font-weight: 800; color: var(--brand); margin: 6px 0; }
.price span { font-size: 14px; color: var(--text-3); font-weight: 500; }
.desc { color: var(--text-2); font-size: 13px; margin: 0 0 12px; }
.feat { list-style: none; padding: 0; margin: 0 0 18px; font-size: 13px; color: var(--text-2); }
.feat li { padding: 5px 0 5px 22px; position: relative; }
.feat li::before { content: '✓'; position: absolute; left: 0; color: var(--ok); font-weight: 700; }
.plan-card .primary { margin-top: auto; justify-content: center; }
.note { text-align: center; color: var(--text-3); font-size: 13px; margin-top: 24px; }
</style>
