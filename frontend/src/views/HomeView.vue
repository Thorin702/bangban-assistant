<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { store } from '../store'
import Icon from '../components/Icon.vue'

const router = useRouter()
const cfg = computed(() => store.config || {})
const isAdmin = computed(() => store.user?.role === 'admin')

const others = [
  { icon: 'message', title: '智能办理', color: 'c-blue',
    desc: '粘贴工单，秒出政策引用、回复话术、办理方法、条款解释；每句关键信息带角标，点击回到政策原文。' },
  { icon: 'archive', title: '类案经验', color: 'c-green',
    desc: '接入本地热线工单数据富矿，检索相似类案并提炼办理经验，把过往办结做法变成可借鉴的参考。' },
  { icon: 'layers', title: '私有政策库', color: 'c-purple',
    desc: '各地市不公开的政策、办事细则一键导入，自动治理分段，与公共政策一并参与检索，本地优先。' },
  { icon: 'shield', title: '可信可控', color: 'c-amber',
    desc: '防幻觉守卫 + 文号/数值核验 + 地域严格锁定 + 人在回路留痕，生成只引用检索原文，说不知道就说不知道。' },
]

const stats = [
  { v: '千万级', l: '热线数据富矿赋能' },
  { v: '336', l: '全国地市预置' },
  { v: '秒级', l: '政策研判响应' },
  { v: '100%', l: '关键信息可溯源' },
]

const steps = [
  { n: '1', t: '粘贴诉求', d: '工单或纠纷原文，无需整理格式' },
  { n: '2', t: '研判 + 生成', d: '办件研判 + 政策话术办法，边生成边读' },
  { n: '3', t: '核实采纳', d: '逐部分采纳/修改/拒绝，全程留痕可追溯' },
]

function start() { router.push('/consult') }
</script>

<template>
  <div class="home">
    <!-- Hero -->
    <section class="hero">
      <div class="hero-glow" />
      <div class="hero-in">
        <div class="brand-pill">
          <img src="/dknowc-logo.png" class="bp-logo" alt="深知智能" />
          深知智能 · 让 AI 大模型可信地赋能业务
        </div>
        <h1 class="hero-title">让每一次 12345 办理<br /><em>办得成、办到满意</em></h1>
        <p class="hero-sub">
          面向政务热线<b>办理端</b>的智能副驾——以可信政策检索与<b>千万级热线数据富矿</b>为底座，
          为一线承办人提供<b>可核实、可追溯</b>的办理研判与参考。辅助不替代，决策权始终在人。
        </p>
        <div class="hero-cta">
          <button class="btn btn-brand" @click="start"><Icon name="send" :size="16" />开始智能办理</button>
          <button v-if="isAdmin" class="btn btn-ghost-brand" @click="router.push('/admin')"><Icon name="sliders" :size="15" />进入后台</button>
        </div>
      </div>
    </section>

    <!-- 核心能力 -->
    <section class="caps">
      <div class="sec-head">
        <span class="sec-kicker">核心能力</span>
        <h2>不只是写好回复，更帮你把事办成</h2>
      </div>

      <!-- 差异化能力：办件研判 -->
      <div class="hero-cap">
        <div class="hc-left">
          <div class="hc-badge"><Icon name="target" :size="14" />差异化核心 · 办件研判</div>
          <h3>把热线数据富矿，变成办这件事的研判</h3>
          <p>不止步于"相似案例"，而是从带结果标签的海量真实工单中，学出办这类诉求的时限、要点与风险——像一位办过千万件的老手在旁边提点。</p>
          <button class="btn btn-brand" @click="start">立即体验 →</button>
        </div>
        <div class="hc-signals">
          <div class="hc-sig">
            <span class="hcs-ic sig-clock"><Icon name="clock" :size="18" /></span>
            <div><b>时限研判</b><p>同类工单办结中位天数与超期率，颜色分级预警，避免超期扣分。</p></div>
          </div>
          <div class="hc-sig">
            <span class="hcs-ic sig-check"><Icon name="sparkle" :size="18" /></span>
            <div><b>满意度处方</b><p>对比"满意 vs 不满意"的真实办理情况，提炼办到满意的关键与易踩的坑。</p></div>
          </div>
          <div class="hc-sig">
            <span class="hcs-ic sig-alert"><Icon name="alert" :size="18" /></span>
            <div><b>关联预警</b><p>识别同小区历史同类诉求，标记重复投诉/老大难热点，提示并案或系统性解决。</p></div>
          </div>
        </div>
      </div>

      <!-- 其他能力 -->
      <div class="cap-grid">
        <div v-for="c in others" :key="c.title" class="cap-card">
          <span class="cap-ic" :class="c.color"><Icon :name="c.icon" :size="20" /></span>
          <h4>{{ c.title }}</h4>
          <p>{{ c.desc }}</p>
        </div>
      </div>
    </section>

    <!-- 数据支撑 -->
    <section class="stats">
      <div v-for="s in stats" :key="s.l" class="stat">
        <div class="stat-v">{{ s.v }}</div>
        <div class="stat-l">{{ s.l }}</div>
      </div>
    </section>

    <!-- 工作流 -->
    <section class="flow">
      <div class="sec-head center">
        <span class="sec-kicker">三步上手</span>
        <h2>粘进来 · 看研判 · 核实采纳</h2>
      </div>
      <div class="flow-steps">
        <template v-for="(s, i) in steps" :key="s.n">
          <div class="flow-step">
            <span class="fs-n">{{ s.n }}</span>
            <b>{{ s.t }}</b>
            <p>{{ s.d }}</p>
          </div>
          <Icon v-if="i < steps.length - 1" name="chevron" :size="18" class="flow-arrow" />
        </template>
      </div>
      <div class="flow-cta">
        <button class="btn btn-brand" @click="start"><Icon name="send" :size="15" />开始智能办理</button>
      </div>
    </section>

    <footer class="home-foot">
      <img src="/dknowc-logo.png" class="foot-logo" alt="深知智能" />
      <span>深知智能 DeepKnown · 让 AI 大模型可信地赋能业务</span>
      <span class="foot-note">所有产出仅供参考，请人工核实后使用</span>
    </footer>
  </div>
