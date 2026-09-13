import { useEffect, useState } from 'react'
import {
  fetchLeaderboard,
  fetchMyStanding,
  type LeaderboardEntry,
  type PlayerStanding,
} from '../lib/api'

type Scope = 'explorers' | 'merchants'

function currentWeekTimestamp(): number {
  return Math.floor(Date.now() / 1000)
}

function rankBadgeClasses(rank: number): string {
  if (rank === 1) return 'bg-accent text-white'
  if (rank === 2) return 'bg-ink-muted/30 text-ink'
  if (rank === 3) return 'bg-brand/20 text-brand-dark'
  return 'text-ink-muted'
}

interface LeaderboardProps {
  myAddress: string
}

export function Leaderboard({ myAddress }: LeaderboardProps) {
  const [scope, setScope] = useState<Scope>('explorers')
  const [entries, setEntries] = useState<LeaderboardEntry[]>([])
  const [standing, setStanding] = useState<PlayerStanding | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setStanding(null)

    const week = currentWeekTimestamp()

    fetchLeaderboard({ scope, week })
      .then((leaderboardEntries) => {
        if (cancelled) return
        setEntries(leaderboardEntries)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Could not load the leaderboard')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    if (scope === 'explorers') {
      fetchMyStanding({ address: myAddress, week })
        .then((myStanding) => {
          if (!cancelled) setStanding(myStanding)
        })
        .catch(() => {
          // No standing yet (no points this week) — not an error, just nothing to show.
        })
    }

    return () => {
      cancelled = true
    }
  }, [scope, myAddress])

  return (
    <div className="min-h-screen bg-bg px-4 py-6">
      <h1 className="text-lg font-bold text-ink">Zone Rankings</h1>

      <div className="mt-3 flex gap-2 border-b border-border">
        <button
          type="button"
          onClick={() => setScope('explorers')}
          className={`px-3 py-2 text-sm font-medium transition ${
            scope === 'explorers'
              ? 'border-b-2 border-brand text-brand'
              : 'text-ink-muted'
          }`}
        >
          Explorers
        </button>
        <button
          type="button"
          onClick={() => setScope('merchants')}
          className={`px-3 py-2 text-sm font-medium transition ${
            scope === 'merchants'
              ? 'border-b-2 border-brand text-brand'
              : 'text-ink-muted'
          }`}
        >
          Most visited stores
        </button>
      </div>

      <p className="mt-3 text-xs text-ink-muted">This week's ranking · resets every Monday</p>

      {loading && <p className="mt-6 text-center text-ink-muted">Loading...</p>}
      {error && <p className="mt-6 text-center text-red-600">{error}</p>}

      {!loading && !error && (
        <ul className="mt-3 flex flex-col gap-2">
          {entries.map((entry) => (
            <li
              key={entry.address}
              className="flex items-center justify-between rounded-2xl border border-border bg-surface px-4 py-3"
            >
              <div className="flex items-center gap-3">
                <span
                  className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${rankBadgeClasses(entry.rank)}`}
                >
                  {entry.rank}
                </span>
                <span className="font-medium text-ink">{entry.label}</span>
              </div>
              <div className="text-right">
                {scope === 'explorers' ? (
                  <>
                    <p className="font-semibold text-ink">{entry.points} pts</p>
                    <p className="text-xs text-ink-muted">{entry.distinct_merchants} new stores</p>
                  </>
                ) : (
                  <p className="font-semibold text-ink">{entry.visits} visits</p>
                )}
              </div>
            </li>
          ))}
          {entries.length === 0 && (
            <p className="mt-6 text-center text-ink-muted">Nobody here yet this week.</p>
          )}
        </ul>
      )}

      {scope === 'explorers' && standing && (
        <div className="mt-6 rounded-2xl bg-brand-dark p-4 text-white">
          <p className="text-xs uppercase tracking-wide text-white/70">You · this week</p>
          <p className="mt-1 text-2xl font-bold">
            {standing.points} pts <span className="text-sm font-normal">#{standing.rank}</span>
          </p>
          <p className="text-xs text-white/70">{standing.distinct_merchants} new stores</p>
          {standing.points_to_next !== null && (
            <p className="mt-2 text-xs text-white/70">
              {standing.points_to_next} pts more to pass the person above you
            </p>
          )}
        </div>
      )}
    </div>
  )
}