import type { Api } from '../contract'
import type { Booking, ParkingSlot, User } from '../types'
import { getDb, nextId, persist } from './db'

const LATENCY = 320

function delay<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), LATENCY))
}

function deriveStatus(booking: Booking): Booking['status'] {
  if (booking.status === 'cancelled') return 'cancelled'
  const now = Date.now()
  const start = new Date(booking.startTime).getTime()
  const end = new Date(booking.endTime).getTime()
  if (now < start) return 'upcoming'
  if (now > end) return 'completed'
  return 'active'
}

function withDerivedStatus(booking: Booking): Booking {
  return { ...booking, status: deriveStatus(booking) }
}

function sanitize(user: User & { password?: string }): User {
  const { id, name, email, role, createdAt } = user
  return { id, name, email, role, createdAt }
}

function makeToken(userId: number) {
  return `mock-token.${userId}.${Math.random().toString(36).slice(2)}`
}

function userIdFromToken(token: string): number {
  const id = Number(token.split('.')[1])
  if (!Number.isFinite(id)) throw new Error('Invalid session — please log in again.')
  return id
}

export const mockApi: Api = {
  auth: {
    async login({ email, password }) {
      const db = getDb()
      const user = db.users.find((u) => u.email.toLowerCase() === email.toLowerCase())
      if (!user || user.password !== password) {
        await delay(null)
        throw new Error('Incorrect email or password.')
      }
      return delay({ user: sanitize(user), token: makeToken(user.id) })
    },

    async register({ name, email, password }) {
      const db = getDb()
      const exists = db.users.some((u) => u.email.toLowerCase() === email.toLowerCase())
      if (exists) {
        await delay(null)
        throw new Error('An account with that email already exists.')
      }
      const user = {
        id: nextId('users'),
        name,
        email,
        password,
        role: 'customer' as const,
        createdAt: new Date().toISOString(),
      }
      db.users.push(user)
      persist()
      return delay({ user: sanitize(user), token: makeToken(user.id) })
    },

    async me(token) {
      const db = getDb()
      const id = userIdFromToken(token)
      const user = db.users.find((u) => u.id === id)
      if (!user) {
        await delay(null)
        throw new Error('Session expired — please log in again.')
      }
      return delay(sanitize(user))
    },
  },

  parkingSlots: {
    async list() {
      const db = getDb()
      return delay([...db.parkingSlots])
    },

    async create(input) {
      const db = getDb()
      const slot: ParkingSlot = { id: nextId('parkingSlots'), isAvailable: true, ...input }
      db.parkingSlots.push(slot)
      persist()
      return delay(slot)
    },

    async update(id, patch) {
      const db = getDb()
      const slot = db.parkingSlots.find((s) => s.id === id)
      if (!slot) throw new Error('Parking slot not found.')
      Object.assign(slot, patch)
      persist()
      return delay({ ...slot })
    },

    async remove(id) {
      const db = getDb()
      db.parkingSlots = db.parkingSlots.filter((s) => s.id !== id)
      persist()
      return delay(undefined)
    },
  },

  bookings: {
    async list() {
      const db = getDb()
      return delay(db.bookings.map(withDerivedStatus))
    },

    async listMine(userId) {
      const db = getDb()
      return delay(db.bookings.filter((b) => b.userId === userId).map(withDerivedStatus))
    },

    async create(userId, userName, input) {
      const db = getDb()
      const slot = db.parkingSlots.find((s) => s.id === input.parkingSlotId)
      if (!slot) throw new Error('Parking slot not found.')
      if (!slot.isAvailable) throw new Error('That slot is no longer available.')

      const hours = Math.max(
        1,
        (new Date(input.endTime).getTime() - new Date(input.startTime).getTime()) / 3_600_000,
      )

      const booking: Booking = {
        id: nextId('bookings'),
        userId,
        userName,
        parkingSlot: slot,
        startTime: input.startTime,
        endTime: input.endTime,
        qrCode: `SP-BK-${String(nextId('bookings')).padStart(5, '0')}`,
        createdAt: new Date().toISOString(),
        status: 'upcoming',
        totalCost: Math.round(hours * slot.pricePerHour * 100) / 100,
      }

      slot.isAvailable = false
      db.bookings.push(booking)
      persist()
      return delay(withDerivedStatus(booking))
    },

    async cancel(id) {
      const db = getDb()
      const booking = db.bookings.find((b) => b.id === id)
      if (!booking) throw new Error('Booking not found.')
      booking.status = 'cancelled'
      const slot = db.parkingSlots.find((s) => s.id === booking.parkingSlot.id)
      if (slot) slot.isAvailable = true
      persist()
      return delay({ ...booking })
    },
  },

  gates: {
    async list() {
      const db = getDb()
      return delay([...db.gates])
    },

    async toggle(id) {
      const db = getDb()
      const gate = db.gates.find((g) => g.id === id)
      if (!gate) throw new Error('Gate not found.')
      gate.isOpen = !gate.isOpen
      persist()
      return delay({ ...gate })
    },
  },

  customers: {
    async list() {
      const db = getDb()
      return delay(db.users.filter((u) => u.role === 'customer').map(sanitize))
    },
  },

  profile: {
    async update(userId, patch) {
      const db = getDb()
      const user = db.users.find((u) => u.id === userId)
      if (!user) throw new Error('User not found.')
      if (patch.email && db.users.some((u) => u.id !== userId && u.email.toLowerCase() === patch.email!.toLowerCase())) {
        await delay(null)
        throw new Error('That email is already in use.')
      }
      Object.assign(user, patch)
      persist()
      return delay(sanitize(user))
    },

    async changePassword(userId, currentPassword, nextPassword) {
      const db = getDb()
      const user = db.users.find((u) => u.id === userId)
      if (!user || user.password !== currentPassword) {
        await delay(null)
        throw new Error('Current password is incorrect.')
      }
      user.password = nextPassword
      persist()
      return delay(undefined)
    },
  },

  dashboard: {
    async stats() {
      const db = getDb()
      const totalSlots = db.parkingSlots.length
      const availableSlots = db.parkingSlots.filter((s) => s.isAvailable).length
      const occupiedSlots = totalSlots - availableSlots
      const bookings = db.bookings.map(withDerivedStatus)
      const activeBookings = bookings.filter((b) => b.status === 'active').length
      const startOfDay = new Date()
      startOfDay.setHours(0, 0, 0, 0)
      const todaysBookings = bookings.filter(
        (b) => new Date(b.createdAt).getTime() >= startOfDay.getTime(),
      ).length
      const todaysRevenue = bookings
        .filter((b) => new Date(b.createdAt).getTime() >= startOfDay.getTime() && b.status !== 'cancelled')
        .reduce((sum, b) => sum + b.totalCost, 0)

      return delay({
        totalSlots,
        availableSlots,
        occupiedSlots,
        activeBookings,
        todaysBookings,
        totalCustomers: db.users.filter((u) => u.role === 'customer').length,
        todaysRevenue: Math.round(todaysRevenue * 100) / 100,
        occupancyRate: totalSlots ? Math.round((occupiedSlots / totalSlots) * 100) : 0,
      })
    },
  },
}
