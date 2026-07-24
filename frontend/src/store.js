import { reactive } from 'vue'

const saved = JSON.parse(localStorage.getItem('bb_session') || 'null')

export const store = reactive({
  token: saved?.token || '',
  user: saved?.user || null,
  config: null, // /api/config
})

export function setSession(token, user) {
  store.token = token
  store.user = user
  localStorage.setItem('bb_session', JSON.stringify({ token, user }))
}

export function clearSession() {
  store.token = ''
  store.user = null
  store.config = null
  localStorage.removeItem('bb_session')
}
