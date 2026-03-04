import api from './api'

export async function createRequest(data) {
  const response = await api.post('/financial/requests', data)
  return response.data
}

export async function getRequests(params = {}) {
  const response = await api.get('/financial/requests', { params })
  return response.data
}

export async function approveRequest(id, notes = '') {
  const response = await api.patch(`/financial/requests/${id}`, {
    status: 'approved',
    admin_notes: notes,
  })
  return response.data
}

export async function rejectRequest(id, notes = '') {
  const response = await api.patch(`/financial/requests/${id}`, {
    status: 'rejected',
    admin_notes: notes,
  })
  return response.data
}
