import { useEffect, useState } from 'react'
import { usePrivy, useSendTransaction } from '@privy-io/react-auth'
import { fetchCampaigns, formatUsd, type Campaign } from '../lib/api'
import { useRole } from '../context/RoleContext'

interface MerchantPanelProps {
  merchantAddress: string
  onGoToScan: () => void
}

const CAMPAIGN_VAULT_ADDRESS = '0x7b4aaDDe248818bAD121431eAd1a3A865914c419'
const USDC_ADDRESS = '0x036CbD53842c5426634e7929541eC2318f3dCF7e'
const BASE_SEPOLIA_CHAIN_ID = 84532

// createCampaign(rewardPerVisit=50000, dailyCap=50, geohash="dr5rsked", radius=120)
const SEED_CAMPAIGN_CALLDATA =
  '0x4247c05a000000000000000000000000000000000000000000000000000000000000c350000000000000000000000000000000000000000000000000000000000000003264723572736b65640000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000078'

// approve(spender=CAMPAIGN_VAULT_ADDRESS, amount=20e6) — 20 USDC de prueba
const APPROVE_CALLDATA =
  '0x095ea7b30000000000000000000000007b4aadde248818bad121431ead1a3a865914c4190000000000000000000000000000000000000000000000000000000001312d00'

// fund(campaignId=1, amount=20e6)
const FUND_CALLDATA =
  '0xa65e2cfd00000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000001312d00'

function SeedCampaignButton({ merchantAddress }: { merchantAddress: string }) {
  const { sendTransaction } = useSendTransaction()
  const [status, setStatus] = useState<'idle' | 'sending' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [txHash, setTxHash] = useState<string | null>(null)
  const [fundStatus, setFundStatus] = useState<'idle' | 'approving' | 'funding' | 'done' | 'error'>('idle')
  const [fundError, setFundError] = useState<string | null>(null)

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

  async function handleFund() {
    setFundStatus('approving')
    setFundError(null)
    try {
      await sendTransaction(
        {
          to: USDC_ADDRESS,
          chainId: BASE_SEPOLIA_CHAIN_ID,
          data: APPROVE_CALLDATA,
        },
        { address: merchantAddress },
      )
      setFundStatus('funding')
      await sendTransaction(
        {
          to: CAMPAIGN_VAULT_ADDRESS,
          chainId: BASE_SEPOLIA_CHAIN_ID,
          data: FUND_CALLDATA,
        },
        { address: merchantAddress },
      )
      setFundStatus('done')
    } catch (err) {
      setFundStatus('error')
      setFundError(err instanceof Error ? err.message : 'Funding failed')
    }
  }

  return (
    <div className="mt-6 rounded-2xl border border-dashed border-border bg-surface p-4 text-center">
      <p className="mb-2 text-xs text-ink-muted">
        Dev only — creates a real demo campaign on-chain, owned by this wallet.
        Needs Base Sepolia ETH for gas, and USDC to fund.
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
      {txHash && (
        <button
          type="button"
          onClick={handleFund}
          disabled={fundStatus === 'approving' || fundStatus === 'funding'}
          className="mt-3 rounded-full bg-accent px-4 py-2 text-sm font-medium text-white transition disabled:opacity-50"
        >
          {fundStatus === 'idle' && 'Fund with 20 USDC'}
          {fundStatus === 'approving' && 'Approving...'}
          {fundStatus === 'funding' && 'Funding...'}
          {fundStatus === 'done' && 'Funded ✓'}
          {fundStatus === 'error' && 'Retry fund'}
        </button>
      )}
      {fundError && <p className="mt-2 text-xs text-red-600">{fundError}</p>}
    </div>
  )
}

export function MerchantPanel({ merchantAddress, onGoToScan }: MerchantPanelProps) {
  const { logout } = usePrivy()
  const { setRole } = useRole()

  async function handleLogout() {
    setRole(null)
    await logout()
  }

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
          Campaign setup isn't built yet — check back soon.
        </p>
        {import.meta.env.DEV && <SeedCampaignButton merchantAddress={merchantAddress} />}
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-bg px-4 py-6">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wide text-ink-muted">Business account</p>
        <button type="button" onClick={handleLogout} className="text-xs text-ink-muted underline">
          Log out
        </button>
      </div>
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

      <p className="mt-6 text-center text-xs text-ink-muted">
        Pricing is fixed for now — variable pricing is planned for a later phase.
      </p>

      <button
        type="button"
        onClick={onGoToScan}
        className="mt-6 w-full rounded-full bg-brand py-3 font-medium text-white transition"
      >
        Scan a customer's QR
      </button>
    </div>
  )
}