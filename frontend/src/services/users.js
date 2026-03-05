import api from './api'

export async function createStaff(data) {
  const response = await api.post('/users/staff', data)
  return response.data
}

export async function listStaff() {
  const response = await api.get('/users/staff')
  return response.data
}

export async function getStaff(id) {
  const response = await api.get(`/users/staff/${id}`)
  return response.data
}

export async function updateStaff(id, data) {
  const response = await api.put(`/users/staff/${id}`, data)
  return response.data
}

export async function toggleStaffStatus(id) {
  const response = await api.patch(`/users/staff/${id}/status`)
  return response.data
}

export async function createAdmin(data) {
  const response = await api.post('/users/admin', data)
  return response.data
}

export async function listAdmins() {
  const response = await api.get('/users/admin')
  return response.data
}
