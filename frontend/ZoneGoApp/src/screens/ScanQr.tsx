import { useEffect, useState } from 'react'
import { Html5Qrcode } from 'html5-qrcode'
import { useSignTypedData } from '@privy-io/react-auth'
import { claimVisit, type QrSignResponse, type WorldAttestation } from '../lib/api'
import { VISIT_REGISTRY_ADDRESS, BASE_SEPOLIA_CHAIN_ID } from '../lib/contracts'

const SCANNER_ELEMENT_ID = 'scan-qr-reader'
const EXPLORER_TX = 'https://sepolia.basescan.org/tx/'

/**
 * Fixed for every visit, to every merchant. Only `message` changes per scan.
 * Reconstructing this here instead of reading it off the QR cuts the payload
 * by roughly a third, which is the difference between a code a phone camera
 * can read off a screen and one it cannot. Must match what /qr/sign issues
 * exactly, or a signature made from this shape will not match the contract.
 */
const VISIT_SIG_TYPES: QrSignResponse['typed_data']['types'] = {
  EIP712Domain: [
    { name: 'name', type: 'string' },
    { name: 'version', type: 'string' },
    { name: 'chainId', type: 'uint256' },
    { name: 'verifyingContract', type: 'address' },
  ],
  VisitSig: [
    { name: 'campaignId', type: 'uint256' },
    { name: 'nonce', type: 'uint256' },
    { name: 'expiry', type: 'uint64' },
    { name: 'geohash', type: 'bytes32' },
    { name: 'visitor', type: 'address' },
  ],
}

const VISIT_SIG_DOMAIN = {
  name: 'ZoneGo',
  version: '1',
  chainId: BASE_SEPOLIA_CHAIN_ID,
  verifyingContract: VISIT_REGISTRY_ADDRESS,
}

const DEMO_ERRORS = [
  'QR expired',
  'Outside radius',
  'Already claimed',
  'Not verified',
] as const

type Step =
  | { kind: 'scanning' }
  | { kind: 'decoded'; typedData: QrSignResponse['typed_data']; attestation: WorldAttestation }
  | { kind: 'signing' }
  | { kind: 'submitting' }
  | { kind: 'success'; txHash: string }
  | { kind: 'error'; message: string }

