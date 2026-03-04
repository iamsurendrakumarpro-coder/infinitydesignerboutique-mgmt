import api from './api'

export async function generate(params = {}) {
  const response = await api.post('/settlements/generate', params)
  return response.data
}

export async function list(params = {}) {
  const response = await api.get('/settlements', { params })
  return response.data
}

export async function getDetail(id) {
  const response = await api.get(`/settlements/${id}`)
  return response.data
}
