import api from './api'

export async function login(phone, pin) {
  const { data } = await api.post('/auth/login', { phone_number: phone, pin })
  return data
}

export async function logout() {
  const { data } = await api.post('/auth/logout')
  return data
}

export async function changePin(currentPin, newPin, confirmPin) {
  const { data } = await api.post('/auth/change-pin', {
    current_pin: currentPin,
    new_pin: newPin,
    confirm_pin: confirmPin,
  })
  return data
}

export async function getCurrentUser() {
  const { data } = await api.get('/auth/me')
  return data
}
