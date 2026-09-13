import { useCallback, useEffect, useState } from 'react'
import { usePrivy, useSendTransaction } from '@privy-io/react-auth'
import { fetchCampaigns, formatUsd, type Campaign } from '../lib/api'
import { useRole } from '../context/RoleContext'
import {
  CAMPAIGN_VAULT_ADDRESS,
  USDC_ADDRESS,
  BASE_SEPOLIA_CHAIN_ID,
  encodeApprove,
  encodeFund,
  encodeCreateCampaign,
  encodeGeohash,
  usdToMicroUsdc,
} from '../lib/contracts'

interface MerchantPanelProps {
  merchantAddress: string
}

// createCampaign(rewardPerVisit=50000, dailyCap=50, geohash="dr5rsked", radius=120)
const SEED_CAMPAIGN_CALLDATA =
  '0x4247c05a000000000000000000000000000000000000000000000000000000000000c350000000000000000000000000000000000000000000000000000000000000003264723572736b65640000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000078'

function CreateCampaignButton({ merchantAddress, onCreated }: { merchantAddress: string; onCreated: () => void }) {
  const { sendTransaction } = useSendTransaction()
  const [status, setStatus] = useState<'idle' | 'locating' | 'sending' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)

  async function handleCreate() {
    setError(null)
    setStatus('locating')

    if (!('geolocation' in navigator)) {
      setStatus('error')
      setError("This browser can't share your location.")
      return
    }

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          setStatus('sending')
          const geohash = encodeGeohash(pos.coords.latitude, pos.coords.longitude)
          // Same reward/cap/radius as the Delancey demo campaign — a real
          // "set your own economics" form is a fast follow, not today's fix.
          await sendTransaction(
            {
              to: CAMPAIGN_VAULT_ADDRESS,
              chainId: BASE_SEPOLIA_CHAIN_ID,
              data: encodeCreateCampaign(50_000n, 50n, geohash, 120n),
            },
            { address: merchantAddress },
          )
          setStatus('idle')
          onCreated()
        } catch (err) {
          setStatus('error')
          setError(err instanceof Error ? err.message : 'Creating the campaign failed')
        }
      },
      () => {
        setStatus('error')
        setError("Couldn't get your location. Turn on location and try again.")
      },
    )
  }

  return (
    <div className="mt-6 rounded-2xl border border-brand/30 bg-brand/10 p-4 text-center">
      <p className="mb-2 text-sm text-ink">
        Create your campaign right where you are — neighbors searching near your
        real location will find it.
      </p>
      <button
        type="button"
        onClick={handleCreate}
        disabled={status === 'locating' || status === 'sending'}
        className="rounded-full bg-brand px-5 py-2.5 text-sm font-medium text-white transition disabled:opacity-50"
      >
        {status === 'locating' && 'Finding your location...'}
        {status === 'sending' && 'Creating...'}
        {(status === 'idle' || status === 'error') && 'Create campaign at my location'}
      </button>
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  )
}

function SeedCampaignButton({ merchantAddress }: { merchantAddress: string }) {
  const { sendTransaction } = useSendTransaction()
  const [status, setStatus] = useState<'idle' | 'sending' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [txHash, setTxHash] = useState<string | null>(null)

  async function handleSeed() {
    setStatus('sending')
    setError(null)
    try {
      const { hash } = await sendTransaction(
        {
          to: CAMPAIGN_VAULT_ADDRESS,
          chainId: BASE_SEPOLIA_CHAIN_ID,
          data: SEED_CAMPAIGN_CALLDATA,
        },
        { address: merchantAddress },
      )
      setTxHash(hash)
      setStatus('idle')
    } catch (err) {
      setStatus('error')
      setError(err instanceof Error ? err.message : 'Transaction failed')
    }
  }

  return (
    <div className="mt-6 rounded-2xl border border-dashed border-border bg-surface p-4 text-center">
      <p className="mb-2 text-xs text-ink-muted">
        Dev only — creates a real demo campaign on-chain, owned by this wallet.
        Needs Base Sepolia ETH for gas.
      </p>
      <button
        type="button"
        onClick={handleSeed}
        disabled={status === 'sending'}
        className="rounded-full bg-brand px-4 py-2 text-sm font-medium text-white transition disabled:opacity-50"
      >
        {status === 'sending' ? 'Sending...' : 'Seed demo campaign'}
      </button>
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
      {txHash && <p className="mt-2 text-xs text-brand">Sent: {txHash.slice(0, 10)}...</p>}
    </div>
  )
}

