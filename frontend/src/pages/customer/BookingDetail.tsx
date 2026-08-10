import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { QRCodeSVG } from 'qrcode.react'
import { ArrowLeft, MapPin, Zap } from 'lucide-react'
import { api } from '../../api'
import type { Booking } from '../../api/types'
import { useAuth } from '../../context/AuthContext'
import Badge from '../../components/ui/Badge'
import Spinner from '../../components/ui/Spinner'
import { formatCurrency, formatDateTime, statusLabel, statusTone } from '../../lib/format'

export default function BookingDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [booking, setBooking] = useState<Booking | null | undefined>(undefined)
  const [cancelling, setCancelling] = useState(false)

  useEffect(() => {
    if (!user) return
    api.bookings.listMine(user.id).then((all) => {
      setBooking(all.find((b) => String(b.id) === id) ?? null)
    })
  }, [user, id])

  const cancel = async () => {
    if (!booking) return
    setCancelling(true)
    const updated = await api.bookings.cancel(booking.id)
    setBooking(updated)
    setCancelling(false)
  }

  if (booking === undefined) return <Spinner full />

  if (booking === null) {
    return (
      <div className="text-center">
        <p className="text-neutral-500">Booking not found.</p>
        <button onClick={() => navigate('/customer/bookings')} className="btn btn-lime mt-4">
          Back to bookings
        </button>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl">
      <Link
        to="/customer/bookings"
        className="mb-6 inline-flex items-center gap-1.5 text-sm font-medium text-neutral-500 hover:text-ink"
      >
        <ArrowLeft size={16} /> All bookings
      </Link>

      <div className="overflow-hidden rounded-2xl border border-neutral-200 bg-white">
        <div className="flex items-center justify-between bg-ink px-7 py-5 text-white">
          <div>
            <p className="text-xs text-white/50">Booking reference</p>
            <p className="font-display font-semibold">{booking.qrCode}</p>
          </div>
          <Badge tone={statusTone[booking.status]}>{statusLabel(booking.status)}</Badge>
        </div>

        <div className="grid gap-8 p-7 sm:grid-cols-[1fr_auto] sm:items-center">
          <div>
            <p className="font-display text-2xl font-bold text-ink">
              Bay {booking.parkingSlot.slotNumber}
            </p>
            <p className="mt-1 flex items-center gap-1.5 text-sm text-neutral-500">
              <MapPin size={14} /> {booking.parkingSlot.level} · Zone {booking.parkingSlot.zone}
            </p>
            {booking.parkingSlot.hasEvCharger && (
              <p className="mt-1 flex items-center gap-1.5 text-sm text-blue-600">
                <Zap size={14} /> EV charging available
              </p>
            )}

            <dl className="mt-6 grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-neutral-400">Starts</dt>
                <dd className="mt-0.5 font-medium text-ink">{formatDateTime(booking.startTime)}</dd>
              </div>
              <div>
                <dt className="text-neutral-400">Ends</dt>
                <dd className="mt-0.5 font-medium text-ink">{formatDateTime(booking.endTime)}</dd>
              </div>
              <div>
                <dt className="text-neutral-400">Total</dt>
                <dd className="mt-0.5 font-medium text-ink">{formatCurrency(booking.totalCost)}</dd>
              </div>
              <div>
                <dt className="text-neutral-400">Booked</dt>
                <dd className="mt-0.5 font-medium text-ink">{formatDateTime(booking.createdAt)}</dd>
              </div>
            </dl>
          </div>

          <div className="grid justify-items-center gap-3 rounded-xl border border-neutral-100 bg-neutral-50 p-5">
            <QRCodeSVG value={booking.qrCode} size={140} fgColor="#101010" />
            <p className="text-xs text-neutral-400">Scan at the barrier</p>
          </div>
        </div>

        {(booking.status === 'upcoming' || booking.status === 'active') && (
          <div className="border-t border-neutral-100 px-7 py-5">
            <button
              onClick={cancel}
              disabled={cancelling}
              className="text-sm font-medium text-red-500 hover:text-red-600 disabled:opacity-50"
            >
              {cancelling ? 'Cancelling…' : 'Cancel this booking'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
