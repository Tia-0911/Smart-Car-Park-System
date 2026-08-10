import { LayoutDashboard, Search, Ticket, User } from 'lucide-react'
import DashboardShell from './DashboardShell'
import type { NavItem } from './DashboardShell'

const nav: NavItem[] = [
  { label: 'Overview', to: '/customer', icon: LayoutDashboard, end: true },
  { label: 'Find Parking', to: '/customer/find', icon: Search },
  { label: 'My Bookings', to: '/customer/bookings', icon: Ticket },
  { label: 'Profile', to: '/customer/profile', icon: User },
]

export default function CustomerLayout() {
  return <DashboardShell nav={nav} brand="Customer Portal" />
}
