import { useEffect, useState } from 'react'
import { useIDKitRequest, selfieCheckLegacy } from '@worldcoin/idkit'
import { QRCodeSVG } from 'qrcode.react'
import {
  fetchWorldRpContext,
  verifyWorld,
  type WorldAttestation,
  type WorldRpContextResponse,
} from '../lib/api'

interface IdentityCheckProps {
  visitorAddress: string
  onVerified: (attestation: WorldAttestation) => void
}

function randomHex(byteLength: number): string {
  const bytes = crypto.getRandomValues(new Uint8Array(byteLength))
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
}

function buildFakeAttestation(visitor: string): WorldAttestation {
  return {
    visitor,
    nullifier_hash: `0x${randomHex(32)}`,
    expiry: Math.floor(Date.now() / 1000) + 120,
    signature: `0x${randomHex(65)}`,
    typed_data: {},
  }
}

/**
 * Only mounted once a fresh rp_context is in hand — the nonce is single-use
 * and expires in 300 seconds, so each attempt needs its own. If World rejects
 * the check, `onRetry` asks the parent for a brand new rp_context and remounts
 * this component (via a changed `key`), rather than reopening this same hook
 * instance with its already-consumed nonce.
 */
function SelfieCheckWidget({
  rpData,
  visitorAddress,
  onVerified,
  onRetry,
}: {
  rpData: WorldRpContextResponse
  visitorAddress: string
  onVerified: (a: WorldAttestation) => void
  onRetry: () => void
}) {
  const [backendError, setBackendError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const flow = useIDKitRequest({
    app_id: rpData.app_id as `app_${string}`,
    action: rpData.action,
    rp_context: rpData.rp_context,
    environment: 'production',
    allow_legacy_proofs: true,
    preset: selfieCheckLegacy({ signal: visitorAddress }),
  })

  async function handleWorldSuccess() {
    if (!flow.result) return
    setSubmitting(true)
    setBackendError(null)
    try {
      const attestation = await verifyWorld({ visitor: visitorAddress, proof: flow.result })
      onVerified(attestation)
    } catch (err) {
      setBackendError(
        err instanceof Error ? err.message : "Selfie check succeeded, but the server rejected it.",
      )
    } finally {
      setSubmitting(false)
    }
  }

  const isBusy = flow.isAwaitingUserConnection || flow.isAwaitingUserConfirmation || submitting

  if (flow.isError) {
    return (
      <>
        <p className="text-sm text-red-600">We couldn't verify you ({flow.errorCode}).</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 rounded-full bg-brand px-6 py-3 font-medium text-white"
        >
          Try again
        </button>
      </>
    )
  }

  return (
    <>
      {flow.isAwaitingUserConnection && flow.connectorURI && (
        <div className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
          <QRCodeSVG value={flow.connectorURI} size={220} />
          <p className="mt-2 text-center text-xs text-ink-muted">
            Scan with the World App on your phone
          </p>
        </div>
      )}

      {flow.isAwaitingUserConfirmation && (
        <p className="text-sm text-ink-muted">Confirm the selfie check in the World App...</p>
      )}

      {flow.isSuccess && !backendError && (
        <p className="text-sm text-ink-muted">Confirming with our server...</p>
      )}
      {backendError && <p className="text-sm text-red-600">{backendError}</p>}

      {!flow.isSuccess ? (
        <button
          type="button"
          onClick={flow.open}
          disabled={isBusy}
          className="rounded-full bg-brand px-6 py-3 font-medium text-white disabled:opacity-50"
        >
          {isBusy ? 'Waiting for World App...' : 'Take Selfie'}
        </button>
      ) : (
        <button
          type="button"
          onClick={handleWorldSuccess}
          disabled={submitting}
          className="rounded-full bg-brand px-6 py-3 font-medium text-white disabled:opacity-50"
        >
          {submitting ? 'Confirming...' : 'Continue'}
        </button>
      )}
    </>
  )
}

export function IdentityCheck({ visitorAddress, onVerified }: IdentityCheckProps) {
  const [rpData, setRpData] = useState<WorldRpContextResponse | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    setRpData(null)
    setLoadError(null)

    fetchWorldRpContext()
      .then((data) => {
        if (!cancelled) setRpData(data)
      })
      .catch((err) => {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : 'Could not reach World')
        }
      })

    return () => {
      cancelled = true
    }
  }, [attempt])

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-bg px-6 text-center">
      <div>
        <h1 className="text-xl font-bold text-ink">Identity check</h1>
        <p className="mt-2 text-sm text-ink-muted">
          One quick selfie to confirm you're a real person. Takes about 30 seconds.
        </p>
      </div>

      {loadError && (
        <div className="text-center">
          <p className="text-sm text-red-600">{loadError}</p>
          <button
            type="button"
            onClick={() => setAttempt((a) => a + 1)}
            className="mt-2 text-sm text-ink-muted underline"
          >
            Try again
          </button>
        </div>
      )}

      <div className="flex w-full max-w-xs flex-col items-center gap-3">
        {rpData && (
          <SelfieCheckWidget
            key={attempt}
            rpData={rpData}
            visitorAddress={visitorAddress}
            onVerified={onVerified}
            onRetry={() => setAttempt((a) => a + 1)}
          />
        )}

        {import.meta.env.DEV && (
          <button
            type="button"
            onClick={() => onVerified(buildFakeAttestation(visitorAddress))}
            className="rounded-full border border-border px-6 py-3 text-sm text-ink-muted"
          >
            Dev only: skip with a fake attestation
          </button>
        )}
      </div>
    </div>
  )
}