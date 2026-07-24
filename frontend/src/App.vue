<script setup>
import { computed, ref, watchEffect } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { store, clearSession, setSession } from './store'
import { api } from './api'
import { toasts, toast } from './toast'
import Icon from './components/Icon.vue'
import Modal from './components/Modal.vue'

const route = useRoute()
const router = useRouter()
const isLogin = computed(() => route.path === '/login')
const menuOpen = ref(false)

watchEffect(async () => {
  if (store.token && !store.config && !isLogin.value) {
    try { store.config = await api.get('/api/config') } catch { /* 401 已统一处理 */ }
  }
})

// 首次登录强制改密
const showPw = computed(() => !!store.user?.must_change_password)
const pwForm = ref({ old_password: '', new_password: '', confirm: '' })
const pwBusy = ref(false)
async function submitPw() {
  if (pwForm.value.new_password.length < 8) return toast('新密码至少 8 位', 'warn')
  if (pwForm.value.new_password !== pwForm.value.confirm) return toast('两次输入的新密码不一致', 'warn')
  pwBusy.value = true
  try {
    await api.post('/api/auth/change-password', pwForm.value)
    setSession(store.token, { ...store.user, must_change_password: false })
    toast('密码已更新', 'ok')
  } catch (e) { toast(e.message, 'err') } finally { pwBusy.value = false }
}

function logout() {
  clearSession()
  router.push('/login')
}

const navs = computed(() => {
  const list = [
    { to: '/', label: '首页', icon: 'home' },
    { to: '/consult', label: '智能办理', icon: 'send' },
    { to: '/history', label: '历史记录', icon: 'history' },
  ]
  if (store.user?.role === 'admin') list.push({ to: '/admin', label: '后台管理', icon: 'sliders' })
  return list
})
</script>

<template>
  <div v-if="isLogin"><router-view /></div>
  <div v-else class="shell">
    <header class="topbar">
      <div class="topbar-in">
        <router-link to="/" class="brand">
          <img src="/dknowc-logo.png" class="brand-logo" alt="深知智能" />
          <span class="brand-name">基层帮办智能助手</span>
        </router-link>
        <nav class="nav">
          <router-link v-for="n in navs" :key="n.to" :to="n.to" class="nav-item"
            :class="{ active: n.to === '/' ? route.path === '/' : route.path.startsWith(n.to) }">
            <Icon :name="n.icon" :size="15" />{{ n.label }}
          </router-link>
        </nav>
        <div class="top-right">
          <div class="user-chip" @click="menuOpen = !menuOpen">
            <span class="avatar">{{ (store.user?.display_name || '?')[0] }}</span>
            <span class="uname">{{ store.user?.display_name }}</span>
            <Icon name="chevron" :size="14" />
            <div v-if="menuOpen" class="user-menu" @click.stop>
              <div class="user-meta">
                <div class="user-meta-name">{{ store.user?.display_name }}</div>
                <div class="user-meta-org">{{ store.user?.org || '—' }} · {{ { handler: '承办人', mediator: '调解员', admin: '管理员' }[store.user?.role] }}</div>
              </div>
              <button class="menu-item" @click="pwForm = { old_password: '', new_password: '', confirm: '' }; store.user.must_change_password = true; menuOpen = false">
                <Icon name="key" :size="14" />修改密码
              </button>
              <button class="menu-item" @click="logout"><Icon name="logout" :size="14" />退出登录</button>
            </div>
          </div>
        </div>
      </div>
    </header>
    <main @click="menuOpen = false"><router-view /></main>

    <Modal v-if="showPw" title="修改密码" @close="store.user.must_change_password = false">
      <p class="pw-hint">为保障账号安全，首次登录或重置后须设置新密码（至少 8 位）。</p>
      <div class="pw-form">
        <input class="input" type="password" v-model="pwForm.old_password" placeholder="当前密码" autocomplete="current-password" />
        <input class="input" type="password" v-model="pwForm.new_password" placeholder="新密码（至少 8 位）" autocomplete="new-password" />
        <input class="input" type="password" v-model="pwForm.confirm" placeholder="确认新密码" autocomplete="new-password" @keyup.enter="submitPw" />
      </div>
      <template #footer>
        <button class="btn btn-primary" :disabled="pwBusy" @click="submitPw">{{ pwBusy ? '提交中…' : '确认修改' }}</button>
      </template>
    </Modal>

    <div class="toast-host">
      <TransitionGroup name="toast">
        <div v-for="t in toasts" :key="t.id" class="toast" :class="'toast-' + t.type">{{ t.message }}</div>
      </TransitionGroup>
    </div>
  </div>
