import axios from 'axios'

const STALE_EVENT = 'stale-session'

export function dispatchStaleSession() {
  window.dispatchEvent(new CustomEvent(STALE_EVENT))
}

export function onStaleSession(cb: () => void) {
  window.addEventListener(STALE_EVENT, cb)
  return () => window.removeEventListener(STALE_EVENT, cb)
}

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error.response?.data?.detail || ''
    const token = localStorage.getItem('token')

    // Session conflict — token valid but Redis has a newer one
    if (error.response?.status === 401 && detail.includes('已在其他地方登录') && token) {
      dispatchStaleSession()
      return Promise.reject(new Error(detail))
    }

    // Normal 401 — expired or missing token
    if (error.response?.status === 401) {
      if (token) {
        localStorage.removeItem('token')
        window.location.href = '/login'
      }
      return Promise.reject(new Error(detail))
    }

    const message = detail || error.message || 'An error occurred'
    console.error('[API Error]', message)
    return Promise.reject(new Error(message))
  }
)

export default apiClient
