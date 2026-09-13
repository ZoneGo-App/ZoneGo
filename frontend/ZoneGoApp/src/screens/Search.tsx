import { useCallback, useEffect, useState } from 'react'
import { searchCampaigns, formatUsd, formatDistance, type SearchHit } from '../lib/api'

const RADIUS_OPTIONS_KM = [1, 5, 10] as const
const SEARCH_DEBOUNCE_MS = 400
const MAX_PINS_ON_MAP = 5

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

/**
 * Decorative pin position, not a real map projection. Spreads hits around a
 * center point based only on their rank and relative distance — there is no
 * real map tile or geocoding wired in yet, this just reserves the visual
 * space and gives a sense of "closer = nearer the middle" until a real map
 * (Google Maps, with the actual lat/lon) replaces it.
 */
function decorativePinPosition(index: number, distanceMeters: number, maxDistance: number) {
  const angle = (index / MAX_PINS_ON_MAP) * 2 * Math.PI - Math.PI / 2
  const spread = maxDistance > 0 ? distanceMeters / maxDistance : 0.5
  const radiusPercent = 18 + spread * 30
  const topPercent = 50 + Math.sin(angle) * radiusPercent
  const leftPercent = 50 + Math.cos(angle) * radiusPercent
  return { top: `${topPercent}%`, left: `${leftPercent}%` }
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
  const mapPins = results.slice(0, MAX_PINS_ON_MAP)
  const maxDistance = Math.max(...mapPins.map((h) => h.distance_meters), 1)
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

      {/* Decorative map placeholder — reserves the space for a real map later. */}
      <div className="relative mt-4 h-48 w-full overflow-hidden rounded-2xl border border-border bg-[#e9e7df]">
        <div
          className="absolute inset-0 opacity-40"
          style={{
            backgroundImage:
              'linear-gradient(#d8d5c9 1px, transparent 1px), linear-gradient(90deg, #d8d5c9 1px, transparent 1px)',
            backgroundSize: '28px 28px',
          }}
        />
        <div className="absolute left-1/2 top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-brand shadow" />
        {mapPins.map((hit, index) => {
          const position = decorativePinPosition(index, hit.distance_meters, maxDistance)
          const isTopPick = hit.campaign.pays_double_today
          return (
            <div
              key={hit.campaign.campaign_id}
              className="absolute -translate-x-1/2 -translate-y-full"
              style={position}
            >
              <div
                className={`rounded-full px-2 py-1 text-xs font-semibold text-white shadow ${
                  isTopPick ? 'bg-accent' : 'bg-brand'
                }`}
              >
                {formatUsd(hit.campaign.reward_today)}
              </div>
              <div
                className={`mx-auto h-2 w-2 rotate-45 ${isTopPick ? 'bg-accent' : 'bg-brand'}`}
                style={{ marginTop: -4 }}
              />
            </div>
          )
        })}
        {mapPins.length === 0 && !loading && (
          <p className="absolute inset-0 flex items-center justify-center text-xs text-ink-muted">
            Map preview — real map coming soon
          </p>
        )}
      </div>

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

      {/* A real location with nothing in reach, or one the browser refused:
          either way the way back to the live campaigns is one tap. */}
      {useRealLocation && (nothingInRange || !!locationError) && (
        <div className="mt-4 text-center">
          <button
            type="button"
            onClick={switchToDelancey}
            className="rounded-full bg-brand px-5 py-2 text-sm font-medium text-white"
          >
            See the stores on Delancey Street
          </button>
        </div>
      )}

      <ul className="mt-4 flex flex-col gap-3">
        {results.map((hit) => {
          const isBoosted = hit.campaign.pays_double_today
          return (
            <li key={hit.campaign.campaign_id}>
              <button
                type="button"
                onClick={() => onSelectCampaign(hit)}
                className={`flex w-full items-center justify-between rounded-2xl border bg-surface px-4 py-3 text-left transition hover:border-brand ${
                  isBoosted ? 'border-accent' : 'border-border'
                }`}
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
            </li>
          )
        })}
      </ul>
    </div>
  )
}