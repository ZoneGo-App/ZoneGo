import { useEffect, useState } from 'react'
import { fetchCampaigns, formatUsd, type Campaign } from '../lib/api'

interface MerchantPanelProps {
  merchantAddress: string
  onGoToScan: () => void
}

export function MerchantPanel({ merchantAddress, onGoToScan }: MerchantPanelProps) {
  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    fetchCampaigns()
      .then((campaigns) => {
        if (cancelled) return
        const mine = campaigns.find(
          (c) => c.merchant.toLowerCase() === merchantAddress.toLowerCase(),
        )
        setCampaign(mine ?? null)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Could not load your campaign')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [merchantAddress])

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">Loading your campaign...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6 text-center">
        <p className="text-red-600">{error}</p>
      </div>
    )
  }

  if (!campaign) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 px-6 text-center">
        <p className="text-gray-600">You don't have a campaign yet.</p>
        <p className="text-sm text-gray-400">
          Campaign setup isn't built yet — check back soon.
        </p>
      </div>
    )
  }

  return (
    <div className="min-h-screen px-4 py-6">
      <p className="text-xs uppercase text-gray-400">Business account</p>
      <h1 className="text-2xl font-bold">{campaign.merchant_name}</h1>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <div className="rounded-xl bg-black p-4 text-white">
          <p className="text-xs uppercase text-gray-300">Pays today</p>
          <p className="mt-1 text-2xl font-bold">{formatUsd(campaign.reward_today)}</p>
          {campaign.pays_double_today && (
            <p className="mt-1 text-xs text-orange-300">boosted today</p>
          )}
        </div>
        <div className="rounded-xl border border-gray-200 p-4">
          <p className="text-xs uppercase text-gray-400">Budget left</p>
          <p className="mt-1 text-2xl font-bold">{formatUsd(campaign.balance)}</p>
        </div>
        <div className="rounded-xl border border-gray-200 p-4">
          <p className="text-xs uppercase text-gray-400">Daily cap</p>
          <p className="mt-1 text-2xl font-bold">{campaign.daily_cap}</p>
          <p className="text-xs text-gray-400">visits per day</p>
        </div>
        <div className="rounded-xl border border-gray-200 p-4">
          <p className="text-xs uppercase text-gray-400">Category</p>
          <p className="mt-1 text-sm font-medium">{campaign.category}</p>
        </div>
      </div>

      <p className="mt-6 text-center text-xs text-gray-400">
        Pricing is fixed for now — variable pricing is planned for a later phase.
      </p>

      <button
        type="button"
        onClick={onGoToScan}
        className="mt-6 w-full rounded-lg bg-black py-3 font-medium text-white"
      >
        Scan a customer's QR
      </button>
    </div>
  )
}