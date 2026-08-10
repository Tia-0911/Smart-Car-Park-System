import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import type { UserRole } from '../api/types'

function FullScreenSpinner() {
  return (
    <div className="grid min-h-screen place-items-center bg-white">
      <div className="h-9 w-9 animate-spin rounded-full border-2 border-neutral-200 border-t-lime" />
    </div>
  )
}

export default function ProtectedRoute({
  allow,
  children,
}: {
  allow: UserRole
  children: ReactNode
}) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) return <FullScreenSpinner />

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  if (user.role !== allow) {
    return <Navigate to={user.role === 'admin' ? '/admin' : '/customer'} replace />
  }

  return <>{children}</>
}
