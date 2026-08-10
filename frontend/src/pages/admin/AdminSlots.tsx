import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Pencil, Plus, Trash2, Zap } from 'lucide-react'
import { api } from '../../api'
import type { CreateSlotInput, ParkingSlot } from '../../api/types'
import PageHeader from '../../components/ui/PageHeader'
import Badge from '../../components/ui/Badge'
import Modal from '../../components/ui/Modal'
import Spinner from '../../components/ui/Spinner'
import { formatCurrency } from '../../lib/format'

const emptyForm: CreateSlotInput = {
  slotNumber: '',
  level: 'Level 1',
  zone: 'A',
  hasEvCharger: false,
  pricePerHour: 2,
}

export default function AdminSlots() {
  const [slots, setSlots] = useState<ParkingSlot[] | null>(null)
  const [editing, setEditing] = useState<ParkingSlot | null>(null)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState<CreateSlotInput>(emptyForm)
  const [saving, setSaving] = useState(false)

  const load = () => api.parkingSlots.list().then(setSlots)

  useEffect(() => {
    load()
  }, [])

  const startCreate = () => {
    setForm(emptyForm)
    setCreating(true)
  }

  const startEdit = (slot: ParkingSlot) => {
    setForm({
      slotNumber: slot.slotNumber,
      level: slot.level,
      zone: slot.zone,
      hasEvCharger: slot.hasEvCharger,
      pricePerHour: slot.pricePerHour,
    })
    setEditing(slot)
  }

  const closeModals = () => {
    setCreating(false)
    setEditing(null)
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSaving(true)
    try {
      if (editing) {
        await api.parkingSlots.update(editing.id, form)
      } else {
        await api.parkingSlots.create(form)
      }
      closeModals()
      load()
    } finally {
      setSaving(false)
    }
  }

  const toggleAvailability = async (slot: ParkingSlot) => {
    await api.parkingSlots.update(slot.id, { isAvailable: !slot.isAvailable })
    load()
  }

  const remove = async (slot: ParkingSlot) => {
    if (!window.confirm(`Remove bay ${slot.slotNumber}?`)) return
    await api.parkingSlots.remove(slot.id)
    load()
  }

  if (!slots) return <Spinner full />

  return (
    <div>
      <PageHeader
        title="Parking Slots"
        text={`${slots.length} bays across ${new Set(slots.map((s) => s.level)).size} levels.`}
        action={
          <button className="btn btn-lime" onClick={startCreate}>
            <Plus size={16} /> Add slot
          </button>
        }
      />

      <div className="overflow-x-auto rounded-2xl border border-neutral-200 bg-white">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-neutral-100 text-left text-xs text-neutral-400 uppercase">
              <th className="px-5 py-3 font-medium">Bay</th>
              <th className="px-5 py-3 font-medium">Location</th>
              <th className="px-5 py-3 font-medium">Rate</th>
              <th className="px-5 py-3 font-medium">Status</th>
              <th className="px-5 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {slots.map((slot) => (
              <tr key={slot.id} className="border-b border-neutral-50 last:border-0">
                <td className="px-5 py-3.5 font-display font-semibold text-ink">
                  {slot.slotNumber}
                  {slot.hasEvCharger && <Zap size={14} className="ml-1.5 inline text-blue-500" />}
                </td>
                <td className="px-5 py-3.5 text-neutral-500">
                  {slot.level} · Zone {slot.zone}
                </td>
                <td className="px-5 py-3.5 text-neutral-500">{formatCurrency(slot.pricePerHour)}/hr</td>
                <td className="px-5 py-3.5">
                  <button onClick={() => toggleAvailability(slot)}>
                    <Badge tone={slot.isAvailable ? 'lime' : 'neutral'}>
                      {slot.isAvailable ? 'Available' : 'Occupied'}
                    </Badge>
                  </button>
                </td>
                <td className="px-5 py-3.5">
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => startEdit(slot)}
                      className="text-neutral-400 hover:text-ink"
                      aria-label="Edit"
                    >
                      <Pencil size={16} />
                    </button>
                    <button
                      onClick={() => remove(slot)}
                      className="text-neutral-400 hover:text-red-500"
                      aria-label="Delete"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {(creating || editing) && (
        <Modal title={editing ? `Edit bay ${editing.slotNumber}` : 'Add a new bay'} onClose={closeModals}>
          <form className="grid gap-4" onSubmit={submit}>
            <div>
              <label className="mb-1 block text-xs font-semibold tracking-wide text-neutral-500 uppercase">
                Bay number
              </label>
              <input
                className="field-light"
                value={form.slotNumber}
                onChange={(e) => setForm({ ...form, slotNumber: e.target.value })}
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-xs font-semibold tracking-wide text-neutral-500 uppercase">
                  Level
                </label>
                <input
                  className="field-light"
                  value={form.level}
                  onChange={(e) => setForm({ ...form, level: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold tracking-wide text-neutral-500 uppercase">
                  Zone
                </label>
                <input
                  className="field-light"
                  value={form.zone}
                  onChange={(e) => setForm({ ...form, zone: e.target.value })}
                  required
                />
              </div>
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold tracking-wide text-neutral-500 uppercase">
                Price per hour (£)
              </label>
              <input
                type="number"
                min={0}
                step={0.5}
                className="field-light"
                value={form.pricePerHour}
                onChange={(e) => setForm({ ...form, pricePerHour: Number(e.target.value) })}
                required
              />
            </div>

            <label className="flex items-center gap-2 text-sm font-medium text-ink">
              <input
                type="checkbox"
                className="accent-lime"
                checked={form.hasEvCharger}
                onChange={(e) => setForm({ ...form, hasEvCharger: e.target.checked })}
              />
              Has EV charger
            </label>

            <button className="btn btn-lime w-full disabled:opacity-60" disabled={saving}>
              {saving ? 'Saving…' : editing ? 'Save changes' : 'Add slot'}
            </button>
          </form>
        </Modal>
      )}
    </div>
  )
}