</template>

<style scoped>
.shell { min-height: 100vh; }
.topbar {
  position: sticky; top: 0; z-index: 50;
  background: rgba(255, 255, 255, 0.86); backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--line);
}
.topbar-in { max-width: 1280px; margin: 0 auto; padding: 0 24px; height: 56px; display: flex; align-items: center; gap: 28px; }
.brand { display: flex; align-items: center; gap: 10px; text-decoration: none !important; }
.brand-logo { width: 30px; height: 30px; border-radius: 50%; display: block; box-shadow: 0 1px 3px rgba(75, 12, 119, .25); }
.brand-name { font-family: var(--font-serif); font-size: 17px; font-weight: 700; color: var(--ink); letter-spacing: .5px; }
.nav { display: flex; gap: 4px; flex: 1; }
.nav-item {
  display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px;
  border-radius: 8px; color: var(--ink-2); font-size: 14px; text-decoration: none !important;
  white-space: nowrap;
}
.nav-item:hover { background: var(--bg-deep); color: var(--ink); }
.nav-item.active { background: var(--primary-soft); color: var(--primary); font-weight: 500; }
.top-right { display: flex; align-items: center; gap: 10px; }
.user-chip { position: relative; display: flex; align-items: center; gap: 7px; padding: 5px 8px; border-radius: 8px; cursor: pointer; color: var(--ink-2); }
.user-chip:hover { background: var(--bg-deep); }
.avatar { width: 26px; height: 26px; border-radius: 50%; background: var(--primary-soft); color: var(--primary); display: grid; place-items: center; font-size: 13px; font-weight: 600; }
.uname { font-size: 13.5px; }
.user-menu {
  position: absolute; right: 0; top: calc(100% + 6px); width: 200px;
  background: #fff; border: 1px solid var(--line); border-radius: 10px; box-shadow: var(--shadow-pop);
  padding: 6px; cursor: default;
}
.user-meta { padding: 8px 10px 10px; border-bottom: 1px solid var(--line); margin-bottom: 4px; }
.user-meta-name { font-weight: 600; }
.user-meta-org { font-size: 12px; color: var(--ink-3); margin-top: 2px; }
.menu-item {
  display: flex; align-items: center; gap: 8px; width: 100%; text-align: left;
  border: none; background: none; padding: 8px 10px; border-radius: 7px; cursor: pointer;
  font-size: 13.5px; color: var(--ink-2);
}
.menu-item:hover { background: var(--bg-deep); color: var(--ink); }
.pw-hint { font-size: 13px; color: var(--ink-3); margin-bottom: 12px; }
.pw-form { display: flex; flex-direction: column; gap: 10px; }
.toast-host { position: fixed; top: 68px; left: 50%; transform: translateX(-50%); z-index: 200; display: flex; flex-direction: column; gap: 8px; align-items: center; }
.toast {
  padding: 9px 18px; border-radius: 999px; font-size: 13.5px; background: var(--ink); color: #fff;
  box-shadow: var(--shadow-pop);
}
.toast-ok { background: var(--green); }
.toast-err { background: var(--red); }
.toast-warn { background: var(--amber); }
.toast-enter-active, .toast-leave-active { transition: all .25s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(-8px); }
@media (max-width: 720px) {
  .topbar-in { padding: 0 12px; gap: 10px; }
  .brand-name, .uname { display: none; }
  .nav-item { padding: 6px 8px; font-size: 13px; }
  .top-right .badge { display: none; }
}
</style>
