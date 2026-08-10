import type {
  AuthResponse,
  Booking,
  CreateBookingInput,
  CreateSlotInput,
  DashboardStats,
  Gate,
  LoginInput,
  ParkingSlot,
  RegisterInput,
  User,
} from './types'

// A single interface both the mock and real (fetch) implementations satisfy,
// so swapping VITE_USE_MOCK never changes a single call-site.
export interface Api {
  auth: {
    login(input: LoginInput): Promise<AuthResponse>
    register(input: RegisterInput): Promise<AuthResponse>
    me(token: string): Promise<User>
  }
  parkingSlots: {
    list(): Promise<ParkingSlot[]>
    create(input: CreateSlotInput): Promise<ParkingSlot>
    update(id: number, patch: Partial<CreateSlotInput> & { isAvailable?: boolean }): Promise<ParkingSlot>
    remove(id: number): Promise<void>
  }
  bookings: {
    list(): Promise<Booking[]>
    listMine(userId: number): Promise<Booking[]>
    create(userId: number, userName: string, input: CreateBookingInput): Promise<Booking>
    cancel(id: number): Promise<Booking>
  }
  gates: {
    list(): Promise<Gate[]>
    toggle(id: number): Promise<Gate>
  }
  customers: {
    list(): Promise<User[]>
  }
  profile: {
    update(userId: number, patch: { name?: string; email?: string }): Promise<User>
    changePassword(userId: number, currentPassword: string, nextPassword: string): Promise<void>
  }
  dashboard: {
    stats(): Promise<DashboardStats>
  }
}
