import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const token = localStorage.getItem('token')
      if (token) {
        localStorage.removeItem('token')
        window.location.href = '/login'
      }
    }
    const message = error.response?.data?.detail || error.message || 'An error occurred'
    console.error('[API Error]', message)
    return Promise.reject(new Error(message))
  }
)

export default apiClient
