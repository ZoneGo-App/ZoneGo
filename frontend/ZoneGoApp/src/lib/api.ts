const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

if (!API_BASE_URL) {
  throw new Error(
    'Missing VITE_API_BASE_URL. Add it to frontend/ZoneGoApp/.env (see .env.example).',
  )
}

export interface Campaign {
  campaign_id: number
  merchant: string
  merchant_name: string
  category: string
  sells: string
  reward_per_visit: number
  daily_cap: number
  lat: number
  lon: number
  geohash: string
  radius_meters: number
  balance: number
  active: boolean
  created_at: string
  boost_day: number | null
  pays_double_today: boolean
  reward_today: number
}

export interface SearchHit {
  campaign: Campaign
  distance_meters: number
}

export interface QrSignResponse {
  typed_data: {
    types: Record<string, { name: string; type: string }[]>
    primaryType: string
    domain: Record<string, unknown>
    message: {
      campaignId: number
      nonce: string
      expiry: number
      geohash: string
      visitor: string
    }
  }
  nonce: string
  expiry: number
  rotate_after_seconds: number
}

export interface WorldAttestation {
  visitor: string
  nullifier_hash: string
  expiry: number
  signature: string
  typed_data: Record<string, unknown>
}

export interface WorldRpContextResponse {
  app_id: string
  action: string
  rp_context: {
    rp_id: string
    nonce: string
    created_at: number
    expires_at: number
    signature: string
  }
}

export interface ClaimResponse {
  tx_hash: string
  status: string
  relayed: boolean
}

/** Amounts from the API arrive in micro-USDC (1,000,000 = $1.00). */
export function formatUsd(microUsd: number): string {
  return `$${(microUsd / 1_000_000).toFixed(2)}`
}

export function formatDistance(meters: number): string {
  if (meters < 1000) return `${Math.round(meters)} m`
  return `${(meters / 1000).toFixed(1)} km`
}

export async function searchCampaigns(params: {
  lat: number
  lon: number
  radiusKm: number
  query?: string
}): Promise<SearchHit[]> {
  const url = new URL('/search', API_BASE_URL)
  url.searchParams.set('lat', String(params.lat))
  url.searchParams.set('lon', String(params.lon))
  url.searchParams.set('radius_km', String(params.radiusKm))
  if (params.query) {
    url.searchParams.set('q', params.query)
  }

  const res = await fetch(url)
  if (!res.ok) {
    throw new Error(`Search failed (status ${res.status})`)
  }
  return res.json()
}

export async function signQr(params: {
  campaignId: number
  visitor: string
}): Promise<QrSignResponse> {
  const url = new URL('/qr/sign', API_BASE_URL)

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      campaign_id: params.campaignId,
      visitor: params.visitor,
    }),
  })

  if (!res.ok) {
    throw new Error(`QR sign failed (status ${res.status})`)
  }
  return res.json()
}

/**
 * Submits a claim to the relay. `attestation` should be a real
 * WorldAttestation from /world/verify once the identity-check screen has
 * run, or null only as a temporary stand-in while that's still being wired up.
 */
export async function claimVisit(params: {
  campaignId: number
  nonce: string
  expiry: number
  geohash: string
  signature: string
  visitor: string
  attestation: WorldAttestation | null
}): Promise<ClaimResponse> {
  const url = new URL('/visits/claim', API_BASE_URL)

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      campaign_id: params.campaignId,
      nonce: params.nonce,
      expiry: params.expiry,
      geohash: params.geohash,
      signature: params.signature,
      visitor: params.visitor,
      attestation: params.attestation,
    }),
  })

  if (!res.ok) {
    const body = await res.text()
    throw new Error(`Claim failed (status ${res.status}): ${body}`)
  }
  return res.json()
}

export async function fetchCampaigns(): Promise<Campaign[]> {
  const url = new URL('/campaigns', API_BASE_URL)
  const res = await fetch(url)
  if (!res.ok) {
    throw new Error(`Fetching campaigns failed (status ${res.status})`)
  }
  return res.json()
}

export async function verifyWorld(params: {
  visitor: string
  proof: unknown
}): Promise<WorldAttestation> {
  const url = new URL('/world/verify', API_BASE_URL)

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      visitor: params.visitor,
      proof: params.proof,
    }),
  })

  if (!res.ok) {
    const body = await res.text()
    throw new Error(`World verification failed (status ${res.status}): ${body}`)
  }
  return res.json()
}

// Defaults to Lucio's deployed API even in local dev — the local mock API
// doesn't implement this endpoint. Override with VITE_WORLD_API_BASE_URL if
// that ever changes, instead of editing this file.
const WORLD_API_BASE_URL =
  import.meta.env.VITE_WORLD_API_BASE_URL || 'https://zonego-api.onrender.com'

export async function fetchWorldRpContext(): Promise<WorldRpContextResponse> {
  const res = await fetch(new URL('/world/rp-context', WORLD_API_BASE_URL))
  if (!res.ok) {
    throw new Error(`Fetching World rp_context failed (status ${res.status})`)
  }
  return res.json()
}

export interface LeaderboardEntry {
  rank: number
  address: string
  label: string
  visits: number
  distinct_merchants: number
  points: number
  zone: string
  zone_name: string
  week_start: number | null
}

export interface PlayerStanding {
  address: string
  label: string
  points: number
  visits: number
  distinct_merchants: number
  rank: number
  players: number
  points_to_next: number | null
  zone: string | null
  zone_name: string | null
  week_start: number | null
}

export async function fetchLeaderboard(params: {
  scope: 'explorers' | 'merchants'
  week?: number
}): Promise<LeaderboardEntry[]> {
  const url = new URL('/leaderboard', API_BASE_URL)
  url.searchParams.set('scope', params.scope)
  if (params.week !== undefined) {
    url.searchParams.set('week', String(params.week))
  }
  const res = await fetch(url)
  if (!res.ok) {
    throw new Error(`Fetching leaderboard failed (status ${res.status})`)
  }
  return res.json()
}

export async function fetchMyStanding(params: {
  address: string
  week?: number
}): Promise<PlayerStanding> {
  const url = new URL('/leaderboard/me', API_BASE_URL)
  url.searchParams.set('address', params.address)
  if (params.week !== undefined) {
    url.searchParams.set('week', String(params.week))
  }
  const res = await fetch(url)
  if (!res.ok) {
    throw new Error(`Fetching your standing failed (status ${res.status})`)
  }
  return res.json()
}