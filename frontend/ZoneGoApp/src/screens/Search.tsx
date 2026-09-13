import { useCallback, useEffect, useState } from 'react'
import 'leaflet/dist/leaflet.css'
import { searchCampaigns, formatUsd, formatDistance, type SearchHit } from '../lib/api'
import { CampaignMap, openDirections } from '../components/CampaignMap'

const RADIUS_OPTIONS_KM = [1, 5, 10] as const
const SEARCH_DEBOUNCE_MS = 400
/**
 * Delancey Street, Lower East Side — where every live campaign is. Five metres
 * from campaign 1, so it comes back at the smallest radius.
 */
const DELANCEY = { lat: 40.7185, lon: -73.988 }
const REAL_LOCATION_KEY = 'zonego_use_real_location'

/**
 * Where search looks from: Delancey Street unless the visitor asks for their own GPS.
 *
 * It opens on New York because that is where ZoneGo is live, and because
 * search only reaches ten kilometres. A judge in Berlin, or anyone opening the
 * link outside Manhattan, would otherwise land on an empty map — and before
 * that on a browser permission prompt, which plenty of people deny.
 *
 * It is not a mock and it cannot be used to cheat. The contract never checks
 * where anyone is; location only decides which stores appear. Getting paid
 * still takes the merchant's signed QR, which they only show at their counter.
 * The banner says plainly which location is in use, and one tap switches to the
 * visitor's own GPS — remembered per browser, so a real neighbour in New York
 * only chooses once.
 */
function useCoords() {
  const [useRealLocation, setUseRealLocation] = useState(() => readFlag())
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(
    useRealLocation ? null : DELANCEY,
  )
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setError(null)

    const forced = import.meta.env.VITE_DEV_FORCE_LOCATION
    if (forced) {
      const [lat, lon] = forced.split(',').map(Number)
      setCoords({ lat, lon })
      return
    }

    if (!useRealLocation) {
      setCoords(DELANCEY)
      return
    }

    setCoords(null)
    if (!('geolocation' in navigator)) {
      setError("This browser can't share your location.")
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => setCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      () => setError("We couldn't find you. Turn on location and try again."),
    )
  }, [useRealLocation])

  const switchToRealLocation = useCallback(() => {
    writeFlag(true)
    setUseRealLocation(true)
  }, [])

  const switchToDelancey = useCallback(() => {
    writeFlag(false)
    setUseRealLocation(false)
  }, [])

  return { coords, error, useRealLocation, switchToRealLocation, switchToDelancey }
}

// Storage can throw — private browsing, blocked site data. A location
// preference is not worth breaking search over, so failure means "Delancey".
function readFlag(): boolean {
  try {
    return localStorage.getItem(REAL_LOCATION_KEY) === '1'
  } catch {
    return false
  }
}

