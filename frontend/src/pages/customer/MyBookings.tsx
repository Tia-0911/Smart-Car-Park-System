import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Ticket } from 'lucide-react'
import { api } from '../../api'
import type { Booking, BookingStatus } from '../../api/types'
import { useAuth } from '../../context/AuthContext'
import PageHeader from '../../components/ui/PageHeader'
import Badge from '../../components/ui/Badge'
import Spinner from '../../components/ui/Spinner'
import EmptyState from '../../components/ui/EmptyState'
import { formatCurrency, formatDateTime, statusLabel, statusTone } from '../../lib/format'

const tabs: { label: string; value: BookingStatus | 'all' }[] = [
  { label: 'All', value: 'all' },
  { label: 'Upcoming', value: 'upcoming' },
  { label: 'Active', value: 'active' },
  { label: 'Completed', value: 'completed' },
  { label: 'Cancelled', value: 'cancelled' },
]

export default function MyBookings() {
  const { user } = useAuth()
  const [bookings, setBookings] = useState<Booking[] | null>(null)
  const [tab, setTab] = useState<BookingStatus | 'all'>('all')
  const [cancellingId, setCancellingId] = useState<number | null>(null)

  const load = () => {
    if (!user) return
    api.bookings.listMine(user.id).then(setBookings)
  }

  useEffect(load, [user])

  const cancel = async (id: number) => {
    setCancellingId(id)
    try {
      await api.bookings.cancel(id)
      load()
    } finally {
      setCancellingId(null)
    }
  }

  if (!bookings) return <Spinner full />

  const visible = bookings
    .filter((b) => tab === 'all' || b.status === tab)
    .sort((a, b) => new Date(b.startTime).getTime() - new Date(a.startTime).getTime())

  return (
    <div>
      <PageHeader title="My Bookings" text="Every reservation, past and upcoming." />

      <div className="mb-6 flex flex-wrap gap-2">
        {tabs.map((t) => (
          <button
            key={t.value}
            onClick={() => setTab(t.value)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
              tab === t.value ? 'bg-ink text-white' : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {visible.length === 0 ? (
        <EmptyState icon={Ticket} title="Nothing here" text="No bookings match this filter yet." />
      ) : (
        <div className="overflow-hidden rounded-2xl border border-neutral-200 bg-white">
          {visible.map((b) => (
            <div
              key={b.id}
              className="flex flex-wrap items-center justify-between gap-4 border-b border-neutral-100 px-5 py-4 last:border-0"
            >
              <div>
                <Link
                  to={`/customer/bookings/${b.id}`}
                  className="font-display text-sm font-semibold text-ink hover:text-lime-dark"
                >
                  Bay {b.parkingSlot.slotNumber} · {b.parkingSlot.level}
                </Link>
                <p className="mt-0.5 text-xs text-neutral-500">
                  {formatDateTime(b.startTime)} → {formatDateTime(b.endTime)}
                </p>
              </div>

              <div className="flex items-center gap-3">
                <span className="text-sm text-neutral-500">{formatCurrency(b.totalCost)}</span>
                <Badge tone={statusTone[b.status]}>{statusLabel(b.status)}</Badge>
                {(b.status === 'upcoming' || b.status === 'active') && (
                  <button
                    onClick={() => cancel(b.id)}
                    disabled={cancellingId === b.id}
                    className="text-sm font-medium text-red-500 hover:text-red-600 disabled:opacity-50"
                  >
                    {cancellingId === b.id ? 'Cancelling…' : 'Cancel'}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
