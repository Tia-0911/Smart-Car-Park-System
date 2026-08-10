import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="grid min-h-screen place-items-center px-6 text-center">
      <div>
        <p className="font-display text-6xl font-bold text-lime">404</p>
        <p className="mt-3 text-neutral-500">That page doesn't exist.</p>
        <Link to="/" className="btn btn-lime mt-6">
          Back to home
        </Link>
      </div>
    </div>
  )
}
