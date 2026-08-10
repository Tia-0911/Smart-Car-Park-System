import { DoorOpen, LayoutDashboard, ParkingSquare, Ticket, Users } from 'lucide-react'
import DashboardShell from './DashboardShell'
import type { NavItem } from './DashboardShell'

const nav: NavItem[] = [
  { label: 'Overview', to: '/admin', icon: LayoutDashboard, end: true },
  { label: 'Parking Slots', to: '/admin/slots', icon: ParkingSquare },
  { label: 'Bookings', to: '/admin/bookings', icon: Ticket },
  { label: 'Gates', to: '/admin/gates', icon: DoorOpen },
  { label: 'Customers', to: '/admin/customers', icon: Users },
]

export default function AdminLayout() {
  return <DashboardShell nav={nav} brand="Admin Console" />
}