function writeFlag(on: boolean) {
  try {
    if (on) localStorage.setItem(REAL_LOCATION_KEY, '1')
    else localStorage.removeItem(REAL_LOCATION_KEY)
  } catch {
    // The switch still works for this visit; it just won't be remembered.
  }
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
  const { coords, error: locationError, useRealLocation, switchToRealLocation, switchToDelancey } =
    useCoords()
  const [results, setResults] = useState<SearchHit[]>([])
  const [loading, setLoading] = useState(false)
  // Kept apart from locationError on purpose. The previous version seeded one
  // from the other with useState(locationError), which only reads the initial
  // value — null, because the browser answers later. Anyone who denied the
  // location prompt waited on "Finding you..." forever with no way out.
  const [searchError, setSearchError] = useState<string | null>(null)

  useEffect(() => {
    if (!coords) return

    let cancelled = false
    setLoading(true)
    setSearchError(null)

    searchCampaigns({ lat: coords.lat, lon: coords.lon, radiusKm, query: debouncedQuery })
      .then((hits) => {
        if (!cancelled) setResults(hits)
      })
      .catch((err) => {
        if (!cancelled) setSearchError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [coords, radiusKm, debouncedQuery])

  const error = locationError ?? searchError
  const nothingInRange = !loading && !!coords && results.length === 0 && !searchError

  return (
    <div className="min-h-screen bg-bg px-4 py-6">
      {useRealLocation ? (
        <div className="mb-4 flex items-center justify-between gap-3 rounded-2xl border border-border bg-surface px-4 py-3">
          <p className="text-sm text-ink">Using your location</p>
          <button
            type="button"
            onClick={switchToDelancey}
            className="shrink-0 rounded-full border border-border px-3 py-1.5 text-xs font-medium text-ink"
          >
            Show Delancey Street
          </button>
        </div>
      ) : (
        <div className="mb-4 flex items-center justify-between gap-3 rounded-2xl border border-brand/30 bg-brand/10 px-4 py-3">
          <div>
            <p className="text-sm font-semibold text-ink">Delancey Street, New York</p>
            <p className="text-xs text-ink-muted">Where ZoneGo is live</p>
          </div>
          <button
            type="button"
            onClick={switchToRealLocation}
            className="shrink-0 rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium text-ink"
          >
            Use my location
          </button>
        </div>
      )}

      <div className="relative">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-ink-muted"
          aria-hidden="true"
        >
          <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
          <path d="M20 20l-4.3-4.3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder='Search for something, e.g. "sneakers"'
          className="w-full rounded-2xl border border-border bg-surface py-3 pl-11 pr-4 text-base text-ink placeholder:text-ink-muted focus:border-brand focus:outline-none"
        />
      </div>

      <div className="mt-3 flex gap-2">
        {RADIUS_OPTIONS_KM.map((km) => (
          <button
            key={km}
            type="button"
            onClick={() => setRadiusKm(km)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${
              radiusKm === km
                ? 'bg-brand text-white shadow-sm'
                : 'border border-border text-ink-muted'
            }`}
          >
            {km} km
          </button>
        ))}
      </div>

      {coords && (
        <CampaignMap center={coords} hits={results} onSelectCampaign={onSelectCampaign} />
      )}

      {!coords && !error && (
        <p className="mt-6 text-center text-ink-muted">Finding you...</p>
      )}
      {error && <p className="mt-6 text-center text-red-600">{error}</p>}
      {loading && <p className="mt-6 text-center text-ink-muted">Searching...</p>}

      {nothingInRange && (
        <p className="mt-6 text-center text-ink-muted">
          Nothing nearby — try a bigger radius.
        </p>
      )}

      <ul className="mt-4 flex flex-col gap-3">
        {results.map((hit) => {
          const isBoosted = hit.campaign.pays_double_today
          return (
            <li
              key={hit.campaign.campaign_id}
              className={`overflow-hidden rounded-2xl border bg-surface ${
                isBoosted ? 'border-accent' : 'border-border'
              }`}
            >
              <button
                type="button"
                onClick={() => onSelectCampaign(hit)}
                className="flex w-full items-center justify-between px-4 py-3 text-left transition hover:bg-bg"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <p className="font-semibold text-ink">{hit.campaign.merchant_name}</p>
                    {isBoosted && (
                      <span className="rounded-full bg-accent/15 px-2 py-0.5 text-xs font-semibold text-accent">
                        NEW
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-ink-muted">
                    {formatDistance(hit.distance_meters)}
                    {isBoosted && (
                      <span className="ml-2 font-medium text-accent">pays more</span>
                    )}
                  </p>
                </div>
                <p className={`text-lg font-semibold ${isBoosted ? 'text-accent' : 'text-ink'}`}>
                  {formatUsd(hit.campaign.reward_today)}
                </p>
              </button>
              <button
                type="button"
                onClick={() => openDirections(hit.campaign.lat, hit.campaign.lon)}
                className="w-full border-t border-border px-4 py-2 text-left text-xs font-medium text-brand"
              >
                Get directions
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}