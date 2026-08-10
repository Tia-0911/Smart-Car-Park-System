import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Zap } from 'lucide-react'
import { api } from '../../api'
import type { ParkingSlot } from '../../api/types'
import { useAuth } from '../../context/AuthContext'
import PageHeader from '../../components/ui/PageHeader'
import Badge from '../../components/ui/Badge'
import Modal from '../../components/ui/Modal'
import Spinner from '../../components/ui/Spinner'
import EmptyState from '../../components/ui/EmptyState'
import { formatCurrency } from '../../lib/format'

function toLocalInput(date: Date) {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export default function FindParking() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [slots, setSlots] = useState<ParkingSlot[] | null>(null)
  const [zone, setZone] = useState('all')
  const [evOnly, setEvOnly] = useState(false)
  const [selected, setSelected] = useState<ParkingSlot | null>(null)
  const [start, setStart] = useState(() => toLocalInput(new Date(Date.now() + 5 * 60_000)))
  const [end, setEnd] = useState(() => toLocalInput(new Date(Date.now() + 125 * 60_000)))
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const load = () => api.parkingSlots.list().then(setSlots)

  useEffect(() => {
    load()
  }, [])

  const zones = useMemo(() => {
    if (!slots) return []
    return Array.from(new Set(slots.map((s) => s.zone))).sort()
  }, [slots])

  const filtered = useMemo(() => {
    if (!slots) return []
    return slots.filter((s) => {
      if (zone !== 'all' && s.zone !== zone) return false
      if (evOnly && !s.hasEvCharger) return false
      return true
    })
  }, [slots, zone, evOnly])

  const openReserve = (slot: ParkingSlot) => {
    setSelected(slot)
    setError(null)
  }

  const submitReservation = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!user || !selected) return
    setError(null)
    setSubmitting(true)
    try {
      const booking = await api.bookings.create(user.id, user.name, {
        parkingSlotId: selected.id,
        startTime: new Date(start).toISOString(),
        endTime: new Date(end).toISOString(),
      })
      navigate(`/customer/bookings/${booking.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not complete the reservation.')
      setSubmitting(false)
    }
  }

  if (!slots) return <Spinner full />

  return (
    <div>
      <PageHeader title="Find Parking" text="Live availability across every connected site." />

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <select
          value={zone}
          onChange={(e) => setZone(e.target.value)}
          className="rounded-lg border border-neutral-200 px-3 py-2 text-sm font-medium text-ink outline-none focus:border-lime-dark"
        >
          <option value="all">All zones</option>
          {zones.map((z) => (
            <option key={z} value={z}>
              Zone {z}
            </option>
          ))}
        </select>

        <label className="flex items-center gap-2 rounded-lg border border-neutral-200 px-3 py-2 text-sm font-medium text-ink">
          <input
            type="checkbox"
            checked={evOnly}
            onChange={(e) => setEvOnly(e.target.checked)}
            className="accent-lime"
          />
          EV charging only
        </label>
      </div>

      {filtered.length === 0 ? (
        <EmptyState icon={Zap} title="No slots match" text="Try clearing a filter to see more bays." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((slot) => (
            <div key={slot.id} className="rounded-2xl border border-neutral-200 bg-white p-5">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-display text-lg font-bold text-ink">{slot.slotNumber}</p>
                  <p className="text-xs text-neutral-500">
                    {slot.level} · Zone {slot.zone}
                  </p>
                </div>
                <Badge tone={slot.isAvailable ? 'lime' : 'neutral'}>
                  {slot.isAvailable ? 'Available' : 'Occupied'}
                </Badge>
              </div>

              {slot.hasEvCharger && (
                <p className="mt-3 flex items-center gap-1.5 text-xs font-medium text-blue-600">
                  <Zap size={14} /> EV charging bay
                </p>
              )}

              <div className="mt-4 flex items-center justify-between">
                <p className="font-display text-sm font-semibold text-ink">
                  {formatCurrency(slot.pricePerHour)}
                  <span className="font-normal text-neutral-400">/hr</span>
                </p>
                <button
                  className="btn btn-lime px-5 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-40"
                  disabled={!slot.isAvailable}
                  onClick={() => openReserve(slot)}
                >
                  Reserve
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {selected && (
        <Modal title={`Reserve bay ${selected.slotNumber}`} onClose={() => setSelected(null)}>
          <form className="grid gap-4" onSubmit={submitReservation}>
            <div>
              <label className="mb-1 block text-xs font-semibold tracking-wide text-neutral-500 uppercase">
                Starts
              </label>
              <input
                type="datetime-local"
                className="field-light"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold tracking-wide text-neutral-500 uppercase">
                Ends
              </label>
              <input
                type="datetime-local"
                className="field-light"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                required
              />
            </div>

            <p className="text-sm text-neutral-500">
              Rate: {formatCurrency(selected.pricePerHour)} / hour, billed to the nearest hour.
            </p>

            {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

            <button className="btn btn-lime w-full disabled:opacity-60" disabled={submitting}>
              {submitting ? 'Reserving…' : 'Confirm reservation'}
            </button>
          </form>
        </Modal>
      )}
    </div>
  )
}
