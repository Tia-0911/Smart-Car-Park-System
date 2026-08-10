import type { BookingStatus } from '../api/types'

export function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

export function formatCurrency(amount: number) {
  return new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' }).format(amount)
}

export const statusTone: Record<BookingStatus, 'lime' | 'blue' | 'neutral' | 'red'> = {
  active: 'lime',
  upcoming: 'blue',
  completed: 'neutral',
  cancelled: 'red',
}

export function statusLabel(status: BookingStatus) {
  return status.charAt(0).toUpperCase() + status.slice(1)
}
