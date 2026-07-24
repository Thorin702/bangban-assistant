<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { setSession } from '../store'
import { toast } from '../toast'

const router = useRouter()
const form = ref({ username: '', password: '' })
const busy = ref(false)
const error = ref('')

async function submit() {
  if (!form.value.username || !form.value.password) return
  busy.value = true
  error.value = ''
  try {
    const { token, user } = await api.post('/api/auth/login', form.value)
    setSession(token, user)
    toast(`欢迎，${user.display_name}`, 'ok')
    router.push('/')
  } catch (e) {
    error.value = e.message
  } finally { busy.value = false }
}
</script>

<template>
  <div class="login-wrap">
    <svg class="login-deco" viewBox="0 0 600 600" fill="none">
      <circle cx="300" cy="300" r="140" stroke="currentColor" stroke-width="1.2" />
      <circle cx="300" cy="300" r="200" stroke="currentColor" stroke-width="1" />
      <circle cx="300" cy="300" r="262" stroke="currentColor" stroke-width="0.8" />
      <circle cx="300" cy="300" r="80" stroke="currentColor" stroke-width="1.4" />
    </svg>

    <div class="login-box">
      <div class="login-brand">
        <img src="/dknowc-logo.png" class="login-mark" alt="深知智能" />
        <div>
          <h1>基层帮办智能助手</h1>
          <p>深知智能 · 让 AI 大模型可信地赋能业务</p>
        </div>
      </div>

      <div class="login-card card">
        <label class="field-label">账号</label>
        <input class="input" v-model.trim="form.username" placeholder="请输入账号" autocomplete="username" @keyup.enter="submit" />
        <label class="field-label" style="margin-top: 14px">密码</label>
        <input class="input" type="password" v-model="form.password" placeholder="请输入密码" autocomplete="current-password" @keyup.enter="submit" />
        <p v-if="error" class="login-error">{{ error }}</p>
        <button class="btn btn-primary login-btn" :disabled="busy || !form.username || !form.password" @click="submit">
          {{ busy ? '登录中…' : '登 录' }}
        </button>
        <p class="login-tip">账号由管理员分配，首次登录须修改密码</p>
      </div>

      <p class="login-foot">辅助不替代 · 所有产出仅供参考，决策权与责任在人</p>
    </div>
  </div>
</template>

<style scoped>
.login-wrap {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(165deg, #f6f5f0 0%, #efeee6 60%, #eae9df 100%);
  position: relative; overflow: hidden; padding: 20px;
}
.login-deco {
  position: absolute; width: 720px; height: 720px; right: -180px; top: -180px;
  color: #d8d4c6; opacity: .55; pointer-events: none;
}
.login-box { width: 100%; max-width: 400px; position: relative; }
.login-brand { display: flex; gap: 14px; align-items: center; margin-bottom: 22px; }
.login-mark {
  width: 52px; height: 52px; border-radius: 50%; flex: none; display: block;
  box-shadow: 0 6px 18px rgba(75, 12, 119, .3);
}
.login-brand h1 { font-family: var(--font-serif); font-size: 22px; letter-spacing: 1px; }
.login-brand p { font-size: 12px; color: var(--ink-3); margin-top: 3px; letter-spacing: .3px; }
.login-card { padding: 24px 22px 18px; }
.login-error { color: var(--red); font-size: 13px; margin-top: 10px; }
.login-btn { width: 100%; margin-top: 18px; height: 40px; font-size: 15px; letter-spacing: 6px; }
.login-tip { text-align: center; font-size: 12px; color: var(--ink-3); margin-top: 12px; }
.login-foot { text-align: center; font-size: 12px; color: #a7a494; margin-top: 26px; letter-spacing: .5px; }
</style>
