import { usePrivy } from '@privy-io/react-auth'
import { useRole } from '../context/RoleContext'
import { formatUsd } from '../lib/api'

const ATTESTATION_STORAGE_KEY = 'zonego_attestation'

interface MyPanelProps {
  // Wired to real values once Lucio exposes an endpoint for a visitor's
  // earnings/visit history. Until then this always renders as zero/empty —
  // that is the true current state (zero real visits exist system-wide),
  // not a placeholder standing in for numbers we haven't built yet.
  totalEarnedMicroUsd?: number
  verifiedVisitCount?: number
}

export function MyPanel({ totalEarnedMicroUsd = 0, verifiedVisitCount = 0 }: MyPanelProps) {
  const { logout } = usePrivy()
  const { setRole } = useRole()

  async function handleLogout() {
    setRole(null)
    localStorage.removeItem(ATTESTATION_STORAGE_KEY)
    await logout()
  }

  return (
    <div className="min-h-screen bg-bg px-4 py-6">
      <p className="text-xs uppercase tracking-wide text-ink-muted">Your earnings</p>
      <h1 className="text-2xl font-bold text-ink">My Panel</h1>

      <div className="mt-4 rounded-2xl bg-brand-dark p-4 text-white">
        <p className="text-xs uppercase tracking-wide text-white/70">Total earned</p>
        <p className="mt-1 text-3xl font-bold">{formatUsd(totalEarnedMicroUsd)}</p>
        <p className="text-xs text-white/70">
          from {verifiedVisitCount} verified {verifiedVisitCount === 1 ? 'visit' : 'visits'}
        </p>
      </div>

      <div className="mt-4 rounded-2xl border border-accent/30 bg-accent/10 p-4">
        <p className="text-sm font-semibold text-accent">Typical earnings</p>
        <p className="mt-1 text-sm text-ink">1 visit: $0.05–0.15 · 10 visits: $0.50–1.50</p>
        <p className="mt-1 text-xs text-ink-muted">
          This is side money, not a salary — explore stores you already like.
        </p>
      </div>

      <div className="mt-4 rounded-2xl border border-border bg-surface p-4">
        <p className="mb-2 text-sm font-semibold text-ink">Verified places</p>
        {verifiedVisitCount === 0 ? (
          <p className="text-sm text-ink-muted">
            You haven't verified any visits yet — search nearby and scan your first QR to see it here.
          </p>
        ) : null}
        {/* Once verified visits exist, list them here — one row per visit,
            with the place name, timestamp, and amount paid. */}
      </div>

      <button
        type="button"
        onClick={handleLogout}
        className="mt-6 w-full rounded-full border border-border py-3 text-sm font-medium text-ink-muted"
      >
        Log out
      </button>
    </div>
  )
}