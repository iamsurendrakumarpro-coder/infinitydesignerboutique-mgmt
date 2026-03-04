import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    if (import.meta.env.DEV) {
      console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`, config.data || '')
    }
    return config
  },
  (error) => {
    console.error('[API] Request error:', error)
    return Promise.reject(error)
  }
)

api.interceptors.response.use(
  (response) => {
    if (import.meta.env.DEV) {
      console.log(`[API] Response ${response.status}:`, response.config.url)
    }
    return response
  },
  (error) => {
    const message = error.response?.data?.error || error.response?.data?.message || error.message
    if (import.meta.env.DEV) {
      console.error(`[API] Error ${error.response?.status}:`, message)
    }

    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('auth_user')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }

    return Promise.reject(error)
  }
)

export default api
