import { useState, type FormEvent } from 'react'
import { saveVisitorProfile, type VisitorProfile } from '../lib/profile'

interface VisitorProfileFormProps {
  visitorAddress: string
  onComplete: (profile: VisitorProfile) => void
}

export function VisitorProfileForm({ visitorAddress, onComplete }: VisitorProfileFormProps) {
  const [name, setName] = useState('')
  const [nickname, setNickname] = useState('')
  const [error, setError] = useState<string | null>(null)

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!nickname.trim()) {
      setError('Pick a nickname to show on the leaderboard.')
      return
    }
    const profile: VisitorProfile = {
      name: name.trim(),
      nickname: nickname.trim(),
    }
    saveVisitorProfile(visitorAddress, profile)
    onComplete(profile)
  }

  return (
    <div className="flex min-h-screen flex-col justify-center bg-bg px-6 py-10">
      <h1 className="text-xl font-bold text-ink">Pick a name for the leaderboard</h1>
      <p className="mt-1 text-sm text-ink-muted">This is how other explorers will see you.</p>

      <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-ink">Name (optional)</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Alex"
            className="w-full rounded-2xl border border-border bg-surface px-4 py-3 text-ink placeholder:text-ink-muted focus:border-brand focus:outline-none"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-ink">Nickname</label>
          <input
            type="text"
            value={nickname}
            onChange={(e) => setNickname(e.target.value)}
            placeholder="alex.eth"
            className="w-full rounded-2xl border border-border bg-surface px-4 py-3 text-ink placeholder:text-ink-muted focus:border-brand focus:outline-none"
          />
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button type="submit" className="mt-2 rounded-full bg-brand py-3 font-medium text-white">
          Continue
        </button>
      </form>
    </div>
  )
}