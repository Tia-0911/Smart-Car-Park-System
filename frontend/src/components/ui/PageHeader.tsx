import type { ReactNode } from 'react'

export default function PageHeader({
  title,
  text,
  action,
}: {
  title: string
  text?: string
  action?: ReactNode
}) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight text-ink sm:text-3xl">
          {title}
        </h1>
        {text && <p className="mt-1.5 text-sm text-neutral-500">{text}</p>}
      </div>
      {action}
    </div>
  )
}
