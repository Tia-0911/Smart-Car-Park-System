import type { LucideIcon } from 'lucide-react'

export default function StatCard({
  label,
  value,
  icon: Icon,
  trend,
}: {
  label: string
  value: string
  icon: LucideIcon
  trend?: string
}) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5">
      <div className="flex items-start justify-between">
        <p className="text-sm font-medium text-neutral-500">{label}</p>
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-lime/20 text-lime-dark">
          <Icon size={18} strokeWidth={2.25} />
        </div>
      </div>
      <p className="mt-3 font-display text-3xl font-bold tracking-tight text-ink">{value}</p>
      {trend && <p className="mt-1 text-xs text-neutral-400">{trend}</p>}
    </div>
  )
}
