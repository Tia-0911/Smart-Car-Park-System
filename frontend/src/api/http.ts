// Real backend client. The Django app currently only exposes sensor and
// dashboard routes (see backend/back1/urls.py) — these paths are the
// contract the backend should grow into: DRF viewsets under /api/ mounted
// at api/auth/, api/parking-slots/, api/bookings/, api/gates/, api/dashboard/.
import type { Api } from './contract'
import { getToken } from './session'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Token ${token}` } : {}),
      ...options.headers,
    },
  })

  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail ?? `Request failed (${res.status})`)
  }

  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const httpApi: Api = {
  auth: {
    login: (input) => request('/api/auth/login/', { method: 'POST', body: JSON.stringify(input) }),
    register: (input) => request('/api/auth/register/', { method: 'POST', body: JSON.stringify(input) }),
    me: (token) =>
      request('/api/auth/me/', { headers: { Authorization: `Token ${token}` } }),
  },
  parkingSlots: {
    list: () => request('/api/parking-slots/'),
    create: (input) => request('/api/parking-slots/', { method: 'POST', body: JSON.stringify(input) }),
    update: (id, patch) =>
      request(`/api/parking-slots/${id}/`, { method: 'PATCH', body: JSON.stringify(patch) }),
    remove: (id) => request(`/api/parking-slots/${id}/`, { method: 'DELETE' }),
  },
  bookings: {
    list: () => request('/api/bookings/'),
    listMine: () => request('/api/bookings/mine/'),
    create: (_userId, _userName, input) =>
      request('/api/bookings/', { method: 'POST', body: JSON.stringify(input) }),
    cancel: (id) => request(`/api/bookings/${id}/cancel/`, { method: 'POST' }),
  },
  gates: {
    list: () => request('/api/gates/'),
    toggle: (id) => request(`/api/gates/${id}/toggle/`, { method: 'POST' }),
  },
  customers: {
    list: () => request('/api/customers/'),
  },
  profile: {
    update: (_userId, patch) => request('/api/profile/', { method: 'PATCH', body: JSON.stringify(patch) }),
    changePassword: (_userId, currentPassword, nextPassword) =>
      request('/api/profile/change-password/', {
        method: 'POST',
        body: JSON.stringify({ currentPassword, nextPassword }),
      }),
  },
  dashboard: {
    stats: () => request('/api/dashboard/stats/'),
  },
}
