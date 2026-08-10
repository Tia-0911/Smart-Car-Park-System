import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Menu, X } from 'lucide-react'

const links = [
  { label: 'Home', href: '/' },
  { label: 'Why us', href: '/#why' },
  { label: 'How it works', href: '/#how' },
  { label: 'FAQ', href: '/#faq' },
  { label: 'Contact', href: '/#contact' },
]

function Navbar() {
  const [open, setOpen] = useState(false)

  return (
    <header className="absolute inset-x-0 top-0 z-20 py-5">
      <div className="mx-auto flex max-w-[1180px] items-center justify-between gap-5 px-6">
        <Link to="/" className="logo">
          SMARTPARK
        </Link>

        <button
          className="text-white md:hidden"
          aria-label="Toggle menu"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X size={26} /> : <Menu size={26} />}
        </button>

        <nav
          className={`${
            open ? 'flex' : 'hidden'
          } absolute inset-x-6 top-full flex-col items-start gap-4 rounded-2xl bg-neutral-950/95 p-6 md:static md:flex md:flex-row md:items-center md:gap-8 md:rounded-none md:bg-transparent md:p-0`}
        >
          {links.map((link) => (
            <a
              key={link.label}
              href={link.href}
              onClick={() => setOpen(false)}
              className="font-display text-sm text-white/90 transition-colors hover:text-lime"
            >
              {link.label}
            </a>
          ))}
          <Link to="/login" onClick={() => setOpen(false)} className="btn btn-lime">
            Get started
          </Link>
        </nav>
      </div>
    </header>
  )
}

export default Navbar
