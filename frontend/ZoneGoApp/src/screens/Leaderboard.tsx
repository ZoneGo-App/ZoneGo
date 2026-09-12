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
    <div className="min-h-screen px-4 py-6">
      <h1 className="text-lg font-bold">Zone Rankings</h1>

      <div className="mt-3 flex gap-2 border-b border-gray-200">
        <button
          type="button"
          onClick={() => setScope('explorers')}
          className={`px-3 py-2 text-sm font-medium ${
            scope === 'explorers'
              ? 'border-b-2 border-black text-black'
              : 'text-gray-400'
          }`}
        >
          Explorers
        </button>
        <button
          type="button"
          onClick={() => setScope('merchants')}
          className={`px-3 py-2 text-sm font-medium ${
            scope === 'merchants'
              ? 'border-b-2 border-black text-black'
              : 'text-gray-400'
          }`}
        >
          Most visited stores
        </button>
      </div>

      <p className="mt-3 text-xs text-gray-400">This week's ranking · resets every Monday</p>

      {loading && <p className="mt-6 text-center text-gray-500">Loading...</p>}
      {error && <p className="mt-6 text-center text-red-600">{error}</p>}

      {!loading && !error && (
        <ul className="mt-3 flex flex-col gap-2">
          {entries.map((entry) => (
            <li
              key={entry.address}
              className="flex items-center justify-between rounded-lg border border-gray-200 px-4 py-3"
            >
              <div className="flex items-center gap-3">
                <span className="w-5 text-sm font-semibold text-gray-500">#{entry.rank}</span>
                <span className="font-medium">{entry.label}</span>
              </div>
              <div className="text-right">
                {scope === 'explorers' ? (
                  <>
                    <p className="font-semibold">{entry.points} pts</p>
                    <p className="text-xs text-gray-400">{entry.distinct_merchants} new stores</p>
                  </>
                ) : (
                  <p className="font-semibold">{entry.visits} visits</p>
                )}
              </div>
            </li>
          ))}
          {entries.length === 0 && (
            <p className="mt-6 text-center text-gray-500">Nobody here yet this week.</p>
          )}
        </ul>
      )}

      {scope === 'explorers' && standing && (
        <div className="mt-6 rounded-xl bg-black p-4 text-white">
          <p className="text-xs uppercase text-gray-300">You · this week</p>
          <p className="mt-1 text-2xl font-bold">
            {standing.points} pts <span className="text-sm font-normal">#{standing.rank}</span>
          </p>
          <p className="text-xs text-gray-300">{standing.distinct_merchants} new stores</p>
          {standing.points_to_next !== null && (
            <p className="mt-2 text-xs text-gray-300">
              {standing.points_to_next} pts more to pass the person above you
            </p>
          )}
        </div>
      )}
    </div>
  )
}