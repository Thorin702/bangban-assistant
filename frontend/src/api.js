import { store, clearSession } from './store'

class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status }
}

function handleUnauthorized() {
  clearSession()
  if (!location.hash.includes('/login')) location.hash = '#/login'
}

async function request(path, { method = 'GET', body } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (store.token) headers.Authorization = `Bearer ${store.token}`
  const resp = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined })
  if (resp.status === 401) {
    handleUnauthorized()
    throw new ApiError('登录已失效', 401)
  }
  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) throw new ApiError(data.detail || `请求失败（${resp.status}）`, resp.status)
  return data
}

export const api = {
  get: (p) => request(p),
  post: (p, body) => request(p, { method: 'POST', body }),
  put: (p, body) => request(p, { method: 'PUT', body }),
  delete: (p) => request(p, { method: 'DELETE' }),
}

/** POST 发起 SSE 流。onEvent(event, data)；返回 abort 函数。用户中断视为正常结束。 */
export function ssePost(path, body, onEvent) {
  const ctrl = new AbortController()
  const promise = (async () => {
    const headers = { 'Content-Type': 'application/json' }
    if (store.token) headers.Authorization = `Bearer ${store.token}`
    let resp
    try {
      resp = await fetch(path, { method: 'POST', headers, body: JSON.stringify(body), signal: ctrl.signal })
    } catch (e) {
      if (e.name === 'AbortError') return   // 主动中断，静默结束
      throw e
    }
    if (resp.status === 401) { handleUnauthorized(); throw new ApiError('登录已失效', 401) }
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}))
      throw new ApiError(data.detail || `请求失败（${resp.status}）`, resp.status)
    }
    if (!resp.body) return
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    try {
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        let idx
        while ((idx = buf.indexOf('\n\n')) >= 0) {
          const block = buf.slice(0, idx)
          buf = buf.slice(idx + 2)
          let event = 'message', data = ''
          for (const line of block.split('\n')) {
            if (line.startsWith('event:')) event = line.slice(6).trim()
            else if (line.startsWith('data:')) data += line.slice(5).trim()
          }
          if (data) {
            try { onEvent(event, JSON.parse(data)) } catch { /* 忽略坏块 */ }
          }
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') throw e   // 中断静默，其他上抛
    } finally {
      try { reader.releaseLock() } catch { /* noop */ }
    }
  })()
  return { promise, abort: () => ctrl.abort() }
}
