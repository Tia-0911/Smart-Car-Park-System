import { useState } from 'react'
import type { ReactNode } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import type { LucideIcon } from 'lucide-react'
import { LogOut, Menu, X } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'

export interface NavItem {
  label: string
  to: string
  icon: LucideIcon
  end?: boolean
}

function initials(name: string) {
  return name
    .split(' ')
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

export default function DashboardShell({
  nav,
  brand,
}: {
  nav: NavItem[]
  brand: string
}) {
  const { user, logout } = useAuth()
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)

  const activeItem =
    nav.find((item) => (item.end ? location.pathname === item.to : location.pathname.startsWith(item.to))) ??
    nav[0]

  const sidebarContent = (
    <>
      <div className="px-6 py-7">
        <Link to="/" className="logo logo-invert">
          SMARTPARK
        </Link>
        <p className="mt-3 text-xs tracking-wide text-white/45 uppercase">{brand}</p>
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {nav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={() => setMobileOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-colors ${
                isActive ? 'bg-lime text-ink' : 'text-white/70 hover:bg-white/10 hover:text-white'
              }`
            }
          >
            <item.icon size={18} strokeWidth={2.25} />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-white/10 p-4">
        <div className="flex items-center gap-3 rounded-xl px-2 py-2">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-lime font-display text-xs font-bold text-ink">
            {user ? initials(user.name) : ''}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-white">{user?.name}</p>
            <p className="truncate text-xs text-white/45 capitalize">{user?.role}</p>
          </div>
        </div>
        <button
          onClick={logout}
          className="mt-2 flex w-full items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium text-white/70 transition-colors hover:bg-white/10 hover:text-white"
        >
          <LogOut size={18} strokeWidth={2.25} />
          Log out
        </button>
      </div>
    </>
  )

  return (
    <div className="min-h-screen bg-neutral-50 md:grid md:grid-cols-[260px_1fr]">
      {/* desktop sidebar */}
      <aside className="hidden flex-col bg-ink md:sticky md:top-0 md:flex md:h-screen">
        {sidebarContent}
      </aside>

      {/* mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
          <aside className="relative flex h-full w-72 flex-col bg-ink">{sidebarContent}</aside>
        </div>
      )}

      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-30 flex items-center justify-between gap-4 border-b border-neutral-200 bg-white/90 px-5 py-4 backdrop-blur sm:px-8">
          <div className="flex items-center gap-3">
            <button
              className="grid h-9 w-9 place-items-center rounded-lg text-neutral-500 hover:bg-neutral-100 md:hidden"
              onClick={() => setMobileOpen((v) => !v)}
              aria-label="Toggle menu"
            >
              {mobileOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
            <h2 className="font-display text-lg font-bold text-ink">{activeItem?.label}</h2>
          </div>
          <Link
            to="/"
            className="hidden text-sm font-medium text-neutral-500 hover:text-ink sm:block"
          >
            ← Back to site
          </Link>
        </header>

        <main className="flex-1 px-5 py-8 sm:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export function ShellPage({ children }: { children: ReactNode }) {
  return <div className="mx-auto max-w-6xl">{children}</div>
}
