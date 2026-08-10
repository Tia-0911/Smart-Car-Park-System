import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Calendar, ParkingSquare, PoundSterling, Users } from 'lucide-react'
import { api } from '../../api'
import type { Booking, DashboardStats, ParkingSlot } from '../../api/types'
import StatCard from '../../components/ui/StatCard'
import PageHeader from '../../components/ui/PageHeader'
import Badge from '../../components/ui/Badge'
import Spinner from '../../components/ui/Spinner'
import { formatCurrency, formatDateTime, statusLabel, statusTone } from '../../lib/format'

export default function AdminOverview() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [slots, setSlots] = useState<ParkingSlot[] | null>(null)
  const [bookings, setBookings] = useState<Booking[] | null>(null)

  useEffect(() => {
    api.dashboard.stats().then(setStats)
    api.parkingSlots.list().then(setSlots)
    api.bookings.list().then(setBookings)
  }, [])

  if (!stats || !slots || !bookings) return <Spinner full />

  const byLevel = Object.entries(
    slots.reduce<Record<string, { total: number; occupied: number }>>((acc, s) => {
      acc[s.level] ??= { total: 0, occupied: 0 }
      acc[s.level].total += 1
      if (!s.isAvailable) acc[s.level].occupied += 1
      return acc
    }, {}),
  ).sort(([a], [b]) => a.localeCompare(b))

  const recent = [...bookings]
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    .slice(0, 6)

  return (
    <div>
      <PageHeader title="Overview" text="Live status across every connected car park." />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Occupancy"
          value={`${stats.occupancyRate}%`}
          icon={ParkingSquare}
          trend={`${stats.occupiedSlots} of ${stats.totalSlots} bays occupied`}
        />
        <StatCard label="Active bookings" value={String(stats.activeBookings)} icon={Calendar} />
        <StatCard label="Registered customers" value={String(stats.totalCustomers)} icon={Users} />
        <StatCard label="Today's revenue" value={formatCurrency(stats.todaysRevenue)} icon={PoundSterling} />
      </div>

      <div className="mt-10 grid gap-6 lg:grid-cols-[1fr_1.2fr]">
        <div className="rounded-2xl border border-neutral-200 bg-white p-6">
          <h2 className="mb-5 font-display font-bold text-ink">Occupancy by level</h2>
          <div className="grid gap-4">
            {byLevel.map(([level, { total, occupied }]) => {
              const pct = Math.round((occupied / total) * 100)
              return (
                <div key={level}>
                  <div className="mb-1.5 flex justify-between text-sm">
                    <span className="font-medium text-ink">{level}</span>
                    <span className="text-neutral-400">
                      {occupied}/{total} occupied
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-neutral-100">
                    <div className="h-full rounded-full bg-lime" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <div className="rounded-2xl border border-neutral-200 bg-white p-6">
          <div className="mb-5 flex items-center justify-between">
            <h2 className="font-display font-bold text-ink">Recent bookings</h2>
            <Link to="/admin/bookings" className="text-sm font-medium text-neutral-500 hover:text-ink">
              View all
            </Link>
          </div>
          <div className="grid gap-3">
            {recent.map((b) => (
              <div key={b.id} className="flex items-center justify-between gap-3 text-sm">
                <div>
                  <p className="font-medium text-ink">{b.userName}</p>
                  <p className="text-xs text-neutral-400">
                    Bay {b.parkingSlot.slotNumber} · {formatDateTime(b.startTime)}
                  </p>
                </div>
                <Badge tone={statusTone[b.status]}>{statusLabel(b.status)}</Badge>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
