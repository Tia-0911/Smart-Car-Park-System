import { useEffect, useMemo, useState } from 'react'
import { Search, Ticket } from 'lucide-react'
import { api } from '../../api'
import type { Booking, BookingStatus } from '../../api/types'
import PageHeader from '../../components/ui/PageHeader'
import Badge from '../../components/ui/Badge'
import Spinner from '../../components/ui/Spinner'
import EmptyState from '../../components/ui/EmptyState'
import { formatCurrency, formatDateTime, statusLabel, statusTone } from '../../lib/format'

const statuses: (BookingStatus | 'all')[] = ['all', 'upcoming', 'active', 'completed', 'cancelled']

export default function AdminBookings() {
  const [bookings, setBookings] = useState<Booking[] | null>(null)
  const [status, setStatus] = useState<BookingStatus | 'all'>('all')
  const [query, setQuery] = useState('')
  const [cancellingId, setCancellingId] = useState<number | null>(null)

  const load = () => api.bookings.list().then(setBookings)

  useEffect(() => {
    load()
  }, [])

  const cancel = async (id: number) => {
    setCancellingId(id)
    try {
      await api.bookings.cancel(id)
      load()
    } finally {
      setCancellingId(null)
    }
  }

  const visible = useMemo(() => {
    if (!bookings) return []
    const q = query.trim().toLowerCase()
    return bookings
      .filter((b) => status === 'all' || b.status === status)
      .filter(
        (b) =>
          !q || b.userName.toLowerCase().includes(q) || b.parkingSlot.slotNumber.toLowerCase().includes(q),
      )
      .sort((a, b) => new Date(b.startTime).getTime() - new Date(a.startTime).getTime())
  }, [bookings, status, query])

  if (!bookings) return <Spinner full />

  return (
    <div>
      <PageHeader title="Bookings" text={`${bookings.length} reservations across the network.`} />

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="relative">
          <Search size={16} className="absolute top-1/2 left-3 -translate-y-1/2 text-neutral-400" />
          <input
            className="rounded-lg border border-neutral-200 py-2 pr-3 pl-9 text-sm outline-none focus:border-lime-dark"
            placeholder="Search customer or bay…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as BookingStatus | 'all')}
          className="rounded-lg border border-neutral-200 px-3 py-2 text-sm font-medium text-ink outline-none focus:border-lime-dark"
        >
          {statuses.map((s) => (
            <option key={s} value={s}>
              {s === 'all' ? 'All statuses' : statusLabel(s)}
            </option>
          ))}
        </select>
      </div>

      {visible.length === 0 ? (
        <EmptyState icon={Ticket} title="No bookings found" text="Try a different search or filter." />
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-neutral-200 bg-white">
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr className="border-b border-neutral-100 text-left text-xs text-neutral-400 uppercase">
                <th className="px-5 py-3 font-medium">Customer</th>
                <th className="px-5 py-3 font-medium">Bay</th>
                <th className="px-5 py-3 font-medium">Window</th>
                <th className="px-5 py-3 font-medium">Total</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium" />
              </tr>
            </thead>
            <tbody>
              {visible.map((b) => (
                <tr key={b.id} className="border-b border-neutral-50 last:border-0">
                  <td className="px-5 py-3.5 font-medium text-ink">{b.userName}</td>
                  <td className="px-5 py-3.5 text-neutral-500">{b.parkingSlot.slotNumber}</td>
                  <td className="px-5 py-3.5 text-neutral-500">
                    {formatDateTime(b.startTime)} → {formatDateTime(b.endTime)}
                  </td>
                  <td className="px-5 py-3.5 text-neutral-500">{formatCurrency(b.totalCost)}</td>
                  <td className="px-5 py-3.5">
                    <Badge tone={statusTone[b.status]}>{statusLabel(b.status)}</Badge>
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    {(b.status === 'upcoming' || b.status === 'active') && (
                      <button
                        onClick={() => cancel(b.id)}
                        disabled={cancellingId === b.id}
                        className="text-sm font-medium text-red-500 hover:text-red-600 disabled:opacity-50"
                      >
                        {cancellingId === b.id ? 'Cancelling…' : 'Cancel'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
