import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import AuthLayout from './AuthLayout'

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await register(name, email, password)
      navigate('/customer', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create your account.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout title="Join SmartPark">
      <form className="mt-8 grid gap-5" onSubmit={handleSubmit}>
        <div>
          <label htmlFor="name" className="mb-1 block font-display text-xs font-semibold tracking-widest text-neutral-500 uppercase">
            Full name
          </label>
          <input
            id="name"
            type="text"
            className="field-light"
            placeholder="Jane Driver"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>

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
            placeholder="At least 8 characters"
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        {error && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
        )}

        <button className="btn btn-lime mt-1 w-full disabled:opacity-60" type="submit" disabled={submitting}>
          {submitting ? 'Creating account…' : 'Register'}
        </button>
      </form>

      <p className="mt-6 text-sm text-neutral-500">
        Already parking with us?{' '}
        <Link to="/login" className="font-semibold text-ink border-b-2 border-lime">
          Log in
        </Link>
      </p>
    </AuthLayout>
  )
}
