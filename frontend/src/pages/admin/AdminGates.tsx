import { useEffect, useState } from 'react'
import { DoorOpen } from 'lucide-react'
import { api } from '../../api'
import type { Gate } from '../../api/types'
import PageHeader from '../../components/ui/PageHeader'
import Badge from '../../components/ui/Badge'
import Spinner from '../../components/ui/Spinner'

export default function AdminGates() {
  const [gates, setGates] = useState<Gate[] | null>(null)
  const [togglingId, setTogglingId] = useState<number | null>(null)

  useEffect(() => {
    api.gates.list().then(setGates)
  }, [])

  const toggle = async (gate: Gate) => {
    setTogglingId(gate.id)
    const updated = await api.gates.toggle(gate.id)
    setGates((prev) => prev!.map((g) => (g.id === updated.id ? updated : g)))
    setTogglingId(null)
  }

  if (!gates) return <Spinner full />

  return (
    <div>
      <PageHeader title="Gates" text="Open or close barriers remotely." />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {gates.map((gate) => (
          <div key={gate.id} className="rounded-2xl border border-neutral-200 bg-white p-6">
            <div className="flex items-start justify-between">
              <div className="grid h-11 w-11 place-items-center rounded-xl bg-lime/20 text-lime-dark">
                <DoorOpen size={20} />
              </div>
              <Badge tone={gate.isOpen ? 'lime' : 'neutral'}>{gate.isOpen ? 'Open' : 'Closed'}</Badge>
            </div>

            <p className="mt-4 font-display font-bold text-ink">{gate.gateName}</p>
            <p className="text-sm text-neutral-500">{gate.location}</p>

            <button
              onClick={() => toggle(gate)}
              disabled={togglingId === gate.id}
              className={`btn mt-5 w-full text-sm disabled:opacity-60 ${
                gate.isOpen ? 'border border-neutral-200 bg-white text-ink hover:bg-neutral-50' : 'btn-lime'
              }`}
            >
              {togglingId === gate.id ? 'Working…' : gate.isOpen ? 'Close gate' : 'Open gate'}
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
