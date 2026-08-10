import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Calendar, PoundSterling, Ticket, Zap } from 'lucide-react'
import { api } from '../../api'
import type { Booking } from '../../api/types'
import { useAuth } from '../../context/AuthContext'
import StatCard from '../../components/ui/StatCard'
import Badge from '../../components/ui/Badge'
import Spinner from '../../components/ui/Spinner'
import EmptyState from '../../components/ui/EmptyState'
import { formatCurrency, formatDateTime, statusLabel, statusTone } from '../../lib/format'

export default function CustomerOverview() {
  const { user } = useAuth()
  const [bookings, setBookings] = useState<Booking[] | null>(null)

  useEffect(() => {
    if (!user) return
    api.bookings.listMine(user.id).then(setBookings)
  }, [user])

  if (!bookings) return <Spinner full />

  const active = bookings.find((b) => b.status === 'active')
  const upcoming = bookings.filter((b) => b.status === 'upcoming').length
  const totalSpent = bookings
    .filter((b) => b.status !== 'cancelled')
    .reduce((sum, b) => sum + b.totalCost, 0)
  const recent = [...bookings]
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    .slice(0, 5)

  return (
    <div>
      <div className="mb-8">
        <p className="eyebrow">Welcome back</p>
        <h1 className="font-display text-2xl font-bold tracking-tight text-ink sm:text-3xl">
          {user?.name.split(' ')[0]}, here's where things stand.
        </h1>
      </div>

      {active ? (
        <div className="mb-8 flex flex-col justify-between gap-6 rounded-2xl bg-ink p-7 text-white sm:flex-row sm:items-center">
          <div>
            <Badge tone="lime">Active now</Badge>
            <p className="mt-3 font-display text-2xl font-bold">
              Bay {active.parkingSlot.slotNumber} · {active.parkingSlot.level}
            </p>
            <p className="mt-1 text-sm text-white/60">
              Until {formatDateTime(active.endTime)} · {active.parkingSlot.zone} zone
              {active.parkingSlot.hasEvCharger && ' · EV charger'}
            </p>
          </div>
          <Link
            to={`/customer/bookings/${active.id}`}
            className="btn btn-lime shrink-0 whitespace-nowrap"
          >
            View session <ArrowRight size={16} />
          </Link>
        </div>
      ) : (
        <div className="mb-8 flex flex-col justify-between gap-6 rounded-2xl border border-neutral-200 bg-white p-7 sm:flex-row sm:items-center">
          <div>
            <p className="font-display text-xl font-bold text-ink">No active session</p>
            <p className="mt-1 text-sm text-neutral-500">
              Find a nearby bay and reserve it in seconds.
            </p>
          </div>
          <Link to="/customer/find" className="btn btn-lime shrink-0">
            Find parking <ArrowRight size={16} />
          </Link>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Upcoming bookings" value={String(upcoming)} icon={Calendar} />
        <StatCard label="Total sessions" value={String(bookings.length)} icon={Ticket} />
        <StatCard label="Total spent" value={formatCurrency(totalSpent)} icon={PoundSterling} />
      </div>

      <div className="mt-10">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-lg font-bold text-ink">Recent activity</h2>
          <Link to="/customer/bookings" className="text-sm font-medium text-neutral-500 hover:text-ink">
            View all
          </Link>
        </div>

        {recent.length === 0 ? (
          <EmptyState
            icon={Zap}
            title="No bookings yet"
            text="Once you reserve a bay, it'll show up here with its status and QR code."
          />
        ) : (
          <div className="overflow-hidden rounded-2xl border border-neutral-200 bg-white">
            {recent.map((b) => (
              <Link
                key={b.id}
                to={`/customer/bookings/${b.id}`}
                className="flex items-center justify-between gap-4 border-b border-neutral-100 px-5 py-4 last:border-0 hover:bg-neutral-50"
              >
                <div>
                  <p className="font-display text-sm font-semibold text-ink">
                    Bay {b.parkingSlot.slotNumber} · {b.parkingSlot.level}
                  </p>
                  <p className="mt-0.5 text-xs text-neutral-500">{formatDateTime(b.startTime)}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="hidden text-sm text-neutral-500 sm:block">
                    {formatCurrency(b.totalCost)}
                  </span>
                  <Badge tone={statusTone[b.status]}>{statusLabel(b.status)}</Badge>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
