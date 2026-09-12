import { useEffect, useState } from 'react'
import { useSendTransaction } from '@privy-io/react-auth'
import { fetchCampaigns, formatUsd, type Campaign } from '../lib/api'

interface MerchantPanelProps {
  merchantAddress: string
  onGoToScan: () => void
}

const CAMPAIGN_VAULT_ADDRESS = '0xf4ADec71da03c6595CF4624f7d4573C9EDb753B0'
const BASE_SEPOLIA_CHAIN_ID = 84532

// createCampaign(rewardPerVisit=50000, dailyCap=50, geohash="dr5rsked", radius=120)
// Matches the existing mock Delancey Bodega numbers — calldata computed from
// the real function selector (createCampaign(uint256,uint256,bytes32,uint256)),
// verified to be exactly 132 bytes (4-byte selector + four 32-byte params).
const SEED_CAMPAIGN_CALLDATA =
  '0x4247c05a000000000000000000000000000000000000000000000000000000000000c350000000000000000000000000000000000000000000000000000000000000003264723572736b65640000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000078'

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
    <div className="mt-6 rounded-lg border border-dashed border-gray-300 p-4 text-center">
      <p className="mb-2 text-xs text-gray-500">
        Dev only — creates a real demo campaign on-chain, owned by this wallet.
        Needs Base Sepolia ETH for gas first.
      </p>
      <button
        type="button"
        onClick={handleSeed}
        disabled={status === 'sending'}
        className="rounded-lg bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {status === 'sending' ? 'Sending...' : 'Seed demo campaign'}
      </button>
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
      {txHash && <p className="mt-2 text-xs text-green-600">Sent: {txHash.slice(0, 10)}...</p>}
    </div>
  )
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
        {import.meta.env.DEV && <SeedCampaignButton merchantAddress={merchantAddress} />}
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