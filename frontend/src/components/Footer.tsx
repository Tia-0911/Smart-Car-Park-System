import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'

const usefulLinks = [
  { label: 'Find parking', href: '/#why' },
  { label: 'Monthly permits', href: '/#why' },
  { label: 'EV charging bays', href: '/#why' },
  { label: 'For businesses', href: '/#contact' },
  { label: 'Operator login', href: '/login' },
]

const socials = [
  { mark: 'f', label: 'Facebook' },
  { mark: 'X', label: 'X' },
  { mark: 'in', label: 'LinkedIn' },
]

function Footer() {
  const handleSignup = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    event.currentTarget.reset()
  }

  return (
    <footer className="bg-ink pt-18 text-white">
      <div className="mx-auto max-w-[1180px] px-6">
        <div className="grid gap-10 pb-14 md:grid-cols-[1.4fr_1fr_1fr] md:gap-12">
          <div>
            <h4 className="max-w-[26ch] font-display text-lg font-bold">
              Sign up here for regular updates on new sites and offers
            </h4>
            <p className="mt-4 mb-4 text-sm text-white/55">
              One short email a month — new locations, launch discounts, no spam.
            </p>
            <form className="flex max-w-md items-center gap-3.5" onSubmit={handleSignup}>
              <input
                className="field-dark"
                type="email"
                name="newsletter"
                placeholder="Enter a valid email address"
                required
              />
              <button className="btn btn-lime shrink-0" type="submit">
                Submit
              </button>
            </form>
          </div>

          <div>
            <h4 className="font-display text-lg font-bold">Useful links</h4>
            <div className="mt-4 grid gap-2.5 text-sm text-white/70">
              {usefulLinks.map((link) => (
                <a key={link.label} href={link.href} className="hover:text-lime">
                  {link.label}
                </a>
              ))}
            </div>
          </div>

          <div>
            <h4 className="font-display text-lg font-bold">Our contact</h4>
            <div className="mt-4 space-y-1.5 text-sm text-white/70">
              <div>
                Call us: <strong className="font-medium text-white">+44 (0) 114 225 5555</strong>
              </div>
              <div>
                Email: <strong className="font-medium text-white">support@smartparking.io</strong>
              </div>
              <div>Unit 4, Arundel Gate, Sheffield S1 2PP</div>
            </div>
            <div className="mt-5 flex gap-3">
              {socials.map(({ mark, label }) => (
                <a
                  key={label}
                  href="/#why"
                  aria-label={`SmartPark on ${label}`}
                  className="grid h-9 w-9 place-items-center rounded-full bg-lime font-display text-xs font-bold text-ink transition-transform hover:-translate-y-0.5"
                >
                  {mark}
                </a>
              ))}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-4 border-t border-white/15 py-6">
          <Link to="/" className="logo logo-invert">
            SMARTPARK
          </Link>
          <small className="text-white/50">
            © {new Date().getFullYear()} SmartPark. Smarter kerbside for every city.
          </small>
        </div>
      </div>
    </footer>
  )
}

export default Footer
