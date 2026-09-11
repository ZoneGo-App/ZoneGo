import { useEffect, useState } from 'react'
import { searchCampaigns, formatUsd, formatDistance, type SearchHit } from '../lib/api'

const RADIOS_KM = [1, 5, 10] as const

export function Search() {
  const [radiusKm, setRadiusKm] = useState<1 | 5 | 10>(1)
  const [query, setQuery] = useState('')
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null)
  const [results, setResults] = useState<SearchHit[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    navigator.geolocation.getCurrentPosition(
      (pos) => setCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      () => setError('No pudimos ubicarte. Activá la ubicación e intentá de nuevo.'),
    )
  }, [])

  useEffect(() => {
    if (!coords) return

    let cancelled = false
    setLoading(true)
    setError(null)

    searchCampaigns({ lat: coords.lat, lon: coords.lon, radiusKm, query })
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
  }, [coords, radiusKm, query])

  return (
    <div className="min-h-screen px-4 py-6">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder='Buscá algo, ej. "zapatillas"'
        className="w-full rounded-lg border border-gray-300 px-4 py-3 text-base"
      />

      <div className="mt-3 flex gap-2">
        {RADIOS_KM.map((km) => (
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
        <p className="mt-6 text-center text-gray-500">Ubicándote...</p>
      )}
      {error && <p className="mt-6 text-center text-red-600">{error}</p>}
      {loading && <p className="mt-6 text-center text-gray-500">Buscando...</p>}

      {!loading && coords && results.length === 0 && !error && (
        <p className="mt-6 text-center text-gray-500">
          Nada por acá — probá un radio más grande.
        </p>
      )}

      <ul className="mt-4 flex flex-col gap-3">
        {results.map((hit) => (
          <li
            key={hit.campaign.campaign_id}
            className="flex items-center justify-between rounded-lg border border-gray-200 px-4 py-3"
          >
            <div>
              <p className="font-medium">{hit.campaign.merchant_name}</p>
              <p className="text-sm text-gray-500">
                {formatDistance(hit.distance_meters)}
                {hit.campaign.pays_double_today && (
                  <span className="ml-2 text-orange-600">paga más hoy</span>
                )}
              </p>
            </div>
            <p className="text-lg font-semibold">
              {formatUsd(hit.campaign.reward_today)}
            </p>
          </li>
        ))}
      </ul>
    </div>
  )
}