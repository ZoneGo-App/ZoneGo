import { useEffect, useRef, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { signQr, formatUsd, type QrSignResponse, type Campaign } from '../lib/api'

interface MyQrProps {
  visitorAddress: string
  campaign: Campaign
  onBack: () => void
}

export function MyQr({ visitorAddress, campaign, onBack }: MyQrProps) {
  const [signed, setSigned] = useState<QrSignResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [secondsLeft, setSecondsLeft] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    let cancelled = false

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
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Could not load the QR code')
        }
      }
    }

    fetchQr()
    const rotationMs = (signed?.rotate_after_seconds ?? 30) * 1000
    const refetchTimer = setInterval(fetchQr, rotationMs)

    return () => {
      cancelled = true
      clearInterval(refetchTimer)
    }
    // Re-runs only when the campaign or visitor changes, not on every `signed` update.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaign.campaign_id, visitorAddress])

  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current)
    if (!signed) return

    timerRef.current = setInterval(() => {
      setSecondsLeft((s) => (s > 0 ? s - 1 : 0))
    }, 1000)

    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
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
            <QRCodeSVG value={JSON.stringify(signed.typed_data)} size={220} />
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