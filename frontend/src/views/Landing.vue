<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const router = useRouter()
const auth = useAuthStore()

// 轮播标语
const words = ['爆款短剧', '竖屏微短剧', '分集脚本', '可拍剧本']
const wordIdx = ref(0)
let timer = null

// 演示动画：剧本元素逐条浮现，循环播放
const demoEls = [
  { type: 'action', text: '火车进站时，雨正下得密。沈墨提着旧皮箱站在月台上。' },
  { type: 'voiceover', who: '沈墨', text: '他没想到自己真的会回来。' },
  { type: 'dialogue', who: '林晚', text: '沈墨？好久不见。' },
  { type: 'dialogue', who: '沈墨', text: '是我。' },
]
const shown = ref(0)
let demoTimer = null

onMounted(() => {
  timer = setInterval(() => { wordIdx.value = (wordIdx.value + 1) % words.length }, 2200)
  demoTimer = setInterval(() => {
    shown.value = shown.value >= demoEls.length ? 0 : shown.value + 1
  }, 1100)
})
onUnmounted(() => { clearInterval(timer); clearInterval(demoTimer) })

function go() {
  router.push(auth.isLoggedIn ? { name: 'works' } : { name: 'login' })
}
const typeLabel = { action: '动作', voiceover: '画外音', dialogue: '对白' }
</script>

<template>
  <div class="landing">
    <!-- 动态背景光斑 -->
    <div class="blob b1"></div>
    <div class="blob b2"></div>
    <div class="blob b3"></div>

    <!-- 主视觉 -->
    <section class="hero">
      <div class="hero-left">
        <div class="badge">✨ AI 驱动 · 一键成稿</div>
        <h1>
          把你的小说<br />
          一键变成
          <span class="rotator">
            <transition name="flip" mode="out-in">
              <span :key="wordIdx" class="rot-word">{{ words[wordIdx] }}</span>
            </transition>
          </span>
        </h1>
        <p class="sub">
          粘贴小说原文，AI 自动分章、切场、识别对白与心理独白，
          一键拆成带钩子/扣子的分集短剧，还能在线编辑、导出标准 YAML。
        </p>
        <div class="cta">
          <button class="primary big" @click="go">
            {{ auth.isLoggedIn ? '进入我的作品 →' : '免费开始创作 →' }}
          </button>
          <button v-if="!auth.isLoggedIn" class="ghost big" @click="router.push({ name: 'login' })">
            登录
          </button>
        </div>
        <div class="trust">
          <span>无需配置即可体验</span><i>·</i><span>离线引擎零成本</span><i>·</i><span>导出标准 YAML</span>
        </div>
      </div>

      <!-- 演示卡片：原文 → 剧本 -->
      <div class="hero-right">
        <div class="demo-card">
          <div class="demo-col src">
            <div class="col-tag">小说原文</div>
            <p>火车进站时，雨正下得密。沈墨提着旧皮箱站在月台上。<em>他没想到自己真的会回来。</em>"沈墨？"林晚撑着伞走来。"是我。"</p>
          </div>
          <div class="demo-arrow">→</div>
          <div class="demo-col out">
            <div class="col-tag">结构化剧本</div>
            <transition-group name="rise" tag="div">
              <div
                v-for="(el, i) in demoEls.slice(0, shown)"
                :key="el.text"
                class="chip-el"
                :class="el.type"
              >
                <span class="el-type">{{ typeLabel[el.type] }}</span>
                <b v-if="el.who">{{ el.who }}：</b>{{ el.text }}
              </div>
            </transition-group>
          </div>
        </div>
      </div>
    </section>

    <!-- 三步流程 -->
    <section class="steps">
      <div class="step"><div class="num">1</div><h3>粘贴 / 上传小说</h3><p>支持 ≥3 章长文，章节标题自动识别。</p></div>
      <div class="step"><div class="num">2</div><h3>AI 一键转换</h3><p>分章 → 切场 → 对白归属 → 心理转旁白。</p></div>
      <div class="step"><div class="num">3</div><h3>在线编辑导出</h3><p>双栏对照微调，导出标准剧本 YAML。</p></div>
    </section>

    <!-- 特性卡片 -->
    <section class="features">
      <div class="feat" style="--d:0s"><div class="ic">🎬</div><h3>短剧分集产线</h3><p>自动拆集，每集带开场钩子、集尾扣子与时长体检，贴合竖屏短剧节奏。</p></div>
      <div class="feat" style="--d:.1s"><div class="ic">🧠</div><h3>会"看懂"心理戏</h3><p>"他没想到…"等心理描写自动转为画外音，Show don't tell。</p></div>
      <div class="feat" style="--d:.2s"><div class="ic">✏️</div><h3>双栏在线编辑</h3><p>左原文右剧本，逐场逐句可改，所见即所得。</p></div>
      <div class="feat" style="--d:.3s"><div class="ic">⚡</div><h3>双引擎兜底</h3><p>有网用 Claude 高质量，无网自动降级离线规则，永远跑得通。</p></div>
    </section>

    <!-- 底部召唤 -->
    <section class="bottom-cta">
      <h2>把抽屉里的小说，变成能拍的爆款短剧</h2>
      <button class="primary big" @click="go">
        {{ auth.isLoggedIn ? '进入我的作品 →' : '立即免费创作 →' }}
      </button>
    </section>
  </div>
