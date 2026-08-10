import { useEffect, useState } from 'react'
import { api } from '../../api'
import type { Booking, User } from '../../api/types'
import PageHeader from '../../components/ui/PageHeader'
import Spinner from '../../components/ui/Spinner'
import { formatDate } from '../../lib/format'

export default function AdminCustomers() {
  const [customers, setCustomers] = useState<User[] | null>(null)
  const [bookings, setBookings] = useState<Booking[] | null>(null)

  useEffect(() => {
    api.customers.list().then(setCustomers)
    api.bookings.list().then(setBookings)
  }, [])

  if (!customers || !bookings) return <Spinner full />

  return (
    <div>
      <PageHeader title="Customers" text={`${customers.length} registered drivers.`} />

      <div className="overflow-x-auto rounded-2xl border border-neutral-200 bg-white">
        <table className="w-full min-w-[560px] text-sm">
          <thead>
            <tr className="border-b border-neutral-100 text-left text-xs text-neutral-400 uppercase">
              <th className="px-5 py-3 font-medium">Name</th>
              <th className="px-5 py-3 font-medium">Email</th>
              <th className="px-5 py-3 font-medium">Joined</th>
              <th className="px-5 py-3 font-medium">Bookings</th>
            </tr>
          </thead>
          <tbody>
            {customers.map((c) => (
              <tr key={c.id} className="border-b border-neutral-50 last:border-0">
                <td className="px-5 py-3.5 font-medium text-ink">{c.name}</td>
                <td className="px-5 py-3.5 text-neutral-500">{c.email}</td>
                <td className="px-5 py-3.5 text-neutral-500">{formatDate(c.createdAt)}</td>
                <td className="px-5 py-3.5 text-neutral-500">
                  {bookings.filter((b) => b.userId === c.id).length}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