</template>

<style scoped>
.home { max-width: 1160px; margin: 0 auto; padding: 0 24px 40px; }

/* Hero */
.hero { position: relative; padding: 56px 0 40px; overflow: hidden; }
.hero-glow {
  position: absolute; top: -140px; left: 50%; transform: translateX(-50%);
  width: 760px; height: 420px; pointer-events: none;
  background: radial-gradient(ellipse at center, rgba(75, 12, 119, .14), rgba(75, 12, 119, 0) 70%);
}
.hero-in { position: relative; text-align: center; }
.brand-pill {
  display: inline-flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--brand);
  background: var(--brand-soft); border: 1px solid var(--brand-line); border-radius: 999px;
  padding: 5px 14px 5px 6px; margin-bottom: 20px;
}
.bp-logo { width: 20px; height: 20px; border-radius: 50%; }
.hero-title { font-family: var(--font-serif); font-size: 40px; line-height: 1.25; letter-spacing: 1px; color: var(--ink); }
.hero-title em { font-style: normal; background: linear-gradient(120deg, var(--brand), var(--brand-2)); -webkit-background-clip: text; background-clip: text; color: transparent; }
.hero-sub { max-width: 680px; margin: 18px auto 0; font-size: 15px; line-height: 1.9; color: var(--ink-2); }
.hero-sub b { color: var(--brand); font-weight: 600; }
.hero-cta { display: flex; gap: 12px; justify-content: center; margin-top: 28px; }

