import api from './api'

export async function getPending() {
  const response = await api.get('/overtime/pending')
  return response.data
}

export async function approve(id, notes = '') {
  const response = await api.patch(`/overtime/${id}/approve`, { notes })
  return response.data
}

export async function reject(id, notes = '') {
  const response = await api.patch(`/overtime/${id}/reject`, { notes })
  return response.data
}
