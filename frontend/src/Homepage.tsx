import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Check } from 'lucide-react'
import Navbar from './components/Navbar'
import Faq from './components/Faq'
import Footer from './components/Footer'

const perks = [
  {
    title: 'Real-time availability',
    text: 'Bay-level sensors refresh every few seconds, so you see what is actually free — not what was free ten minutes ago.',
  },
  {
    title: 'Easy payments',
    text: 'Pay by card, mobile wallet, or online — no cash, no coins, no hunting for a working machine in the rain.',
  },
  {
    title: 'Safe & secure',
    text: '24/7 monitored, gated and well-lit lots with ANPR entry, so your car is watched even when you are not.',
  },
  {
    title: 'Flexible plans',
    text: 'Hourly, daily, and monthly options that fit your schedule and budget — cancel or switch any time you like.',
  },
]

const steps = [
  {
    title: '1. Search your location',
    text: 'Open the app or the website, drop a pin on where you are heading, and see every nearby space with live prices.',
  },
  {
    title: '2. Reserve or drive-in',
    text: 'Book ahead to lock in your rate, or just pull up to any available lot and let the cameras do the rest.',
  },
  {
    title: '3. Park & go',
    text: 'Your space is guaranteed — no circling the block. The barrier lifts on your plate and the clock starts itself.',
  },
]

