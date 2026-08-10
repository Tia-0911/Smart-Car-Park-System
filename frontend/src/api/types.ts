// Shapes mirror the Django models in backend/back1/models.py
// (ParkingSlot, Booking, Gate). Fields marked "UI extension" don't exist
// on the backend yet and default to sensible values from the mock layer —
// add them to the Django models/serializers before pointing at a real API.

export type UserRole = 'customer' | 'admin'

export interface User {
  id: number
  name: string
  email: string
  role: UserRole
  createdAt: string
}

export interface AuthResponse {
  user: User
  token: string
}

export interface ParkingSlot {
  id: number
  slotNumber: string
  isAvailable: boolean
  level: string // UI extension
  zone: string // UI extension
  hasEvCharger: boolean // UI extension
  pricePerHour: number // UI extension
}

export type BookingStatus = 'upcoming' | 'active' | 'completed' | 'cancelled'

export interface Booking {
  id: number
  userName: string
  userId: number
  parkingSlot: ParkingSlot
  startTime: string
  endTime: string
  qrCode: string
  createdAt: string
  status: BookingStatus // UI extension
  totalCost: number // UI extension
}

export interface Gate {
  id: number
  gateName: string
  isOpen: boolean
  location: string // UI extension
}

export interface DashboardStats {
  totalSlots: number
  availableSlots: number
  occupiedSlots: number
  activeBookings: number
  todaysBookings: number
  totalCustomers: number
  todaysRevenue: number
  occupancyRate: number
}

export interface CreateBookingInput {
  parkingSlotId: number
  startTime: string
  endTime: string
}

export interface CreateSlotInput {
  slotNumber: string
  level: string
  zone: string
  hasEvCharger: boolean
  pricePerHour: number
}

export interface LoginInput {
  email: string
  password: string
}

export interface RegisterInput {
  name: string
  email: string
  password: string
}
