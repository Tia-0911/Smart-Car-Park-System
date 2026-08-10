import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from '../api'
import type { User } from '../api/types'
import { clearToken, getToken, setToken } from '../api/session'

interface AuthContextValue {
  user: User | null
  loading: boolean
  error: string | null
  login: (email: string, password: string) => Promise<User>
  register: (name: string, email: string, password: string) => Promise<User>
  logout: () => void
  clearError: () => void
  updateUser: (user: User) => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const token = getToken()
    if (!token) {
      setLoading(false)
      return
    }
    api.auth
      .me(token)
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setLoading(false))
  }, [])

  const login = async (email: string, password: string) => {
    setError(null)
    try {
      const { user: loggedIn, token } = await api.auth.login({ email, password })
      setToken(token)
      setUser(loggedIn)
      return loggedIn
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not log in.'
      setError(message)
      throw err
    }
  }

  const register = async (name: string, email: string, password: string) => {
    setError(null)
    try {
      const { user: created, token } = await api.auth.register({ name, email, password })
      setToken(token)
      setUser(created)
      return created
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not create your account.'
      setError(message)
      throw err
    }
  }

  const logout = () => {
    clearToken()
    setUser(null)
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        error,
        login,
        register,
        logout,
        clearError: () => setError(null),
        updateUser: setUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
