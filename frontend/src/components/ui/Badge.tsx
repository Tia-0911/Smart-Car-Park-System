import type { ReactNode } from 'react'

const tones = {
  lime: 'bg-lime/20 text-lime-dark',
  neutral: 'bg-neutral-100 text-neutral-600',
  blue: 'bg-blue-50 text-blue-600',
  red: 'bg-red-50 text-red-600',
  amber: 'bg-amber-50 text-amber-600',
} as const

export default function Badge({
  children,
  tone = 'neutral',
}: {
  children: ReactNode
  tone?: keyof typeof tones
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-display text-xs font-semibold ${tones[tone]}`}
    >
      {children}
    </span>
  )
}
