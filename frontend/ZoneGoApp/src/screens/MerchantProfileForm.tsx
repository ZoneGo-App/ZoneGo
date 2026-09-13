import { useState, type FormEvent } from 'react'
import { useSignMessage } from '@privy-io/react-auth'
import { saveMerchantProfile, type MerchantProfile } from '../lib/profile'
import { merchantProfileMessage, saveMerchantProfileRemote } from '../lib/api'

interface MerchantProfileFormProps {
  merchantAddress: string
  initialProfile?: MerchantProfile | null
  onComplete: (profile: MerchantProfile) => void
  /**
   * Leave this out on first setup. Without a name and a description the store
   * is invisible to search, so the only way out of the initial form is to fill
   * it in. Once a profile exists, someone who opened this screen just to look
   * has to be able to leave without signing anything.
   */
  onBack?: () => void
}

export function MerchantProfileForm({
  merchantAddress,
  initialProfile,
  onComplete,
  onBack,
}: MerchantProfileFormProps) {
  const [name, setName] = useState(initialProfile?.name ?? '')
  const [address, setAddress] = useState(initialProfile?.address ?? '')
  const [description, setDescription] = useState(initialProfile?.description ?? '')
  const [error, setError] = useState<string | null>(null)
  const { signMessage } = useSignMessage()

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!name.trim() || !address.trim()) {
      setError('Name and address are required.')
      return
    }
    const profile: MerchantProfile = {
      name: name.trim(),
      address: address.trim(),
      description: description.trim(),
    }
    saveMerchantProfile(merchantAddress, profile)

    // The API only takes a profile signed by the wallet it names. Sign exactly
    // the values being sent — the trimmed ones above — or the signature will
    // not match. Best-effort: dismissing the prompt still keeps the local
    // profile, the store just won't show its name to others yet.
    const issuedAt = Math.floor(Date.now() / 1000)
    const message = merchantProfileMessage({
      wallet: merchantAddress,
      name: profile.name,
      description: profile.description,
      issuedAt,
    })
    signMessage({ message })
      .then(({ signature }) =>
        saveMerchantProfileRemote({
          wallet: merchantAddress,
          name: profile.name,
          description: profile.description,
          issuedAt,
          signature,
        }),
      )
      .catch((err) => console.warn('[ZoneGo] profile signature dismissed or failed:', err))

    onComplete(profile)
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg px-6 py-6">
      {onBack && (
        <button
          type="button"
          onClick={onBack}
          className="mb-6 flex w-fit items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-ink"
        >
          <span aria-hidden="true">&larr;</span> Back
        </button>
      )}

      <div className="flex flex-1 flex-col justify-center">
        <h1 className="text-xl font-bold text-ink">
          {initialProfile ? 'Edit your business profile' : 'Tell us about your business'}
        </h1>
        <p className="mt-1 text-sm text-ink-muted">
          This is what neighbors will see when they find you nearby.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-ink">Business name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Delancey Bodega"
              className="w-full rounded-2xl border border-border bg-surface px-4 py-3 text-ink placeholder:text-ink-muted focus:border-brand focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-ink">Address</label>
            <input
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="180 Delancey St, New York, NY"
              className="w-full rounded-2xl border border-border bg-surface px-4 py-3 text-ink placeholder:text-ink-muted focus:border-brand focus:outline-none"
            />
            <p className="mt-1 text-xs text-ink-muted">
              The map location isn't always exact — write the real address here.
            </p>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-ink">Short description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Sneakers, sportswear, backpacks."
              rows={3}
              className="w-full rounded-2xl border border-border bg-surface px-4 py-3 text-ink placeholder:text-ink-muted focus:border-brand focus:outline-none"
            />
            <p className="mt-1 text-xs text-ink-muted">
              Neighbors find you by these words, so write what you actually sell.
            </p>
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button type="submit" className="mt-2 rounded-full bg-brand py-3 font-medium text-white">
            {initialProfile ? 'Save' : 'Continue'}
          </button>

          {onBack && (
            <p className="text-center text-xs text-ink-muted">
              Saving asks for one signature. Use Back if nothing changed.
            </p>
          )}
        </form>
      </div>
    </div>
  )
}