</template>

<style scoped>
.landing { position: relative; overflow: hidden; }

/* ---- 动态背景光斑 ---- */
.blob { position: absolute; border-radius: 50%; filter: blur(60px); opacity: .55; z-index: 0; pointer-events: none; }
.b1 { width: 420px; height: 420px; background: #f0a868; top: -120px; left: -80px; animation: float1 14s ease-in-out infinite; }
.b2 { width: 380px; height: 380px; background: #c0612f; top: 120px; right: -100px; animation: float2 18s ease-in-out infinite; }
.b3 { width: 300px; height: 300px; background: #e7c79a; bottom: -120px; left: 35%; animation: float1 16s ease-in-out infinite reverse; }
@keyframes float1 { 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(40px,30px) scale(1.1); } }
@keyframes float2 { 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(-30px,40px) scale(1.08); } }

/* ---- 主视觉 ---- */
.hero { position: relative; z-index: 1; display: grid; grid-template-columns: 1.1fr 1fr; gap: 40px; align-items: center; padding: 48px 0 36px; }
.badge { display: inline-block; background: rgba(192,97,47,.12); color: #c0612f; padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: 600; animation: fadeUp .6s both; }
.hero h1 { font-size: 44px; line-height: 1.25; margin: 16px 0; animation: fadeUp .6s .05s both; }
.rotator { display: inline-block; }
.rot-word { display: inline-block; background: linear-gradient(90deg,#c0612f,#f0a868); -webkit-background-clip: text; background-clip: text; color: transparent; }
.sub { font-size: 17px; color: #6b5b43; line-height: 1.8; max-width: 520px; animation: fadeUp .6s .1s both; }
.cta { display: flex; gap: 12px; margin: 26px 0 14px; animation: fadeUp .6s .15s both; }
.big { padding: 14px 26px; font-size: 16px; border-radius: 10px; }
.primary.big { box-shadow: 0 8px 20px rgba(192,97,47,.3); transition: transform .15s, box-shadow .15s; }
.primary.big:hover { transform: translateY(-2px); box-shadow: 0 12px 26px rgba(192,97,47,.4); }
.ghost.big:hover { background: #e7dcc4; }
.trust { font-size: 13px; color: #8a7a5a; display: flex; gap: 10px; align-items: center; animation: fadeUp .6s .2s both; }
.trust i { color: #c9b690; font-style: normal; }

/* ---- 演示卡片 ---- */
.hero-right { animation: fadeUp .7s .2s both; }
.demo-card { background: #fff; border: 1px solid #eaddc2; border-radius: 16px; padding: 18px; display: grid; grid-template-columns: 1fr auto 1.1fr; gap: 12px; align-items: stretch; box-shadow: 0 20px 50px rgba(120,80,30,.14); }
.demo-col { background: #faf6ee; border-radius: 10px; padding: 12px; }
.col-tag { font-size: 12px; color: #b08a4f; font-weight: 700; margin-bottom: 8px; }
.demo-col.src p { font-size: 13px; line-height: 1.7; color: #555; margin: 0; }
.demo-col.src em { color: #b07b3a; font-style: italic; }
.demo-arrow { align-self: center; color: #c0612f; font-size: 22px; font-weight: 700; animation: pulse 1.6s ease-in-out infinite; }
@keyframes pulse { 0%,100% { transform: translateX(0); opacity: .6; } 50% { transform: translateX(4px); opacity: 1; } }
.demo-col.out { min-height: 180px; }
.chip-el { font-size: 12px; line-height: 1.5; padding: 7px 9px; border-radius: 8px; margin-bottom: 7px; background: #fff; border: 1px solid #eee; }
.chip-el .el-type { display: inline-block; font-size: 10px; padding: 1px 6px; border-radius: 6px; margin-right: 6px; background: #efe7d6; color: #8a6f4a; }
.chip-el.dialogue { background: #eef6ff; } .chip-el.dialogue .el-type { background: #d6e8ff; color: #2a5a9a; }
.chip-el.voiceover { background: #fff8e8; } .chip-el.voiceover .el-type { background: #ffe9bf; color: #9a6a1a; }

/* ---- 三步 ---- */
.steps { position: relative; z-index: 1; display: grid; grid-template-columns: repeat(3,1fr); gap: 16px; margin: 24px 0; }
.step { background: rgba(255,255,255,.7); border: 1px solid #eaddc2; border-radius: 12px; padding: 18px; text-align: center; }
.step .num { width: 34px; height: 34px; line-height: 34px; margin: 0 auto 8px; border-radius: 50%; background: #c0612f; color: #fff; font-weight: 700; }
.step h3 { margin: 6px 0; font-size: 16px; } .step p { margin: 0; font-size: 13px; color: #6b5b43; }

/* ---- 特性 ---- */
.features { position: relative; z-index: 1; display: grid; grid-template-columns: repeat(4,1fr); gap: 16px; margin: 30px 0; }
.feat { background: #fff; border: 1px solid #eaddc2; border-radius: 14px; padding: 20px; transition: transform .18s, box-shadow .18s; animation: fadeUp .6s var(--d) both; }
.feat:hover { transform: translateY(-6px); box-shadow: 0 14px 30px rgba(120,80,30,.14); }
.feat .ic { font-size: 30px; } .feat h3 { font-size: 16px; margin: 10px 0 6px; } .feat p { font-size: 13px; color: #6b5b43; line-height: 1.7; margin: 0; }

/* ---- 底部 ---- */
.bottom-cta { position: relative; z-index: 1; text-align: center; padding: 48px 20px 60px; }
.bottom-cta h2 { font-size: 28px; margin: 0 0 22px; }

/* ---- 动画 ---- */
@keyframes fadeUp { from { opacity: 0; transform: translateY(18px); } to { opacity: 1; transform: translateY(0); } }
.flip-enter-active,.flip-leave-active { transition: all .4s; }
.flip-enter-from { opacity: 0; transform: translateY(14px) rotateX(40deg); }
.flip-leave-to { opacity: 0; transform: translateY(-14px) rotateX(-40deg); }
.rise-enter-active { transition: all .45s cubic-bezier(.2,.7,.3,1); }
.rise-enter-from { opacity: 0; transform: translateY(12px) scale(.96); }

@media (max-width: 900px) {
  .hero { grid-template-columns: 1fr; } .hero h1 { font-size: 34px; }
  .steps,.features { grid-template-columns: 1fr 1fr; }
}
</style>
