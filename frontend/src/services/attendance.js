import api from './api'

export async function getStatus() {
  const response = await api.get('/attendance/status')
  return response.data
}

export async function punch() {
  const response = await api.post('/attendance/punch')
  return response.data
}

export async function getHistory(period = 'weekly') {
  const response = await api.get('/attendance/history', { params: { period } })
  return response.data
}
