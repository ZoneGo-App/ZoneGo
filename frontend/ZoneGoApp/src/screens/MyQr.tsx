import { useEffect, useRef, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import {
  signQr,
  formatUsd,
  type QrSignResponse,
  type Campaign,
  type WorldAttestation,
} from '../lib/api'

interface MyQrProps {
  visitorAddress: string
  campaign: Campaign
  attestation: WorldAttestation
  onBack: () => void
}

export function MyQr({ visitorAddress, campaign, attestation, onBack }: MyQrProps) {
  const [signed, setSigned] = useState<QrSignResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [secondsLeft, setSecondsLeft] = useState(0)
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    let cancelled = false
    let refreshTimeout: ReturnType<typeof setTimeout> | null = null

    async function fetchQr() {
      try {
        const result = await signQr({
          campaignId: campaign.campaign_id,
          visitor: visitorAddress,
        })
        if (cancelled) return
        setSigned(result)
        setError(null)
        setSecondsLeft(result.rotate_after_seconds)
        // Schedule the next refresh using the interval the server actually
        // returned, not a value assumed ahead of time — this used to read
        // `signed` from a stale closure and always fell back to 30s.
        refreshTimeout = setTimeout(fetchQr, result.rotate_after_seconds * 1000)
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Could not load the QR code')
        }
      }
    }

    fetchQr()

    return () => {
      cancelled = true
      if (refreshTimeout) clearTimeout(refreshTimeout)
    }
  }, [campaign.campaign_id, visitorAddress])

  useEffect(() => {
    if (countdownRef.current) clearInterval(countdownRef.current)
    if (!signed) return

    countdownRef.current = setInterval(() => {
      setSecondsLeft((s) => (s > 0 ? s - 1 : 0))
    }, 1000)

    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current)
    }
  }, [signed])

  return (
    <div className="min-h-screen px-4 py-6">
      <button type="button" onClick={onBack} className="mb-4 text-sm text-gray-600">
        &larr; Back
      </button>

      <div className="text-center">
        <h1 className="text-lg font-semibold">{campaign.merchant_name}</h1>
        <p className="text-sm text-gray-500">
          {formatUsd(campaign.reward_today)} per visit
        </p>
      </div>

      <p className="mt-6 text-center text-gray-600">
        Show this to the store so you can get paid
      </p>

      <div className="mt-4 flex justify-center">
        {error && <p className="text-red-600">{error}</p>}
        {!error && !signed && <p className="text-gray-500">Loading your code...</p>}
        {signed && (
          <div className="rounded-2xl bg-white p-4 shadow">
            <QRCodeSVG
              value={JSON.stringify({ typedData: signed.typed_data, attestation })}
              size={220}
            />
          </div>
        )}
      </div>

      {signed && (
        <>
          <div className="mt-6 flex justify-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full border-2 border-black text-lg font-semibold">
              {secondsLeft}
            </div>
          </div>
          <p className="mt-2 text-center text-sm text-gray-500">
            Refreshes every {signed.rotate_after_seconds} seconds
          </p>

          <div className="mt-6 rounded-xl bg-gray-100 p-4 text-center">
            <p className="text-xs uppercase text-gray-500">You earn</p>
            <p className="text-2xl font-bold text-black">
              {formatUsd(campaign.reward_today)}
            </p>
            <p className="text-xs text-gray-500">instantly &middot; verified in real time</p>
          </div>
        </>
      )}
    </div>
  )
}