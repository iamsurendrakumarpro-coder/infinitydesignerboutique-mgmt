import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import * as authService from '../services/auth'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem('auth_user')
    return stored ? JSON.parse(stored) : null
  })
  const [token, setToken] = useState(() => localStorage.getItem('auth_token'))
  const [loading, setLoading] = useState(true)
  const [mustChangePin, setMustChangePin] = useState(false)

  useEffect(() => {
    async function verifyAuth() {
      if (!token) {
        setLoading(false)
        return
      }
      try {
        const data = await authService.getCurrentUser()
        const currentUser = data.user || data
        setUser(currentUser)
        localStorage.setItem('auth_user', JSON.stringify(currentUser))
        if (currentUser.must_change_pin || currentUser.first_login) {
          setMustChangePin(true)
        }
      } catch {
        setToken(null)
        setUser(null)
        localStorage.removeItem('auth_token')
        localStorage.removeItem('auth_user')
      } finally {
        setLoading(false)
      }
    }
    verifyAuth()
  }, [token])

  const login = useCallback(async (phone, pin) => {
    const data = await authService.login(phone, pin)
    const authToken = data.token
    const authUser = data.user
    setToken(authToken)
    setUser(authUser)
    localStorage.setItem('auth_token', authToken)
    localStorage.setItem('auth_user', JSON.stringify(authUser))
    if (authUser.must_change_pin || authUser.first_login) {
      setMustChangePin(true)
    }
    return authUser
  }, [])

  const logout = useCallback(async () => {
    try {
      await authService.logout()
    } catch {
      // Ignore logout errors
    } finally {
      setToken(null)
      setUser(null)
      setMustChangePin(false)
      localStorage.removeItem('auth_token')
      localStorage.removeItem('auth_user')
    }
  }, [])

  const completePinChange = useCallback(() => {
    setMustChangePin(false)
    if (user) {
      const updatedUser = { ...user, must_change_pin: false, first_login: false }
      setUser(updatedUser)
      localStorage.setItem('auth_user', JSON.stringify(updatedUser))
    }
  }, [user])

  const isAdmin = user?.role === 'admin' || user?.role === 'root_admin'
  const isStaff = user?.role === 'staff'
  const isAuthenticated = !!token && !!user

  const value = {
    user,
    token,
    loading,
    mustChangePin,
    isAdmin,
    isStaff,
    isAuthenticated,
    login,
    logout,
    completePinChange,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

export default AuthContext
