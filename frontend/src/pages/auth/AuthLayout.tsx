import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Check } from 'lucide-react'

const perks = [
  'Live availability at 150+ connected car parks',
  'Reserve a guaranteed bay in 20 seconds',
  'Barrier-free entry with plate recognition',
  'One receipt for parking and EV charging',
]

export default function AuthLayout({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <div className="grid min-h-screen md:grid-cols-2">
      <aside
        className="flex min-h-[300px] flex-col justify-between bg-cover bg-center px-8 py-12 text-white sm:px-12"
        style={{
          backgroundImage:
            "linear-gradient(rgba(8,8,8,.66),rgba(8,8,8,.66)), url('https://images.unsplash.com/photo-1590674899484-d5640e854abe?auto=format&fit=crop&w=1200&q=80')",
        }}
      >
        <Link to="/" className="logo w-fit">
          SMARTPARK
        </Link>

        <div>
          <h2 className="font-display text-3xl font-bold tracking-tight">
            Park smarter from your very first trip.
          </h2>
          <ul className="mt-6 grid gap-3 text-sm text-white/85">
            {perks.map((perk) => (
              <li key={perk} className="flex items-start gap-2.5">
                <Check size={16} className="mt-0.5 shrink-0 text-lime" strokeWidth={3} />
                {perk}
              </li>
            ))}
          </ul>
        </div>

        <p className="text-sm text-white/55">
          Free to join. No booking fees on your first three sessions.
        </p>
      </aside>

      <main className="grid place-items-center px-6 py-14">
        <div className="w-full max-w-[420px]">
          <p className="eyebrow">{title === 'Join SmartPark' ? 'Create your account' : 'Welcome back'}</p>
          <h1 className="font-display text-3xl font-bold tracking-tight">{title}</h1>
          {children}
        </div>
      </main>
    </div>
  )
}
