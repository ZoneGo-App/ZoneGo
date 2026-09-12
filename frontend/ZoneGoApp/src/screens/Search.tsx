import { useEffect, useState } from 'react'
import { searchCampaigns, formatUsd, formatDistance, type SearchHit } from '../lib/api'

const RADIUS_OPTIONS_KM = [1, 5, 10] as const
const SEARCH_DEBOUNCE_MS = 400

function useCoords() {
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const forced = import.meta.env.VITE_DEV_FORCE_LOCATION
    if (forced) {
      console.warn(
        '[ZoneGo] Location forced for local development:',
        forced,
        '— remove VITE_DEV_FORCE_LOCATION from .env before deploying.',
      )
      const [lat, lon] = forced.split(',').map(Number)
      setCoords({ lat, lon })
      return
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => setCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      () => setError("We couldn't find you. Turn on location and try again."),
    )
  }, [])

  return { coords, error }
}

/** Delays following a fast-changing value, without delaying the render of the input itself. */
function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timeoutId = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timeoutId)
  }, [value, delayMs])

  return debounced
}

interface SearchProps {
  onSelectCampaign: (hit: SearchHit) => void
}

export function Search({ onSelectCampaign }: SearchProps) {
  const [radiusKm, setRadiusKm] = useState<1 | 5 | 10>(1)
  const [query, setQuery] = useState('')
  const debouncedQuery = useDebouncedValue(query, SEARCH_DEBOUNCE_MS)
  const { coords, error: locationError } = useCoords()
  const [results, setResults] = useState<SearchHit[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(locationError)

  useEffect(() => {
    if (!coords) return

    let cancelled = false
    setLoading(true)
    setError(null)

    searchCampaigns({ lat: coords.lat, lon: coords.lon, radiusKm, query: debouncedQuery })
      .then((hits) => {
        if (!cancelled) setResults(hits)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [coords, radiusKm, debouncedQuery])

  return (
    <div className="min-h-screen px-4 py-6">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder='Search for something, e.g. "sneakers"'
        className="w-full rounded-lg border border-gray-300 px-4 py-3 text-base"
      />

      <div className="mt-3 flex gap-2">
        {RADIUS_OPTIONS_KM.map((km) => (
          <button
            key={km}
            type="button"
            onClick={() => setRadiusKm(km)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium ${
              radiusKm === km
                ? 'bg-black text-white'
                : 'border border-gray-300 text-gray-700'
            }`}
          >
            {km} km
          </button>
        ))}
      </div>

      {!coords && !error && (
        <p className="mt-6 text-center text-gray-500">Finding you...</p>
      )}
      {error && <p className="mt-6 text-center text-red-600">{error}</p>}
      {loading && <p className="mt-6 text-center text-gray-500">Searching...</p>}

      {!loading && coords && results.length === 0 && !error && (
        <p className="mt-6 text-center text-gray-500">
          Nothing nearby — try a bigger radius.
        </p>
      )}

      <ul className="mt-4 flex flex-col gap-3">
        {results.map((hit) => (
          <li key={hit.campaign.campaign_id}>
            <button
              type="button"
              onClick={() => onSelectCampaign(hit)}
              className="flex w-full items-center justify-between rounded-lg border border-gray-200 px-4 py-3 text-left"
            >
              <div>
                <p className="font-medium">{hit.campaign.merchant_name}</p>
                <p className="text-sm text-gray-500">
                  {formatDistance(hit.distance_meters)}
                  {hit.campaign.pays_double_today && (
                    <span className="ml-2 text-orange-600">pays more today</span>
                  )}
                </p>
              </div>
              <p className="text-lg font-semibold">
                {formatUsd(hit.campaign.reward_today)}
              </p>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}