function Homepage() {
  const [sent, setSent] = useState(false)

  const handleQuote = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    event.currentTarget.reset()
    setSent(true)
  }

  return (
    <>
      <Navbar />

      {/* ---------------- hero ---------------- */}
      <section
        className="relative flex min-h-[720px] items-center bg-cover bg-center pt-[150px] pb-24 text-white"
        style={{
          backgroundImage:
            "linear-gradient(rgba(8,8,8,.62),rgba(8,8,8,.62)), url('https://images.unsplash.com/photo-1573348722427-f1d6819fdf98?auto=format&fit=crop&w=1900&q=80')",
        }}
      >
        <div className="mx-auto grid w-full max-w-[1180px] gap-14 px-6 md:grid-cols-2 md:items-center">
          <div>
            <div className="mb-6 grid h-14 w-14 place-items-center rounded-[10px] bg-lime font-display text-2xl font-bold text-ink">
              P
            </div>
            <h1 className="max-w-[8ch] font-display text-5xl font-bold tracking-tight sm:text-6xl lg:text-7xl">
              Premium City Parking Made Easy
            </h1>
            <p className="mt-6 text-sm text-white/70">
              Live availability across <strong className="text-lime">150+ connected car parks</strong>{' '}
              — book in 20 seconds, park in minutes.
            </p>
          </div>

          <form
            className="rounded-[22px] bg-neutral-900/80 p-9 backdrop-blur"
            onSubmit={handleQuote}
          >
            <h2 className="font-display text-2xl font-bold">Quick Services Request</h2>
            <p className="mt-1 mb-6 text-sm font-medium text-white/80">
              24 Hours Services Available!
            </p>

            <div className="grid gap-x-4 sm:grid-cols-2">
              <input
                className="field-dark mb-5"
                type="email"
                name="email"
                placeholder="Enter a valid email address"
                required
              />
              <input
                className="field-dark mb-5"
                type="text"
                name="name"
                placeholder="Enter your Name"
                required
              />
            </div>

            <div className="grid gap-x-4 sm:grid-cols-2">
              <input className="field-dark mb-5" type="text" name="zipcode" placeholder="Zipcode" />
              <input
                className="field-dark mb-5"
                type="tel"
                name="phone"
                placeholder="Enter your phone (e.g. +14155…)"
              />
            </div>

            <textarea
              className="field-dark mb-5 min-h-[54px] resize-y"
              name="message"
              rows={2}
              placeholder="Enter your message here"
            />

            {sent && (
              <p className="mb-4 text-sm text-lime">
                Thanks — a parking advisor will call you back within the hour.
              </p>
            )}

            <button className="btn btn-lime w-full" type="submit">
              Submit
            </button>
          </form>
        </div>
      </section>

      {/* ---------------- find & book ---------------- */}
      <section className="py-24">
        <div className="mx-auto grid max-w-[1180px] items-center gap-16 px-6 md:grid-cols-2">
          <div>
            <img
              className="h-[400px] w-full object-cover"
              src="https://images.unsplash.com/photo-1590674899484-d5640e854abe?auto=format&fit=crop&w=1200&q=80"
              alt="Bright, empty underground car park with marked bays"
              loading="lazy"
            />
          </div>
          <div>
            <h2 className="font-display text-4xl font-bold tracking-tight sm:text-5xl">
              Find and book your perfect parking spot in seconds
            </h2>
            <p className="mt-6 mb-8 max-w-[46ch] text-[1.02rem] leading-relaxed text-neutral-500">
              Whether you are commuting to work, heading downtown, or catching a flight — we have
              a parking space waiting for you. One search shows every nearby bay, what it costs
              today, and how long the walk is at the other end.
            </p>
            <Link className="btn btn-lime" to="/login">
              Find
            </Link>
          </div>
        </div>
      </section>

      {/* ---------------- why choose us ---------------- */}
      <section id="why" className="py-18">
        <div className="mx-auto max-w-[1180px] px-6">
          <h2 className="font-display text-4xl font-bold tracking-tight sm:text-5xl">
            Why Choose Us?
          </h2>
          <div className="mt-14 grid gap-10 sm:grid-cols-2 sm:gap-x-18 sm:gap-y-14">
            {perks.map((perk) => (
              <article key={perk.title}>
                <div className="mb-4.5 grid h-8 w-8 place-items-center rounded-md border-2 border-lime text-lime">
                  <Check size={18} strokeWidth={3} />
                </div>
                <h3 className="font-display text-base font-medium tracking-[0.14em] uppercase">
                  {perk.title}
                </h3>
                <p className="mt-3 text-sm text-neutral-500 italic">{perk.text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------- app band ---------------- */}
      <section
        className="bg-cover bg-center py-28 text-center text-white"
        style={{
          backgroundImage:
            "linear-gradient(rgba(8,8,8,.5),rgba(8,8,8,.5)), url('https://images.unsplash.com/photo-1470224114660-3f6686c562eb?auto=format&fit=crop&w=1900&q=80')",
        }}
      >
        <div className="mx-auto max-w-[1180px] px-6">
          <h2 className="font-display text-4xl font-bold tracking-tight sm:text-5xl">
            Download Our App
          </h2>
          <p className="mx-auto mt-4.5 max-w-[54ch] text-white/85">
            Get full access to features, manage reservations, and receive live updates the moment
            a space opens up near you.
          </p>
          <p className="mt-3.5 font-display font-semibold">
            Available on{' '}
            <a href="/#why" className="border-b border-transparent text-lime hover:border-lime">
              iOS
            </a>{' '}
            and{' '}
            <a href="/#why" className="border-b border-transparent text-lime hover:border-lime">
              Android
            </a>
          </p>
        </div>
      </section>

      {/* ---------------- how it works ---------------- */}
      <section id="how" className="grid md:grid-cols-2">
        <div className="bg-lime px-8 py-14 text-ink sm:px-14">
          <h2 className="mb-10 font-display text-4xl font-bold tracking-tight sm:text-5xl">
            How It Works:
          </h2>
          {steps.map((step, i) => (
            <div key={step.title} className={i > 0 ? 'mt-8.5' : ''}>
              <h3 className="mb-2 font-display text-base font-medium tracking-[0.12em] uppercase">
                {step.title}
              </h3>
              <p className="text-sm text-ink/75">{step.text}</p>
            </div>
          ))}
        </div>
        <div>
          <img
            className="h-full min-h-[320px] w-full object-cover md:min-h-[460px]"
            src="https://images.unsplash.com/photo-1506521781263-d8422e82f27a?auto=format&fit=crop&w=1200&q=80"
            alt="Aerial view of a car park with marked bays"
            loading="lazy"
          />
        </div>
      </section>

      {/* ---------------- faq ---------------- */}
      <Faq />

      {/* ---------------- contact ---------------- */}
      <section id="contact" className="py-24">
        <div className="mx-auto grid max-w-[1180px] items-center gap-16 px-6 md:grid-cols-2">
          <div>
            <h2 className="font-display text-4xl font-bold tracking-tight sm:text-5xl">
              Have Questions?
            </h2>
            <p className="mt-3.5 mb-4 font-display text-lg font-semibold">We're here to help</p>
            <p className="max-w-[46ch] text-[1.02rem] leading-relaxed text-neutral-500">
              Offer convenient, managed parking for your employees and visitors. Contact us to
              learn about our corporate solutions — pooled billing, reserved bays, and a live
              dashboard of every session your team runs.
            </p>

            <p className="mt-6.5 font-display text-sm font-semibold tracking-wide uppercase">
              Call us:
            </p>
            <a className="block font-display text-lg hover:text-lime-dark" href="tel:+441142255555">
              +44 (0) 114 225 5555
            </a>

            <p className="mt-6.5 font-display text-sm font-semibold tracking-wide uppercase">
              Email:
            </p>
            <a
              className="block font-display text-lg hover:text-lime-dark"
              href="mailto:support@smartparking.io"
            >
              support@smartparking.io
            </a>

            <div className="mt-7.5">
              <a className="btn btn-lime" href="tel:+441142255555">
                Order a call
              </a>
            </div>
          </div>

          <div>
            <img
              className="h-[400px] w-full object-cover"
              src="https://images.unsplash.com/photo-1573497019940-1c28c88b4f3e?auto=format&fit=crop&w=900&q=80"
              alt="SmartPark customer support advisor"
              loading="lazy"
            />
          </div>
        </div>
      </section>

      <Footer />
    </>
  )
}

export default Homepage
