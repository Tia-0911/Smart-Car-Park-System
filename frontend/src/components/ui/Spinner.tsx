export default function Spinner({ full = false }: { full?: boolean }) {
  const spin = (
    <div className="h-8 w-8 animate-spin rounded-full border-2 border-neutral-200 border-t-lime" />
  )
  if (!full) return spin
  return <div className="grid min-h-[40vh] place-items-center">{spin}</div>
}
