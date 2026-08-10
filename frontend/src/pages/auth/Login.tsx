import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { isMockApi } from '../../api'
import AuthLayout from './AuthLayout'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const from = (location.state as { from?: string } | null)?.from

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const user = await login(email, password)
      navigate(from ?? (user.role === 'admin' ? '/admin' : '/customer'), { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not log in.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout title="Log in">
      <form className="mt-8 grid gap-5" onSubmit={handleSubmit}>
        <div>
          <label htmlFor="email" className="mb-1 block font-display text-xs font-semibold tracking-widest text-neutral-500 uppercase">
            Email
          </label>
          <input
            id="email"
            type="email"
            className="field-light"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>

        <div>
          <label htmlFor="password" className="mb-1 block font-display text-xs font-semibold tracking-widest text-neutral-500 uppercase">
            Password
          </label>
          <input
            id="password"
            type="password"
            className="field-light"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        {error && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
        )}

        <button className="btn btn-lime mt-1 w-full disabled:opacity-60" type="submit" disabled={submitting}>
          {submitting ? 'Logging in…' : 'Log in'}
        </button>
      </form>

      {isMockApi && (
        <div className="mt-6 rounded-xl border border-neutral-200 bg-neutral-50 p-4 text-xs text-neutral-500">
          <p className="mb-1.5 font-display font-semibold text-neutral-600">Demo accounts</p>
          <p>Admin — admin@smartpark.io / admin123</p>
          <p>Customer — jordan@example.com / customer123</p>
        </div>
      )}

      <p className="mt-6 text-sm text-neutral-500">
        New to SmartPark?{' '}
        <Link to="/register" className="font-semibold text-ink border-b-2 border-lime">
          Create an account
        </Link>
      </p>
    </AuthLayout>
  )
}
