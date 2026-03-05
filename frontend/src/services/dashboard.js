import api from './api'

export async function getSummary() {
  const response = await api.get('/dashboard/summary')
  return response.data
}

export async function getFinancialSummary(period = 'weekly') {
  const response = await api.get('/dashboard/financial-summary', { params: { period } })
  return response.data
}

export async function getAttendanceSummary(period = 'weekly') {
  const response = await api.get('/dashboard/attendance-summary', { params: { period } })
  return response.data
}
