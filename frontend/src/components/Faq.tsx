import { useState } from 'react'
import { Plus } from 'lucide-react'

const faqs = [
  {
    q: 'Do I need to reserve in advance?',
    a: 'You never have to — but it pays to. Drive-in guests are matched to whatever is free the moment they arrive, while reserved drivers get a bay held under their plate for a 30-minute grace window and skip the queue at the barrier entirely. On match days, festival weekends and airport runs, our busiest sites sell out hours ahead, so a 20-second booking is the difference between parking and circling.',
  },
  {
    q: 'How do I extend my parking time?',
    a: 'Tap "Extend" in the app, or reply to the SMS we send you fifteen minutes before your session ends. Time is added instantly at the same hourly rate — no walking back to the machine, no returning to your car, no fine. If the bay is booked by someone else after you, we tell you up front and offer the nearest alternative.',
  },
  {
    q: 'Is my payment information secure?',
    a: 'Yes. Card details never touch our servers — they are tokenised by our PCI-DSS Level 1 payment provider and stored as an encrypted reference only. Every session is protected with 3-D Secure, and you can revoke a saved card from your account in one tap.',
  },
  {
    q: 'What happens if the space I booked is taken?',
    a: 'Our sensors know within seconds, and so do you. We reassign you to the nearest free bay on the same level before you reach the barrier, and the difference in price — if there is one — is on us. If nothing suitable is free on site, the booking is refunded in full automatically.',
  },
  {
    q: 'Can I charge my electric vehicle while I park?',
    a: 'Over 60% of our sites have 7kW and 22kW bays, with rapid 50kW chargers at flagship locations. Filter for "EV" when you search, and charging is billed per kWh on the same receipt as your parking — one payment, one invoice, no separate app or RFID card.',
  },
  {
    q: 'Do you offer plans for businesses and fleets?',
    a: 'We do. Fleet and employee accounts get pooled billing, per-driver spend limits, priority bays at chosen sites and a live dashboard of every session. Most teams of ten or more save around 20% against pay-as-you-go — talk to us and we will model it against your last three months of parking spend.',
  },
]

function Faq() {
  const [open, setOpen] = useState<number | null>(0)

  return (
    <section id="faq" className="bg-ink py-24 text-white">
      <div className="mx-auto max-w-[1180px] px-6">
        <h2 className="font-display text-4xl font-bold tracking-tight sm:text-5xl">
          Frequently Asked Questions
        </h2>

        <div className="mt-12 border-t border-white/15">
          {faqs.map((item, index) => {
            const isOpen = open === index
            return (
              <div key={item.q} className="border-b border-white/15">
                <button
                  className={`flex w-full items-center justify-between gap-6 py-6 text-left font-display text-lg font-semibold transition-colors ${
                    isOpen ? 'text-lime' : 'text-white hover:text-lime'
                  }`}
                  aria-expanded={isOpen}
                  onClick={() => setOpen(isOpen ? null : index)}
                >
                  <span>{item.q}</span>
                  <Plus
                    size={22}
                    className={`shrink-0 transition-transform duration-300 ${isOpen ? 'rotate-45' : ''}`}
                  />
                </button>
                <div
                  className={`grid overflow-hidden transition-all duration-300 ${
                    isOpen ? 'grid-rows-[1fr] pb-6 opacity-100' : 'grid-rows-[0fr] opacity-0'
                  }`}
                >
                  <div className="overflow-hidden">
                    <p className="max-w-3xl text-[0.94rem] leading-relaxed text-white/65">
                      {item.a}
                    </p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}

export default Faq
