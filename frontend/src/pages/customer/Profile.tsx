import { useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../../api'
import { useAuth } from '../../context/AuthContext'
import PageHeader from '../../components/ui/PageHeader'
import { formatDate } from '../../lib/format'

export default function Profile() {
  const { user, updateUser } = useAuth()
  const [name, setName] = useState(user?.name ?? '')
  const [email, setEmail] = useState(user?.email ?? '')
  const [savingProfile, setSavingProfile] = useState(false)
  const [profileMessage, setProfileMessage] = useState<string | null>(null)
  const [profileError, setProfileError] = useState<string | null>(null)

  const [currentPassword, setCurrentPassword] = useState('')
  const [nextPassword, setNextPassword] = useState('')
  const [savingPassword, setSavingPassword] = useState(false)
  const [passwordMessage, setPasswordMessage] = useState<string | null>(null)
  const [passwordError, setPasswordError] = useState<string | null>(null)

  if (!user) return null

  const saveProfile = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setProfileMessage(null)
    setProfileError(null)
    setSavingProfile(true)
    try {
      const updated = await api.profile.update(user.id, { name, email })
      updateUser(updated)
      setProfileMessage('Profile updated.')
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : 'Could not update profile.')
    } finally {
      setSavingProfile(false)
    }
  }

  const savePassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setPasswordMessage(null)
    setPasswordError(null)
    setSavingPassword(true)
    try {
      await api.profile.changePassword(user.id, currentPassword, nextPassword)
      setCurrentPassword('')
      setNextPassword('')
      setPasswordMessage('Password changed.')
    } catch (err) {
      setPasswordError(err instanceof Error ? err.message : 'Could not change password.')
    } finally {
      setSavingPassword(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="Profile" text={`Customer since ${formatDate(user.createdAt)}.`} />

      <form
        onSubmit={saveProfile}
        className="mb-8 grid gap-5 rounded-2xl border border-neutral-200 bg-white p-6"
      >
        <h2 className="font-display font-bold text-ink">Account details</h2>

        <div>
          <label className="mb-1 block text-xs font-semibold tracking-wide text-neutral-500 uppercase">
            Full name
          </label>
          <input className="field-light" value={name} onChange={(e) => setName(e.target.value)} required />
        </div>

        <div>
          <label className="mb-1 block text-xs font-semibold tracking-wide text-neutral-500 uppercase">
            Email
          </label>
          <input
            type="email"
            className="field-light"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>

        {profileMessage && <p className="text-sm text-lime-dark">{profileMessage}</p>}
        {profileError && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{profileError}</p>}

        <button className="btn btn-lime w-fit disabled:opacity-60" disabled={savingProfile}>
          {savingProfile ? 'Saving…' : 'Save changes'}
        </button>
      </form>

      <form
        onSubmit={savePassword}
        className="grid gap-5 rounded-2xl border border-neutral-200 bg-white p-6"
      >
        <h2 className="font-display font-bold text-ink">Change password</h2>

        <div>
          <label className="mb-1 block text-xs font-semibold tracking-wide text-neutral-500 uppercase">
            Current password
          </label>
          <input
            type="password"
            className="field-light"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            required
          />
        </div>

        <div>
          <label className="mb-1 block text-xs font-semibold tracking-wide text-neutral-500 uppercase">
            New password
          </label>
          <input
            type="password"
            className="field-light"
            minLength={8}
            value={nextPassword}
            onChange={(e) => setNextPassword(e.target.value)}
            required
          />
        </div>

        {passwordMessage && <p className="text-sm text-lime-dark">{passwordMessage}</p>}
        {passwordError && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{passwordError}</p>}

        <button className="btn btn-lime w-fit disabled:opacity-60" disabled={savingPassword}>
          {savingPassword ? 'Saving…' : 'Update password'}
        </button>
      </form>
    </div>
  )
}
