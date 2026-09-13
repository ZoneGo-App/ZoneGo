import { useState, type FormEvent } from 'react'
import { saveMerchantProfile, type MerchantProfile } from '../lib/profile'

interface MerchantProfileFormProps {
  merchantAddress: string
  initialProfile?: MerchantProfile | null
  onComplete: (profile: MerchantProfile) => void
}

export function MerchantProfileForm({
  merchantAddress,
  initialProfile,
  onComplete,
}: MerchantProfileFormProps) {
  const [name, setName] = useState(initialProfile?.name ?? '')
  const [address, setAddress] = useState(initialProfile?.address ?? '')
  const [description, setDescription] = useState(initialProfile?.description ?? '')
  const [error, setError] = useState<string | null>(null)

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
    onComplete(profile)
  }

  return (
    <div className="flex min-h-screen flex-col justify-center bg-bg px-6 py-10">
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
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button type="submit" className="mt-2 rounded-full bg-brand py-3 font-medium text-white">
          {initialProfile ? 'Save' : 'Continue'}
        </button>
      </form>
    </div>
  )
}