function shortHash(hash: string): string {
  return hash.slice(0, 10) + '...' + hash.slice(-8)
}

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
        // Never started, or already stopped. Nothing to clean up.
      }
    }

    scanner
      .start(
        { facingMode: 'environment' },
        { fps: 10, qrbox: { width: 240, height: 240 } },
        (decodedText) => {
          try {
            const parsed = JSON.parse(decodedText) as {
              message: QrSignResponse['typed_data']['message']
              attestation: WorldAttestation
            }
            const typedData: QrSignResponse['typed_data'] = {
              types: VISIT_SIG_TYPES,
              primaryType: 'VisitSig',
              domain: VISIT_SIG_DOMAIN,
              message: parsed.message,
            }
            setStep({ kind: 'decoded', typedData, attestation: parsed.attestation })
          } catch {
            setStep({ kind: 'error', message: 'That QR code is not a valid ZoneGo code.' })
          }
        },
        () => {
          // Fired continuously while no code is found. Not an error, ignore it.
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

  async function handleSignAndConfirm(
    typedData: QrSignResponse['typed_data'],
    attestation: WorldAttestation,
  ) {
    setStep({ kind: 'signing' })
    try {
      const { signature } = await signTypedData({
        domain: typedData.domain,
        types: typedData.types,
        primaryType: typedData.primaryType,
        message: typedData.message,
      })

      setStep({ kind: 'submitting' })

      const result = await claimVisit({
        campaignId: typedData.message.campaignId,
        nonce: typedData.message.nonce,
        expiry: typedData.message.expiry,
        geohash: typedData.message.geohash,
        signature,
        visitor: typedData.message.visitor,
        attestation,
      })

      setStep({ kind: 'success', txHash: result.tx_hash })
    } catch (err) {
      setStep({
        kind: 'error',
        message: err instanceof Error ? err.message : 'Something went wrong.',
      })
    }
  }

  // The whole screen becomes the receipt. A camera behind a confirmation is
  // noise, and this is the moment the product is actually proving something.
  if (step.kind === 'success') {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-bg px-6 py-10 text-center">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-brand">
          <svg viewBox="0 0 24 24" className="h-10 w-10" fill="none" stroke="white" strokeWidth="3">
            <path d="M20 6 L9 17 L4 12" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>

        <h1 className="mt-6 text-2xl font-bold text-ink">Visit confirmed</h1>

        <p className="mt-2 max-w-xs text-sm text-ink-muted">
          A verified human walked in. The contract released the reward to their wallet, and we never
          touched it.
        </p>

        <div className="mt-8 w-full max-w-sm rounded-2xl border border-border bg-surface p-4 text-left">
          <p className="text-xs uppercase tracking-wide text-ink-muted">
            Transaction on Base Sepolia
          </p>
          <p className="mt-1 break-all font-mono text-sm text-ink">{shortHash(step.txHash)}</p>
          <a
            href={EXPLORER_TX + step.txHash}
            target="_blank"
            rel="noreferrer"
            className="mt-3 inline-block text-sm font-medium text-brand underline"
          >
            View on the block explorer
          </a>
        </div>

        <button
          type="button"
          onClick={() => setStep({ kind: 'scanning' })}
          className="mt-8 w-full max-w-sm rounded-full bg-brand py-3 font-medium text-white"
        >
          Scan the next customer
        </button>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-900 text-white">
      <div className="flex items-center justify-between px-4 py-3">
        <span className="flex items-center gap-2 text-sm">
          <span className="h-2 w-2 animate-pulse rounded-full bg-red-500" />
          Camera
        </span>
        <span className="text-xs text-slate-400">Scan to pay a verified visit</span>
      </div>

      <div className="relative flex-1">
        <div
          id={SCANNER_ELEMENT_ID}
          className="h-full w-full [&>video]:h-full [&>video]:w-full [&>video]:object-cover"
        />

        {step.kind === 'scanning' && (
          <>
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
              <div className="h-56 w-56 rounded-3xl border-2 border-white/70 shadow-[0_0_0_9999px_rgba(0,0,0,0.35)]" />
            </div>
            <p className="absolute bottom-8 left-0 right-0 text-center text-sm text-slate-100">
              Point at the customer's QR code
            </p>
          </>
        )}
      </div>

      <div className="bg-slate-950 px-4 py-4">
        {step.kind === 'decoded' && (
          <>
            <p className="mb-3 text-center text-sm text-slate-300">
              Code read. Signing confirms this person was here.
            </p>
            <button
              type="button"
              onClick={() => handleSignAndConfirm(step.typedData, step.attestation)}
              className="w-full rounded-full bg-brand py-3 font-medium text-white"
            >
              Sign and confirm
            </button>
          </>
        )}

        {step.kind === 'signing' && (
          <p className="text-center text-sm text-slate-200">Waiting for your signature</p>
        )}

        {step.kind === 'submitting' && (
          <p className="text-center text-sm text-slate-200">Sending it to the chain</p>
        )}

        {step.kind === 'error' && (
          <div className="text-center">
            <p className="mx-auto max-w-sm break-words text-sm text-red-400">{step.message}</p>
            <button
              type="button"
              onClick={() => setStep({ kind: 'scanning' })}
              className="mt-3 rounded-full border border-slate-600 px-5 py-2 text-sm text-slate-200"
            >
              Try again
            </button>
          </div>
        )}

        {step.kind === 'scanning' && import.meta.env.DEV && (
          <>
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
                    const parsed = JSON.parse(e.target.value) as {
                      message: QrSignResponse['typed_data']['message']
                      attestation: WorldAttestation
                    }
                    const typedData: QrSignResponse['typed_data'] = {
                      types: VISIT_SIG_TYPES,
                      primaryType: 'VisitSig',
                      domain: VISIT_SIG_DOMAIN,
                      message: parsed.message,
                    }
                    setStep({ kind: 'decoded', typedData, attestation: parsed.attestation })
                  } catch {
                    // Still typing or pasting. Ignore until it is valid JSON.
                  }
                }}
              />
            </details>

            <p className="mb-2 text-center text-xs text-slate-500">Dev only: simulate error state</p>
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