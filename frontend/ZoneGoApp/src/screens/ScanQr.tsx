import { useEffect, useState } from 'react'
import { Html5Qrcode } from 'html5-qrcode'
import { useSignTypedData } from '@privy-io/react-auth'
import { claimVisit, type QrSignResponse } from '../lib/api'

const SCANNER_ELEMENT_ID = 'scan-qr-reader'

const DEMO_ERRORS = [
  'QR expired',
  'Outside radius',
  'Already claimed',
  'Not verified',
] as const

type Step =
  | { kind: 'scanning' }
  | { kind: 'decoded'; typedData: QrSignResponse['typed_data'] }
  | { kind: 'signing' }
  | { kind: 'submitting' }
  | { kind: 'success'; txHash: string }
  | { kind: 'error'; message: string }

export function ScanQr() {
  const { signTypedData } = useSignTypedData()
  const [step, setStep] = useState<Step>({ kind: 'scanning' })

  useEffect(() => {
    if (step.kind !== 'scanning') return

    let cancelledBeforeStart = false
    const scanner = new Html5Qrcode(SCANNER_ELEMENT_ID)

    function safeStop() {
      try {
        scanner.stop().catch(() => {})
      } catch {
        // Never started, or already stopped — nothing to clean up.
      }
    }

    scanner
      .start(
        { facingMode: 'environment' },
        { fps: 10, qrbox: { width: 240, height: 240 } },
        (decodedText) => {
          try {
            const typedData = JSON.parse(decodedText) as QrSignResponse['typed_data']
            setStep({ kind: 'decoded', typedData })
          } catch {
            setStep({ kind: 'error', message: 'That QR code is not a valid ZoneGo code.' })
          }
        },
        () => {
          // Fired continuously while no code is found — not an error, ignore it.
        },
      )
      .then(() => {
        if (cancelledBeforeStart) safeStop()
      })
      .catch(() => {
        if (!cancelledBeforeStart) {
          setStep({ kind: 'error', message: "Couldn't access the camera. Check permissions." })
        }
      })

    return () => {
      cancelledBeforeStart = true
      safeStop()
    }
  }, [step.kind])

  async function handleSignAndConfirm(typedData: QrSignResponse['typed_data']) {
    setStep({ kind: 'signing' })
    try {
      const { signature } = await signTypedData({
        domain: typedData.domain,
        types: typedData.types,
        primaryType: typedData.primaryType,
        message: typedData.message,
      } as never)

      setStep({ kind: 'submitting' })

      const result = await claimVisit({
        campaignId: typedData.message.campaignId,
        nonce: typedData.message.nonce,
        expiry: typedData.message.expiry,
        geohash: typedData.message.geohash,
        signature,
        visitor: typedData.message.visitor,
        attestation: null, // TODO: wire real World attestation once identity check exists
      })

      setStep({ kind: 'success', txHash: result.tx_hash })
    } catch (err) {
      setStep({
        kind: 'error',
        message: err instanceof Error ? err.message : 'Something went wrong.',
      })
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-900 text-white">
      <div className="flex items-center justify-between px-4 py-3">
        <span className="flex items-center gap-2 text-sm">
          <span className="h-2 w-2 rounded-full bg-red-500" />
          Camera
        </span>
      </div>

      <div className="relative flex-1">
        <div id={SCANNER_ELEMENT_ID} className="h-full w-full [&>video]:h-full [&>video]:w-full [&>video]:object-cover" />

        {step.kind === 'scanning' && (
          <p className="absolute bottom-24 left-0 right-0 text-center text-sm text-slate-200">
            Point at the customer's QR code
          </p>
        )}
      </div>

      <div className="bg-slate-950 px-4 py-4">
        {step.kind === 'decoded' && (
          <button
            type="button"
            onClick={() => handleSignAndConfirm(step.typedData)}
            className="w-full rounded-lg bg-white py-3 font-medium text-black"
          >
            Sign &amp; confirm
          </button>
        )}

        {step.kind === 'signing' && <p className="text-center text-sm">Signing...</p>}
        {step.kind === 'submitting' && <p className="text-center text-sm">Submitting...</p>}

        {step.kind === 'success' && (
          <p className="text-center text-sm text-green-400">
            Confirmed. Transaction: {step.txHash.slice(0, 10)}...
          </p>
        )}

        {step.kind === 'error' && (
          <div className="text-center">
            <p className="text-sm text-red-400">{step.message}</p>
            <button
              type="button"
              onClick={() => setStep({ kind: 'scanning' })}
              className="mt-2 text-sm text-slate-300 underline"
            >
              Try again
            </button>
          </div>
        )}

        {step.kind === 'scanning' && (
          <>
            {import.meta.env.DEV && (
              <details className="mb-3 rounded-lg bg-slate-800 p-3 text-xs">
                <summary className="cursor-pointer text-slate-300">
                  Dev only: paste QR payload manually
                </summary>
                <textarea
                  className="mt-2 w-full rounded bg-slate-900 p-2 text-slate-100"
                  rows={3}
                  placeholder="Paste the JSON from the neighbor's QR here"
                  onChange={(e) => {
                    try {
                      const typedData = JSON.parse(e.target.value) as QrSignResponse['typed_data']
                      setStep({ kind: 'decoded', typedData })
                    } catch {
                      // Still typing/pasting — ignore until it's valid JSON.
                    }
                  }}
                />
              </details>
            )}

            <p className="mb-2 text-center text-xs text-slate-500">Demo: simulate error state</p>
            <div className="grid grid-cols-2 gap-2">
              {DEMO_ERRORS.map((label) => (
                <button
                  key={label}
                  type="button"
                  onClick={() => setStep({ kind: 'error', message: label })}
                  className="rounded-lg bg-slate-800 py-2 text-xs text-slate-200"
                >
                  {label}
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}