function AddFundsForm({ merchantAddress, campaignId }: { merchantAddress: string; campaignId: number }) {
  const { sendTransaction } = useSendTransaction()
  const [amount, setAmount] = useState('20')
  const [status, setStatus] = useState<'idle' | 'approving' | 'funding' | 'done' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)

  async function handleAddFunds() {
    const usd = Number(amount)
    if (!usd || usd <= 0) {
      setError('Enter a valid amount.')
      return
    }
    setError(null)
    setStatus('approving')
    try {
      const microUsdc = usdToMicroUsdc(usd)
      await sendTransaction(
        {
          to: USDC_ADDRESS,
          chainId: BASE_SEPOLIA_CHAIN_ID,
          data: encodeApprove(CAMPAIGN_VAULT_ADDRESS, microUsdc),
        },
        { address: merchantAddress },
      )
      setStatus('funding')
      await sendTransaction(
        {
          to: CAMPAIGN_VAULT_ADDRESS,
          chainId: BASE_SEPOLIA_CHAIN_ID,
          data: encodeFund(BigInt(campaignId), microUsdc),
        },
        { address: merchantAddress },
      )
      setStatus('done')
    } catch (err) {
      setStatus('error')
      setError(err instanceof Error ? err.message : 'Adding funds failed')
    }
  }

  return (
    <div className="mt-4 rounded-2xl border border-border bg-surface p-5">
      <div className="flex items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand/10 text-brand-dark">
          <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4">
            <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
          </svg>
        </span>
        <p className="text-sm font-semibold text-ink">Add funds</p>
      </div>

      <div className="mt-3 flex items-center gap-2 rounded-full border border-border bg-bg px-4 py-2">
        <span className="text-ink-muted">$</span>
        <input
          type="number"
          min="0"
          step="1"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="w-full bg-transparent text-ink focus:outline-none"
        />
      </div>

      <button
        type="button"
        onClick={handleAddFunds}
        disabled={status === 'approving' || status === 'funding'}
        className="mt-3 w-full rounded-full bg-brand py-2.5 text-sm font-medium text-white transition disabled:opacity-50"
      >
        {status === 'idle' && 'Add funds'}
        {status === 'approving' && 'Approving...'}
        {status === 'funding' && 'Funding...'}
        {status === 'done' && 'Added ✓'}
        {status === 'error' && 'Retry'}
      </button>

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
      <p className="mt-2 text-center text-xs text-ink-muted">Requires two confirmations: approve, then fund.</p>
    </div>
  )
}

export function MerchantPanel({ merchantAddress }: MerchantPanelProps) {
  const { logout } = usePrivy()
  const { setRole } = useRole()

  async function handleLogout() {
    setRole(null)
    await logout()
  }

  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // A campaign just created on-chain doesn't appear here instantly — the
  // backend indexer has to catch up first. Rather than one silent fetch
  // right after, this retries a few times over ~20s so "Create campaign"
  // resolves into the real panel without the merchant needing to refresh
  // by hand.
  const [waitingForIndex, setWaitingForIndex] = useState(false)

  const loadCampaign = useCallback(() => {
    let cancelled = false

    fetchCampaigns()
      .then((campaigns) => {
        if (cancelled) return null
        const mine = campaigns.find(
          (c) => c.merchant.toLowerCase() === merchantAddress.toLowerCase(),
        )
        setCampaign(mine ?? null)
        return mine ?? null
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Could not load your campaign')
        }
        return null
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [merchantAddress])

  useEffect(() => loadCampaign(), [loadCampaign])

  function handleCampaignCreated() {
    setWaitingForIndex(true)
    let attempts = 0
    const interval = setInterval(() => {
      attempts += 1
      fetchCampaigns()
        .then((campaigns) => {
          const mine = campaigns.find(
            (c) => c.merchant.toLowerCase() === merchantAddress.toLowerCase(),
          )
          if (mine) {
            setCampaign(mine)
            setWaitingForIndex(false)
            clearInterval(interval)
          } else if (attempts >= 6) {
            // Still not indexed after ~18s — stop polling silently rather
            // than forever; the merchant can reopen this tab later.
            setWaitingForIndex(false)
            clearInterval(interval)
          }
        })
        .catch(() => {
          // A transient fetch error here shouldn't cancel the whole retry
          // loop — just skip this attempt and try again next tick.
        })
    }, 3000)
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg">
        <p className="text-ink-muted">Loading your campaign...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg px-6 text-center">
        <p className="text-red-600">{error}</p>
      </div>
    )
  }

  if (!campaign) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 bg-bg px-6 text-center">
        <p className="text-ink">You don't have a campaign yet.</p>
        <p className="text-sm text-ink-muted">
          Create one to start paying real visitors who walk in.
        </p>
        {waitingForIndex ? (
          <p className="mt-4 text-sm text-ink-muted">
            Campaign sent — waiting for it to show up here...
          </p>
        ) : (
          <CreateCampaignButton merchantAddress={merchantAddress} onCreated={handleCampaignCreated} />
        )}
        {import.meta.env.DEV && <SeedCampaignButton merchantAddress={merchantAddress} />}
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-bg px-4 py-6">
      <p className="text-xs uppercase tracking-wide text-ink-muted">Business account</p>
      <h1 className="text-2xl font-bold text-ink">{campaign.merchant_name}</h1>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <div className="rounded-2xl bg-brand-dark p-4 text-white">
          <p className="text-xs uppercase tracking-wide text-white/70">Pays today</p>
          <p className="mt-1 text-2xl font-bold">{formatUsd(campaign.reward_today)}</p>
          {campaign.pays_double_today && (
            <p className="mt-1 text-xs text-accent">boosted today</p>
          )}
        </div>
        <div className="rounded-2xl border border-border bg-surface p-4">
          <p className="text-xs uppercase tracking-wide text-ink-muted">Budget left</p>
          <p className="mt-1 text-2xl font-bold text-ink">{formatUsd(campaign.balance)}</p>
        </div>
        <div className="rounded-2xl border border-border bg-surface p-4">
          <p className="text-xs uppercase tracking-wide text-ink-muted">Daily cap</p>
          <p className="mt-1 text-2xl font-bold text-ink">{campaign.daily_cap}</p>
          <p className="text-xs text-ink-muted">visits per day</p>
        </div>
        <div className="rounded-2xl border border-border bg-surface p-4">
          <p className="text-xs uppercase tracking-wide text-ink-muted">Category</p>
          <p className="mt-1 text-sm font-medium text-ink">{campaign.category}</p>
        </div>
      </div>

      <AddFundsForm merchantAddress={merchantAddress} campaignId={campaign.campaign_id} />

      <p className="mt-4 text-center text-xs text-ink-muted">
        Pricing is fixed for now — variable pricing is planned for a later phase.
      </p>

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