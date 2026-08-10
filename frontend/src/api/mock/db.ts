import type { Booking, Gate, ParkingSlot, User } from '../types'

interface StoredUser extends User {
  password: string
}

interface Db {
  users: StoredUser[]
  parkingSlots: ParkingSlot[]
  bookings: Booking[]
  gates: Gate[]
  nextIds: Record<'users' | 'parkingSlots' | 'bookings' | 'gates', number>
}

const STORAGE_KEY = 'smartpark.mock.db.v1'

function seed(): Db {
  const now = new Date()
  const iso = (offsetHours: number) =>
    new Date(now.getTime() + offsetHours * 3_600_000).toISOString()

  const parkingSlots: ParkingSlot[] = [
    { id: 1, slotNumber: 'A-01', isAvailable: true, level: 'Level 1', zone: 'A', hasEvCharger: true, pricePerHour: 2.5 },
    { id: 2, slotNumber: 'A-02', isAvailable: false, level: 'Level 1', zone: 'A', hasEvCharger: false, pricePerHour: 2.5 },
    { id: 3, slotNumber: 'A-03', isAvailable: true, level: 'Level 1', zone: 'A', hasEvCharger: false, pricePerHour: 2.5 },
    { id: 4, slotNumber: 'A-04', isAvailable: true, level: 'Level 1', zone: 'A', hasEvCharger: true, pricePerHour: 2.5 },
    { id: 5, slotNumber: 'B-01', isAvailable: false, level: 'Level 2', zone: 'B', hasEvCharger: false, pricePerHour: 2.0 },
    { id: 6, slotNumber: 'B-02', isAvailable: true, level: 'Level 2', zone: 'B', hasEvCharger: false, pricePerHour: 2.0 },
    { id: 7, slotNumber: 'B-03', isAvailable: false, level: 'Level 2', zone: 'B', hasEvCharger: true, pricePerHour: 2.0 },
    { id: 8, slotNumber: 'B-04', isAvailable: true, level: 'Level 2', zone: 'B', hasEvCharger: false, pricePerHour: 2.0 },
    { id: 9, slotNumber: 'C-01', isAvailable: true, level: 'Level 3', zone: 'C', hasEvCharger: false, pricePerHour: 1.5 },
    { id: 10, slotNumber: 'C-02', isAvailable: true, level: 'Level 3', zone: 'C', hasEvCharger: false, pricePerHour: 1.5 },
    { id: 11, slotNumber: 'C-03', isAvailable: false, level: 'Level 3', zone: 'C', hasEvCharger: false, pricePerHour: 1.5 },
    { id: 12, slotNumber: 'C-04', isAvailable: true, level: 'Level 3', zone: 'C', hasEvCharger: true, pricePerHour: 1.5 },
  ]

  const users: StoredUser[] = [
    {
      id: 1,
      name: 'Ava Okafor',
      email: 'admin@smartpark.io',
      password: 'admin123',
      role: 'admin',
      createdAt: iso(-2400),
    },
    {
      id: 2,
      name: 'Jordan Lee',
      email: 'jordan@example.com',
      password: 'customer123',
      role: 'customer',
      createdAt: iso(-800),
    },
  ]

  const bookings: Booking[] = [
    {
      id: 1,
      userName: 'Jordan Lee',
      userId: 2,
      parkingSlot: parkingSlots[1],
      startTime: iso(-3),
      endTime: iso(2),
      qrCode: 'SP-BK-00001',
      createdAt: iso(-3),
      status: 'active',
      totalCost: 12.5,
    },
    {
      id: 2,
      userName: 'Jordan Lee',
      userId: 2,
      parkingSlot: parkingSlots[6],
      startTime: iso(-72),
      endTime: iso(-68),
      qrCode: 'SP-BK-00002',
      createdAt: iso(-72),
      status: 'completed',
      totalCost: 8,
    },
    {
      id: 3,
      userName: 'Priya Nair',
      userId: 3,
      parkingSlot: parkingSlots[4],
      startTime: iso(-1),
      endTime: iso(4),
      qrCode: 'SP-BK-00003',
      createdAt: iso(-1),
      status: 'active',
      totalCost: 10,
    },
    {
      id: 4,
      userName: 'Tom Baxter',
      userId: 4,
      parkingSlot: parkingSlots[10],
      startTime: iso(6),
      endTime: iso(10),
      qrCode: 'SP-BK-00004',
      createdAt: iso(-0.5),
      status: 'upcoming',
      totalCost: 6,
    },
  ]

  users.push(
    { id: 3, name: 'Priya Nair', email: 'priya@example.com', password: 'customer123', role: 'customer', createdAt: iso(-1500) },
    { id: 4, name: 'Tom Baxter', email: 'tom@example.com', password: 'customer123', role: 'customer', createdAt: iso(-400) },
  )

  const gates: Gate[] = [
    { id: 1, gateName: 'Main Entrance', isOpen: false, location: 'North approach' },
    { id: 2, gateName: 'Exit Gate', isOpen: false, location: 'South approach' },
    { id: 3, gateName: 'Staff Gate', isOpen: true, location: 'Service road' },
  ]

  return {
    users,
    parkingSlots,
    bookings,
    gates,
    nextIds: { users: 5, parkingSlots: 13, bookings: 5, gates: 4 },
  }
}

function load(): Db {
  if (typeof window === 'undefined') return seed()
  const raw = window.localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    const fresh = seed()
    save(fresh)
    return fresh
  }
  try {
    return JSON.parse(raw) as Db
  } catch {
    const fresh = seed()
    save(fresh)
    return fresh
  }
}

function save(db: Db) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(db))
}

let db = load()

export function getDb() {
  return db
}

export function persist() {
  save(db)
}

export function resetDb() {
  db = seed()
  save(db)
}

export function nextId(kind: keyof Db['nextIds']) {
  const id = db.nextIds[kind]
  db.nextIds[kind] += 1
  return id
}

export type { StoredUser }
