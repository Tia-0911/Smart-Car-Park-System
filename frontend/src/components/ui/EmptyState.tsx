import type { LucideIcon } from 'lucide-react'

export default function EmptyState({
  icon: Icon,
  title,
  text,
}: {
  icon: LucideIcon
  title: string
  text: string
}) {
  return (
    <div className="grid place-items-center rounded-2xl border border-dashed border-neutral-300 px-6 py-16 text-center">
      <div className="mb-4 grid h-12 w-12 place-items-center rounded-full bg-neutral-100 text-neutral-400">
        <Icon size={22} />
      </div>
      <p className="font-display font-semibold text-ink">{title}</p>
      <p className="mt-1 max-w-sm text-sm text-neutral-500">{text}</p>
    </div>
  )
}