.btn-brand { background: linear-gradient(135deg, var(--brand-2), var(--brand)); color: #fff; height: 42px; padding: 0 22px; font-size: 15px; box-shadow: 0 6px 18px rgba(75, 12, 119, .28); }
.btn-brand:hover { filter: brightness(1.08); }
.btn-ghost-brand { background: #fff; color: var(--brand); border-color: var(--brand-line); height: 42px; padding: 0 18px; font-size: 15px; }
.btn-ghost-brand:hover { background: var(--brand-soft); }

/* 区块通用 */
.sec-head { margin-bottom: 22px; }
.sec-head.center { text-align: center; }
.sec-kicker { font-size: 12.5px; font-weight: 600; letter-spacing: 3px; color: var(--brand); }
.sec-head h2 { font-family: var(--font-serif); font-size: 24px; margin-top: 6px; color: var(--ink); }

.caps { padding-top: 24px; }

/* 办件研判 hero-cap */
.hero-cap {
  display: grid; grid-template-columns: 1fr 1.15fr; gap: 30px; align-items: center;
  background: linear-gradient(135deg, #2a0a48, #4b0c77 60%, #5b1f8f);
  border-radius: 18px; padding: 30px 32px; color: #fff; position: relative; overflow: hidden;
  box-shadow: 0 12px 40px rgba(75, 12, 119, .3);
}
.hero-cap::after { content: ''; position: absolute; right: -80px; top: -80px; width: 260px; height: 260px; border-radius: 50%; background: radial-gradient(circle, rgba(202,213,255,.18), transparent 70%); }
.hc-badge { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; background: rgba(202,213,255,.18); color: var(--periwinkle); padding: 4px 11px; border-radius: 999px; }
.hc-left h3 { font-family: var(--font-serif); font-size: 22px; line-height: 1.5; margin: 14px 0 10px; }
.hc-left p { font-size: 13.5px; line-height: 1.85; color: rgba(255,255,255,.82); margin-bottom: 18px; }
.hc-left .btn-brand { background: #fff; color: var(--brand); box-shadow: none; }
.hc-left .btn-brand:hover { background: var(--periwinkle); }
.hc-signals { display: flex; flex-direction: column; gap: 12px; position: relative; }
.hc-sig { display: flex; gap: 13px; background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.12); border-radius: 12px; padding: 14px 16px; backdrop-filter: blur(4px); }
.hcs-ic { flex: none; width: 38px; height: 38px; border-radius: 10px; display: grid; place-items: center; }
.sig-clock { background: rgba(255,196,120,.2); color: #ffd08a; }
.sig-check { background: rgba(150,230,180,.2); color: #a9ecc4; }
.sig-alert { background: rgba(255,150,150,.2); color: #ffb0b0; }
.hc-sig b { font-size: 14.5px; }
.hc-sig p { font-size: 12.5px; line-height: 1.7; color: rgba(255,255,255,.78); margin-top: 3px; }

/* 其他能力 grid */
.cap-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-top: 18px; }
.cap-card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 22px 22px; box-shadow: var(--shadow-card); transition: transform .15s, box-shadow .15s; }
.cap-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-pop); }
.cap-ic { display: inline-flex; width: 42px; height: 42px; border-radius: 11px; align-items: center; justify-content: center; margin-bottom: 12px; }
.c-blue { background: var(--primary-soft); color: var(--primary); }
.c-green { background: var(--green-soft); color: var(--green); }
.c-purple { background: var(--brand-soft); color: var(--brand); }
.c-amber { background: var(--amber-soft); color: var(--amber); }
.cap-card h4 { font-family: var(--font-serif); font-size: 17px; margin-bottom: 8px; }
.cap-card p { font-size: 13px; line-height: 1.8; color: var(--ink-2); }

/* stats */
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 40px 0; padding: 26px 20px; background: var(--bg-deep); border-radius: 16px; }
.stat { text-align: center; }
.stat-v { font-family: var(--font-serif); font-size: 30px; font-weight: 700; background: linear-gradient(120deg, var(--brand), var(--brand-2)); -webkit-background-clip: text; background-clip: text; color: transparent; }
.stat-l { font-size: 13px; color: var(--ink-3); margin-top: 4px; }

/* flow */
.flow { padding: 12px 0; }
.flow-steps { display: flex; align-items: stretch; justify-content: center; gap: 8px; margin-top: 8px; }
.flow-step { flex: 1; max-width: 240px; background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 20px; text-align: center; box-shadow: var(--shadow-card); }
.fs-n { display: inline-grid; place-items: center; width: 34px; height: 34px; border-radius: 10px; background: var(--brand-soft); color: var(--brand); font-family: var(--font-serif); font-weight: 700; font-size: 17px; margin-bottom: 10px; }
.flow-step b { font-size: 15px; }
.flow-step p { font-size: 12.5px; color: var(--ink-3); margin-top: 4px; line-height: 1.7; }
.flow-arrow { align-self: center; color: var(--brand-line); transform: rotate(-90deg); flex: none; }
.flow-cta { text-align: center; margin-top: 24px; }

.home-foot { display: flex; align-items: center; justify-content: center; gap: 10px; flex-wrap: wrap; margin-top: 40px; padding-top: 22px; border-top: 1px solid var(--line); font-size: 12.5px; color: var(--ink-3); }
.foot-logo { width: 18px; height: 18px; border-radius: 50%; }
.foot-note { color: var(--amber); }

@media (max-width: 860px) {
  .hero-title { font-size: 30px; }
  .hero-cap { grid-template-columns: 1fr; gap: 20px; padding: 24px; }
  .cap-grid { grid-template-columns: 1fr; }
  .stats { grid-template-columns: repeat(2, 1fr); gap: 20px 16px; }
  .flow-steps { flex-direction: column; align-items: stretch; }
  .flow-step { max-width: none; }
  .flow-arrow { transform: rotate(0deg); }
}
</style>
