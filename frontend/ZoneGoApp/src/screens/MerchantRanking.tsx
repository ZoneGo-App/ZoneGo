interface MerchantRankingProps {
  // Wired to real values once Lucio adds a campaign_id filter to
  // /leaderboard. Until then this always renders empty — there is no way
  // to know today which explorers visited this specific store most.
  topVisitors?: { label: string; visits: number }[]
}

export function MerchantRanking({ topVisitors = [] }: MerchantRankingProps) {
  return (
    <div className="min-h-screen bg-bg px-4 py-6">
      <p className="text-xs uppercase tracking-wide text-ink-muted">Your store</p>
      <h1 className="text-2xl font-bold text-ink">Top visitors</h1>

      <div className="mt-4 rounded-2xl border border-accent/30 bg-accent/10 p-4">
        <p className="text-sm font-semibold text-accent">Coming soon</p>
        <p className="mt-1 text-sm text-ink">
          This ranking will show which explorers visit your store the most.
        </p>
        <p className="mt-1 text-xs text-ink-muted">
          Today's leaderboard only tracks explorers and stores globally — a
          per-store breakdown needs a new endpoint first.
        </p>
      </div>

      <div className="mt-4 rounded-2xl border border-border bg-surface p-4">
        <p className="mb-2 text-sm font-semibold text-ink">This week</p>
        {topVisitors.length === 0 ? (
          <p className="text-sm text-ink-muted">No visitor data to show yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {topVisitors.map((visitor, index) => (
              <li
                key={visitor.label}
                className="flex items-center justify-between rounded-xl border border-border px-3 py-2"
              >
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand/10 text-xs font-semibold text-brand-dark">
                    {index + 1}
                  </span>
                  <span className="font-medium text-ink">{visitor.label}</span>
                </div>
                <span className="text-sm text-ink-muted">{visitor.visits} visits</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}